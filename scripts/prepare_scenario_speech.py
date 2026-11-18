"""Prepare TTS input clips for the 16 voice re-planning scenarios; paid calls need --run-real.

One clip per user turn (<SID>_T<n>.wav, mono PCM16 16 kHz). A turn with scripted pauses is
synthesized as separate segments joined by exact digital silence, so the pause length is
controlled and longer than the 600 ms server-VAD silence. Uses the same TTS endpoint, model,
voice and instruction as prepare_natural_test_speech.py; no retries or fallbacks.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.scenarios import load_scenarios  # noqa: E402
from scripts.prepare_natural_test_speech import ENDPOINT, INSTRUCTION, MODEL, VOICE, convert_wav  # noqa: E402


def clip_plan(scenarios, selected=None):
    plan = []
    for scenario in scenarios.values():
        if selected and scenario["id"] not in selected:
            continue
        for turn in scenario["turns"]:
            if turn["speaker"] != "user":
                continue
            words, segments, cursor = turn["text"].split(), [], 0
            for pause in turn["pauses"]:
                segments.append({"text": " ".join(words[cursor:pause["after_words"]]), "silence_after_ms": pause["ms"]})
                cursor = pause["after_words"]
            segments.append({"text": " ".join(words[cursor:]), "silence_after_ms": 0})
            plan.append({"id": f"{scenario['id']}_T{turn['turn']}", "scenario_id": scenario["id"],
                         "turn": turn["turn"], "text": turn["text"], "segments": segments})
    return plan


def join_with_silence(parts, destination):
    """parts: [(16 kHz PCM bytes, silence_after_ms)] -> one WAV; returns duration seconds."""
    pcm = b"".join(chunk + b"\x00\x00" * (16 * silence) for chunk, silence in parts)
    with wave.open(str(destination), "wb") as recording:
        recording.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        recording.writeframes(pcm)
    return len(pcm) / 32000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scenarios", default="", help="Comma-separated IDs; default all 16.")
    parser.add_argument("--run-real", action="store_true")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    selected = {item for item in args.scenarios.split(",") if item}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    plan = clip_plan(load_scenarios(), selected)
    manifest = {"model": MODEL, "voice": VOICE, "endpoint": ENDPOINT, "instruction": INSTRUCTION,
                "run_real": args.run_real, "clips": plan}
    manifest_path = args.output_dir / "speech-manifest.json"

    def save():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    if not args.run_real:
        print(f"Prepared {len(plan)} clip texts only: {manifest_path}")
        return
    assert args.env_file, "--run-real requires an explicit --env-file"
    import httpx
    from dotenv import dotenv_values
    values = dotenv_values(args.env_file)
    key = values.get("DASHSCOPE_API_KEY") or values.get("QWEN_API_KEY")
    assert key, "Explicit env file must contain a nonempty API key"
    with httpx.Client(timeout=60) as client:
        for clip in plan:
            directory = args.output_dir / clip["id"]
            directory.mkdir()
            parts = []
            for index, segment in enumerate(clip["segments"]):
                request = {"model": MODEL, "input": {"text": segment["text"], "voice": VOICE, "format": "wav",
                                                     "sample_rate": 24000, "instruction": INSTRUCTION}}
                attempt = {"started_at": datetime.now(timezone.utc).isoformat(), "segment": index}
                try:
                    response = client.post(ENDPOINT, headers={"Authorization": f"Bearer {key}"}, json=request)
                    attempt["http_status"] = response.status_code
                    response.raise_for_status()
                    raw = client.get(response.json()["output"]["audio"]["url"]).content
                    (directory / f"segment-{index}.wav").write_bytes(raw)
                    audio = convert_wav(raw, directory / f"segment-{index}-16k.wav")
                    with wave.open(str(directory / f"segment-{index}-16k.wav"), "rb") as recording:
                        parts.append((recording.readframes(recording.getnframes()), segment["silence_after_ms"]))
                    segment.update(seconds=audio["seconds"], sha256=audio["sha256"])
                    attempt["status"] = "complete"
                except Exception as error:
                    attempt.update(status="failed", error_type=type(error).__name__)
                    raise RuntimeError(f"TTS {clip['id']} segment {index} failed; nothing retried") from None
                finally:
                    attempt["finished_at"] = datetime.now(timezone.utc).isoformat()
                    (directory / f"attempt-{index}.json").write_text(json.dumps(attempt, indent=2), encoding="utf-8")
                    save()
            path = args.output_dir / f"{clip['id']}.wav"
            clip["seconds"] = join_with_silence(parts, path)
            clip["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            assert clip["seconds"] <= 10, f"{clip['id']} exceeds the 10-second input cap"
            save()
            print(f"{clip['id']}: {clip['seconds']:.2f}s")


if __name__ == "__main__":
    main()
