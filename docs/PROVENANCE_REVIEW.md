# Source provenance repair and cross-review

Date: 2026-11-13 (project/client date). Changes are local-only verification;
no new paid model call or participant experiment was performed.

## Problem and resulting behavior

The retained real case selected Chart 1 at revision 3 (`chart:3:v1`), while the
model explicitly chose `chart:1:v1`. Their members were equal. The runtime had
not lost the selection and did not rematch by members. The old numerical pass
therefore did not establish source correctness. No model-selection cause is claimed.

The shared compiler now records the selected reference and consumed reference
separately, without replacing a valid explicit candidate. B2 displays any difference;
B0 receives the same model-facing facts and uses the same executor. Re-ranking
does not claim that the selected historical evidence was consumed.

## Implementation map

| Files / functions | Responsibility |
| --- | --- |
| `backend/revisions.py`: `evidence_source`, `prepare_revision` | Canonical source facts, comparison with selection, per-target membership attribution |
| `backend/app.py`: `preview_revision`, `_execute`, `context` | Pass bound context through all revision/saved-set paths; expose selected candidate identity |
| `backend/providers.py`: `_speech_started`; `Workspace.provider_event` | Group continuation flag; first-onset binding while every onset still revokes/stops |
| `backend/charts.py`: `prepare` | Explicit membership replacement removes old attribution; scope/presentation edits preserve it |
| `backend/intent_scoring.py`: `validate_resolved_intent`, `compare_state` | Private source requirements; analytical/numeric/provenance results; known-failure precedence |
| `frontend/src/revisionDisplay.js`: `provenanceNotice` | Render compiler facts without reconstructing a different source |
| `RevisionSummary.vue`, `RevisionDetails.vue`, `RevisionPanel.vue` | Selected/used difference; selected-set-consistent labels; reachable correction action |
| `ChartCard.vue`, `chart.js`, `style.css`, `App.vue` | Stable selected chart numbers, scaled value labels, compact plots, newest Journey item |
| `scripts/verify_complete_revision_flow.py` | Future authored diagnostics also check required source identity; old reports remain unchanged |

The selected field refers to audio-group onset for model voice requests and to
invocation for manual edits. The existing provider group ends when an accepted
response is created (or explicit cancellation/failure clears it). This is an
operational grouping, not a claim of sentence segmentation or human listening.
Subsequent click events are retained but do not rebind an existing group. This
does not freeze current public execution state, new image delivery or provider history.

`membership_origin` records a consumed fixed-set source, separate from the query.
Changing dates/region/metric alone preserves that origin; an explicit replacement
or rerank removes it. Previous snapshots and untargeted views keep their records.
The three reuse entry points (`revise_analysis`, `apply_evidence_candidate`,
`apply_category_set`) share `prepare_revision`.

## Independent scoring

The compiler records actual execution, never intended execution. Coders separately
declare `source_requirement` using user speech, selections and contemporary evidence:

| Mode | Source-identity assessment |
| --- | --- |
| `exact` | Compare the independently specified candidate ID with recorded origin; a saved set built from the required chart version satisfies the same lineage while retaining its set ID |
| `members_only` | Grade the required members; report origin without requiring version equality |
| `none` | No new historical-source requirement (for example, explicit reranking) |
| `unknown` | Source requirement unresolved; retain uncertainty |

`lineage_id` identifies the chart version independently of whether it was reached
as a chart candidate or through a saved set. A set built from the selected version
is therefore not an override: the card says it was saved from the selected chart
version, and an exact requirement for that version is satisfied by the set while a
`set:` requirement is not satisfied by a plain chart execution.

The selection is context, not automatic ground truth. SQL checks numerical results;
it does not identify the intended source. A missing actual source record cannot be
scored as an observed different source. Any known failed analytical check still
makes the combined outcome false even when another dimension is unknown.
New templates start unknown, including the researcher UI download. Existing
authored tests explicitly state their no-source requirement; no human labels are
manufactured. The outbound known-private-field scan includes `source_requirement`.

## Reproduction and evidence limits

Run locally from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts\verify_revision_support_browser.py
```

The browser script supplies disabled provider URLs and no key. It exercises equal
members/different versions, corrected sources and dates, saved-set label switching,
single-view reranking and three desktop widths with real Olist calculations.
`tests/test_source_provenance.py` additionally tests B0/B2 parity, VAD-fragment
binding, retained attribution, explicit overrides, independent exact/member-only
requirements, and unknown versus demonstrated failure.

These checks cannot establish real-Qwen source selection, truthful native speech,
actual listening, participant interpretation or a B2 benefit. Full-duplex is shared
by B0/B2; the research concerns the support package within that environment.
Do not treat a card presented after a commit as preventing that commit's error.
Both conditions need access to the same facts; differences in lookup/correction
cost are outcomes, not something to eliminate artificially.

## Validation in this revision

- Full backend regression: **404 passed**. After the final missing-origin/unknown
  adjustment, **30 targeted tests passed** across source provenance, intent scoring,
  parity audit and the complete-flow driver. The full suite was not rerun after
  that small adjustment.
- Frontend unit tests: **52 passed**. Production build passed after the final
  footer-layout fix, retaining Vite's existing >500 kB chart-chunk warning.
- Final browser acceptance: **23 checks passed**, no browser errors, zero paid API
  calls, and the test-owned service closed. See the [public check report](images/provenance-review/browser-report.json).
- These are authored local checks with real Olist calculations. They are not a
  new real-model result, natural mismatch frequency, or participant evidence.

Screenshots are unedited captures of the authored local browser scenario, with
model access disabled. They contain aggregate chart data, not raw records.

| State | 1920 CSS px | 2560 CSS px | 3840 CSS px |
| --- | --- | --- | --- |
| One view reranked; other views retain fixed membership | [Workspace](images/provenance-review/workspace-1920.png) | [Workspace](images/provenance-review/workspace-2560.png) | [Workspace](images/provenance-review/workspace-3840.png) |
| Correction drawer with reachable preview action | [Correction](images/provenance-review/correction-1920.png) | [Correction](images/provenance-review/correction-2560.png) | [Correction](images/provenance-review/correction-3840.png) |

[Selected v3 versus executed v1, with equal members](images/provenance-review/source-version-mismatch.png).
Additional comparisons: B0 [reuse](images/provenance-review/direct-historical-reuse.png)
and [correction](images/provenance-review/direct-corrected.png); B2
[reuse](images/provenance-review/bound_revision-historical-reuse.png) and
[correction](images/provenance-review/bound_revision-corrected.png).
The drawer still overlays part of the workspace; no claim is made that all three
charts remain simultaneously visible during correction or that screenshot checks
establish usability. The final summary footer no longer overlays summary content.

## Reviewer source access

Open these raw files rather than relying on lazy-loaded GitHub diffs. These links
track main; for a reproducible review replace `main` with the full commit SHA in
the review request. Report any file you could not actually read.

### Runtime, compiler and scoring

- [app.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/backend/app.py)
- [providers.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/backend/providers.py)
- [revisions.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/backend/revisions.py)
- [charts.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/backend/charts.py)
- [evidence_candidates.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/backend/evidence_candidates.py)
- [category_sets.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/backend/category_sets.py)
- [model_contract.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/backend/model_contract.py)
- [intent_scoring.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/backend/intent_scoring.py)
- [CONTRACT.md](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/docs/CONTRACT.md)
- [UNIFIED_RESEARCH_PROTOCOL.md](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/docs/UNIFIED_RESEARCH_PROTOCOL.md)
- [FORMAL_STUDY.md](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/docs/FORMAL_STUDY.md)

### Participant interface

- [App.vue](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/App.vue)
- [style.css](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/style.css)
- [chart.js](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/chart.js)
- [audio.js](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/audio.js)
- [visualContext.js](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/visualContext.js)
- [revisionDisplay.js](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/revisionDisplay.js)
- [RevisionPanel.vue](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/components/RevisionPanel.vue)
- [RevisionSummary.vue](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/components/RevisionSummary.vue)
- [RevisionDetails.vue](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/components/RevisionDetails.vue)
- [RevisionSupport.vue](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/components/RevisionSupport.vue)
- [ChartCard.vue](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/frontend/src/components/ChartCard.vue)

### Local verification

- [test_source_provenance.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/tests/test_source_provenance.py)
- [test_intent_scoring.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/tests/test_intent_scoring.py)
- [audit_study_parity.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/scripts/audit_study_parity.py)
- [verify_complete_revision_flow.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/scripts/verify_complete_revision_flow.py)
- [verify_revision_support_browser.py](https://raw.githubusercontent.com/sloney-hsq/CoVisStudio/main/scripts/verify_revision_support_browser.py)

Review the first-onset policy explicitly: we did not implement the external
reviewer's competing suggestion that a later click silently replaces the binding
of a continuing audio group. Selection events are retained and explicit candidate
overrides are still allowed. This policy must not be described as deciding the
user's intended source or determining which audio the user actually heard.
