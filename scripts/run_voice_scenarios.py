"""Run voice re-planning scenarios in live voice (real browser path) or as a text twin.

Default is a credential-free preflight. --run-real opens model connections and needs an
explicit --env-file; every connection must be separately authorized (AGENTS.md).

Voice mode drives the production frontend in Chromium with each turn's TTS clip injected
through a substituted getUserMedia stream; barge-in points are timed from the browser's
AudioWorklet playback receipts, not from generated text. Text mode sends the same
utterances in order with no timing. Each scenario gets a fresh setup; no retries.
Scores are evaluator-private and written per scenario; nothing enters model context.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.scenarios import load_scenarios  # noqa: E402

OUTPUT_RATE = 24000


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def preflight(args, scenarios):
    clips = {}
    if args.mode == "voice":
        for scenario in scenarios:
            for turn in scenario["turns"]:
                if turn["speaker"] != "user":
                    continue
                name = f"{scenario['id']}_T{turn['turn']}"
                path = args.audio_dir / f"{name}.wav"
                with wave.open(str(path), "rb") as audio:
                    assert audio.getparams()[:3] == (1, 2, 16000), f"{name}: expected mono PCM16 16 kHz"
                    seconds = audio.getnframes() / audio.getframerate()
                assert 0 < seconds <= 10, f"{name}: inputs are capped at 10 seconds"
                clips[name] = {"path": str(path.resolve()), "seconds": seconds}
    return clips


def latest_request(events):
    accepted = [e for e in events if e["name"] == "request_accepted"]
    return accepted[-1]["request_id"] if accepted else None


def played_seconds(events, request_id):
    """Largest played-sample count among this request's responses, from worklet receipts."""
    played = [e["details"].get("played_samples", 0) for e in events
              if e.get("request_id") == request_id and e["name"] in ("playback_start", "playback_progress",
                                                                     "playback_end", "playback_stopped")]
    return max(played, default=0) / OUTPUT_RATE


def audible(events):
    started, finished = set(), set()
    for event in events:
        rid = event.get("details", {}).get("response_id") if isinstance(event.get("details"), dict) else None
        if event["name"] == "playback_start":
            started.add(rid)
        elif event["name"] in ("playback_end", "playback_stopped"):
            finished.add(rid)
    return started - finished


def settled(events, request_id):
    return request_id is None or any(e["name"] == "request_outcome" and e.get("request_id") == request_id
                                     for e in events)


async def wait_until(predicate, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.04)
    return False


async def wait_for_turn(workspace, turn, args, previous_clip_end):
    """Block until this turn's injection point; return a record of what was observed."""
    events = workspace.trace.events
    timing = turn["timing"]
    request_id = latest_request(events)
    record = {"timing": timing, "anchor_request_id": request_id}
    if timing["type"] == "after_end":
        record["met"] = await wait_until(lambda: settled(workspace.trace.events, request_id)
                                         and not audible(workspace.trace.events), args.turn_timeout)
    elif timing["type"] in ("barge_in", "backchannel"):
        offset = timing.get("offset_s") or args.barge_in_fallback_seconds
        record["offset_s"] = offset
        record["met"] = await wait_until(lambda: played_seconds(workspace.trace.events, request_id) >= offset
                                         and audible(workspace.trace.events), args.turn_timeout)
    else:  # during_tool
        await asyncio.sleep(max(0.0, previous_clip_end + timing.get("offset_s", 0) - time.monotonic()))
        record["met"] = not any(e["name"] == "request_outcome" and e.get("request_id") == request_id
                                for e in workspace.trace.events)
    record["played_seconds_at_injection"] = played_seconds(workspace.trace.events, request_id)
    record["audible_at_injection"] = sorted(map(str, audible(workspace.trace.events)))
    return record


async def run_voice(args, scenario, page, workspace, base, context):
    await context.request.post(f"{base}/api/scenarios/{scenario['id']}/setup",
                               data={"mode": "live_voice", "condition": args.condition})
    await page.goto(base, wait_until="networkidle")
    await wait_until(lambda: any(e["name"] == "clock_calibrated" for e in workspace.trace.events), 20)
    report = {"scenario_id": scenario["id"], "mode": "voice", "turns": [], "windows": []}
    started = time.monotonic()
    await page.get_by_role("button", name="Start speaking", exact=True).click()
    connected = await wait_until(lambda: any(e["name"] in ("voice_connected", "session_error", "error")
                                             for e in workspace.trace.events), 18)
    if not connected or not any(e["name"] == "voice_connected" for e in workspace.trace.events):
        report["error"] = "voice did not connect"
        return report
    await page.wait_for_function("!!window.__spokenInput")
    previous_clip_end = time.monotonic()
    for turn in scenario["turns"]:
        if turn["speaker"] != "user":
            continue
        if workspace.voice is None:
            report["stopped"] = f"voice closed before T{turn['turn']}"
            break
        wait = await wait_for_turn(workspace, turn, args, previous_clip_end)
        window = {"turn": turn["turn"], "start_index": len(workspace.trace.events)}
        report["windows"].append(window)
        segment = await page.evaluate("(name) => window.__spokenInput.start(name)",
                                      f"{scenario['id']}_T{turn['turn']}")
        previous_clip_end = time.monotonic()
        report["turns"].append({"turn": turn["turn"], "wait": wait, "segment": segment,
                                "seconds_since_start": round(previous_clip_end - started, 3)})
    final = latest_request(workspace.trace.events)
    await wait_until(lambda: settled(workspace.trace.events, final) and not audible(workspace.trace.events),
                     args.turn_timeout)
    report["connection_wall_seconds"] = round(time.monotonic() - started, 3)
    report["budget_reached"] = any(e["name"] == "voice_budget_reached" for e in workspace.trace.events)
    await workspace.close_voice()
    return report


async def run_text(args, scenario, workspace):
    workspace.setup_scenario(scenario, "text", args.condition)
    report = {"scenario_id": scenario["id"], "mode": "text", "turns": [], "windows": []}
    for turn in scenario["turns"]:
        if turn["speaker"] != "user":
            continue
        report["windows"].append({"turn": turn["turn"], "start_index": len(workspace.trace.events)})
        if "BC" in turn["tags"]:
            # An acknowledgement has no text-mode equivalent; it is scored as a no-op turn.
            report["turns"].append({"turn": turn["turn"], "skipped": "acknowledgement_voice_only"})
            continue
        await workspace.text({"text": turn["text"]})
        if workspace.text_task is not None:
            try:
                await asyncio.wait_for(workspace.text_task, args.turn_timeout)
            except asyncio.TimeoutError:
                report["turns"].append({"turn": turn["turn"], "timed_out": True})
                break
        report["turns"].append({"turn": turn["turn"], "completed": True})
    return report


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["voice", "text"], default="voice")
    parser.add_argument("--scenarios", default="", help="Comma-separated IDs; default all 16.")
    parser.add_argument("--condition", choices=["direct", "bound_revision"], default="bound_revision")
    parser.add_argument("--run-real", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--audio-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frontend-dir", type=Path, default=ROOT / "frontend/dist")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--budget-seconds", type=int, default=150,
                        help="Diagnostic voice budget, recorded in every session.")
    parser.add_argument("--barge-in-fallback-seconds", type=float, default=4.5,
                        help="Played seconds before a barge-in whose scenario gives no offset (S05).")
    parser.add_argument("--turn-timeout", type=float, default=30)
    args = parser.parse_args()
    all_scenarios = load_scenarios()
    chosen = [s for s in all_scenarios.values() if not args.scenarios or s["id"] in args.scenarios.split(",")]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    if args.mode == "voice":
        assert args.audio_dir, "--mode voice needs --audio-dir from prepare_scenario_speech.py"
    summary = {"started_at": datetime.now(timezone.utc).isoformat(), "mode": args.mode,
               "condition": args.condition, "scenarios": [s["id"] for s in chosen], "run_real": args.run_real,
               "automatic_retries": 0, "budget_seconds": args.budget_seconds, "results": []}
    summary["clips"] = preflight(args, chosen)
    save(args.output_dir / "summary.json", summary)
    if not args.run_real:
        summary["status"] = "prepared"
        save(args.output_dir / "summary.json", summary)
        print(json.dumps({"status": "prepared", "summary": str(args.output_dir / "summary.json")}))
        return
    assert args.env_file, "--run-real requires an explicit --env-file"
    from backend.settings import load_settings
    settings = {**load_settings(args.env_file), "trace_dir": args.output_dir / "sessions",
                "voice_budget_seconds": args.budget_seconds, "frontend_dir": args.frontend_dir}
    assert settings["api_key"], "Selected configuration has no key."
    import uvicorn
    from backend.app import create_app
    app = create_app(settings)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="error"))
    running = asyncio.create_task(server.serve())
    try:
        await wait_until(lambda: server.started, 20)
        workspace = app.state.workspace
        if args.mode == "text":
            for scenario in chosen:
                report = await run_text(args, scenario, workspace)
                report["score"] = workspace.score_scenario(scenario, report["windows"])
                summary["results"].append(report)
                save(args.output_dir / f"{scenario['id']}-text.json", report)
                await workspace.archive()
        else:
            from playwright.async_api import async_playwright
            from scripts.verify_two_real_cases import microphone_script
            clips = {name: Path(record["path"]) for name, record in summary["clips"].items()}
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True, args=["--autoplay-policy=no-user-gesture-required"])
                context = await browser.new_context(viewport={"width": 2560, "height": 1440}, device_scale_factor=1.5,
                                                    record_video_dir=str(args.output_dir / "video"))
                await context.add_init_script(microphone_script(clips))
                page = await context.new_page()
                base = f"http://127.0.0.1:{args.port}"
                for scenario in chosen:
                    try:
                        report = await run_voice(args, scenario, page, workspace, base, context)
                    finally:
                        await workspace.close_voice()
                    report["score"] = workspace.score_scenario(scenario, report["windows"])
                    summary["results"].append(report)
                    save(args.output_dir / f"{scenario['id']}-voice.json", report)
                    await page.screenshot(path=str(args.output_dir / f"{scenario['id']}-final.png"))
                await context.close()
                await browser.close()
        summary["status"] = "completed"
    except (Exception, asyncio.CancelledError) as error:
        summary.update(status="failed", error=repr(error).replace(settings["api_key"], "[REDACTED]"))
    finally:
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        summary["by_scenario"] = {r["scenario_id"]: r.get("score", {}).get("summary") for r in summary["results"]}
        save(args.output_dir / "summary.json", summary)
        server.should_exit = True
        await running
    print(json.dumps({"status": summary["status"], "summary": str(args.output_dir / "summary.json")}))


if __name__ == "__main__":
    asyncio.run(main())
