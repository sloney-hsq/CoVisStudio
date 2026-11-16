# Implementation and acceptance — 2026-11-13

## Amendment A1, dual ground truth, temporal anchoring and shared prompt — 2026-11-16

Four commits, all local-only (zero paid API calls), pushed to `origin`.

- **Amendment A1** (`docs/amendments/A1-single-primary-2026-11-15.md`): terminal
  intent-consistency is the sole primary outcome; interface-assisted interpretation,
  repair funnel, interaction cost/time and public-constraint completion are
  secondary; overlap, reference dependence, `first_publication_consistent` and
  window expiry are descriptive only. Paired B2-minus-B0 estimand with cluster
  bootstrap and Manski bounds; no Holm adjustment. `formal_manifest()` now carries
  the `analysis_plan` block. `FORMAL_STUDY.md`, `UNIFIED_RESEARCH_PROTOCOL.md`,
  `README.md` and `AGENTS.md` updated to match.
- **Scoring & dual ground truth** (`backend/intent_scoring.py`, `app.py`,
  `prepare_intent_review.py`, `intentReview.js`, `IntentEpisodeReview.vue`):
  `terminal_packet`, `terminal_coverage` and `score_terminal` (reusing
  `compare_state` against trial-start/trial-finished states); `no_change`
  (episode) and `retain_all` (terminal) dispositions with `disposition="revise"`
  default; `source_requirement` defaults to `none` (reason required only for
  `exact`/`members_only`); `interpretation_key` + `lock_understanding`;
  `first_commit_correct` renamed to `first_publication_consistent` (legacy
  `score.json` still read); `view_overrides`/`reference_interval` synced across
  backend and frontend templates.
- **Temporal anchoring** (`delivery.py`, `app.py`, `providers.py`, `microphone.js`,
  `audio.js`, `App.vue`): pure `reference_context(events, snapshots,
  anchor_interval)` reports generated/played (never "heard")/rendered/committed/
  pending states with before/after/unknown ordering and committed-not-yet-rendered
  flags; capture sample-clock metadata (`sequence`, `first_sample`, `sample_count`,
  `capture_client_ms`, `client_clock_id`) forwarded into local `audio_sent` logs
  only, degrading to `coarse`.
- **Shared prompt, tool contracts, frontend** (`app.py`, `revisions.py`,
  `style.css`, `RevisionPanel.vue`, `revision.js`): INSTRUCTIONS replaced with the
  6-sentence shared prompt; domain rules (inclusive/exclusive dates, within-group
  rates, freight exclusion) moved into the `revise_analysis` tool description;
  `unbound_preview` removed from participant-reachable paths; 12px font floor and
  4.5:1 contrast floor enforced with `scripts/audit_text_floor.py`.
- **Verification:** **411 backend tests** passed (7 new: reference_context cases
  1–4, terminal scoring/interpretation key, formal manifest analysis plan and
  repeat accounting); **50 frontend tests** passed; production build passed with
  the existing ECharts chunk-size advisory; `audit_text_floor.py` reports no
  violations. No real Qwen call, no participant evidence; human intent/listening
  review remains pending.

The entries below preserve earlier implementation stages and their original outcomes.

## Source provenance and correction UI — local verification only

- The shared compiler now records selected versus consumed source identity,
  explicit overrides and member equality. Omission uses the bound selection;
  explicit valid IDs still win. Equal members do not collapse different versions.
- Reuse stores membership origin on each changed view. Date/region changes retain
  it; reranking clears it only on targeted views. A rerank card identifies selected
  historical evidence as unused rather than as the calculation source.
- Continuing VAD fragments retain the first-onset binding. Each onset still
  revokes old publication permission and stops playback. Later selections apply
  to the next provider group; this is not word alignment or frozen native history.
- Independent intent coding now states whether an exact source is required.
  Analytical, numeric and provenance results are separate. Missing evidence stays
  unknown; neither selection nor model output automatically becomes intended truth.
- Fixed saved-set mapping labels, selected chart-number visibility, correction
  action placement and summary overlap; scaled chart values and compacted plots.
- Validation: **404 backend tests passed** in the full run; **30 targeted tests
  passed** after the final missing-origin/unknown scoring adjustment. **52 frontend
  tests passed**, production build passed, and the final browser run passed **23
  checks** at 1920/2560/3840 widths. The build retains its chart-chunk size warning.
- **No paid API call**, no new participant evidence, no change to original real
  traces. The local browser service closed. Real Qwen source choice and spoken
  truthfulness remain unverified for this patch. Public screenshots and source map:
  [provenance review](docs/PROVENANCE_REVIEW.md).

## Follow-up review — local evidence and receipt corrections

- Fixed absent-request scoping: manual commits cannot certify an absent request.
  Native stale receipts now derive publication from the exact call's ledger entry,
  preserving already legal commits. Attempted and committed remain separate.
- Generalized the new follow-up prompt, recorded the static policy hash in new
  sessions and restricted parity normalization to the random session prefix.
  Evidence-package and live public revisions are recorded separately, not asserted
  equal across a legitimate cutoff.
- Reconstructed the added context fields for the original failed request offline:
  no request commit, empty recent outcomes, public/evidence v6. All existing fields
  remain unchanged. This is explicit execution status, not missing chart evidence.
- **56 targeted local tests passed**, covering three stale-call outcomes, B0/B2
  parity, capture ordering, manual commits, driver and replay. No paid API call.
  Reconstructed videos carry a burned-in label; original silent video/WAVs remain.

## Real reuse check after runtime-fact repair — qualified success

- One authorized Qwen Realtime connection completed in **33.547 seconds**, with
  complete **4.24 / 6.64-second** inputs, no retry and no new TTS call. Speech began
  during actual explanation playback. The old partial-request tool was suppressed;
  the current request issued a new tool and committed **v6 → v7** before completion
  speech. This case did not reproduce the prior no-commit false completion.
- Charts 2/3 adopted the historical members while retaining MG, 2017, status and
  their respective metrics; chart 1 stayed unchanged. All three final chart queries
  matched independent SQL. The v7 JPEG was sent before the same request's reply.
  The final 10.08-second output audio played completely.
- **Remaining discrepancy:** selected evidence was chart 1 at v3, but the model
  chose `chart:1:v1`. The two member lists are identical. The card matches the
  actual tool and resulting charts, but not the selected source version. The
  original driver's numerical pass is retained alongside this separate audit.
- API closure was recorded once, the test process exited and port 8078 closed.
  A Windows Proactor 10054 cleanup warning remains recorded. No service restart.
- Private evidence and synchronized audiovisual replay:
  `traces/reuse-runtime-truth-20261113/review.html`, `audit.json`, `run/report.json`,
  `run/shutdown.json`, and the original native/audio/browser archives. Eleven local
  recording/driver checks passed before the authorized run. One authored case is
  not evidence of a stable model improvement or a participant benefit.

## Runtime execution facts after external review — local only

- Every prepared response now includes request-scoped commit facts and recent
  settled outcomes, derived from the ledger in both B0 and B2. Current chart
  context was already sent in the failed run; this is not a missing-state fix.
- Stale native receipts include public revision and distinguish never-invoked
  work from attempted-but-uncommitted work. Earlier legal commits remain legal.
- The complete-flow wait follows a clip's superseding VAD request instead of
  waiting on an obsolete prefix. Terminal no-change edits stop; discussion does not.
- No keyword-based semantic verdict, automatic retry, VAD change or paid API call.
  Model compliance and human interpretation remain unverified. See
  [source review and repair boundaries](docs/RUNTIME_TRUTH_REVIEW.md).
- Validation: initial full run 389 passed / two legacy assertions failed; after
  updating receipt expectations and session-prefix normalization, all 46 tests in
  the affected seven modules passed. No second full run; no real-model claim.

## Browser replay with synchronized audio

- Complete-flow runs export an MP4 containing injected user speech and the actual
  played assistant sample intervals after the API closes. Interrupted unplayed
  tails are excluded; gaps and overlap are retained. Original media is unchanged.
- The existing failed flow now has a derived audiovisual replay and alignment
  manifest; its review page uses this recording. This changes no test outcome.
- Video alignment uses the first traced screencast frame and calibrated browser
  timing; it is not a sample-exact acoustic recording. Future source videos use
  1920×1080 capture. Conversion and verification require no model calls.

## Latest cumulative real-flow check — failed, retained

- One authorized connection ended **failed/timeout at 56.36 s**, no retries.
  Only complete **4.24/6.64 s** clips were sent with actual playback overlap;
  Q1 correction and chart-2 reranking were not reached. One new 6.88 s TTS clip
  was prepared but never sent, and is not an evaluated step.
- Supplementary speech revoked the partial request before its correct reuse tool
  arrived. Its receipt was `superseded`, `committed:false`. The new request had
  the complete intended text but falsely claimed success without another tool.
  Actual outcome: `no_changes`, unchanged **v6**, no revision card.
- Offline SQL **15/15** verifies setup and unchanged state, not the requested edit;
  no post-commit image sequence exists to assess. API and isolated 8076 service
  closed. Prior successful and failed records remain separate; both papers now
  report this failure. Independent audit: `traces/complete-flow-20261113/AUDIT.md`.

## Current delivery — correctable interpretation and active terminal intent

- Revision cards now retain the exact compiled patch, fixed-versus-ranked membership,
  current computation scope and immutable untouched-view facts. Correct interpretation
  restores original target IDs instead of the currently selected chart, preserving
  distinct measures across target charts. Participant-facing wording is plain English.
- Shared model instructions explicitly distinguish historical identities from current
  conditions and respect a later request to release a fixed set and rerank.
- Private independent scoring follows actual episode chronology and the still-active
  cumulative intent. Per-view overrides express different continuing obligations;
  later unknown intent cannot be replaced with an earlier successful score.
- Offline real-run audits now require the original live attempt to have completed,
  and associate the fresh JPEG and following response with the committing request.
- Verification: **377 backend tests**, **51 frontend tests**, production build and
  **14 local browser checks** passed. Browser checks cover actual correction controls,
  logging, B0/B2 shared execution and 1920/2560/3840 CSS-pixel layouts.
- Exactly two newly authorized real Qwen Realtime attempts passed: reranking
  **35.360 s**, historical-member reuse **33.141 s**. Input segments were
  **4.24/8.08 s** and **4.24/6.64 s**. Both revisions occurred during actual playback;
  no automatic retries or new TTS calls. **36/36** archived SQL checks and both
  same-request post-commit JPEG sequences passed; final audio ended naturally.
- Transcription imperfections remain recorded; human listening and participant
  effects remain pending. These authored cases are not a B0/B2 outcome comparison.
- Both manuscript sources and six-page PDFs are synchronized. Current Chinese PDF:
  `paper/cscwd_zh/main-current.pdf`; English: `paper/cscwd_en/main.pdf`.
- Current description: [revision support delivery](docs/REVISION_SUPPORT_DELIVERY.md).
  Private real evidence: `traces/revision-support-20261113-164326/`.
  Final browser evidence: `traces/revision-support-final-20261113/browser-20261114-045315-656196/`.

The entries below preserve earlier implementation stages and their original outcomes.

## Current focused repair — declared ranking contract and real post-edit images

- Added `backend/model_contract.py` and the shared `Workspace.execute_model` gateway.
  Six model tool paths advertise positive decimal-string/null `top_n`; validated compilation
  produces the strict internal integer. Manual edits and stored sources remain numeric.
  Native raw arguments and compiled arguments are separately archived. No retry, generic
  coercion, fallback, or additional model was introduced. Both primary conditions share it.
- The common post-commit instruction requests one short result sentence, without output
  truncation or replay. The model may still speak before its tool call; actual commits,
  captions and output-sample receipts remain the evidence of execution and delivery.
- Exactly two authorized real Qwen attempts passed: reranking 39.937 s, historical-member
  reuse 27.906 s. Complete clips were 4.24/8.08 s and 4.24/6.64 s. Both had genuine speech
  overlap, correct final goals, matched render/capture and actual fresh JPEG bytes before
  follow-up, and naturally completed replies. No retries or new TTS calls were used.
- The reranking ASR still transcribed “Release” as “These”. The model nevertheless released
  fixed categories in this authored case; this is not a claim of general recognition reliability.
  Human listening and participant outcomes remain pending. Old failed runs are unchanged.
- Focused gateway/provider tests: 52 passed; complete backend suite: 367 passed (one existing
  Starlette deprecation warning); frontend tests: 47 passed; production build succeeded.
  The complete current verification and shutdown record are indexed under
  `traces/rerank-repair-20261113/`. See [RERANK_REPAIR.md](docs/RERANK_REPAIR.md).

## Subsequent single real API validation

- One authorized current-build bound_revision call; no retries or new TTS. Source clips
  8.56/6.32 s, connection including cleanup 56.109 s, actual microphone PCM including silence 54.16 s.
- Real overlap produced v7 half-year → v8 Q1, correct selected charts, preserved MG/member identities/
  measures/untargeted chart. All 21 archived queries pass independent SQL. Both exact-revision
  captures precede native receipts and fresh image delivery precedes response creation.
- **18/19 checks pass, original run remains failed/timeout**: final audio is 32.08 s, 28.72 s played
  before the budget stop. Default explanation length still needs improvement; no paid rerun made.
- Main-screen three-part card exposed; no user Apply/reading/understanding assumed. Two outcome-blinded
  intent packets and blank coding/adjudication forms prepared from the real inputs, human review pending.
- Records and offline playback: `traces/route-real-validation/RESULTS.md` and `review.html`.
  No formal participant record or independent human score manufactured; project test services closed.

## Current delivery — normal flow, inline revision support and independent intent study

Three delegated work streams plus integration implement the agreed route in this existing
project. No paid API/TTS call, credentials inspection or participant collection occurred.

- Corrected failed ASR-fragment groups, pending-Apply permission checks, closure of unexecuted
  calls after a failed batch, single voice cleanup, origin-associated PTT/render/tool records,
  and Journey source provenance. Finished assigned archives are no longer overwritten during
  review/export/disconnect. Missing playback remains unknown; Undo/Restore remain publications.
- B2 shows **Sources / Change / Keep & release** inline with expandable detail. Both main
  conditions retain Apply/Modify for actual proposals. Corrections preserve their original
  source/targets/patch. Close is not a correction; partial failure preserves prior commits.
  Empty canvas has an explicit context acknowledgement; hidden preparation has no exposure.
- Eight new `study_*` business materials and the two-condition assignment/window contract are
  integrated. Participant choices are not scored against the old `exp_*` fixed answers. Formal
  tasks use one 60-second Realtime window within 480 seconds; six response fields save before
  Finish. The participant flow does not open researcher controls at completion/next task.
- Researcher archives now prepare blinded packets, import two independent codings and an
  adjudication, lock intent, designate the terminal task episode, run independent SQL and
  record separate understanding labels. Direct manual inputs are recorded before execution.
  Formal reports retain first actual attempts, repeats, missing assignments and explicit
  unknown bounds. Original data and human/listening statuses are not replaced by test results.

Actual final verification:

| Check | Result | Evidence |
| --- | --- | --- |
| Complete backend suite | **338 passed**, existing Starlette/httpx warning | `traces/route-delivery/backend-final.txt` |
| Frontend suite / production build | **47 passed** / built; existing ECharts size advisory | `traces/route-delivery/frontend-final-*.txt` |
| Main-screen browser workflow | **32/32**, 1920/2560/3840 CSS widths | `traces/workspace-revision-20261113/browser-010843/report.json` |
| Researcher intent workflow in browser | **10/10**, including original archive after shutdown | `traces/route-delivery/review-browser-011158/report.json` |
| PCM/JPEG/tool/render/playback revision loop | **24/24**, versions 6→7→8→8 | `traces/route-delivery/voice-integration/report.json` |

The last voice case uses authored transcripts/decisions and test tones with a local native
protocol peer, not real Qwen or human speech judgments. A Windows Proactor connection-close
callback warning followed its passing assertions; the raw log is retained. The test process
exited and isolated listeners 8074/8079/8087 were closed. Other user processes were untouched.
Earlier failed assertions and browser-selector runs are retained with later verification.

Read [REVISION_STUDY_DELIVERY.md](docs/REVISION_STUDY_DELIVERY.md) for operation and API details,
[FORMAL_STUDY.md](docs/FORMAL_STUDY.md) for the candidate study contract, and
[formal_manifest.json](docs/formal_manifest.json) for its eight materials and 30-slot plan.
Human review, listening, formal-study approval and treatment-effect evidence remain pending.
Technical checks and a working scorer do not establish a paper's empirical contribution.

## Current deep review and bilingual paper update

- Confirmed and repaired native tool-output ordering on supersession. Already committed work is reported truthfully with its revision; unexecuted work carries no stale rows or state. Immediate onset revocation and playback stop remain.
- Fixed ordinary capture/continuation race found in new real 03: the asynchronous tool task now waits outside the transaction lock for the matching rendered image or explicit empty-canvas context. First-create and last-delete flows are included. Input, revoke and voice close wake the wait. Same frame IDs are not sent twice.
- Actual local browser final flow passes 24 checks. Independent ordering audit passes both commits: current render -> matching capture -> native receipt -> new image -> next response. This establishes image delivery, not remote image reasoning; PTT still follows native audio-buffer commit boundaries.
- Fixed grouping metadata for fixed-category month/state charts, authoritative saved-set route ID, and deletion of an expanded chart. English UI uses readable condition values, clearer target/scope hierarchy and separated participant controls at 1920/2560/3840 CSS widths. Frontend 40 tests/build and actual browser checks pass.
- Two real calls only: 02-direct failed after 19.89s (top_n string); 03-bound passed after 33.75s (one correct service-chart commit and naturally completed 14.8s output). Late ASR fragments now associate, but ASR words can still be wrong. Neither new case reproduced the specific old late-created tool race. Six actual final chart queries match independent SQL; this does not make 02's requested outcome correct. Raw audio, images, requests, results and failures are preserved.
- Chinese and English six-page IEEE review drafts now report the two new diagnostics separately and define the treatment as visible, correctable revision support over shared execution. Human intent, listening, understanding and participant-effect claims remain pending. Research review covers DataTone, CLEO and VoCa using primary sources.

Evidence root: `traces/deep-review/`. Final verification and shutdown state are indexed in `verification-index.json`. Earlier paragraphs below describe their respective historical deliveries.

Final local verification: **298 backend tests passed**, **40 frontend tests passed**, production build successful, actual browser **24/24** checks passed and both post-commit capture sequences independently verified. Earlier failing runs are retained; their fixtures were updated to acknowledge real rendered/context events and truthful superseded receipts. The complete final backend run is `backend-verified-tests.txt`. Only the existing Starlette test-client deprecation warning remains in that run. All project test processes and service listeners were closed afterward; no unrelated Python process was terminated.

## Research acceleration — concrete runtime fixes and study preparation

Current plan: [RESEARCH_EXECUTION_PLAN.md](docs/RESEARCH_EXECUTION_PLAN.md). No paid API calls in this iteration.

- Real VAD fragments retain late actual ASR and attach the ordered continuing speech to the latest request without restoring stale permission. A response created late after newer input drains remotely with truthful superseded tool receipts, while stale text/audio/execution remain suppressed. Normal onset stop/revocation and already-active cancellation remain. This exact remote sequence still needs a bounded real check.
- Direct/bound use identical analytical instructions. Removed redundant condition labels from model context and revision cards; runtime/UI/export session condition remains. Controlled before/after context, candidate/set/history reads, final data, receipt card, commit and clarification comparisons pass with no semantic differences. Native history is not claimed frozen.
- Eight outcome-blinded intent packets with complete original revision inputs and two empty coder forms are under `traces/research-acceleration/intent-review/reviewer-handouts/`; outcome mappings are in separate researcher-private files. All intent/listening labels remain pending, and these eight are authored diagnostics.
- Provider/alignment/observed-order tests: 30 passed. Full backend: 279 passed, 3 failed because older tests required the now-removed model condition label. Corrected those assertions while retaining UI condition checks; business flow + parity + blinding rerun: 5 passed. No clean second full run is claimed.
- Actual local browser: 24/24 checks passed, revisions 6→7→8→8, independent Olist SQL, actual playback interruption, request-scoped receipts and exact outbound archives. Scripted model/audio evidence is not a paid-model result.

Verification: `traces/research-acceleration/integration-20261113/verification-index.json`. The previous eight real attempts remain unchanged; no result is upgraded by local fixes.

## Latest real matrix — eight authored diagnostics, not a user study

On November 13, the user authorized real experiments. Evidence: `traces/real-study-20261113-224313/`; interpretation and next steps: [REAL_API_FINDINGS.md](docs/REAL_API_FINDINGS.md).

- Eight Qwen3.8 Realtime connections, four families × two runtime paths; all under 60 seconds, complete source utterances 4.24–8.56 seconds, no automatic retry. Three new natural neural TTS calls; earlier complete clips reused.
- Four final analytical goals passed with actual commits/rendering and naturally completed revision playback. Original driver statuses remain 3 passed / 5 failed: one correct/delivered trial was marked timeout when its watchdog fired during normal shutdown.
- Failures: one false completion without a Q1 tool call; two integer-string toolrejections; one native cancelled-tool-turn continuation error. VAD fragment epoch advancement also dropped early transcripts from application context. These are concrete remaining production problems, not evidence of B2 effectiveness.
- Independently recomputed 24 actual finalqueries: 24 matched. Actual-query correctness does not imply requested-goal correctness.
- Post-matrix measurement fixes only: latest-fragment tracking, watchdog shutdown classification, transport error reporting, and natural playback vs emptied interrupted queue. Four local driver regression tests passed; no paid rerun. TTS source-duration metadata corrected from actual PCM, with byte-identical converted clips.
- Chinese manuscript updated and compiled to 6 pages. Formal B0/B2 parity, human intent/listening/understanding and participant study remain pending. All real connections and temporary test services closed.

## Latest local optimization — single-call analytical revision and truthful outcomes

Three GPT-6.1 Sol agents and root integration addressed the observed failures without new API calls or credential access. `revise_analysis` now accepts flat fields, resolves real candidate/selected evidence, and executes the existing private-preview/commit path in one call for explicit requests. Unresolved choices remain uncommitted. Direct and bound conditions use the same compiler and exact-member semantics. Existing saved-set tools remain available.

Every settled request now has an execution outcome derived from its own actual commits/failures. The frontend attaches receipts to the correct turn, distinguishes Committed from Displayed, and shows neutral **No chart changes** for a reply without a commit. Earlier success cannot certify a later spoken promise. Review edit opens an existing local editor without calling a model. Shared awaited shutdown preserves one close event even with concurrent closers or cancellation of the caller.

Verification directory: `traces/goal-optimization/20261113-135547-550114/`.

- Local browser: **24/24 passed**, revisions **6 → 7 → 8 → 8**. Two real-Olist single-call edits cover historical members/first half then Q1, followed by a scripted unexecuted promise. Actual worklet overlap, preserved scope/other view, independent SQL, image delivery, rendering, request-scoped receipts and recorded closure are checked. Screenshots inspected at 2560 and 3840 CSS widths.
- Frontend: **40 tests passed**, production build passed with the existing ECharts size advisory.
- Full backend run: **268 passed, 4 failed** before adapting old protocol fixtures. Those failures expected a closed fake without an awaitable `close`, automatic audio after a failed tool receipt, or no new `request_accepted` event. The corrected scopes passed **8 live-alignment + 4 revision-flow + 2 accepted-event checks**. The original full-run failure log and follow-up logs are retained; no clean second full run is claimed.
- New focused coverage includes **27 flat-tool/revision checks**, **17 provider checks**, and **6 workspace goal checks**. Their results are local implementation evidence, not extra independent samples or real-model success.

The Windows Proactor cleanup warning remains recorded; the browser had no page errors and the isolated service exited. There is no nested-string coercion, automatic corrective model call, hidden intention classifier or invented forced-tool API flag. Real model choice/argument reliability, human listening and research benefit still require actual evidence. See [GOAL_EXECUTION.md](docs/GOAL_EXECUTION.md).

## Latest real check — two authorized cases, both analytical goals failed

Evidence: `traces/real-two-cases/20261113-213538/RESULTS.md`; original and offline reconstructed reports are preserved separately. Three genuine Qwen-Audio 3.1 TTS Flash / Abby_v3.1 requests produced complete input speech of 6.64, 8.56 and 6.32 seconds. Two real Qwen3.8 Omni Flash Realtime connections followed; no extra paid attempt was made after the failures.

- **Historical-set reuse, PTT:** correct ASR and native image upload; the model supplied nested `evidence` as a JSON string instead of an object. Twenty-four tool failures occurred, with no commit or output audio. Connection-to-close interval: 55.238 seconds; captured PCM: 6.84 seconds.
- **First half to Q1, live voice:** the first-half update of charts 2/3 succeeded after two malformed previews and a valid candidate-based call. Actual speech onset interrupted the old playback. Q1 ASR was correct, but the model only promised to change the dates and issued no subsequent tool call. Final charts remained January–June. Recorded activity: 34.182 seconds; exact close event is missing. Live PCM totaled 34.144 seconds, including silence, while the two source utterances total 14.88 seconds.
- Independent SQL confirms values for all six actual final chart sources. This does **not** make the requested goals correct. The second case's screenshot also shows the previous successful action receipt below the later promise; that receipt is not evidence of a Q1 commit.
- The old runtime automatically continued after failed tool receipts. This enabled the repeated calls despite no connection retries. A concrete post-test fix in `backend/providers.py` now sends/acknowledges a failed receipt once, stops the remaining batch, and does not request another response. Earlier valid commits remain. All **13 provider tests passed locally**, including three failure variants and the existing successful continuation case. No paid retest followed.
- The driver lost its second case summary during cleanup and incorrectly left aggregate `api_attempted=false`. Append-only traces, screenshots, browser recordings and audio survive; an offline reconstructed report corrects the account without replacing the originals. The driver now checkpoints attempted calls/results before cleanup and stops the test after the first tool failure.

Remaining work is concrete: simplify model-facing evidence references around existing candidate IDs; distinguish a spoken promise from a committed edit in the UI; repair the missing close-event path. Human listening remains pending. These two authored trials are not participant-study evidence.

## Current delivery — Jarvis-inspired receipts, evidence and shared execution

Seven GPT-6.1 Sol subagents contributed implementation, local integration and independent review. The existing Qwen3.8 Realtime / Olist chain is retained. **No real API calls, no credentials read, no added paid coordinator, no new experimental condition.**

- Replaced output playback timers with `frontend/public/playback-worklet.js` source-cursor receipts. Progress occurs about every 1,200 source samples; clearing acknowledges actual partial output and discards queued audio by generation. Received WAVs remain complete received audio. The microphone implementation is unchanged.
- Added immutable application evidence packages with separate calibrated capture and server availability times, source request/chart/response IDs and content hashes. Unknown or cutoff-straddling capture times are retained as excluded evidence. Current execution state remains distinct from interpretation evidence.
- Centralized decision preparation: history/set/candidate reads use the package, and new screenshots are selected/uploaded at response preparation. Exact attempted/sent native JSON and HTTP bodies are archived without headers. **Native provider history is not frozen**, explicitly recorded in each input/package association.
- Added actual chart/set candidate tools and a shared compiler for direct/bound revision and saved-set reuse. B2 shows origin, targets/changes and retained/released conditions; B0 has the same deterministic member resolution. No extra mandatory confirmation was introduced.
- Added an execution/delivery ledger and English review UI. Commit, render, visibility, generated text and output samples remain separate. Standalone offline auditing reads archived evidence, optionally verifies category aggregates using independent Olist SQL, and fingerprints sources/data. Human intent, word alignment and semantic/listening review remain pending.

Final evidence is indexed in `traces/jarvis-adaptation-20261113-210751/verification-index.json`. Main browser case: **32/32 checks passed**, input PCM **2.032 seconds**; interrupted output **2,432/96,000 samples**, final output **14,400/14,400**. Candidate direct/bound browser comparison: **8/8 passed**. Offline historical/intermediate/final category aggregates: **21/21 SQL checks passed**. Latest frontend suite: **38 passed**, production build successful with the existing bundle-size advisory. Backend full suite: **243 passed**, with the existing Starlette/httpx deprecation warning.

The original task's static outcome report still evaluates its original full-year specification. The authored Q1 revision deliberately differs, so those original-task fields remain “Not met”; they were not rewritten to manufacture success. The revision harness checks the explicit revised scope independently. This is why a participant-intent episode scorer remains a separate research deliverable.

Retained failures include old native-image fixtures without capture clocks and exact equality of independently summed floating-point data. Fixtures now declare synthetic calibration, and parity checks keep source/member identity exact while using the existing numeric tolerance for query values. The final browser run has no browser errors or teardown warnings; earlier teardown logs remain untouched. Details, function map and remaining boundaries: [JARVIS_ADAPTATION.md](docs/JARVIS_ADAPTATION.md).

## Current delivery — stage 1 measurement for the unified protocol

Implemented by three GPT-6.1 Sol agents plus integration. The real voice default remains `qwen3.8-omni-flash-realtime`. **Zero real API calls; no credentials read.** Existing trial materials, model decisions, conditions and human-review statuses are unchanged.

- `covis-event-1` events now carry session/event identity and known request/epoch/response/item/call origin. Async tools and later playback keep their original request association. A normalized `speech_start` is recorded once; raw provider onset remains a separate transport event.
- Onset and explicit revocation invalidate local publication first and send playback stop before awaiting remote cancellation. Prior legal commits remain intact.
- Audio chunks record sample ranges and browser audio-clock progress. Stop clips the active chunk, credits zero samples to queued chunks, and reports per-response queue completion. Received WAVs remain received audio, not evidence of listening.
- Current, historical and expanded charts have distinct render/surface/exposure identities. Exposure requires actual current rendering, positive plot intersection, a visible page and an enabled surface. Existing-render acknowledgements preserve their original completion timestamp. Fixed the parent empty-array identity that caused repeated unnecessary renders.
- Browser/server calibration records three timestamp exchanges, the selected sample, offset and uncertainty; raw clocks remain. Trace uses the measured high-resolution Windows performance counter. Fixed the browser-native timer invocation found by actual integration, without adding retries or reconnect logic.
- Added [unified research protocol](docs/UNIFIED_RESEARCH_PROTOCOL.md) and [file/function implementation map](docs/STAGE1_IMPLEMENTATION.md). Full evidence cutoff, shared B0/B2 compilation and offline episode scoring are subsequent stages, not claimed complete.

| Current verification | Result | Record |
| --- | --- | --- |
| Backend full suite | **226 passed**, existing Starlette/httpx warning | `traces/stage1-implementation-20261113-204914/backend/final-high-resolution-tests.txt` |
| Frontend units / production build | **35 passed** / built, existing ECharts bundle advisory | `traces/stage1-implementation-20261113-204914/run/integration/frontend-*-render-time.txt` |
| Actual-browser local protocol peer | **25/25 passed**, no browser errors | `traces/playback-revision/20261113-130403-383977/report.json` |

The browser case publishes a first-half update, interrupts its playing explanation, changes only service charts 2/3 to Q1, retains MG and historical members, and leaves orders chart 1 unchanged. Final values pass independent Olist SQL. The interrupted response played 1,816 of 96,000 received samples; the final response played 14,400 of 14,400 with an empty queue. Input PCM was 1.96 seconds; the recorded flow lasted 4.799808 seconds. Input/output are tones and decisions/transcripts are authored. These figures are not real Qwen recognition, word alignment, human listening or study outcomes.

Original failing browser runs and backend logs remain in the verification index. The existing 20ms timeout test initially failed on Windows timer quantization; its assertion now allows the measured scheduler resolution and verifies the recorded interval, without changing the production timer. Earlier browser runs also retained a Windows teardown callback warning; the final browser run was clean. No service is left running by these temporary checks. Source originals and hashes are preserved under `traces/stage1-implementation-20261113-204914/`.

## Current delivery — audio lifecycle, execution receipts and one application entry

The current application is **http://127.0.0.1:8066/**. `start.ps1` builds the current frontend and `python -m backend` serves `frontend/dist`; `serve_studio.py` calls the same launcher. Development `/api` and `/ws` also target 8066. New application sessions are in `traces/studio/`. Older build snapshots and records remain untouched.

- Fixed four reproduced audio problems: reply end arriving during AudioContext readiness; old chunks returning after Stop; paused microphone samples entering the next segment; and a UI-timer-only recording cap. PTT now stops at exactly 160,000 captured samples. Pause flushes the legitimate tail; playback completion and interruption are recorded separately from provider completion.
- Actual tool receipts now reach the UI with stable chart numbers and committed revision. Prepared, confirmation-required, failed and committed actions remain distinct. Tool-only replies no longer create empty assistant bubbles. Manual edits and model calls use the same execution feedback.
- Final backend **217 passed** and frontend **25 passed**, build successful. Four assigned business tasks passed all ten browser checks, including unified reports and 4K/scaled layouts. Both native voice conditions passed with local scripted decisions. Complete offline English speech passed the one-shot browser driver (8.055-second utterance; 8.280-second input stream).
- Added a browser playback/revision check: first-half service charts, actual assistant playback, intervening first-quarter revision, interrupted old audio, unchanged orders chart, independently verified new values and completed new playback. Authored transcription and test tones remain explicitly local evidence.

Evidence and exact current-source fingerprints: `traces/integration-fix-20261113/verification-index.json`. Original audio reproductions and the first interruption-run Windows teardown warning are retained. The current 8066 service was confirmed idle and exported before replacing it; no working user session was reset.

The user then identified the existing DuplexVisEval/VerbalVis configuration. Both contain `DASHSCOPE_API_KEY`. One authorized real attempt (`traces/live-browser/20261113-120939-580704`) returned **HTTP 401 at handshake**, with **zero uploaded PCM/JPEG, zero tool commits and zero output audio**. Inspection showed that the process environment had overridden the explicitly selected file. File credentials now take precedence; a declared blank file stays disabled. Eight focused tests cover both names, precedence and integration. The harness also preserves the original rejection instead of masking it with a closed-browser screenshot error. No real retry was made.

**Still unverified:** endpoint acceptance with the corrected file selection, recognition, model semantics and updated-image inspection. Human listening, interpretation, repair coding, task difficulty and method benefit remain pending. Live backchannel classification is not implemented. At the user's request, the idle main app and old review processes were stopped after their records were exported. Restart with `start.ps1 -EnvFile C:\DuplexVisEval\.env.local`; startup does not open a model connection.

## Earlier delivery — integrated model-ready application

The current frontend/backend entry is **http://127.0.0.1:8066/** (`scripts/serve_studio.py`), serving `traces/live-build-20261113/frontend-dist` with new session records under `traces/studio-live-20261113`. It loads this project's local env, or an explicitly supplied `--env-file`; old review services remain model-disabled and unchanged. Opening the app does not call a model.

- Screenshot composition now uses the actual rendered canvases synchronously, with one exact revision/view/member-selection reference. Category highlight changes wait for their rendering. A stale render callback cannot mark a newer revision ready.
- The interface distinguishes model-disabled review, missing configuration and a configured connection. Images have honest captured/queued/sent receipts linked to their original frame and selection; an empty canvas clears the old cached image. A late receipt cannot label a changed selection as sent.
- Real transport and handshake failures close provider resources, the Workspace voice timer and browser microphone consistently. There is no reconnect, fallback or automatic retry.
- Unified trial reports now record actual image-delivery counts and PCM durations separately from task time and pending human assessments.
- A one-attempt real verification driver is prepared: offline English SAPI input through the production PTT browser pipeline, under ten seconds of input and a 55-second total deadline. `--run-real` is explicit; default execution does not read credentials. The same driver has been verified against a local native-protocol peer.

### This delivery's checks

| Check | Actual result | Evidence |
| --- | --- | --- |
| Full backend suite | **214 passed**, existing Starlette/httpx warning | `traces/live-build-20261113/python-tests.txt` |
| Frontend units / build | **20 passed** / built, existing ECharts advisory | Same directory, `frontend-tests.txt`, `frontend-build.txt` |
| Current-build assigned voice protocol | **2/2 passed**, direct and bound_revision | `traces/assigned-voice/20261113-112728-428837/report.json` |
| Selection, screenshot and desktop UI | **4 checks passed**, actual mark selection and rapid view changes; 1920/2560/3840 widths; no JS errors | `traces/live-alignment-20261113/visual-browser/20261113-112858/report.json` |
| Offline spoken-input driver | **12 checks passed**, 8.055-second complete spoken request, 8.264 seconds sent PCM, 9.156-second local attempt | `traces/live-harness-local/20261113-112736-193794/report.json` |

The user authorized an API test in this turn, but `C:\CoVisStudio\.env.local` still contains no nonempty `QWEN_API_KEY`, and no environment override supplies one. The exact alternative env path has been requested without requesting the secret itself. **No real API attempt was made.** The prepared driver is PTT and does not validate overlapping speech. Image-buffer delivery is not proof of inspection of the modified chart before a reply. All human semantic/listening and participant results remain pending. Acceptance index: `traces/live-build-20261113/verification-index.json`.

## Current delivery — archived evidence, draft coding and assigned voice verification

Review at **http://127.0.0.1:8065/** with `scripts/serve_study_review.py`. This isolated service has an explicitly empty key and disabled remote endpoints. It includes the earlier frozen matched records and local assigned-voice traces, with new sessions in `traces/study-review-20261113`. The previous services remain running. The temporary 8063 review process was retained after automatic review rejected its stop operation; the final service uses a separate port.

- Experiment records now open the exact selected attempt: public task, submitted response, event indices, technical report, committed versions, transcript and available WAV/JPEG evidence. New exports snapshot the public task brief; older records explicitly use frozen-material lookup. Viewing an archive does not reset the active session, canvas or timer.
- Reviewers can append labelled coding drafts with measured event ranges and reasons, distinguishing repair, exploration, deliberate intent change and uncertainty. Original `session.json`, `events.jsonl` and automatic scores remain byte-for-byte unchanged. Drafts appear separately in JSON and as counts/save times in CSV; human outcomes remain pending/null.
- Selecting a `tool_committed`, Undo or Restore event now displays that publication's revision, including the ordinary case where `node_created` is recorded just afterwards. Other event selections retain chronological snapshot behavior, including old-image references.
- The assigned native-voice verification runs the same `exp_01_a` under direct (slot 1) and bound_revision (slot 5). Both use browser microphone PCM, JPEG input, the production realtime adapter against a local scripted peer, real Olist tools, actual chart rendering, WebAudio callbacks and unified scoring. Direct follows history → save/apply set; bound follows history → preview/apply. Only current views 2 and 3 change, with current MG scope retained.

### Actual checks in this delivery

| Check | Result | Record |
| --- | --- | --- |
| Full backend suite | **206 passed**; existing Starlette/httpx deprecation warning | `traces/study-review-build-20261113/python-tests.txt` |
| Frontend units / build | **18 passed** / built; existing ECharts size advisory | Same directory, `frontend-tests.txt`, `frontend-build.txt` |
| Archived review browser workflow | **8 checks passed**, no JavaScript errors; 1920/2560/3840 CSS widths inspected | `browser/20261113-181538/report.json` |
| Archived media in the browser | Both WAVs loaded and playback progressed; actual JPEG and two transcripts displayed; active workspace unchanged | `browser-media/20261113-181731/report.json` |
| Assigned native voice paths | **2/2 passed**, input 1.352 / 1.256 seconds; connection 1.375 / 1.265 seconds | `traces/assigned-voice/20261113-101324-523919/report.json` |
| Existing archived evidence | Five earlier trial packets opened with original hashes and scores unchanged | `traces/review-packet-checks-20261113/actual-archives.json` |
| Unified offline export | 11 authored attempts, 13 missing assignments, one draft, pending human review | `traces/experiment-exports/20261113-101744-881167/` |

Acceptance index: `traces/study-review-build-20261113/verification-index.json`. The initial browser-harness failure (Finish drawer left open before clicking Experiment) is preserved; the corrected harness closes the drawer explicitly. A Windows Proactor 10054 callback after the voice assertions/browser close remains recorded and unsuppressed in the voice run log.

**Evidence boundaries:** zero real API calls and no participant collection. Voice input/output are test tones with scripted transcription and decisions. Uploaded JPEGs establish initial visual delivery; this run does not establish that the model inspected the modified chart before replying. Human listening, semantic accuracy, repair adjudication, matched human difficulty and method benefit remain unverified. Draft coding is an entry point for that work, not its completion.

## Current delivery — matched experiments, assignment and unified reporting

Review at **http://127.0.0.1:8062/** using `scripts/serve_experiment_review.py`. The independent service reads real Olist, uses an explicitly empty API key and leaves 8050/8060/8061 unchanged. Frontend: `traces/experiment-build-20261113/frontend-dist`; final session records: `traces/experiment-review-final-20261113`.

- Eight `exp_*` materials provide A/B versions of each of the four business families. Original `biz_*` and `rev_*` cases remain intact. Within each pair, chart/member counts, history depth, required targets/fields, prompt length and cohort overlap match. Real comparison sample volumes differ by about 1.16–1.30; minimum valid review denominator is 49. These are objective matching checks, not human difficulty equivalence.
- `docs/experiment_allocations.json` and `.csv` contain the retained 30-slot plan: four distinct families per participant, two direct and two bound_revision, 120 assignments total. A 16-slot Williams-order × condition-order × variant-pattern cycle is exactly balanced. Thirty slots yield 60 tasks per condition, with joint cells 1–2 rather than falsely reporting perfect balance. Public task manifest is `docs/experiment_manifest.json`.
- Explicit Prepare → Begin → Finish/Timeout/Abandon is wired through frontend and server. Assignment fixes task/version/condition. Preparation hides chart evidence; timed editing begins on Begin. The 480-second server deadline ends the attempt. Finished charts remain inspectable and read-only. Starting another task archives an unfinished attempt, and next-task selection is explicit. The 60-second voice budget is unchanged.
- Unified trial reports retain assignment identity, actual start/end, first complete-correct publication, every relevant commit, actual tools, history/evidence selections, card exposures/opens/confirmations, audio and input events. Partial correct edits are distinct from full completion. Setup and later review do not count as timed task work. Repair and understanding are never inferred from event counts.
- Chart correctness, complete/current four-field responses and human interpretation are separate. Missing or stale answers yield submitted_incomplete even with correct charts. Human fields remain pending/null. JSON/CSV exports preserve all attempts, failures, timeouts, abandonment, explicit missing tasks and latest-attempt selection rather than best-score selection. Local authored and participant records are separate strata; paired summaries are descriptive only.

### Actual checks

| Check | Result | Record |
| --- | --- | --- |
| Full backend suite | **186 passed**, one existing Starlette/httpx deprecation warning | `traces/experiment-build-20261113/python-tests.txt` |
| Frontend units / build | **15 passed** / built; existing ECharts size advisory | `traces/experiment-build-20261113/frontend-tests.txt`, `frontend-build.txt` |
| Matched real-Olist reference paths | **16/16 passed** (8 materials × 2 conditions) | `traces/matched-task-runs/20261113-052833-913169/summary.json` |
| Actual wrong-tool counterexamples | **16/16 detected** | Same matched-task record |
| Pair matching | **4/4 objective pairs passed** | Same directory, `matching-audit.json` |
| Browser assignment and full workflow | **10 checks passed**, including all four assigned tasks, unfinished export and three screen sizes | `traces/experiment-build-20261113/browser/20261113-133432/report.json` |

The browser run contains four completed local-authored trials (two per condition), one abandoned attempt and three explicit missing assignments; it contains no participant evidence. Both bound previews record one start per actual preview. A review caught and removed a duplicate tool-start log during integration. The first browser run stopped on a test locator for the Rank by control; explicit accessible labels fixed it. Its original record remains under `browser/20261113-133041`, and its unfinished attempt was archived before stopping that isolated test server. Final records use a separate directory rather than rewriting the earlier development schema/results.

Combined evidence and source hashes: `traces/experiment-build-20261113/verification-index.json`. Unified example JSON/CSV: `unified-report.json` and `unified-report.csv` in the same directory. No real API call, human review or participant experiment was run. Human difficulty, study effectiveness and continuous eight-minute voice use remain unverified. See `docs/EXPERIMENT_PROTOCOL.md` and `docs/MATCHED_TASKS.md` for the complete method and limits.

## Previous delivery — strong saved-set baseline and business tasks

Review on **http://127.0.0.1:8061/** with `scripts/serve_business_review.py`. This isolated service uses real Olist and an explicitly empty API key. Existing 8050/8060 services and their records are unchanged. The new frontend is staged under `traces/business-build-20261113/frontend-dist`.

- All three configurations now expose `save_category_set`, `list_category_sets`, `apply_category_set`. Current or historical full/subset members can be named and reused without copying IDs. A set is immutable within the session, preserves provenance and exports with the session. Applying it uses the normal private-candidate/commit path on exact current targets; current region, dates, status and metric remain unless explicitly patched. The direct baseline has the same UI and model tools.
- Revision observations separate generated, displayed, opened, confirmation-clicked, successfully user-applied and model-applied cards. Real DOM intersection, visible-page state and drawer coverage control intervals. Reports show actual counts; no exposure threshold is interpreted as reading or understanding.
- The primary task picker contains four business goals plus the starter: SP priorities evaluated in MG, MG-specific priorities requiring release/reranking, a stable seasonal cohort, and revenue within an unchanged cohort. Eighteen frozen diagnostics remain separate. Public goals enter model context; evaluator answers do not.
- Participants can save conclusion, rationale, object origin and calculation scope. Technical completion is separate from human interpretation. After subsequent chart changes the old answer is retained and marked stale until reviewed/resaved. Pending interpretation and listening are unchanged.
- Export v3 includes sets, actual observations, answers/revision provenance and technical report. Trace payloads now preserve event-time values instead of changing when an in-memory proposal later commits.

### Verification in this delivery

| Check | Actual result | Record |
| --- | --- | --- |
| Full backend suite | **148 passed**, existing Starlette/httpx deprecation warning | `traces/business-build-20261113/python-tests.txt` |
| Frontend units / staged build | **13 passed** / built; existing ECharts chunk-size advisory | `traces/business-build-20261113/frontend-tests.txt`, `frontend-build.txt` |
| Real Olist business reference paths | **4/4 passed** | `traces/business-task-runs/20261113-043840-210333/summary.json` |
| Deliberate wrong cohort/scope/release/period cases | **8/8 detected** | Same business-task record |
| Local model transport + shared saved-set tools | **3/3 conditions passed** through production text adapter and scripted local SSE peer | `traces/business-model-flow/20261113-124018-253871/` |
| Browser UI, observations and 4K/scaled layouts | **10 checks passed**, no page errors/overflow; direct and method business paths technically complete, human interpretation pending | `traces/business-build-20261113/browser/20261113-124856/report.json` |

The first browser run exposed a genuine reload issue: a card could mount before the WebSocket opened, dropping its visible event and later recording an unmatched hidden event. Observation now starts only when the transport is connected. The original failure remains in `browser/20261113-124258` and `server.stderr.log`; `original-observation-records.json` retains its unmatched interval with unknown duration instead of inventing exposure. A separate review found the saved-answer freshness issue described above; real-Olist and browser tests cover edit-after-answer and resave. Final browser records contain six closed visibility intervals and no unmatched hidden event. A Windows Proactor 10054 callback appeared after browser close; it remains in `server-final.stderr.log` and was not suppressed. The final service bootstrap remained healthy. Full acceptance index with source hashes: `traces/business-build-20261113/verification-index.json`.

No real API calls or participant experiments ran. Synthetic provider decisions are protocol evidence only. The four business tasks still need matched formal-study versions and frozen allocation; the planned eight-minute task has not changed the sixty-second development voice budget. Actual listening, interpretation, repair coding and method benefit remain pending. Nothing here establishes that the full method beats the stronger saved-set baseline.

## Prior research-value review and scoring correction — 2026-11-13

Two reviewer agents audited the mechanism and experimental fairness. Recommendations are appended to section ten of `docs/RESEARCH_PLAN.md`: distinguish reference selection from member transfer, challenge the method with a simple reusable-set alternative, measure total interaction cost, and distinguish generated previews from actual user review. These recommendations do not claim a new baseline or user-study protocol has already been implemented.

The audit reproduced and corrected two ordinary scoring errors in `backend/study.py`:

- Requested category membership used ordered-list equality, unfairly rejecting a correct set returned in another order. Target sets now use membership equality; untouched views must still stay unchanged.
- A valid two-step edit of one chart was checked against the entire final target after its first step. Process scoring now checks fields actually changed and independently recomputes numeric values for the intermediate source; final scoring still checks the complete task. Illegal changes to retained regions and scope-external edits still fail.

Actual validation: **37 revision-study tests and 33 API/workspace regression tests passed** (the existing Starlette/httpx warning remains). The same real Olist artifacts were rescored before and after: correct category reordering is accepted, and both legal member/metric edit orders pass without being labeled recovered errors. Evidence, original failures and reproduction scripts: `traces/research-review-20261113/summary.json`; API regression: `api-regression.txt` in the same directory. No real model API or participant study ran. Existing services were not restarted by this review.

The 60-second development voice budget and planned 8-minute participant task limit remain an unresolved study-configuration mismatch. Formal collection needs a separately frozen, equal session budget; this review did not change paid-call limits. Current 216-run/30-participant figures remain proposals, not performed experiments.

## Current delivery: evidence-linked revision

Review at **http://127.0.0.1:8060/** using `scripts/serve_revision_review.py`. The review process uses real Olist, a blank API key and disabled remote endpoints. The older 8050 process remains running. [Research plan](docs/RESEARCH_PLAN.md), [study protocol](docs/STUDY_PROTOCOL.md) and [acceptance index](docs/ACCEPTANCE.md) define this version.

### Implemented in this revision

- Historical chart evidence and current edit targets are separately selectable. Journey supports category subsets; selecting historical evidence never restores old filters.
- `read_history`, `preview_revision` and `apply_revision` join the existing six chart tools. Historical members bind to current sources; only explicitly requested fields change. Fixed members can be released for reranking.
- The actual preview shows changed and retained conditions, source version and target views. Model self-approval is blocked when a question remains unresolved. An explicit user approval publishes the candidate.
- New speech supersedes an old proposal. Its card remains in conversation context so a spoken clarification can lead to a new proposal. A current request referencing an invalid ID receives a failure receipt; obsolete requests cannot publish or continue old output. Closing voice updates the card's visible status.
- Committed Journey nodes retain evidence and actual change cards. Undo/Restore preserve history and are included in outcome trajectories. Frontend telemetry uses distinct event names to avoid duplicate research counts.
- Three configurations: strong direct-edit baseline, evidence-linked method, preview-without-binding ablation. They receive the same raw history/tools; no evaluator answer enters model context. Text/PTT/live are input modes, not the primary independent variable.
- Six development and twelve held-out cases with real Olist initial histories. Independent raw-table SQL checks source, members, values and rate denominators. Final completion, first publication, subsequent errors and recovery are separate fields. Human interpretation and spoken-semantic fields remain pending/null.
- All-English user interface, verified at 1920×1080 CSS/2×, 2560×1440 CSS/1.5× and native 3840×2160. Charts and conversation remain primary; study/review controls are secondary drawers.

### Actual checks in this delivery

| Check | Result | Evidence |
| --- | --- | --- |
| Full Python suite | **101 passed**, one existing deprecation warning | `traces/revision-build-20261113/python-tests.txt` |
| Frontend units / staged build | **10 passed** / built | `traces/revision-build-20261113/frontend-tests.txt`, `frontend-build.txt` |
| Real browser workflow | **12 checks passed**, no page errors or horizontal overflow | `traces/revision-build-20261113/browser/20261113-121215/report.json` |
| Real Olist authored reference paths | **18/18 passed** | `traces/revision-study-20261113/summary.json` |
| Injected scorer counterexamples | **6/6 distinguished** | Same summary, individual counterexample records |
| Local native voice revision protocol | Four cases: complete, user approval, spoken confirmation, supersession | `traces/revision-model-20261113/` |
| Actual browser PCM/JPEG/tool/render/playback | Passed with current staged frontend and local scripted peer | `traces/browser-voice/20261113-041316-699112/report.json` |

These are local execution results, not real model success rates. The browser voice run uses test tones and a scripted transcript. A Windows Proactor connection-close callback warning occurred after the assertions; full output is retained. The ECharts size advisory and Starlette/httpx deprecation were not suppressed. Original failed test assertions remain in the evidence directories.

### Still requiring research evidence

- **No real API calls in this delivery.** The exact hosted model's tool behavior, visual understanding, recognition and real spoken responses remain unverified for this mechanism.
- The planned 216 timing/configuration trials and 30-participant comparison have not been run. The current local scripts exercise authored tool paths, native-protocol fixtures and UI; they do not constitute an automatic real-model timing campaign or statistical results.
- Human listening, semantic review, repair coding and participant outcomes remain pending. First correct partial commit is not first complete task success. A restored incomplete state is not automatically a new user misunderstanding.
- Live mode still treats every detected utterance as a replacement; acknowledgement classification/resumption is absent. No claim of semantic action before an utterance ends or full-duplex superiority.
- General research contribution remains a hypothesis: the new method must beat the strong baseline on correctness/repair effort under the declared controls. DataTone/CLEO/VoCa are related work, not faithfully reimplemented benchmark systems.

## Earlier build (retained historical record)

The remaining entries describe the preceding build. They are not substitutes for the current results above.

### Implemented

- Independent FastAPI + Vue/ECharts application at `C:\CoVisStudio`, port8050. Old projects and credentials unchanged.
- All-English user canvas, collaboration pane, explicit starters, chart/member selection, six chart forms, inspector, multi-chart edits, layout/order controls, Undo and version restore.
- Journey nodes contain committed snapshots, observable source/style changes, intent/reference and bounded event windows. Nodes are not fabricated reasoning. Restore creates a new version.
- Real Olist orders, item revenue, canonical review risk/denominators and mean delivery duration. Category/month/state queries. Fixed members and dynamic rankings are explicit.
- Six shared tools, private candidate preparation and atomic commit. Superseded requests cannot install candidate results. No handwritten Numeric_Value input.
- Real Qwen HTTP/SSE text adapter and native realtime adapter with PCM, image append, tool receipts and audio. Three modes: text, manually submitted speech, and VAD-ended continuous voice.
- Actual rendered chart images preserve canvas geometry and selections. Reference/image bundles carry one visible revision. Browser render and playback callbacks are recorded separately from backend/provider completion.
- 12 task briefs in six independent/linked pairs; task checks, pending human review, notes, recordings and downloadable session data. Outcome report is invalidated after later edits/restores.
- Blank local key configuration. No automatic provider connection, reconnect, retry or fallback model. Explicit voice sessions have a60-second budget; manual recordings max10seconds.

## This build's actual checks

| Verification | Result | Evidence |
| --- | --- | --- |
| Full Python regression | **49 passed** | `traces/final-python-tests.txt` |
| Frontend unit checks | **6 passed** | `traces/final-frontend-tests.txt` |
| Production frontend build | Passed | `traces/final-frontend-build.txt` |
| Real UI manual workflow | **8 acceptance checks passed** | `traces/browser-verification/report.json` |
| Actual browser voice pipeline with local peer | Passed twice, latest frozen build passed | `traces/browser-voice/20261112-191857-244152/report.json` |
| Authored task/tool feasibility | **36/36 paths**, unfinished counterexample fails correctly | `traces/study-verification/summary.json` |

Python checks include independent raw-table SQL, grain/review tests, transactional edits, history/undo, old-report invalidation, mode recording, malformed tool JSON accounting, local HTTP/WebSocket transport and cross-layer real Olist execution. One Starlette/httpx deprecation warning remains. The frontend build has an ECharts chunk-size advisory; both are reported rather than suppressed.

The manual browser workflow exercises multi-selection, changed-region preservation, node before/after inspection, Undo, two-/three-column layout, task choice, outcome checks, review notes and export. Screenshots cover1920×1080 at2×,2560×1440 at1.5×, and native3840×2160; no horizontal overflow or JavaScript errors. The initial test-selector mismatch is preserved in `traces/browser-verification/initial-selector-failure.txt`; it was a test locator issue, not a failed edit.

The browser voice check uses a test microphone WAV and synthetic assistant tone with a scripted local Qwen peer. It runs the real frontend, PCM capture, actual chart JPEG, native protocol, real Olist tool, commit/render and WebAudio callbacks. Only selected chart1 changes color; other charts and source/data stay unchanged. The isolated8052 service and all test connections close at completion. This is protocol/UI evidence, not real-model comprehension or human listening.

Cross-layer interruption test blocks a real prepared half-year candidate, receives a quarter revision, and confirms only the new quarter is published. Original candidate/result suppression is visible in `traces/provider-integration/`.

The36 authored trajectories repeat12 tool tasks under three labels. They do not exercise speech and do not compare mode performance. All human review remains pending. Real-data inspection found SP/RJ2017 top-three members equal; tasks now use MG to make preserve-versus-rerank outcomes distinguishable.

## Remaining evidence and scope

- **No paid API used in this build.** Remote session-flag acceptance, actual recognition, model tool behavior, microphone echo and human listening need a separately authorized real run.
- Live voice replaces an unfinished response on each new utterance. Backchannel classification/resumption is not implemented. Text and realtime use different model IDs; comparison is initially between systems.
- Native image input follows real audio. Queued/manual image input does not prove visual verification of every newly committed chart before spoken follow-up.
- Human semantic and rework review are pending. These12 cases are development materials, not a validated benchmark or completed user study.
- The report checks required source/data outcomes. It does not automatically infer a user's changing intention, detect false spoken completion, or estimate cognitive burden.
- One local process and one active workspace. Session archives are saved to disk; the main canvas starts empty after server restart, rather than silently resuming a participant trial.
