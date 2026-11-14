# Model transport and verification

Current input audit: response_prepare refreshes the application evidence package before each native response or text tool continuation. Captured screenshots are uploaded from eligible packages, rather than continuously forwarding every incoming context update. Attempted/sent application JSON bytes are saved with hashes; authentication headers are excluded. Native conversation/audio-image buffer state is not frozen. See [JARVIS_ADAPTATION.md](JARVIS_ADAPTATION.md).

Stage 1 (2026-11-13) preserves the configured voice model `qwen3.8-omni-flash-realtime`. Provider onset includes available input-buffer offsets and is normalized once. Workspace revokes local publication permission and sends playback stop before upstream cancellation is awaited. Normalized responses and tool callbacks carry captured origin; forwarded audio carries chunk/sample positions. Browser playback progress is measured separately from provider receipt/completion. See [the implementation contract](STAGE1_IMPLEMENTATION.md). The local verification peer does not validate real Qwen recognition or reasoning.

`backend/providers.py` connects only when the application explicitly calls it. There is no model simulation, retry loop, automatic reconnect, or paid startup probe.

## Shared model inputs

Text uses HTTP Chat Completions with SSE. The caller supplies the English instructions, conversation, visible reference snapshot and JPEG screenshot in the message list. The adapter assembles streamed function arguments, executes the shared tool callback, returns its actual receipt and requests a continuation. Eight tool rounds bound one text request; an interrupted or truncated completion is not marked successful.

Voice uses the Qwen native WebSocket protocol. Both voice input modes receive the same nested function schemas, instructions, image input and tool callback. The adapter supports PCM16 mono input at 16 kHz and PCM16 output at 24 kHz. It queues a screenshot until real audio has been appended; it never manufactures silence to enable image upload. `context(text)` replaces session instructions, so callers must send the complete instructions plus the updated public context.

## Input submission modes (not the primary research conditions)

| Input mode | Audio submission | Response scheduling |
| --- | --- | --- |
| Push to talk | Audio is streamed during recording; the participant explicitly commits the utterance | Manual input buffer commit, then response creation after transcription is delivered to the application |
| Live voice | Audio remains open during assistant playback | Server VAD detects speech boundaries; application creates the response after transcription |

Live voice requests `server_vad`, 600 ms silence, `create_response=false` and `interrupt_response=false`. The endpoint must acknowledge application-controlled responses. An incompatible endpoint ends the connection; the implementation does not silently run a different condition. The public event reference documents server VAD/manual mode but does not currently enumerate the latter two control flags. They are inherited from the existing laboratory integration and still require a real endpoint check.

These modes support input submission and overlapping speech reception. The current research compares direct and evidence-linked revision within the same live-voice mode; it does not compare voice superiority. This implementation does not claim semantic action before an utterance ends. A new detected utterance revokes pending voice/tool delivery; benign backchannels are not separately classified or resumed in this version. Report that behavior when interpreting live-voice results.

All three revision configurations receive the same tool schemas, public historical states and selected evidence. Evidence-linked revision binds explicitly referenced historical members in the tool executor; the two unbound configurations execute the model-supplied member values. No private task answer or reference oracle is inserted into provider context.

The latest revision card stays inspectable in context after being superseded. A verbal answer can therefore be interpreted by the model and used to create a new preview; the old ID never regains permission. A current request that calls an outdated proposal receives a normal failed tool receipt. Calls belonging to a genuinely obsolete request are suppressed instead. This preserves response continuity without an automatic retry or a hardcoded Yes classifier.

## Tools, interruption and recording

Tool work runs outside the receive loop, so incoming audio, transcription and cancellation remain processable. A response's completed calls execute in order and receive one continuation after the whole batch. Every call is checked before invocation and after return against the current generation. The application separately checks its request epoch before committing charts; generation filtering cannot replace commit permission.

Tool receipts are sent as `conversation.item.create` with `function_call_output`; the adapter waits for their provider acknowledgement. A late response created after cancellation retains its old generation and is cancelled without being presented. Already heard audio and previously legal chart commits cannot be recalled.

`provider_event` records sent/received payloads, excluding HTTP headers and API keys. Normalized events include `response_start`, `user_transcript`, `speech_start`, `speech_end`, `assistant_delta`, `assistant_done`, `audio`, `audio_end`, `response_end`, `usage` and `error`. The application owns file storage, browser playback observations and human review. Provider `response_end` is not browser playback completion.

## Local verification

Run `python -m pytest tests/test_providers.py -q` from the project root. Local HTTP and WebSocket peers exercise the actual transport implementation. They check streamed argument assembly, receipt return, audio-before-image order, single follow-up for multiple tools, reception during tool execution, and suppression after cancellation.

These are protocol checks, not model performance, speech recognition, microphone echo cancellation or human listening results. No remote model API was called while implementing this module.

## Frontend and transport alignment

The current frontend composes rendered ECharts canvases synchronously with their exact view and category selections. This removes the earlier asynchronous image-decode interval in which `sendText` or `startVoice` could receive a stale snapshot even after a background update had rejected it.

Image delivery now retains a trace frame ID and explicitly reports queued versus actually sent input. After manual audio commit, a new JPEG waits for another real audio segment; no silence, extra utterance or undocumented image message is generated to force its consumption. Thus this implementation still does not establish model inspection of every updated chart before a spoken follow-up.

The local browser driver uses offline Windows speech synthesis through the production microphone worklet, PTT submission and real tool/render/playback paths. Its scripted local provider check establishes the pipeline only. A real attempt requires explicit `--run-real` and a nonempty key in the selected configuration, opens at most one connection and preserves failure without retry.

The worklet now starts and pauses capture explicitly and caps PTT at 160,000 samples. Samples collected while the participant is not recording do not enter a later segment. Speaker bookkeeping begins before AudioContext readiness so a short reply's end or a user's stop cannot be lost. The local `verify_playback_revision.py` check injects an authored revision only during actual browser playback, verifies interruption and the subsequent reply, and independently recomputes the revised chart values. Its tones and authored transcription are not real model evidence.

## One authorized real attempt — 2026-11-13

`traces/live-browser/20261113-120939-580704/` retains one attempt with the explicitly selected DuplexVisEval env. The WebSocket handshake returned HTTP 401, before session configuration, audio or image input. No tool or output audio occurred. The initial report's outer error was a screenshot request after Playwright had closed; the original HTTP 401 remains in the session trace. The harness now preserves the original error without requesting a screenshot from a closed browser, verified through a local rejecting peer.

The earlier configuration merge used a different process `DASHSCOPE_API_KEY` instead of the key in the selected file. Credential precedence has been fixed and the selected value has been checked against the file without exposing it. The actual file key remains unverified remotely because the authorized single attempt was not retried. Test and review Python processes were stopped; neither a failed handshake nor missing usage is presented as an actual billing statement.

## References checked on 2026-11-13

- [Qwen WebSocket interaction flow](https://help.aliyun.com/zh/model-studio/omni-realtime-interaction-process)
- [Qwen client event reference](https://www.alibabacloud.com/help/en/model-studio/client-events)
- Existing local source: `C:\VerbalVis\backend\realtime.py`, `C:\VerbalVis\backend\text_provider.py`, and `C:\DuplexVisEval\src\duplexviseval\models\qwen.py`.
