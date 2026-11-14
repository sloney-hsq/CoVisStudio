# Evidence-bound revision study protocol

**Status update, 2026-11-13:** The next study design is governed by [UNIFIED_RESEARCH_PROTOCOL.md](UNIFIED_RESEARCH_PROTOCOL.md). This file records the earlier apparatus and diagnostic materials, including its historical ablation. It must not be used to claim that current runtime conditions already meet the new B0/B2 evidence and execution parity requirements.

Diagnostic protocol: `covis-revision-0.1`, frozen on 2026-11-13. Original business materials remain `covis-business-0.1`. Assigned experiments now use the eight parallel materials `covis-matched-0.1` and `covis-experiment-0.1` allocation/reporting; see [the assignment protocol](EXPERIMENT_PROTOCOL.md) and [matching audit design](MATCHED_TASKS.md). The four original briefs and diagnostic definitions remain unchanged. This is an executable apparatus, not model or participant results. The preceding three-input-mode study is superseded.

## Research question

Does explicitly separating historical evidence references from current edit scope reduce mistaken objects, loss of still-valid conditions, and additional repair effort during collaborative dashboard revision?

The mechanism identifies members from a committed historical chart, applies requested changes to specified current charts, exposes a preview, and asks for a choice when the reference is unresolved. A historical reference does not restore its old region, dates or metric.

## Conditions

| ID | Implementation | Role |
| --- | --- | --- |
| `direct` | Full current/history information, strong preservation instructions, ordinary edits and shared saved-set reuse; model/user chooses intended evidence and members | Main baseline |
| `bound_revision` | Explicit reference, exact historical member binding, current scope patch, preview and needed clarification | Proposed mechanism |
| `unbound_preview` | Same preview UI and inspectable history, without automatic historical-member binding into the edit | Technical ablation |

Conditions use the same model version, realtime audio, screenshots, data tools, cancellation and commit permissions. Full duplex is common infrastructure. This comparison does not establish that realtime voice is superior to text or that the mechanism requires full duplex. Record actual overlap: execution overlap is not automatically an audible speech interruption.

Simple category-set saving and reuse is available in every condition, including direct. The user/model selects a real visible historical/current cohort; deterministic reuse avoids requiring manual transcription. It does not provide the correct reference or evaluator answer. Bound revision's complete change card and evidence/current-scope relationship are therefore compared against a baseline that can already reuse sets. There is no fourth participant condition and no claim of faithfully reproducing an earlier research system.

The shared tools are `save_category_set`, `list_category_sets` and `apply_category_set`. A saved set contains a name, actual members and the chosen evidence's revision/view identity and source. Applying it transfers those members to explicitly chosen current views; it does not restore historical filters. `category_set_saved` records saving and actor; application is an ordinary `tool_committed` receipt with `tool=apply_category_set` and `result.category_set` provenance.

Record assigned condition and actual mechanism use separately, including bound previews, unbound previews, ordinary edits, saved-set reuse and applying actor. A generated preview is not evidence that the browser displayed it; an actual display or open event is not evidence that a person read or understood it. Unambiguous instructions may be applied without a separate user decision. An unresolved choice remains pending until an explicit user choice; the system must not auto-approve it. These distinctions and all selection/inspection cost belong in the interaction record.

Browser `revision_card_visible` / `revision_card_hidden` delimit actual displayed intervals by `display_id`, `proposal_id`, `surface` (summary/detail) and browser `client_ms`. `revision_card_opened` records opening detail. `revision_confirmation_clicked` records the button action; `revision_card_revision_requested` records a requested change. Only the server's successful `revision_confirmed` with committed revision and `channel=apply_button` counts as successful explicit button confirmation. `revision_applied.actor` distinguishes user/model application. A spoken answer followed by a new model proposal is not relabeled as a button-confirmed proposal. Browser and server clocks remain separate; do not subtract them to fabricate review latency.

## Cases and split

`backend.study.REVISION_CASES` defines six development and twelve held-out configurations. `docs/revision_cases.json` is the frozen evaluator-private export. They cover preservation, explicit release, local scope, genuine reference ambiguity and stable controls. Held-out changes include historical time windows, subsets, ranking measure, middle historical versions, independent current regions and target subsets. Cases share families: they are not eighteen independent research situations.

`tasks()` returns a starter plus four English business-goal participant tasks; `diagnostic_tasks()` returns the eighteen frozen technical briefs separately. `task_brief(id)` supports both groups and legacy IDs. Public briefs contain no expected source, reference-resolution answer or private target set. `setup_operations(task_id, data)` constructs authored initial history using real query-backed commits. Store `initial` after all setup. Complete phases occupy three revisions: first historical dashboard is revision 3; second is revision 6.

[BUSINESS_TASKS.md](BUSINESS_TASKS.md) defines four bounded participant goals: SP priorities assessed using MG service measures while preserving local volume; MG local priorities requiring release and reranking; seasonal service comparison for the same earlier cohort; and a stable local revenue change. Each combines mandatory data outcomes with a free business conclusion and rationale. Participants choose their expression and workflow. They are not instructed to cause an error or follow clicks. The seasonal interpretation can use saved earlier evidence; its human quality is not inferred merely because current charts meet the technical requirements. No additional matched versions are implemented in this material version.

`evidence_for_case`, `revision_targets` and `evaluate_revision` are evaluator-private. Never include them in provider instructions or call them to supply model arguments. Reference trajectories are authored operations, not successful model trials.

Freeze cases and prompts before held-out model trials. Local oracle checks validate the apparatus, not model generalization. Changes prompted by model failures require a new protocol version and transparent treatment of affected cases.

## Planned trials

Technical study: 12 held-out configurations × 2 timing conditions × 3 conditions × 3 independent runs = 216 planned trials. Timing is before/after the prior operation's public commit. Fixed recorded scripts support this diagnostic. Retain invalid timing and failures without moving input or forcing commits to manufacture valid trials. Local scripted verification is separate.

User study: target 30 participants, two conditions (`direct`, `bound_revision`), four tasks per participant, two per condition. Allocate AB and BA equally and balance matched task versions. Thirty is a recruitment target, not a power guarantee. Estimate precision using main outcomes and report uncertainty. Participants receive goals and constraints, not prescribed errors or millisecond interruption scripts. Obtain institution-appropriate review and informed consent before collection.

The original four briefs remain development materials. Eight new parallel forms and the 30-slot assignment are now implemented and saved in `experiment_manifest.json`, `experiment_allocations.json` and `.csv`. Each participant receives one version of each family, two tasks per condition; 16-slot blocks have exact joint balance while the 30-slot prefix honestly reports its residual imbalance. The server implements the eight-minute task deadline. It remains separate from the sixty-second voice-connection budget, which is unchanged; do not describe this as continuous eight-minute live voice. Human difficulty calibration and formal data collection remain pending.

## Outcomes and independent oracle

Primary outcomes: final object/condition correctness and additional repair effort. Report final correctness alongside publication-trajectory correctness. Secondary outcomes: clarification, completion time, wrong blocking, reference correction, independently reviewed speech consistency.

`backend.oracle` queries raw Olist tables through independent DuckDB SQL and never calls `OlistData.query`. It checks exact members, source fields, values and denominators. It uses order-category distinct counts; latest reviews by creation date and ID; low-score count (1–2) over valid reviewed orders (1–5); nonnegative valid delivery duration; item revenue excluding freight. Dates are inclusive start / exclusive end. Unaffected views remain unchanged.

| Report field | Meaning |
| --- | --- |
| `completed` | Final chart membership, source, untouched conditions and independent numeric checks pass; ambiguous references require documented resolution. For business tasks this is a technical-completion compatibility alias, not an approved business conclusion |
| `technical_completed` | Business-task final data/condition correctness, separate from interpretation |
| `task_response` / `task_response_submitted` | Participant's saved conclusion, rationale, object origin and calculation scope / all four fields present; presence does not imply correctness |
| `task_response_status` / `task_response_current` | none, incomplete, stale or current / complete response tied to the final chart revision. Earlier text is preserved after edits and must be reviewed/resaved; freshness is not semantic correctness |
| `interpretation_status` | Business interpretation remains pending genuine human review |
| `business_conclusion_correct` / `understanding_correct` | Null until human review; no single gold business recommendation is manufactured |
| `first_commit_correct` | First post-request publication's changed views obey the revision; null with no publication |
| `all_revision_commits_correct` | All effective post-request publications obey that contract; null with none |
| `recovered_after_error` | A wrong publication occurred and final checks pass |
| `commit_assessments` | Changed views, event type, failed checks and revision for each publication |
| `pre_revision_commits_not_scored` | Publications before revision acceptance, not retroactively judged against later intent |
| `unchanged_restores_not_scored` | Undo/Restore events producing no view change |
| `review_status` | Pending until genuine human review; fixtures never approve it |

**A correct first partial commit is not a successful first complete revision.** Intermediate scoring checks the source fields actually changed in the requested views against the intended values, and checks data against independent SQL for that intermediate source. Untouched fields that still need a later edit are not prematurely judged as final failures. This permits both multi-view and within-view stepwise edits; scope-external changes and illegal changes to retained fields still fail. Final completeness checks every required field and value. Report `completed` and `all_revision_commits_correct` together, without calling this first-attempt task success. First complete attempt boundaries require explicit completion events or independent annotation.

The current cases specify category membership, not its display order. Requested category sets are compared without order, while source selection mode, metrics and scope remain checked. A view outside the requested edit scope must remain unchanged. Business target views can change presentation; the diagnostic presentation checks are unchanged. Releasing a fixed set requires a dynamic ranking, even if a fixed list currently contains the same members. The 2026-11-13 review corrected order-sensitive member scoring; its original counterexample and corrected result are preserved in `traces/research-review-20261113/`.

The current scorer assumes one specified revision episode per case. `request_accepted` starts it. Actual `tool_committed` receipts and full `state` on `undo`/`restore` rebuild the trajectory. A restored state may fail current task requirements without constituting a new misunderstanding: human coding distinguishes deliberate repair from new semantic error. Invalid-public-state counts are not automatically repair counts.

Ambiguous references must be selected or explicitly resolved before publication. `evidence_selected` with `evidence: null` clears selection. An answer added later does not make earlier unsupported publication correct. Natural-language resolution and voice meaning require review; final chart agreement alone is not shared understanding evidence.

## Human coding and statistics

Repair means correction of a misunderstood request or erroneous execution; normal exploration and deliberate goal changes are excluded. Code additional operations, clarification turns and repair time. Two coders review a shared subset, report agreement, resolve disagreements and retain unknown labels. `repair_turns`, `repair_seconds` and `spoken_consistency` stay null in local reports.

The implemented archive-review interface now provides the evidence entry point and event-linked draft storage described in [REVIEW_CODING.md](REVIEW_CODING.md). Its proposed labels remain drafts, separate from the frozen automatic report. No sum of annotations is automatically treated as repair effort; independent coding and adjudication are still required.

For business tasks, independently review whether the participant's recommendation and rationale follow from actual evidence and whether their stated object origin differs correctly from the calculation scope. Accept defensible alternative conclusions and justified uncertainty. Record the submitted statements verbatim; do not infer intention, reference understanding or a reason for release from final charts. Technical outcomes, response submission and reviewed interpretation are separate. Interaction observations such as selections, preview displays/opens, explicit approvals and saved-set reuse describe actual events, not automatically classified repair or understanding.

Predeclare bound_revision versus direct as the main comparison. Use a binomial mixed model for correctness and a negative-binomial mixed model for repair counts, with condition, task family and execution order as fixed effects and participant/task configuration intercepts. Report marginal probability differences, odds/rate ratios and 95% intervals; Holm-correct the two primary tests. Use the predeclared participant-level paired/bootstrap alternative if data cannot support the mixed-model structure. Four tasks by one person are not four independent people. Set an eight-minute task limit; retain unsuccessful trials as right-censored for time analysis and report correct completion by the limit. Do not compare successful times only.

Technical trials report paired condition differences with uncertainty clustered by case. Three repeated runs are not three new semantic cases. Report invalid timing separately. Associations between visual changes and failure are not causal without controlled manipulation.

## Local verification

Run from the root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_revision_study.py -q
.\.venv\Scripts\python.exe scripts\verify_revision_study.py
.\.venv\Scripts\python.exe -m pytest tests\test_business_tasks.py -q
.\.venv\Scripts\python.exe scripts\verify_business_tasks.py
```

The script runs eighteen authored real-Olist reference paths and six injected counterexamples: current members substituted, region rolled back, obsolete fixed rule retained, scope expanded, numeric artifact corrupted, wrong then recovered. Complete authored starting history, initial/final snapshots, events and reports are stored under timestamped `traces/revision-study-runs/` directories. The frozen acceptance run remains in `traces/revision-study-20261113`; rerunning does not overwrite it. Artifact corruption tests the scorer; production tools cannot supply arbitrary values.

The business script independently exercises four authored real-Olist business paths and eight deliberate counterexamples covering current-cohort confusion, region/scope errors, unreleased or falsely fixed ranking, seasonal cohort/period confusion and out-of-scope metric changes. It saves full histories, initial/final snapshots, receipts, public briefs and reports under timestamped `traces/business-task-runs/`. It uses the shared private-case/SQL pipeline, does not call a provider and leaves every participant interpretation pending.

Local results do not measure model understanding, speech delivery, real overlap, user benefit or external validity. Real API, listening and human trials remain pending. See `RESEARCH_PLAN.md` for the Chinese proposal and related-work boundaries.
