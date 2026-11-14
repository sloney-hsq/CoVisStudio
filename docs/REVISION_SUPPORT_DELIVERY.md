# Revision support, verification and research scope

## Research question

In the same full-duplex visual-analysis environment, does an inspectable and
correctable account of evidence sources, current changes and retained conditions
improve final intent-consistency and interface-assisted interpretation, and at
what interaction cost?

The participant comparison remains **B0 direct editing / B2 explicit revision
support**. Both conditions use the same model, tools, historical evidence, saved
category sets, compilation, commit rules and budgets. The experiment estimates
the support package's effect, not full-duplex superiority or the separate effects
of visibility, persistence and correction controls. User-study findings and human
listening are pending.

## Implemented changes

| Module | Change |
| --- | --- |
| `backend/revisions.py` | Retain the exact compiled source patch; distinguish fixed category identities, dynamic rankings and displayed grouping values; record actually changed and untouched views from real candidate states. |
| `frontend/src/revisionDisplay.js` and revision components | Show object origin separately from current computation. Correct interpretation restores the original targets and exact patch, preserving different measures across charts. |
| `backend/app.py` | Shared instructions distinguish historical identities from current calculation conditions and permit a later explicit reranking request to release the fixed set. |
| `backend/intent_scoring.py` | Select terminal intent by episode chronology, not annotation order. Later unknown intent cannot be replaced by an older successful score. Private per-view overrides express still-valid, different obligations across views. |
| `scripts/audit_rerank_real.py` | Require the original live attempt to have completed successfully; match the post-commit image and following response to the committing request. An offline audit cannot upgrade a failed live attempt. |

The correction bug was concrete: rebuilding an edit from the union of per-chart
differences could copy one chart's measure onto another chart. Corrections now use
the exact shared patch supplied to the original revision. Historical members are
not a command to restore historical dates, region or metrics. Untargeted charts
may intentionally keep a different category set.

## Scoring and protocol corrections

- The final dashboard is evaluated against requirements still active at task end.
  A later explicit goal change can replace an earlier requirement. Earlier legal
  commits remain legal at their original time.
- Independent human intent locks precede SQL verification. The evaluator's
  per-view intent annotations never enter the model's public tool inputs.
- Unknown intent remains unknown. Missing and unsuccessful assigned attempts
  remain in the primary analysis.
- A card cannot affect an action preceding its exposure. Prior B2 experience or
  clarification can affect later requests; first-commit equality is not assumed.
- Detection, attempted correction and successful repair are descriptive process
  observations with explicit denominators. They do not establish a component's
  independent causal effect.
- Final intent-consistency and interface-assisted interpretation remain the two
  primary outcomes. A high pilot correctness rate does not silently change them.

## New real Qwen diagnostics

These are two authored engineering checks, not a participant comparison.
Model: `qwen3.8-omni-flash-realtime`. Both revise during actual assistant playback.
Each case opens exactly one connection; no automatic retry or new TTS call occurs.
Complete cached neural speech is injected through the browser microphone path.

| Case | Condition | Connection including cleanup | Complete input clips | Result |
| --- | --- | --- | --- | --- |
| Release fixed members and rerank all three current views | B0 / direct | 35.360 s | 4.24 s; 8.08 s | Passed |
| Reuse historical category identities in two selected service views | B2 / bound_revision | 33.141 s | 4.24 s; 6.64 s | Passed |

Both cases committed revision 7, rendered the matching charts, delivered the new
JPEG bytes before the same request's subsequent response, and naturally completed
the final output audio. Independent SQL matched all 36 archived chart-query checks.
These observations establish execution, rendering, transport and playback behavior;
they do not establish model visual reasoning or human listening and understanding.

Returned transcriptions were imperfect: the reranking command's "Release fixed
categories" became "These fixed categories", and the historical-reuse command
lost "Keep". The actual operations still matched the authored requests. Because
the provider receives native audio, these transcript differences do not identify
the causal source of model understanding or error.

Private records are retained locally under
`traces/revision-support-20261113-164326/`: `real-two/`, both offline audit JSONs,
the runtime test log, and the full backend test log. Original earlier failures
remain in their separate archives. Credentials, recordings and raw trace archives
are excluded from GitHub.

## Local verification

The integrated suite passed **377 backend tests** and **51 frontend tests**.
The frontend production build also passed. Existing non-fatal Starlette test-client
deprecation and chart bundle-size notices are retained in the local logs.

The local browser check exercises both conditions with real Olist data, then uses
the actual correction control while a different chart is selected. It verifies
the original target IDs, a date-only patch, distinct retained metrics, single-view
reranking, matching render receipts and explicit card interaction events.
All 14 checks pass at 1920, 2560 and 3840 CSS-pixel widths, with no page errors.

The browser check uses no provider connection. Its initial two driver errors
(manual numeric contract and exact floating-point comparison) were corrected;
the original failed driver records remain available locally.

Both updated manuscript PDFs compile to six pages with unchanged IEEE layout.
Chinese: `paper/cscwd_zh/main-current.pdf`; English: `paper/cscwd_en/main.pdf`.
Their sources and distribution ZIPs retain the distinction between authored
technical checks and the still-pending participant study.

Run the current checks from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts\verify_revision_support_browser.py
```

## Related-work boundary

Interpretation externalization, editable analysis operations and conversational
goal tracking have direct precedents in
[Who's That Player?](https://arxiv.org/html/2608.00876v1),
[WaitGPT](https://arxiv.org/html/2408.01703v1), and
[OnGoal](https://arxiv.org/html/2508.21061v1).
CoVisStudio does not claim to invent those capabilities. The prospective study
examines the final analytical consequences of historical evidence reuse and
scoped repair under a shared full-duplex runtime.
