# CoVisStudio: execute the requested revision and report what happened

Implemented November 13, 2026. This update follows the two real failures recorded in `traces/real-two-cases/20261113-213538/RESULTS.md`. It introduces no new study condition and makes no additional paid call.

## Goal and concrete changes

The user must be able to interrupt an explanation, change the selected charts, retain valid analysis conditions, and inspect whether the change actually happened. Referring to historical members must not restore historical filters. Hearing a promise must not imply a committed chart update.

1. **One call for an explicit analytical change.** `revise_analysis` takes flat fields and reuses the existing private preview, source compiler, epoch checks and chart commit. Explicit requests need no extra confirmation click or second model call to apply a proposal. A genuinely unresolved choice remains a preview requiring user input.
2. **Simple historical references.** Model calls choose a real `candidate_id`, or use the user's explicitly selected evidence. The model-facing preview no longer asks for a nested evidence object. Manual evidence selection still uses the existing internal representation. Bad JSON strings are rejected, not silently interpreted or repaired.
3. **Actual outcomes per request.** Both text and voice transports emit settlement only when their final answer ends or a tool failure stops the batch. The workspace derives the outcome from that request's execution events. Old tool receipts remain under old conversation turns.
4. **Complete shutdown evidence.** Concurrent close requests await the same cleanup. A provider receiver or tool job cannot cancel/await itself. Workspace close also waits for completion before recording `voice_closed`, finalizing audio and releasing the browser microphone.

## Example

The current service charts use MG and preserve their distinct measures. A historical chart has the requested category set.

```json
{
  "view_ids": ["v2", "v3"],
  "candidate_id": "chart:3:v1",
  "member_action": "use_evidence",
  "start": "2017-01-01",
  "end": "2017-07-01"
}
```

After this `revise_analysis` call succeeds, an interruption can request the first quarter:

```json
{
  "view_ids": ["v2", "v3"],
  "member_action": "keep_current",
  "end": "2017-04-01"
}
```

The second call changes only the end date. Exact members, MG, the start date, delivered-order status, per-chart measures and untouched chart 1 are retained. These IDs and dates describe the authored diagnostic, not a hidden answer supplied to model sessions.

## File and function relationships

| File/function | Responsibility |
| --- | --- |
| `backend/revisions.py`: `REVISE_ANALYSIS_SCHEMA`, `normalize_revise_analysis` | Validate the flat tool contract and construct the existing source patch |
| `backend/app.py`: `_execute`, `preview_revision`, `apply_revision` | Resolve selected/candidate evidence, calculate Olist results, prepare a card, and commit only while the request remains current |
| `backend/providers.py`: `run`, `_handle`, `_run_tools` | Return real receipts; stop after a failed receipt; emit `request_settled` after the final answer rather than after an intermediate tool response |
| `backend/app.py`: `request_outcome` | Join the settled response to its request and derive committed, pending, failed or no-change outcome from actual execution |
| `frontend/src/App.vue`: `acceptRequest`, `receiveReceipt`, `receiptForMessage` | Associate user/assistant turns and receipts by request ID; never place an old success under a new request |
| `frontend/src/toolFeedback.js` | Render neutral no-change feedback; distinguish committed from actually displayed versions |
| `backend/providers.py`: `close`, `_close`; `backend/app.py`: `close_voice`, `_close_voice` | Await one cleanup and preserve final closure/audio evidence |
| `scripts/verify_goal_revision.py` | Replay a local scripted peer through the real browser, microphone/playback worklets, tools, Olist and chart rendering |

No generic workflow engine, additional model, automatic repair call, retry layer, JSON-string coercion or case-specific intention classifier is added. The current Realtime client reference does not document forced `tool_choice`, so this implementation does not invent a forcing flag or claim deterministic model compliance. [Official client-event reference](https://www.alibabacloud.com/help/en/model-studio/client-events)

## Verification and interpretation

The browser record at `traces/goal-optimization/20261113-135547-550114/report.json` passes 24 checks. Its public revisions are **6 → 7 → 8 → 8**: first-half update, Q1 revision, then an intentionally unexecuted promise. The last response displays **No chart changes** while the earlier successful edits retain their own Displayed receipts. Checks include actual playback interruption, independent Olist SQL, preserved chart 1 and conditions, screenshot delivery, matching rendered revisions and a recorded close event. Screenshots cover 2560 CSS pixels at 150% scaling and 3840 CSS pixels.

Unit/integration checks cover shared direct/bound execution, ambiguity without publication, stale request suppression, failed receipts without model continuation, and concurrent close with cancellation. The local browser uses authored tool calls and synthetic audio: it does not demonstrate improved real Qwen tool selection, ASR or spoken semantics. The original real failures remain the latest real-model evidence. Human listening and study outcomes remain pending.

The existing Windows Proactor cleanup warning appeared after the browser check and is preserved in `console-observation.txt`; the browser had no page errors and the isolated service exited. Full and targeted backend logs are stored alongside the browser report. Do not replace an unsuccessful real-model result with this successful local protocol test.

## Next bounded real validation

On a separately authorized attempt, use the already synthesized modern speech files and the same two goals. Inspect actual `revise_analysis` selection, native arguments, submitted scopes, render receipts and final playback. Stop the attempt after a tool failure; do not spend another series of model turns repairing the same malformed call. If the model again speaks without executing, keep the no-change result visible and report the remaining model-selection failure.
