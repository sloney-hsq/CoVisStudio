# Matched-task allocation and unified reporting

**Scope update, 2026-11-13:** This document describes the existing assignment/report apparatus. [UNIFIED_RESEARCH_PROTOCOL.md](UNIFIED_RESEARCH_PROTOCOL.md) governs the next study; its assigned-attempt and intent-dependent outcomes are not yet implemented by this older trial aggregator. Stage 1 calibrates new browser events while preserving raw clocks; old archives without calibration remain unaligned. Instrumentation does not change the participant conditions or authorize data collection.

Assignment/report protocol: `covis-experiment-0.1`. Materials protocol: `covis-matched-0.1`. The current materials have four business families with two parallel versions per family (`exp_01_a` through `exp_04_b`). Objective matching and real Olist checks are in [MATCHED_TASKS.md](MATCHED_TASKS.md). Equal structure and comparable data do not establish equal human difficulty.

## Assignment

Each participant receives four trials, one from each family, with two `direct` and two `bound_revision` tasks. The same tools, historical evidence, saved-set reuse and source information are available. The participant does not repeat the same family in both conditions. The assignment never includes a correct category list or private reference resolution.

Sixteen allocation slots cross these independent factors:

- Four Williams family orders: 1–2–4–3, 2–3–1–4, 3–4–2–1, 4–1–3–2.
- Two condition block orders: Direct–Direct–Bound–Bound and Bound–Bound–Direct–Direct.
- Two complementary version sequences: A–B–A–B and B–A–B–A.

Within each complete 16-slot block, every family appears once in every position × condition × version cell. Each ordered pair of different families appears once across the four Williams rows. Task order, condition order and version are crossed, rather than assigning an easier version only to the proposed method. Slots 17–32 repeat the design with distinct trial IDs.

The pre-existing target of 30 participants is retained as the default allocation table, not silently increased. Thirty slots contain one complete block and fourteen slots of the next block. They provide 60 tasks per condition, but joint cells have either one or two observations; this is explicitly reported as a partial, not perfectly balanced, plan. Sixteen and thirty-two slots have exact complete-block balance. Sample adequacy and formal recruitment are research decisions, not proven by the scheduler.

`allocation_for(slot)` returns four immutable trial assignments. Each includes participant slot, ordinal trial ID, family, version, task, assigned condition and 480-second task limit. `allocation_table(count=30)` includes every allocation and a complete 64-cell balance audit, including zero cells in small plans.

## Session and process boundaries

The service places the trial assignment in `session.assignment` and records an explicit `session.evidence_kind` such as `local_authored` or `participant`. Loading starter charts and reading task instructions precede `trial_started`; Begin starts the measured trial. The service supplies actual server `trial_started` and `trial_finished` events. Finish records `reason=completed`; this is a submission action and does not force technical success. Timeout and abandonment have separate reasons. An unfinished session remains running or ready.

Unified reports use the event window from Begin through the terminal event. Setup actions and post-task review actions are not counted as timed work. Historical reference selection and other actual analysis actions belong inside that window. Server elapsed duration uses only server timestamps; browser exposure intervals use only their own browser clock. The first complete-correct publication comes from an independent whole-state check, not from the first locally correct partial edit.

The 480-second task timer is separate from the existing 60-second development voice-session budget. This implementation does not authorize a longer paid connection, remove that limit or claim continuous eight-minute voice use. Hosted-model trials, listening and participant collection remain unperformed.

## Unified trial report

`build_trial_report(session, base_report, events, task_response=None)` has these groups:

| Group | Recorded content |
| --- | --- |
| `identity` | Participant, slot, trial, family, version, assigned condition, session/attempt, materials version and evidence kind |
| `outcome` | Completed deliverables, submitted-incomplete, timeout, abandoned, running or ready; chart correctness, chart submission, current response completeness and interpretation stay separate |
| `timing` | Actual server start/end and elapsed time, task limit, observed successful completion and censoring, first whole-state-correct publication time |
| `process` | Actual requests, tools/failures, selection, saved-set use, publication checks, browser card exposure/opens/confirmation, audio input/output events and playback |
| `task_response` | Verbatim response plus revision freshness from the base report; not a graded conclusion |
| `human_review` | Interpretation, listening, semantic consistency and repair effort remain pending/null |

Audio chunks are not utterances. Generated output audio is not proof of listening. Card visibility is not proof of reading. A tool failure or Undo is not automatically a misunderstanding or repair. History opens, recording boundaries, text focus/submission and inspector opens are recorded separately. Selection events include programmatic clearing and therefore are not automatically a count of deliberate user actions. Counts never manufacture those labels.

`submitted_correct` (also `chart_submitted_correct`) is explicitly the chart-only submission score. `response_complete_current` requires all four response fields tied to the final revision; a stale answer does not qualify. `deliverables_complete` requires technical chart correctness and a current complete response; `submitted_deliverables_complete` additionally requires explicit completed submission. Only the latter gives outcome status `completed`. This checks the presence and freshness of the business deliverable, not whether the recommendation or explanation is correct. Those fields remain pending/null. Timing labels distinguish not started, ongoing, observed chart submission and censored outcomes.

`process.interaction` uses the same underlying recorded observations as the normal report, restricted to the measured window. An exposure still open at Finish has unknown duration; it is not completed by subtracting a server timestamp from a browser timestamp. No arbitrary dwell threshold is used.

## Attempts, missing trials and comparison summaries

Each session ID identifies one attempt. `aggregate_reports` preserves all supplied attempts, including incorrect submissions, timeouts, abandonments and unfinished runs. Per assigned participant/slot/trial, it selects the latest attempt by its Begin timestamp (or preparation timestamp before Begin), never by the best score. Earlier attempts remain in JSON and the CSV with an explicit `selected_latest` flag and attempt index. Actual repeated attempts are not additional participants.

Observed participants have four expected trials. Missing trial rows remain explicit; optionally supplied registrations expose all four missing trials for a person who has not started. Local authored and participant evidence are always separate strata, even if their participant identifiers happen to match.

Participant summaries contain two-task condition totals and descriptive paired differences only when both conditions have their two terminal observations. Missing and running trials do not produce a fabricated paired estimate. Elapsed totals include failures/timeouts/abandonments; they are not successful-only means. Censoring fields remain available for the planned completion-time analysis. These summaries are not hypothesis tests, confidence intervals or evidence of an effect. Formal repeated-measures analysis remains the declared study protocol and requires actual participant data and repair coding.

## Inspect and code the underlying evidence

The Experiment archive view links every attempt to its own task, written response, original event indices, committed versions and available transcript/audio/images. Inspection does not replace the active workspace. Reviewer-labelled drafts append separately and link proposed repair/exploration/intent-change labels to measured event ranges. See [REVIEW_CODING.md](REVIEW_CODING.md).

Draft history appears separately in the unified JSON, with counts and latest save time in CSV. It does not overwrite automatic outcomes or fill pending human interpretation, repair or listening metrics. A local authored draft is still local authored evidence. The current review service includes the earlier frozen trial directory explicitly rather than copying or migrating those original records.

## Reproduce local reports

```powershell
cd C:\CoVisStudio
.\.venv\Scripts\python.exe -m pytest tests/test_experiment.py -q
.\.venv\Scripts\python.exe scripts/export_experiment_report.py --trace-dir traces/experiment-review-20261113
```

The exporter reads immediate child session archives, writes all-attempt CSV, unified JSON and the allocation table to a new timestamped directory under `traces/experiment-exports/`, and never opens a model connection. It does not change the archived evidence or invent scores for sessions without a trial report.
