# Jarvis mechanisms adapted to CoVisStudio

Date: 2026-11-13. This delivery keeps the existing Qwen Realtime 3.8 Omni Flash, Olist, FastAPI and Vue paths. All verification is local, using authored peer responses where a provider is needed. No credentials were read and no real API was called.

The scope remains two research conditions in the same full-duplex environment. These changes add no participant arm, coordinator model, worker pool, memory subsystem or automatic retry. They implement measurement and shared execution support; they do not establish a research benefit.

## 1. What was borrowed and implemented

| Jarvis reference, read locally | CoVisStudio implementation | Boundary |
| --- | --- | --- |
| `C:/Jarvis/jarvis/resources/frontend/audio-worklet.js` | Dedicated output worklet with a source-sample cursor, chunk receipts and generation clearing | Counts samples written to the audio graph; not acoustic perception |
| `jarvis/omni/timeline.py` | Evidence objects with capture/availability times, calibration uncertainty, immutable package and hash | Application evidence is frozen; native provider conversation is not |
| `jarvis/core/jev.py` concrete task/version choices | Actual chart/set candidate IDs; shared member resolution and current-scope compiler | Model/user still chooses the candidate; no evaluator answer is supplied |
| `jarvis/core/schemas.py` and runtime presentation completion | Separate commit, render, exposure, generated text and playback fields | No single delivered flag claims semantic correctness or comprehension |
| `jarvis/resources/prompts/worker.md` | Tool-receipt-based success statements, retained constraints and concise spoken results | Same Qwen call chain; no extra paid coordinator |

These are adaptations of the mechanisms, not an import of the Jarvis runtime. Jarvis and the older projects remain unchanged.

## 2. File and function map

| File | Main functions and relationship |
| --- | --- |
| `frontend/public/playback-worklet.js` | `Playback.process` emits samples and receipts; port audio/clear messages control one queue and generation |
| `frontend/src/audio.js` | `Speaker.prepare/append` initialize and enqueue; `receipt` consumes worklet facts; `stop/finish/close` wait for clear/drain acknowledgements; microphone path unchanged |
| `frontend/src/App.vue` | `updateContext` sends captured JPEG/reference/time/clock ID; `chartTelemetry` and `log` forward observations; report drawer renders the separate delivery report |
| `backend/trace.py` | Existing calibration plus `client_stamp`; `record_model_input` archives exact outbound application JSON bytes and SHA256, excluding headers |
| `backend/evidence.py` | `EvidenceStore.add` records a deep copy with source IDs and times; `package` filters and archives immutable eligible evidence |
| `backend/app.py` | `record_browser_event`, `freeze_evidence`, `decision_material`, `decision_image`, `candidates` connect evidence to model context and tools |
| `backend/providers.py` | Realtime `_dispatch` calls `response_prepare` before response creation; text refreshes system context before each HTTP request; exact attempted/sent payload audit on both transports |
| `backend/evidence_candidates.py` | `build_candidates`, `resolve_candidate`, `prepare_candidate_apply`; candidates resolve into the shared revision compiler |
| `backend/revisions.py` | `prepare_revision` transfers exact selected members for direct and bound paths, preserves unspecified current scope, and computes changed/kept/released fields |
| `backend/category_sets.py` | `prepare_apply` routes saved-set application through the same candidate/compiler path |
| `frontend/src/components/RevisionPanel.vue` | Displays object origin, current targets/changes, and kept/released conditions; no extra mandatory confirmation |
| `backend/delivery.py` | `summarize_delivery` is a pure read model over events; it never grants publication permission |
| `frontend/src/components/DeliveryReview.vue` | Shows commit versions, target render/visibility and received/output sample counts in the review drawer |
| `scripts/audit_delivery.py` | Reads archived events/states, creates the delivery report, optionally checks category-chart values with independent Olist SQL, and fingerprints inputs |

## 3. Runtime sequence

1. Browser captures the rendered canvas and exact selection, then sends its capture timestamp and clock ID. Server records arrival independently. Capturing a new frame does not immediately upload it to Qwen.
2. Speech onset revokes old publication permission and stops old playback. This existing policy is unchanged; a prior legal chart commit stays committed.
3. Before each model response, including tool follow-ups, `response_prepare` freezes an application evidence package. History, sets and candidate reads use that package. Real execution still uses the current ChartStore and existing epoch/version checks.
4. System context is generated from the package. An eligible image is selected from the package and passed through the existing native-image path. Qwen image buffering can still queue it until real audio is available; queued, sent and inspected remain different claims. No fabricated silence is inserted.
5. The model chooses an actual candidate ID or an explicit supported edit. Shared code resolves members, patches only requested current conditions, queries Olist and commits if still authorized. The successful receipt records the resulting state/version.
6. Model output is saved as received text/PCM. The output worklet reports what its queue actually emitted, including the cursor at interruption. Chart render/exposure observations are recorded independently.
7. The delivery report and offline audit join these records. Numeric checks do not judge intent, and playback completion does not grade spoken semantics.

Upstream response creation rechecks the provider epoch after preparation; an onset during preparation cannot create a response for the superseded request. Existing private candidates and Workspace publication authority are retained.

## 4. Playback contract

Each queued chunk carries `chunk_id`, `generation_epoch`, response/request identity and source sample range. The worklet advances its source cursor as it writes output samples; it reports started, progress, ended and clear acknowledgements. Progress is reported after approximately 1,200 additional source samples (50 ms at 24 kHz), plus boundaries. Output at 48 kHz is supported through source-cursor interpolation.

`timing_basis=audio_worklet_source_cursor` distinguishes the new measurements from old `browser_audio_clock` estimates. The old samples/time calculation and playback-start timers are removed. Pending-resume chunks and queued chunks that were never output receive zero played credit. An old generation cannot return after clearing. Full received WAVs are still preserved.

`client_ms` on the host observation means the browser received the worklet receipt. `audio_context_time` is the source audio-clock position from the worklet. Neither is a microphone measurement of sound leaving a speaker. Capture/arrival cutoff for playback evidence therefore concerns when that progress became observable, not a fabricated exact time at which a person heard a word. Word alignment and listening stay unknown/pending.

## 5. Evidence contract and limits

Each evidence record stores `evidence_id`, `kind`, copied content, `content_sha256`, `source_request_id`, chart revision/response ID where applicable, capture time, arrival time, calibration and uncertainty. A newly saved old set has a new creation/availability time and retains the older chart provenance; its availability is not backdated to the chart.

A record is eligible only when its calibrated capture interval ends at or before the cutoff **and** its server availability is at or before the cutoff. Missing calibration/capture time is `unknown_capture`; a straddling interval is `clock_uncertain`. Those records remain in the archive and the package's exclusion list, rather than being silently relabelled timely. Late arrival after an earlier cutoff never changes that earlier archived package.

Packages contain available committed chart snapshots, saved sets, image references/hashes, received text and browser render/playback observations. A generated transcript is explicitly received text, not a heard utterance. Candidate listing, history reads, saved-set reads and historical member resolution use the package; an edit applies to current execution state. Newly computed tool outputs become continuation evidence and enter the next response's package.

Exact outbound JSON is archived for session instructions/tool schemas, response control, PCM/JPEG messages and tool receipts. HTTP bodies are captured as actually sent bytes; WebSocket application messages are recorded before attempted send and after send returns. These are transport observations, not proof of remote model inspection. Authentication headers are not logged.

**Native conversation is not frozen or rebuilt.** Old native items, generated assistant text and provider-managed audio/image buffers remain separate from the application package. Input audit records explicitly carry `native_conversation_frozen=false`. This delivery prevents continuous new screenshot uploads between decisions and makes outgoing inputs inspectable; it does not claim complete native-history isolation or a perfectly replayable Qwen internal state. The text path retains the original user screenshot as historical conversation context while refreshing system state on continuation.

## 6. Shared candidate example

For “Change the region to RJ, but keep the saved three categories in charts 2 and 3,” both main conditions can list and choose `set:cs1`.

The common compiler obtains the actual `cs1` members, sets `top_n=null`, changes only `region=RJ`, and preserves each target chart's date, status, dimension and measure. Chart 1 is untouched. B0 can directly apply the candidate; B2 can expose a proposal using the same candidate and compiler. A conflicting explicit member list fails as an invalid tool request, rather than being silently corrected in only B2.

Explicit re-ranking releases fixed categories and requires its ranking parameters. The saved set remains inspectable but is not permanently imposed on future intent. Unknown candidate IDs cannot select an invented chart or set. The historical `unbound_preview` diagnostic remains separate from the two-condition study.

## 7. Completion, delivery and offline checks

The report keeps independent observations:

- Commit version and target views, including legitimate earlier commits after later revocation.
- Rendered and visible surfaces by revision/view; exposure is not reading.
- Generated text marked complete-received or partial-received.
- Audio received, output sample counts, generation, interruption and per-response drain status.
- Stop-only, cancellation and onset controls, without automatically calling a voluntary stop a semantic error.
- Human semantic consistency/listening pending and exact spoken-word alignment unknown.

Raw response creation may precede request association; the ledger fills known request identity when normalized registration arrives. Legacy unassociated requests remain explicit rather than inheriting the newest request.

Offline reproduction:

```powershell
.\.venv\Scripts\python.exe scripts\audit_delivery.py --session-dir C:\path\to\session --output C:\path\to\delivery.json --data-dir C:\VerbalVis\datasets\olist\data
```

The audit reads files and data directly, not an active Workspace. Numeric SQL checks cover the category aggregates supported by the independent oracle; unsupported view types are recorded as unchecked. Numeric agreement does not establish that the user intended that source or cohort. Artifacts include archive/source/data fingerprints. No model judge is called.

## 8. Evidence and remaining research work

This delivery's source originals, failed checks and final reports are indexed in `traces/jarvis-adaptation-20261113-210751/verification-index.json`. The browser harness uses real WebAudio/AudioWorklet, real images and Olist, with authored text/tool decisions and tone audio from a local protocol peer. It is not a Qwen semantic or natural-user result.

Still required before a formal participant study: actual Qwen verification when separately authorized; manual speech/intent/understanding review; task materials allowing participant-selected reference choices; a frozen primary episode ledger/analysis rule; and an explicit research decision about native-history/input parity. No extra experimental variable has been added to address these items.
