# Participant business tasks

Material version: `covis-business-0.1`, 2026-11-13. Four bounded tasks replace the precise revision instructions in the primary participant picker. The eighteen `rev_*` cases retain their IDs and frozen definitions in the diagnostic picker. These materials and authored tool paths are not participant results.

Each task supplies a business objective, required analytical outcomes and a free conclusion. Participants choose their wording, references and interaction sequence. No prompt requires an artificial error, prescribed interruption or click sequence. The required outcomes define a comparable data result; they do not prescribe the participant's service recommendation. A participant may conclude that available evidence is insufficient, with a rationale.

## Four tasks

| ID | Business decision | Required analytical result | Free interpretation |
| --- | --- | --- | --- |
| `biz_01_sp_priorities_mg` | Assess service for headquarters' SP priority categories in MG | Use the earliest SP 2017 cohort in current MG 2017 review and delivery views; keep the current MG volume view unchanged | Select a service issue to investigate, or explain why no clear priority is justified |
| `biz_02_mg_local_priorities` | Change from headquarters monitoring to MG local operating priorities | Release the inherited fixed set; all three MG 2017 views use dynamic top three by delivered-order volume, retaining measures | Explain why the local objective needs a different selection rule and recommend a supported investigation |
| `biz_03_seasonal_same_cohort` | Compare service across periods without mixing a changed category cohort into the comparison | Use January–March 2017 SP leaders in the October–December SP review and delivery views; keep Q4 volume unchanged and inspect Q1 saved service evidence | Describe a service change or uncertainty and a follow-up question, without claiming seasonal causation |
| `biz_04_stable_metric_control` | Bring financial scale into an existing SP service discussion | Change only the volume view to item revenue excluding freight; keep fixed cohort, SP, 2017, delivered orders and both service views | Explain whether revenue changes the operating priority; distinguish revenue from profit and orders |

The full English participant wording lives in `backend/business_tasks.py` and is returned by `tasks()` / `task_brief()`. No standard member IDs, expected source dictionaries or private resolution answers appear in these public briefs. The business task IDs remain separate from all diagnostic and legacy IDs. There are no matched variants in this material version; counterbalancing is a study-design plan, not a claim of implemented matching.

## Starting evidence and legitimate execution

`setup_operations(task_id, data)` builds the three real-query views for every authored phase using ordinary `create_chart` and `edit_charts` operations. Each complete phase occupies three revisions. Revision 3 contains the first complete dashboard; revision 6 contains the second when present. Initial participant state is captured only after setup completes. This is labeled authored history, never a model-generated analysis trajectory.

For the regional task, the first complete history is SP and the current state is MG, each ranked within its own 2017 delivered orders. For the release task, current MG measures deliberately retain the earlier fixed SP cohort. The seasonal task has Q1 and Q4 SP histories, with each period initially using its own leading categories. The stable control has one SP cohort and requires no historical transfer. Real Olist checks verify that the regional and seasonal earlier/current sets differ; the task wording still supplies no member list.

All conditions can inspect the same history, query the same data, use ordinary edits and explicitly save/reuse category sets. The simple saved-set facility is shared, including in `direct`; it deterministically transfers a user/model-selected visible set without selecting the correct evidence on their behalf. It provides a meaningful alternative to manual member transcription. Bound revision adds the explicit historical-source/current-target relationship and change card. No condition receives an evaluator answer. Selecting a set is not approval of an unresolved analytical choice.

## Scoring and participant response

Business cases map privately into the existing phase, target-source, publication and independent raw-table SQL pipeline. They do not create a second execution authority or a duplicate runtime. The original eighteen diagnostic definitions and oracle are retained.

Technical checks require the requested members, region, dates, status, metric and selection rule, plus independently recomputed values and denominators. The release case requires dynamic ranking: a fixed list of the currently correct members does not satisfy release. Unchanged views must stay unchanged. Presentation changes to intended business target views are allowed; no specific color or chart form is a hidden business requirement. Existing diagnostic presentation checks remain unchanged.

Participants submit four free-text fields: `conclusion`, `rationale`, `object_origin` and `calculation_scope`. The last two ask where the compared categories were selected and where/when the values were calculated. Their content is stored verbatim. Blank answers are not synthesized from the final chart, and contradictory explanations are not silently corrected. A submitted response only means all four fields are filled; it is not a correctness result.

| Field | Interpretation |
| --- | --- |
| `technical_completed` | Required final data/condition checks pass |
| `completed` | Compatibility alias for technical completion only |
| `task_response` / `task_response_submitted` | Saved participant statements / all four fields present |
| `interpretation_status` | `pending`; automatic checks do not perform human review |
| `business_conclusion_correct` / `understanding_correct` | `null` pending genuine review; there is no single gold business decision |
| `first_commit_correct`, `all_revision_commits_correct`, `recovered_after_error` | Existing publication-trajectory checks, separate from final completion and interpretation |

Human review checks whether the conclusion follows from the cited evidence, whether object origin and calculation scope are understood, whether uncertainty is acknowledged, and whether unsupported causal claims occur. Multiple business recommendations can be defensible. Interpretation is not inferred from a technical pass or from the assistant's success statement. Explicit reference choices and clarification answers must be recorded when needed; a final matching chart does not prove clarification occurred. Diagnostic ambiguity behavior is unchanged.

Interaction observations are exported separately from technical outcome evaluation. Displayed previews, opened details, evidence selection, set reuse and user decisions describe observed actions. Generated previews do not imply display, and display does not imply reading or understanding. Automatically applying an unambiguous proposal is distinguishable from explicit user approval. Total elapsed time includes selection, inspection, clarification and waiting; overlapping durations must not be added as independent time savings.

## Timing and evidence boundary

Eight minutes is the planned participant-task limit. The current sixty-second voice connection cap is an explicit development resource budget, not that task limit and not an automatically renewable eight-minute voice session. This work does not extend it, make paid calls or authorize a formal live-voice study. Before collection, freeze an equal, funded voice/session budget for all conditions and the handling of any interruption. No completed participant or human-listening result is claimed.

## Local verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_business_tasks.py -q
.\.venv\Scripts\python.exe scripts\verify_business_tasks.py
```

The script saves timestamped `traces/business-task-runs/<timestamp>/` directories with public briefs, complete starting histories, initial/final snapshots, actual tool receipts, events and reports. It exercises all four authored real-Olist paths plus eight deliberate counterexamples: current cohort, wrong region, scope expansion, failed release, fixed correct members instead of a dynamic rule, wrong seasonal cohort, wrong seasonal period and an out-of-scope metric edit. It never calls a model, invents participant responses or approves interpretation. Existing evidence is not overwritten.

These checks establish data/tool/scorer feasibility. They do not measure model understanding, voice behavior, actual participant reading, repair cost or business decision quality.
