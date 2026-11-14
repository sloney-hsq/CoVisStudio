# Stage 1: event, playback and visibility implementation

Historical Stage 1 implementation. The current [Jarvis adaptation](JARVIS_ADAPTATION.md) replaces AudioContext-time playback estimates with worklet receipts and adds application evidence, shared candidates and delivery reporting.

Date: 2026-11-13. Model: `qwen3.8-omni-flash-realtime`; no paid model connection was used. Implementation preserves the existing one-workspace architecture and Workspace epoch authority.

## Code responsibilities

| File / function | Responsibility |
| --- | --- |
| `backend/trace.py: Trace.record` | Append immutable event-time payloads with schema, session ID, event ID, server monotonic time and known origin |
| `Trace.scope`, `Trace.origin` | Carry a captured request/response/tool origin across awaited operations; an unknown response is not assigned to the newest request |
| `Trace.record_client` | Preserve browser raw time and event identity, join known origin and add calibrated server-time estimate |
| `Trace.calibrate_clock` | Calculate offset/round-trip time from four timestamps; retain all three samples and select the lowest round trip |
| `Trace.audio` | Archive received PCM with stable chunk ID and per-response sample range; retain WAV finalization |
| `backend/app.py: Workspace.begin_request` | Associate local epoch/request identity with known input item; does not introduce another publication authority |
| `Workspace.provider_event` | Normalize one onset, revoke old work, send stop, map response identity, archive and forward audio metadata |
| `Workspace.execute` | Capture invocation context once; tool start/result/commit records retain that origin while execution awaits |
| `Workspace.revoke` | Increment local authority first, send stop before awaiting upstream cancellation; preserve earlier commits |
| WS `/ws` clock/event branches | Answer clock probes without contacting Qwen; accept completed calibration and browser telemetry |
| `backend/providers.py: QwenRealtime._speech_started` | Advance transport generation, notify Workspace before upstream cancel; retain provider input offsets |
| `QwenRealtime._run_tools`, `QwenText.run` | Pass response/call origin through the existing tool callback, without changing public tool schemas |
| `frontend/src/clockSync.js: ClockSync` | Three timestamp exchanges on connection/session change and every 30 seconds; stop timer on socket close |
| `frontend/src/audio.js: Speaker.append` | Associate received chunks with response/item/sample ranges and schedule WebAudio buffers |
| `Speaker.chunkPosition`, `details`, `sampleProgress` | Calculate cumulative played/queued samples from the AudioContext clock; sample about every 250 ms |
| `Speaker.stop`, `finish` | Clip each chunk at stop time, give queued chunks zero playback credit, record queue completion and received-WAV metadata |
| `frontend/src/chartVisibility.js: observeChartVisibility` | Open/close rendered plot exposure intervals using render identity, intersection, document visibility and surface enablement |
| `ChartCard.vue: render` | Associate ECharts completion plus animation-frame callback with the current render generation; invalidate old callbacks |
| `frontend/src/App.vue: log`, `chartTelemetry`, `receive` | Forward raw client timestamps/IDs, wire clock pongs and distinguish main/history/expanded surfaces |

`Trace` is observational. It does not approve a tool or change a chart. `ChartStore` keeps private candidates and version checks. Workspace epoch remains the local publication rule. Provider epoch only routes transport events.

## Onset and tool sequence

1. Provider reports speech onset and input item/available audio offset.
2. Provider advances its transport generation; Workspace advances local epoch and assigns request identity.
3. Workspace records exactly one normalized `speech_start`, supersedes any pending proposal, and sends `stop_audio` and onset to the browser.
4. Browser clips the playback position and stops queued buffers; upstream response cancellation follows independently.
5. Transcript acceptance records the words and updates the normal context. This phase does not freeze all model evidence.
6. New response/tool calls capture request, epoch, response and call IDs. The existing private candidate/commit path checks local permission and base revision.
7. Chart publication, ECharts render completion, chart exposure and subsequent browser playback remain distinct observations.

Raw `provider_event` still contains the upstream onset; it is a different event type, not another normalized onset. Raw `response.created` can precede registration and lack a request association; the normalized `response_start` supplies the established association. No origin is guessed for an unknown late response.

## Clock contract

`clock_ping` carries session ID, browser clock ID, sync ID and `client_send_ms`. `clock_pong` echoes them with Trace-relative `server_receive_ms` and `server_send_ms`; the browser records `client_receive_ms`. After three exchanges it submits `clock_sample` with the raw samples. Trace now uses `time.perf_counter()` for high-resolution monotonic measurement; this Windows Python's `time.monotonic()` has a measured 15.625 ms resolution and is unsuitable for the desired alignment precision. The asyncio task timer remains unchanged.

For each sample: offset = `((server_receive-client_send) + (server_send-client_receive))/2`; round trip = `(client_receive-client_send) - (server_send-server_receive)`. The selected minimum-round-trip sample supplies offset and half-round-trip uncertainty. Raw timestamps remain unchanged. `aligned_server_ms` is an estimate, with calibration ID and uncertainty, and is null before calibration. The estimate assumes the ordinary exchange timing model; it is not proof of perfectly symmetric delay or physical audio latency.

A new workspace has a new server clock and calibration. Old-session browser events are retained as session-mismatch evidence rather than counted as current-task playback or exposure. Calibration is periodic measurement, not an API retry.

## Audio contract

Audio forwarding includes `chunk_id`, `sample_start`, `sample_end`, `sample_rate`, response ID and known item/content/request/epoch identity. Samples are PCM16 frames per response. `playback_chunk_scheduled`, `playback_progress`, `playback_chunk_ended`, `playback_stopped`, and existing start/end events provide scheduled AudioContext times and played/queued positions.

Queue fields describe one response's queue. A natural `playback_end` requires stream end plus drained chunks. A stopped response records its clip position and an empty active queue while retaining received-but-discarded samples. A pending AudioContext resume cannot resurrect stopped playback. `response.done` is never used as audible completion.

Archived WAV and the browser recording callback remain **received audio**, not a cropped “heard audio” file. Physical output latency, speaker volume, attention and word-level listening remain unmeasured. The new sample timeline enables later alignment; it does not supply word-to-sample alignment by itself.

## Chart exposure contract

Identity is `view_id + revision + render_generation + surface_id`. A `display_id` identifies each visible interval. Main, expanded and historical instances are separate surfaces. `chart_rendered` does not imply visible. `chart_visible` requires a completed current render, positive plot intersection, visible document and enabled surface. `chart_hidden` records end/duration on the same browser clock. Covered main surfaces pause exposure; the displayed history/expanded surface is measured separately.

An already-rendered surface may become enabled after the initial connection or an overlay closes. Its receipt retains the original `render_completed_client_ms` and is marked `notification_kind=existing_render`; it is not a new render. Actual completion uses `notification_kind=render_completed`. Join or deduplicate render identity rather than treating each acknowledgement as another render.

No duration threshold counts as reading. Intersection cannot detect eye gaze or another desktop window covering the browser. An interval without a closing observation remains open/unknown; do not manufacture its end by subtracting unrelated clocks.

## Local acceptance

- Backend: event identity, raw time, calibration arithmetic/session change, captured tool origin, single onset, upstream offsets, onset/revoke stop ordering.
- Frontend: natural drain, mid-chunk stop, queued zero-credit, pre-start and pending-resume stop; current/stale renders, offscreen/background/covered surfaces; clock exchange/session reset.
- Browser integration: actual microphone fixture PCM, screenshots through the native adapter against a local peer, real Olist edits, interrupted playback, correct later playback, exact per-onset counts, aligned events and main/expanded visibility. Decisions and transcripts are authored; output is a test tone.
- Preserve every verification report under `traces/`. No real recognition, model reasoning, participant understanding or method benefit is claimed.

Source backup and this delivery's validation index: `traces/stage1-implementation-20261113-204914/`. See `verification-index.json` for final results and the integration report path. The earlier planned-only audit directory is not this implementation's evidence.

## Follow-on code changes, not implemented in Stage 1

| Stage | Existing code to reuse | Required addition |
| --- | --- | --- |
| Evidence package | `Workspace.context`, `set_context`, history/set tools, `QwenRealtime.context/image` | Immutable package/source IDs and shared cutoff across every actual outbound input, including native conversation |
| Episode scoring | `Workspace.export/score`, `backend/oracle.py`, existing `backend/study.py: evaluate` | Offline ledger, independent annotated intent, retained unknown/failed/missing outcomes; never answer leakage |
| B0/B2 parity | `backend/revisions.py: prepare_revision`, saved-set tools, `Workspace.instructions/execute` | Shared member resolution/compiler; only the declared interpretation/card support differs |
| Participant workflow | `App.vue`, `TaskBrief`, `RevisionObservation`, `TaskResponseReview`, experiment assignment | Explicit phases, common response questions, participant/examiner views, provenance-aware speech segment review |

Do not rename `direct`/`bound_revision` to B0/B2 and declare parity, or expose new telemetry as proof of a complete evidence cutoff. These are separately testable later deliverables.
