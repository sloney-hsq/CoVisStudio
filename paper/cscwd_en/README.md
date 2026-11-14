# CoVisStudio: English full-paper review draft

`main.pdf` is a complete English manuscript, synchronized with the updated Chinese review manuscript in `../cscwd_zh/` (current verified output: `main-rerank.pdf`; its old `main.pdf` is externally locked). It includes motivation, related work, revision representation, implementation, technical evidence, a prospective B0/B2 user-study protocol, discussion, conclusion, and 11 cited references.

The manuscript uses IEEEtran conference format, 10-point body text, US letter paper, and **six pages including all figures and references**. No margins or body fonts were reduced to meet that limit. The author line is **Anonymous review draft**, because no author names or affiliations were provided; this does not assert that the conference requires anonymous submission. Acceptance, ethical approval, funding, and participant findings are not invented.

## Reproduce the PDF

Install TeX Live with XeLaTeX, BibTeX, and the TeX Gyre fonts, then run:

```powershell
cd C:\CoVisStudio\paper\cscwd_en
.\build.ps1
```

The script runs XeLaTeX, BibTeX, and XeLaTeX twice, stopping on errors. The included `IEEEtran.cls` and `IEEEtran.bst` retain their original license notices. The bibliography matches the Chinese source; its unused Eviza entry is retained, while the same 11 works are cited in the manuscript. Preprints retain their arXiv status.

`figures/` contains the same three English-language figures as the Chinese manuscript, byte-for-byte. Their editable Python sources and screenshot provenance are in `../cscwd_zh/figure_sources/`. No figure was replaced in only one language. Figure 3 explicitly depicts an earlier local scripted validation, not the latest real model or participant results.

## Evidence distinctions preserved

- Two earlier real-model failures, the local 24-assertion workflow, the earlier eight-run matrix, and two subsequent focused real-model checks are separate records and versions. The latter two are not pooled with the eight as a condition-effect estimate.
- The focused reranking check failed after 19.890 seconds because `top_n` again arrived as a string. The focused transfer check passed after 33.750 seconds, with one revision-7 commit and 14.8 seconds of naturally completed software output.
- The successful transfer still sent a revision-6 image in its post-commit follow-up. The later route test verified matching images but retained failed status because only 28.72/32.08 seconds of final audio played. The specific late-created stale-tool sequence was not triggered by these focused checks.
- The latest two bounded checks passed after the explicit decimal-string/null model contract and shared strict-integer compilation: reranking 39.937 seconds and historical transfer 27.906 seconds, no retries/new TTS, complete cached input. All 36 archived queries (six final charts) matched independent SQL; each v7 commit had matching render/capture, exact native JPEG delivery, then follow-up. Post-tool audio naturally completed at 11.52/8.32 seconds. Original failures remain separate; no single-repair causality or condition effect is estimated.
- Formal reporting now uses first actual Begin, all registered assignments including missing rows, locked independent intent and terminal SQL scoring. Understanding reviews four dimensions with an all-correct/unknown endpoint. One voice window of at most 60 seconds occurs inside the 480-second task; human freeze remains pending.
- B0/B2 share candidate resolution, compilation, tools, and exact-member reuse. The planned contrast is visible, correctable revision support, not a different binding algorithm. Explicit edits may commit before their card is inspected.
- There are no participant-study results, listening scores, method-effectiveness estimates, or full-duplex superiority findings. The four-task, two-condition study and proposed recruitment target remain prospective.

## Verification

The final PDF is rendered page by page in `review/page-1.png` through `review/page-6.png`; every page was visually inspected for clipping, collisions, figure/caption legibility, column flow, and reference layout. `QA.json` records dimensions, reference count, figure hashes, and text/log checks. `build-output.txt` contains the reproducible compile output. Normal underfull-box messages are retained; there are no overfull boxes, undefined references/citations, or font-substitution warnings in the final log.

This package is for the current private collaboration. It contains no credentials, raw Olist CSVs, source audio, participant identities, or private trace exports. This English version is a review draft; real author information, final collection policy, and any claims about user benefit still require appropriate completion before submission.
