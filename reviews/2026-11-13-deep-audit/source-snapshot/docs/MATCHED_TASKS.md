# Matched business tasks — covis-matched-0.1

Eight experimental materials form four A/B pairs. They extend the four business goals while leaving the original four `biz_*` briefs and eighteen frozen `rev_*` diagnostics unchanged. `experiment_tasks()` is public; private case specifications remain in the evaluator. Every case uses real Olist, three bar charts, three category members, the same chart labels/styles, four written response fields and the same task instructions across conditions. Human interpretation stays pending.

These are **structurally matched parallel forms**, not demonstrated equal human difficulty. Matching can reduce obvious task confounds; it does not establish equal interpretation demands or eliminate learning between related business scenarios. Allocation must balance versions, family, position and condition, and analysis must retain family/version identities.

## Materials

| Family | Variant A | Variant B | Required analytical change |
| --- | --- | --- | --- |
| `01` Regional service review | `exp_01_a`: categories selected in RJ, measures calculated in MG | `exp_01_b`: categories selected in MG, measures calculated in RJ | Reuse the earlier top-three categories in service charts 2/3; preserve the current local-volume chart 1 |
| `02` Release for local planning | `exp_02_a`: inherited RJ set currently measured in MG | `exp_02_b`: inherited MG set currently measured in RJ | Release the inherited fixed set; dynamically rank top three by local delivered-order volume in all three views |
| `03` Stable seasonal cohort | `exp_03_a`: RJ January–March selection, July–September measures | `exp_03_b`: MG January–March selection, July–September measures | Use the first-quarter cohort for current service charts 2/3; keep current volume chart 1 and compare with saved first-quarter evidence |
| `04` Stable metric control | `exp_04_a`: current RJ annual cohort | `exp_04_b`: current MG annual cohort | Change chart 1 from orders to item revenue, retaining the cohort, scope and service charts |

Families 01/02/04 use calendar year 2017. Family 03 uses the first and third quarters of 2017. All use delivered orders. Source dates remain inclusive start/exclusive end. Revenue excludes freight; low-review-rate and delivery-time denominators remain visible in stored data. No task has a gold business recommendation: justified uncertainty and alternative evidence-based recommendations may be valid.

The seasonal pair deliberately uses RJ/MG and Q1/Q3 rather than simply copying the original SP Q1/Q4 case: real category sample sizes are closer while the selection difficulty stays the same. The original `biz_03_seasonal_same_cohort` remains available unchanged.

## Auditable matching criteria

Pairs are matched within a family, not across all four families. The stable single-view metric control is intentionally simpler than historical multi-view changes.

| Feature | Families 01/02/03 | Family 04 |
| --- | --- | --- |
| Views / category members | 3 / 3 | 3 / 3 |
| Authored history phases / initial commits | 2 / 6 | 1 / 3 |
| Earlier vs current ranked-set overlap | 2 of 3 in each variant | 3 of 3 |
| Target count | 2 / 3 / 2, respectively | 1 |
| Minimum chart commits | One batch | One edit |
| Intended source-field changes | Fixed membership or release: categories and top_n | Metric |
| Public goal word counts A/B | 119 / 113 / 132, respectively; equal within each pair | 99 / 99 |

`scripts/verify_matched_tasks.py` computes the source/destination sets and all comparison numerators/denominators through the independent raw-table SQL oracle. The audit records exact members and values privately; it is not delivered as a model answer.

On the current Olist data, minimum reviewed-order denominators for A/B are 339/385, 339/385, 49/55 and 426/389. Minimum valid delivery denominators are 343/388, 343/388, 50/55 and 432/391. Total current-scope counts across the referenced groups have within-pair maximum/minimum ratios 1.1686, 1.1686, 1.3031 and 1.1597. These counts are support checks, not unique totals across possibly overlapping product groups. Matching does not equate statistical uncertainty, actual metric values or human decision difficulty.

Prompt wording is template-identical within each pair except for region names. No task-specific hint or expected category list is added to model context. The direct baseline has deterministic named-set saving/reuse, just like the method; a correct result need not require copying member names.

## Execution, scoring and records

`study.task_brief`, `setup_operations`, `revision_case`, `revision_targets` and `evaluate` support `exp_*` IDs. Experimental reports preserve business technical completion, written-response freshness and pending interpretation, adding public family/variant IDs and the matched protocol version.

Scoring begins at explicit `trial_started` for assigned experimental cases, or a user request for ad-hoc cases. Manual tools do not need a fabricated transcript to enter the process record. Each actual public commit has two distinct checks:

- `correct`: the fields it changed obey the task and keep unaffected views intact. A legal partial edit can pass.
- `full_correct`: the entire observed dashboard already satisfies all final requirements. The first true entry identifies `first_full_correct_revision` and `first_full_correct_event_index`.

This prevents a correct edit to only chart 2 from being counted as completing a task that also needs chart 3. Independent numeric checks and actual source states support both evaluations. Neither quantity proves that a participant understood the result or that normal exploration was error repair.

The verification script runs both direct and bound-revision authored paths for every variant (16 paths), plus two deliberate error trajectories per variant (16 cases), including current-cohort substitution, retaining a fixed set, fixing a newly ranked set, wrong period, wrong metric and out-of-scope edits. It saves starting histories, public briefs, actual tool receipts, final states and reports under a fresh timestamp in `traces/matched-task-runs/`, with a separate `matching-audit.json`.

```powershell
.\.venv\Scripts\python.exe scripts\verify_matched_tasks.py
.\.venv\Scripts\python.exe -m pytest tests/test_matched_tasks.py -q
```

All of this is local tool/data/scorer evidence. No real API, participant difficulty calibration, listening approval or effectiveness result is produced. The existing sixty-second development voice connection cap remains separate from the planned eight-minute task duration.
