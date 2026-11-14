"""One browser voice loop against a local scripted provider; no remote API.

The microphone file and assistant audio are test tones. Browser capture, canvas
JPEG upload, tool execution, rendering and WebAudio callbacks are real.
"""

import asyncio
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import traceback
import wave

import uvicorn
from playwright.async_api import async_playwright
from websockets.asyncio.server import serve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import create_app


def tone(rate, seconds, frequency):
    return b"".join(struct.pack("<h", int(4200 * math.sin(2 * math.pi * frequency * i / rate)))
                    for i in range(int(rate * seconds)))


def write_wav(path, pcm, rate):
    with wave.open(str(path), "wb") as file:
        file.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        file.writeframes(pcm)


async def until(predicate, seconds=20):
    async with asyncio.timeout(seconds):
        while not predicate():
            await asyncio.sleep(.025)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--frontend-dir', type=Path, default=ROOT / 'frontend' / 'dist')
    options = parser.parse_args()
    output = ROOT / "traces" / "browser-voice" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    output.mkdir(parents=True)
    report = {
        "status": "running", "paid_api_calls": 0,
        "scope": "Actual built frontend, Chromium fake microphone, local scripted Qwen peer and real Olist",
        "not_established": ["real model recognition", "model semantic correctness", "human hearing", "physical microphone echo cancellation"],
        "viewport": {"css_width": 2560, "css_height": 1440, "device_scale_factor": 1.5,
                     "screenshot_pixels": "3840x2160"},
    }
    microphone_file = output / "fixture-microphone.wav"
    write_wav(microphone_file, tone(16000, 3, 330), 16000)
    output_pcm = tone(24000, .8, 440)
    write_wav(output / "fixture-assistant.wav", output_pcm, 24000)
    peer_events, peer_images, console_errors = [], [], []
    response_count, utterance_started = 0, False

    async def peer(ws):
        nonlocal response_count, utterance_started

        async def send(event):
            await ws.send(json.dumps(event))

        async for raw in ws:
            event = json.loads(raw)
            kind = event["type"]
            saved = json.loads(raw)
            if kind == "input_audio_buffer.append":
                pcm = base64.b64decode(event["audio"])
                saved["audio"] = {"bytes": len(pcm), "sha256": hashlib.sha256(pcm).hexdigest()}
            if kind == "input_image_buffer.append":
                jpeg = base64.b64decode(event["image"])
                filename = f"provider-frame-{len(peer_images) + 1:02}.jpg"
                (output / filename).write_bytes(jpeg)
                peer_images.append(filename)
                saved["image"] = {"file": filename, "bytes": len(jpeg), "sha256": hashlib.sha256(jpeg).hexdigest()}
            peer_events.append(saved)
            if kind == "session.update":
                await send({"type": "session.updated", "session": event["session"]})
            elif kind == "input_image_buffer.append" and not utterance_started:
                utterance_started = True
                await send({"type": "input_audio_buffer.speech_started", "item_id": "browser-user-1"})
                await send({"type": "input_audio_buffer.speech_stopped", "item_id": "browser-user-1"})
                await send({"type": "input_audio_buffer.committed", "item_id": "browser-user-1"})
                await send({"type": "conversation.item.input_audio_transcription.completed", "item_id": "browser-user-1",
                            "transcript": "Make the selected chart orange. Keep the other charts unchanged."})
            elif kind == "response.create":
                response_count += 1
                rid = f"browser-response-{response_count}"
                await send({"type": "response.created", "response": {"id": rid}})
                if response_count == 1:
                    args = {"view_ids": ["v1"], "patch": {"style": {"color": "#cb7047"}}}
                    items = [{"type": "function_call", "call_id": "browser-edit-1", "name": "edit_charts", "arguments": json.dumps(args)}]
                else:
                    items = []
                    text = "Chart one is now orange. The other two charts are unchanged."
                    await send({"type": "response.audio_transcript.delta", "response_id": rid, "delta": text})
                    for index in range(0, len(output_pcm), 4800):
                        await send({"type": "response.audio.delta", "response_id": rid,
                                    "delta": base64.b64encode(output_pcm[index:index + 4800]).decode()})
                        await asyncio.sleep(.035)
                    await send({"type": "response.audio_transcript.done", "response_id": rid, "transcript": text})
                    await send({"type": "response.audio.done", "response_id": rid})
                await send({"type": "response.done", "response": {"id": rid, "status": "completed", "output": items}})
            elif kind == "conversation.item.create":
                await send({"type": "conversation.item.created", "item": event["item"]})

    server = None
    running = None
    browser = None
    page = None
    workspace = None
    try:
        await until(lambda: (options.frontend_dir / "index.html").exists(), 60)
        async with serve(peer, "127.0.0.1", 0) as provider:
            provider_port = provider.sockets[0].getsockname()[1]
            settings = {
                "frontend_dir": options.frontend_dir,
                "data_dir": Path("C:/VerbalVis/datasets/olist/data"), "trace_dir": output / "sessions",
                "api_key": "local-browser-fixture-only", "text_model": "local-scripted-text",
                "realtime_model": "local-scripted-voice", "voice": "Tina",
                "text_url": "http://127.0.0.1:1/unused-text",
                "realtime_url": f"ws://127.0.0.1:{provider_port}",
            }
            app = create_app(settings)
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8052, log_level="error"))
            running = asyncio.create_task(server.serve())
            await until(lambda: server.started)
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True, args=[
                    "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                    "--use-file-for-fake-audio-capture=" + str(microphone_file),
                    "--autoplay-policy=no-user-gesture-required",
                ])
                context = await browser.new_context(viewport={"width": 2560, "height": 1440}, device_scale_factor=1.5,
                                                    permissions=["microphone"], record_video_dir=str(output / "video"))
                page = await context.new_page()
                page.on("pageerror", lambda error: console_errors.append(str(error)))
                await page.goto("http://127.0.0.1:8052/", wait_until="networkidle")
                await page.get_by_role("button", name="Start with Olist").click()
                await page.locator(".chart-card").nth(2).wait_for()
                await page.get_by_role("button", name="Select chart 1", exact=True).click()
                await page.get_by_role("button", name="Live voice", exact=True).click()
                workspace = app.state.workspace
                await until(lambda: workspace.reference["view_ids"] == ["v1"] and bool(workspace.image))
                initial = workspace.store.snapshot()
                await page.screenshot(path=str(output / "before.png"))
                await page.get_by_role("button", name="Start speaking", exact=True).click()
                await until(lambda: any(event["name"] == "playback_end" for event in workspace.trace.events))
                await until(lambda: any(event["name"] == "chart_rendered" and event.get("details", {}).get("revision") == initial["revision"] + 1 for event in workspace.trace.events))
                await page.get_by_role("button", name="End voice session", exact=True).click()
                await until(lambda: workspace.voice is None)
                await page.screenshot(path=str(output / "after.png"))
                final = workspace.store.snapshot()
                assert final["revision"] == initial["revision"] + 1
                assert final["views"][0]["style"]["color"] == "#cb7047"
                assert final["views"][0]["source"] == initial["views"][0]["source"]
                assert final["views"][0]["data"] == initial["views"][0]["data"]
                assert final["views"][1:] == initial["views"][1:]
                accepted = [e for e in workspace.trace.events if e["name"] == "request_accepted"]
                assert accepted[-1]["reference"]["view_ids"] == ["v1"]
                assert accepted[-1]["reference"]["revision"] == initial["revision"]
                assert peer_images
                sent = [e["type"] for e in peer_events]
                assert sent.index("input_audio_buffer.append") < sent.index("input_image_buffer.append")
                assert sent.count("response.create") == 2
                starts = [e for e in workspace.trace.events if e["name"] == "playback_start"]
                ends = [e for e in workspace.trace.events if e["name"] == "playback_end"]
                assert len(starts) == len(ends) == 1
                assert starts[0]["client_ms"] < ends[0]["client_ms"]
                assert ends[0]["details"]["interrupted"] is False
                incoming = next(workspace.trace.directory.glob("input-*.pcm")).read_bytes()
                outgoing = next(workspace.trace.directory.glob("output-*.pcm")).read_bytes()
                assert any(incoming)
                assert outgoing == output_pcm
                assert not console_errors, console_errors
                assert await page.get_by_text("Chart one is now orange. The other two charts are unchanged.", exact=True).count() == 1
                report.update({
                    "status": "passed", "initial_revision": initial["revision"], "final_revision": final["revision"],
                    "selected_view_ids": accepted[-1]["reference"]["view_ids"],
                    "input_pcm_bytes": len(incoming), "output_pcm_bytes": len(outgoing),
                    "playback_client_duration_ms": round(ends[0]["client_ms"] - starts[0]["client_ms"], 3),
                    "actual_browser_screenshots": ["before.png", "after.png"], "actual_frontend_jpegs": peer_images,
                    "assertions": ["Selected chart reference reached request", "Actual ECharts canvas JPEG reached peer after PCM",
                                   "Real chart tool committed only the selected color edit", "Other charts and all numeric data unchanged",
                                   "Assistant transcript displayed", "Actual WebAudio start/end callbacks returned",
                                   "Fake microphone PCM captured", "Output PCM matches fixture", "No browser page errors", "Voice connection released"],
                    "session_directory": str(workspace.trace.directory),
                })
                await context.close()
                await browser.close()
                browser = None
    except BaseException as error:
        report.update({"status": "failed", "error": str(error), "traceback": traceback.format_exc()})
        if page is not None and not page.is_closed():
            await page.screenshot(path=str(output / "failure.png"))
        raise
    finally:
        if browser is not None:
            await browser.close()
        if server is not None:
            server.should_exit = True
        if running is not None:
            await running
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (output / "provider-events.json").write_text(json.dumps(peer_events, indent=2), encoding="utf-8")
        (output / "console-errors.json").write_text(json.dumps(console_errors, indent=2), encoding="utf-8")
        print(json.dumps({"status": report["status"], "report": str(output / "report.json"), "paid_api_calls": 0}))


if __name__ == "__main__":
    asyncio.run(main())
