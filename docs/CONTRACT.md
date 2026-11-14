# Integration contract (v4 — assigned experiments and unified reports)

Current execution extension: [GOAL_EXECUTION.md](GOAL_EXECUTION.md). `revise_analysis` is the primary single-call analytical edit with flat source fields. `preview_revision` remains for explicit preview workflows but no longer advertises an `evidence` object in its model schema; manual HTTP/internal payloads still support their existing evidence references. Request-scoped execution receipts, provider settlement and awaited voice shutdown are described below.

Current extension: [JARVIS_ADAPTATION.md](JARVIS_ADAPTATION.md) specifies dual-time packages, candidate tools, exact outbound request records, AudioWorklet receipts and delivery reports. Images include captured_client_ms/client_clock_id; a frame without a calibrated capture is retained but cannot qualify for an application evidence package. Native history remains outside package freezing.

Stage 1 update (2026-11-13): [STAGE1_IMPLEMENTATION.md](STAGE1_IMPLEMENTATION.md) specifies current telemetry and clock messages. Events use `schema=covis-event-1`, stable session/event IDs and known request/epoch/response/item/call associations. Browser events retain `client_ms`, `client_clock_id`, `client_event_id`, and optional alignment with calibration ID/uncertainty. Clock probes never call a model. Received audio, audio-clock playback, commit, render and visibility remain distinct. Earlier descriptions below of clocks being unaligned are historical; raw domains remain preserved and only calibrated estimates may be compared.

## Data/tools (backend/data.py and backend/charts.py)

`OlistData(data_dir: Path)` loads real Olist; `catalog()` returns metric descriptors, states and categories; `query(source)` returns `{rows, columns, selection, definition}`. Dataset grain is distinct order per category, canonical review per order, item revenue, elapsed delivery days. Low review rate = score <= 2 / valid reviewed orders; retain numerator/denominator.

`selection.field` and `selection.members` describe the displayed grouping dimension. Fixed category filters imply `selection.mode=fixed` only for category charts. A month/state chart with fixed category filters reports its observed groups as `mode=all`; `selection.categories` still records the exact category filter. This distinction changes metadata, not query values.

Source shape: `{metric: 'orders'|'revenue'|'low_review_rate'|'avg_delivery_days', dimension: 'category'|'month'|'state', region: 'SP'|null, start:'2017-01-01', end:'2018-01-01', status:'delivered', categories: null|[category IDs], top_n: 5|null, rank_by:'orders'|metric}`. Dates are start-inclusive/end-exclusive. Fixed categories and dynamic top_n are mutually exclusive. Category order is preserved for a fixed list.

The model wire contract deliberately differs in one representation: `top_n` is a positive decimal string (for example `"3"`) or null. `backend/model_contract.py` advertises this in all six tools exposing the field. `Workspace.execute_model` validates the advertised schema and compiles the declared string once to the domain integer; `model_arguments_compiled` records both raw and compiled arguments. Null clears ranking and omission preserves the current rule. Numeric alternatives, decimal strings and malformed text are rejected at this boundary; there is no permissive type fallback or corrective model retry. Manual editing, domain queries and stored sources keep the strict integer/null contract above. Both text and Realtime providers and both study conditions use the same gateway. Existing integer-schema failures remain failures in their original archives.

`ChartStore(data)` owns `state = {revision:0,title:'Untitled dashboard',views:[]}`. `snapshot()` deepcopies state. `prepare(name,args,reference=None)` returns `{base_revision,candidate,result}` without changing public state; `commit(prepared)` installs candidate, increments revision and returns `{state,result}`; reject stale base revision. Pure reads return candidate null. Root handles request-epoch permissions. `restore(snapshot)` publishes a new revision. No undo history duplication in store.

View: `{id:'v1',number:1,title,chart_type:'bar'|'line'|'area'|'pie'|'scatter'|'heatmap',source,style:{color:'#238579',show_labels:false,sort:'source'|'ascending'|'descending'},data:{rows,columns,selection,definition}}`. Rows use `label`, `value`, `orders`, `low_review_count`, `reviewed_orders`, `avg_delivery_days`, `revenue` where relevant. Stable category IDs in label; frontend humanizes labels. For scatter x=orders, y=value. Heatmap uses label/value in a one-row heatmap if only one dimension. Do not claim arbitrary multidimensional graphics. State also has `layout:{columns:3}`; `arrange_charts({view_ids:all IDs in desired order,columns:2|3})` changes public order/layout without querying data.

Tools `read_dashboard({})`, `create_chart({title,chart_type,source,style?})`, `edit_charts({view_ids,patch:{title?,chart_type?,source?:partial source,style?:partial style}})`, `remove_charts({view_ids})`, `set_dashboard({title})`. All batch edits atomic. Source patch preserves unspecified fields. All values computed from Olist; no manual numeric overrides. Export `TOOL_DEFINITIONS` as OpenAI function entries `{type:'function',function:{name,description,parameters}}`. Browser manual edit uses identical tools. No unconstrained Python evaluation.

## Provider transport (backend/providers.py)

`QwenText(settings)` async `run(messages,tools,on_event,execute_tool)` where on_event receives normalized messages and execute_tool async(name,args) returns actual receipt. Text events `{type:'assistant_delta',text,response_id}`, final `{type:'assistant_done',text,response_id}`; log provider usage via on_event. Use actual HTTP streaming and function outputs; no retries. `messages` include current screenshot and context.

`QwenRealtime(settings,mode,tools,on_event,execute_tool)` with async `connect(context)`, `audio(pcm_b64)`, `image(jpeg_b64)`, `commit()` (manual mode only), `context(text)`, `cancel()`, `close()`. connect starts a receive task; mode push_to_talk has manual audio commit/response; live_voice server VAD with controlled response creation. Actual function calling executes callback and sends receipt; normalized events include transcript `{type:'user_transcript',text,item_id}`, speech_start/end, assistant_delta/done, audio `{type:'audio',data,response_id,sample_rate:24000}`, response_end and usage. On speech_start notify root before proceeding so root can bind visible selection/revision and revoke old work. Image upload after audio has begun, queue latest image until then. Do not create duplicate follow-up responses per function.

Settings is dict: api_key, text_url, realtime_url, text_model, realtime_model, voice. Never log headers/keys. Endpoint defaults borrow current VerbalVis workspace URLs; env file belongs only to this project.

`load_settings(env_file=None)` loads the project's `.env.local` or an explicit configuration path. Both `QWEN_API_KEY` and the existing projects' `DASHSCOPE_API_KEY` are recognized. If the file declares either name, its credential values take precedence over process environment values; an intentionally blank credential remains disabled. Process credentials are used only when the file declares neither name. Bootstrap exposes only the configured boolean, model names, credential file path and `connection_mode=disabled|configured|unconfigured`, never the key. The model-enabled launchers use `backend.__main__`; old review launchers still disable remote calls.

Realtime `image(jpeg_b64, frame_id=None)` emits `image_delivery` with `queued` or `sent` and the local frame ID. Workspace maps it to the original frame's exact reference and sends `visual_context {reference,status,frame_id}`. Local capture emits `captured`; an empty canvas emits `empty`. The frontend must not associate a late receipt with a different chart or member selection. Native image-buffer delivery does not prove audio-buffer consumption or visual reasoning.

After a real transport failure, the provider closes and emits `transport_closed`; Workspace ends the voice budget and sends `voice_closed`, which closes the browser microphone. A connection-handshake failure follows the same resource cleanup boundary. No reconnect or retry is added.

After a model tool commits during active voice with an established browser visual context, the asynchronous tool job waits outside the transaction lock for the exact committed revision's captured image or explicit empty-canvas context before returning its native receipt. Speech onset, revoke and close release the wait without rolling back the legal commit. A superseded call that already committed closes with its true committed revision but no stale rows; unexecuted remaining calls close as unexecuted. Native response creation waits for these tool receipts. No same-frame reupload occurs. This provides captured-image ordering, not proof of native visual consumption; PTT images still follow audio-buffer submission.

## HTTP / browser WS (root implements backend/app.py)

GET /api/bootstrap -> `{state,catalog,tasks,diagnostic_tasks,experiment_tasks,category_sets,task_response,report,settings:{configured,text_model,realtime_model},session,nodes,condition,conditions,evidence,proposal}`.
POST /api/session `{mode:'text'|'push_to_talk'|'live_voice',condition?:'direct'|'bound_revision'|'unbound_preview',task_id?:string,participant_id?:string}` -> bootstrap; explicit new session, no API connect. `mode` is transport; `condition` is the revision mechanism. The default mechanism is bound_revision.
POST /api/tools `{name,arguments,reference?}` -> `{state,result,node}`.
POST /api/undo -> `{state,result,node}`. GET /api/history -> `{nodes}`.
GET /api/nodes/{id} -> `{node,state,events}` (historical snapshot). POST /api/nodes/{id}/restore -> tool-like receipt.
POST /api/finish -> `{report,export_url}`. GET /api/export -> downloadable JSON (includes all final state/nodes/events/report, no credentials). POST /api/review `{notes,classification}` records human classification, never auto-passes review.

WS /ws sends bootstrap on connect. Client:
- `{type:'text',text,reference,image,captured_client_ms,client_clock_id}` image is JPEG base64; reference `{revision,view_ids,entities:{view_id:[labels]}}` is captured from actually rendered state.
- `{type:'voice_start',mode,reference,image,captured_client_ms,client_clock_id}` opens paid provider only on explicit user click; missing key reports English error, never fake response.
- `{type:'audio',data}` PCM16 mono 16kHz base64; `{type:'voice_commit'}` manual segment; `{type:'voice_stop'}` closes provider and releases work.
- `{type:'context',reference,image,captured_client_ms,client_clock_id}` after rendering/selection; captures and arrivals are archived, and an eligible image is supplied at response preparation through the existing native buffer path.
- `{type:'cancel'}` revoke current work and stop playback; `{type:'stop_speaking'}` only audio stops, tool continues.
- `{type:'event',name,client_ms,details}` actual render/audio start/end, selection, edit focus, recording boundaries. Both clock domains logged separately.
Server: `{type:'state',state,node}`, `{type:'evidence',evidence}`, `{type:'proposal',proposal}`, normalized provider events, `{type:'status',status:'thinking'|'listening'|'working'|'ready',message?}`, `{type:'error',message}`, `{type:'stop_audio'}`, `{type:'voice_ready'}`, `{type:'voice_closed'}`.

Accepted user input additionally emits `request_accepted {request_id,epoch,text,item_id?}`. `request_outcome {request_id,epoch,response_id,status,committed,revision,view_numbers,proposal_id,message}` uses status `committed|awaiting_confirmation|failed|no_changes`. It is computed from actual commits/failures belonging to that request after provider `request_settled`, not from reply wording. A tool-calling response does not settle before its tools and follow-up complete. Receipts attach to their original conversation turn; a prior commit cannot certify the new request. A committed receipt becomes Displayed only after actual matching chart-render acknowledgements. No-change discussion is neutral, not automatically a failed analysis.

`tool_result` carries the actual tool name, execution status, committed flag, publication revision, stable view numbers, summary and any failure message/proposal ID. It is produced from the same execution receipt returned to the model, including manual tool actions. Preview and awaiting-confirmation receipts never appear as applied edits. Malformed provider arguments arrive as `tool_failed`, also shown as an unapplied action. Ordinary read tools do not replace the latest visible edit receipt.

Frontend must capture actual selected chart/dashboard JPEG, stream mic in live mode during playback, manual recording in push-to-talk, 10-second segment cap, no automatic retries. Playback queue in the dedicated AudioWorklet with output cursor/clear acknowledgements and response IDs. No autoplay provider on page load. Export and review UI are secondary drawers; main page is a user-facing canvas. History nodes show user intent/tool outcome and committed chart version, not fabricated model reasoning. Default empty workspace; explicit starter/task opens seeded real-query charts and is labeled starter.

The microphone worklet owns capture boundaries: start resets the segment, pause flushes its final samples and excludes paused input, and PTT stops at 160,000 samples at 16 kHz. UI timing only displays progress. Playback registers received chunks before awaiting AudioContext readiness; end and stop remain effective while that await is pending. `audio_end` ends the stream, while `playback_end` occurs after queued audio ends or is stopped. Its `started` flag distinguishes a scheduled reply that never actually began playback. Recordings contain received audio, not proof of human listening.

## Historical evidence and revision tools (backend/revisions.py)

The model receives the same tool definitions in every condition; model history/set/candidate reads use the current application evidence package. `read_history({revision?})` returns a complete saved state, or a version index when revision is omitted. It never restores the canvas. The chart and saved-set tools remain available alongside list_evidence_candidates and apply_evidence_candidate. Candidate-based preview_revision accepts candidate_id instead of an explicit evidence object.

`revise_analysis({view_ids,member_action,candidate_id?,start?,end?,region?,metric?,dimension?,status?,categories?,top_n?,rank_by?,needs_confirmation?,question?})` validates flat fields, compiles a normal private revision, and applies it immediately for an explicit request. When `needs_confirmation=true`, it returns `awaiting_confirmation` without publishing. Omitted source fields remain unchanged; dates use inclusive start/exclusive end. Both direct and bound paths share this execution mechanism. B2 exposes its revision card; B0 retains the same exact-member resolution. No string-to-object repair or hidden reference answer is introduced.

`preview_revision({evidence?,view_ids,source_patch,member_action,needs_confirmation?,question?})` prepares a private candidate. Evidence is `{revision,view_id,members?}` using stable category IDs from an actually saved chart. If omitted, the explicitly selected evidence bound to this user request is used. `view_ids` identifies current targets; `source_patch` contains only desired source changes. `member_action` is:

- `keep_current`: leave the current membership rule unchanged unless explicitly patched.
- `use_evidence`: in direct and bound_revision, use the selected historical category IDs and clear dynamic top_n through the same compiler. Do not copy historical region, dates, status or metric. The historical unbound_preview diagnostic still uses supplied categories/top_n explicitly.
- `rerank`: release fixed categories and require explicit top_n and rank_by.

Return `{status:'completed',committed:false,proposal:{id,epoch,status:'pending',card}}`. The card shows evidence, current target IDs, before/after source, actual member lists, changed/kept fields and unresolved question. Preview does not publish or add a committed Journey node. Ambiguity is a user/model decision; the server does not fabricate the user's intention.

`apply_revision({proposal_id})` publishes the prepared candidate only while the proposal and request are current. A model cannot apply a proposal with needs_confirmation=true. A user can approve it, or answer in conversation and create a revised proposal. A new accepted request supersedes an older pending proposal. User confirmation revokes old assistant output before committing. ChartStore checks the candidate's base revision; stale candidates do not overwrite current state. These are ordinary revision semantics, not retry or recovery layers.

HTTP equivalents:

- `POST /api/evidence` with `{revision,view_id,members?}` selects inspectable historical evidence; `{clear:true}` clears it. Returns bootstrap and does not modify the canvas.
- `POST /api/revisions/preview` accepts the preview payload plus optional `label`, records a user request, and returns the actual preview receipt.
- `POST /api/revisions/{proposal_id}/apply` is explicit user approval and returns the committed tool receipt.
- `POST /api/revisions/{proposal_id}/dismiss` supersedes and clears the proposal.

Committed revision nodes include the actual revision card and evidence in addition to user intent, before/after differences and saved state. Version restore is a distinct new commit. Model follow-up must rely on the committed receipt, not a pending preview.

## Saved category sets and task responses

`save_category_set({name,revision,view_id,members?})` returns `result.category_set` with `{id,name,members,evidence:{revision,view_id,number,title,source}}`. The set is immutable and session-local. Saving changes no chart. `list_category_sets({})` returns `result.category_sets`. `apply_category_set({set_id,view_ids,source_patch?})` creates a normal private candidate: preserve current source fields, apply explicit patches, set the saved members and clear top_n. Shared identically in all three conditions; no hidden reference answer. The committed receipt includes category_set provenance.

HTTP: GET `/api/category-sets` lists; POST on the same path saves and returns bootstrap; POST `/api/category-sets/{id}/apply` accepts `{view_ids,source_patch?}` and returns a normal committed receipt. WS `category_sets` updates the library. Export v3 contains category_sets.

The category-set ID in the apply route identifies the selected set; a body field cannot replace that selection.

POST `/api/task-response` stores `{conclusion,rationale,object_origin,calculation_scope}` verbatim with current revision and submission time; returns `{response,report:null}`. It invalidates the report. Bootstrap/export include task_response. Later chart edits preserve the text and expose `task_response_status=stale`, recorded/final revision and `task_response_current=false`. Resaving after review updates the revision; technical completion or freshness does not grade interpretation.

## Revision-card observations

Browser `revision_card_visible/hidden` events carry `{proposal_id,display_id,surface:'summary'|'detail',proposal_status?,visibility_reason?}` and client_ms. Intersection and document visibility determine exposure; overlays close the covered interval. The same display_id pairs one browser interval. Open intervals have unknown duration; summary/detail times may overlap. No server/browser clock subtraction or reading threshold.

`revision_card_opened`, `revision_confirmation_clicked` and `revision_card_revision_requested` record explicit controls. Server `revision_confirmed` records a successful user Apply, with proposal_id and committed_revision. `revision_applied.actor` distinguishes model application. A generated preview, on-screen exposure and successful user application are separate quantities. None proves comprehension. Reports and exports include `interaction` with saved-set use, committed tool paths and per-proposal observations. Append-only trace payloads preserve their event-time state.

## Study boundary

### Assigned trials

GET `/api/experiment/plan?slot=1` returns the deterministic four-trial assignment and public task briefs. GET `/api/experiment/allocations?count=30` returns the complete allocation and joint balance counts. Assignment contains no reference answers. Every complete 16-slot block balances family × position × condition × variant; all participants receive two tasks per condition.

POST `/api/experiment/start` takes `{participant_id,slot,trial_index,evidence_kind:'local_authored'|'participant'}`. It archives any preceding unfinished attempt as abandoned, resets exact assigned task/condition, and returns bootstrap. It opens no provider. `session.assignment` is the single assignment source; `trial_status` is ready/running/finished and `trial_started_at` is an ISO timestamp for display.

POST `/api/experiment/begin` changes ready to running, records actual `trial_started`, and starts the server's 480-second timer. Assigned editing/request actions are available only while running. The client hides task evidence during preparation and makes finished charts read-only. Ordinary ad-hoc sessions keep their existing editing behavior. The independent 60-second voice budget is unchanged.

POST `/api/finish` optionally takes `{reason:'completed'|'timeout'|'abandoned'}`; repeated review returns the frozen report. Automatic deadline uses timeout. Switching away from an unfinished assigned task archives an abandoned attempt. Returns `{report,session,export_url}`; assigned completion also emits WS `trial_finished` with the same fields. Completion is a submission action, never a forced successful score.

The base report remains compatible and adds `trial_report`: identity, chart outcomes, current response/deliverable completeness, timing, process, actual input modes and pending human review. Technical correctness and four filled current response fields do not approve interpretation. Timing covers Begin to terminal event using server timestamps, excluding setup and later review. First full correctness comes from the whole published state; legal partial edits remain distinct.

Trial `process.visual_input` separates captured, queued and sent frames and lists sent frame IDs. `process.audio` records PCM input and received-output durations in the measured interval. These are delivery quantities, not recognition accuracy, human listening, connection duration or billing.

GET `/api/experiment/report` aggregates assigned archives plus the active attempt once. GET `/api/experiment/export?format=json|csv` downloads every attempt and explicit latest-attempt summaries, missing trials and participant-level paired descriptive differences. Failed/unfinished repeats are retained rather than replaced by the best score. Evidence kinds are separate strata. Export v4 includes session.assignment and the complete underlying events.

### Archived evidence and draft coding

New session exports also snapshot the public `task` brief. GET `/api/experiment/attempts/{session_id}` returns the selected attempt's task, automatic report, response, original events, measured event indices, nodes, saved states, transcript, media and draft history. `task_source` distinguishes an archived brief from lookup of an older frozen material. This read never changes the active workspace. Explicit `review_archive_dirs` in the isolated review launcher add earlier record roots; the current root takes precedence for a duplicate session ID.

GET `/api/experiment/attempts/{session_id}/media/{filename}` serves only WAV/JPEG files registered in that attempt directory, independent of the current session. Output recording, actual browser playback and human listening remain distinct evidence.

POST `/api/experiment/attempts/{session_id}/review-drafts` accepts `reviewer_id`, `notes`, proposed `interpretation`, proposed `spoken_consistency` and `segments`. Each segment has `start_event_index`, `end_event_index`, `kind` and `reason`; its ordered event range must lie in the measured task interval. Coding is available after the attempt finishes. Each save appends a new draft to `review-drafts.jsonl`; it never rewrites `session.json`, `events.jsonl` or the automatic report. The response is the refreshed packet.

Unified JSON retains every draft separately; CSV adds `review_draft_count` and `last_draft_at`. All approved human scores remain pending/null, regardless of proposed labels. Draft ranges are not automatically summed as repair effort. Full definitions and coding boundaries: [REVIEW_CODING.md](REVIEW_CODING.md).

Public task briefs and setup history are available to every condition. Evaluator-only expected sources, reference resolutions and authored answer trajectories stay in backend/study.py and the verification scripts. Independent SQL in backend/oracle.py checks real numeric outcomes. No evaluator calls run in model context construction.

`tasks()` returns starter plus four business goals; `diagnostic_tasks()` returns the frozen six development and twelve held-out cases. Previous twelve legacy briefs remain callable by ID. Business reports expose technical_completed, verbatim task_response and pending interpretation; business_conclusion_correct and understanding_correct remain null. Task briefs are public model context; private resolution keys and target sources are not. Human repair, spoken consistency and listening stay pending. See RESEARCH_PLAN.md, BUSINESS_TASKS.md and STUDY_PROTOCOL.md.
