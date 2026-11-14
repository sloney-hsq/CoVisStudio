# Offline study parity audit — 2026-11-13

Shared direct/bound application parity is locally validated for the controlled workspace below after the prompt/context fixes. Formal B0/B2 participant parity is **not frozen**: native provider history, frozen participant materials and semantic/listening outcomes remain unresolved. The audit makes no paid call and reads no credentials. It does not rename runtime conditions or add a condition. The governing design remains [UNIFIED_RESEARCH_PROTOCOL.md](UNIFIED_RESEARCH_PROTOCOL.md).

## Reproduce

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\audit_study_parity.py --output traces/research-acceleration/parity-after
.\.venv\Scripts\python.exe -m pytest tests/test_study_parity_audit.py -q
```

The script constructs two isolated workspaces with a blank key and disabled endpoints, using the same real Olist starter, historical saved set, current MG scope, reference and explicit tool arguments. DuckDB uses one thread so aggregate reduction order is identical. It never constructs a model provider. The original pre-fix result is preserved at ignored `traces/research-acceleration/parity/audit.json`; the post-fix result is `traces/research-acceleration/parity-after/audit.json`. Originals in `traces/real-study-20261113-224313/` are read only. Use a new `--output` directory for another retained rerun.

The controlled comparison normalizes the application evidence-package archive ID and, in the post-edit comparison, the generated proposal UUID. It retains category IDs, ordering, filters, source versions, values and exact instruction strings; any condition label present would remain a reported difference. Numeric differences are retained and labelled if within 1e-12; they are never silently rounded away. Local archive IDs do not determine the selected evidence.

Before the production fixes, pre-edit context differed at `$.condition`; post-edit context also differed at `$.last_proposal.card.condition`, and the returned receipt card differed at `$.condition`. Instruction suffixes also differed. Root then made direct/bound analytical instructions identical (including the same numeric JSON example), removed the model-facing context condition and redundant card condition, and retained `session.condition` for UI/export. The historical unbound path is unchanged. The post-fix run shows zero context/read/result/post-edit-context/receipt-card differences; instructions, tools, committed receipt and clarification receipt match. This establishes the tested application parity without claiming model reliability or complete native-context freezing.

## Current implementation versus planned contrast

| Surface | Implemented current behavior | Audit / remaining freeze decision |
| --- | --- | --- |
| Model and transport | Same configured realtime model; same native audio/image transport, cancellation and session budget | This is source/local evidence, not a new real speech result |
| Tool schemas | `backend/app.py:MODEL_TOOLS` is shared, including history, sets, candidates and flat `revise_analysis` | Exact same schema hash in controlled runs; no weaker manual-copy baseline |
| Instructions | Identical direct/bound analytical instructions, preservation, exact membership, ambiguity, receipt and playback guidance | Exact instruction equality after fixes; both before/after strings retained in their JSON artifacts. Prompt equality does not establish equal speech interpretation |
| Context | Same visible/current snapshots, history, sets, candidates, task brief, selected evidence and playback fields; model-facing condition labels removed | Zero controlled pre/post-edit context differences after fixes; original label differences remain recorded in the pre-fix artifact |
| Saved sets/history/candidates | Model reads use `decision_material()` from the current application package | Exact result equality for all three controlled reads. Both receive the immutable historical set, with provenance |
| Candidate compilation | Direct and bound `use_evidence` bind exact members through `prepare_revision`; explicit patches modify current sources | Same historical chart candidate applied to charts 2–3 produces byte-equivalent JSON state/data; MG and current measures retained, chart 1 unchanged |
| Clarification | Same `needs_confirmation` gate; unresolved edits return an uncommitted `awaiting_confirmation` | Controlled receipt equality; interpreting ambiguity is still model/human behavior, not established by deterministic tools |
| Commit permissions | Same private preparation, epoch check, store version check and commit route | Same committed receipt for explicit operation; this audit does not replace existing stale-publication race tests |
| Presentation | `frontend/src/App.vue:revisionAvailable` hides the primary revision surface for direct; bound exposes it | Internal proposal/card and source differences also reach receipts and history in both. History detail shows revision provenance when present. Freeze which surfaces constitute the intended information contrast; a generated card is not exposure |
| Native history | Ongoing provider conversation contains prior audio, images, tool receipts and generated replies | Exact outbound archives are available but do not isolate/remove native history. Application package freezing is not provider-context freezing |

The controlled operation intentionally supplies an identical candidate ID; it establishes deterministic execution parity. It does not demonstrate that either model would choose that candidate from speech. Likewise identical receipt statuses do not establish equal recognition, clarification frequency, reasoning or user understanding.

## Eight archived real diagnostics

The script reads all eight original per-trial reports and every `model-input-*-sent.json` under their session directories, including setup/session directories rather than selecting the first directory. The JSON lists per-trial input-type counts, exact instruction/schema hashes, original driver status and original `study_parity` label. Partial `session.update` messages without a tools field are not counted as a different schema. No equality is inferred from differing instruction hashes: changing state/context is embedded in instructions.

The original 3 pass / 5 fail statuses remain intact. These are authored diagnostic attempts with different realized tool/audio histories and timing, not controlled identical native model inputs. The archive itself labels study parity `not_established`. Independent numeric correctness of actual queries cannot certify requested intent or experimental parity. No model result is reclassified by this audit.

This run scanned 6,366 exact sent payload files across all eight trial directories (per-trial counts: 1,368; 1,363; 420; 428; 381; 914; 785; 707 in sorted directory order). The named-private-field scan found zero matches in controlled context/reads and archived non-media JSON. Full schema-bearing session updates in these archives share the same schema hash. Archive instructions are not identical, and counts/hashes alone cannot establish context parity.

## Evaluator-field leakage check and its limit

`backend/study.py` separates public `task_brief` prose from private expected-source generation and diagnostic `resolution`/phase/target fields. The scanner recursively checks controlled model context/read results and archived non-media sent JSON (including JSON-encoded tool outputs) for the explicit private-field names recorded in `known_private_fields`. Public task `goal` text is expected input and is not flagged as a private answer merely because it describes a business goal.

The machine result records every match with file/path. Zero matches means only that these named authoritative fields were absent in the scanned JSON. It **does not prove absence of paraphrased answers, evaluator-derived prose, visual leakage, all possible private keys, or native retained history**. PCM and image bytes are counted but not semantically inspected. This is an auditable bounded scan, not a general leakage guarantee.

## Smallest remaining gates

1. Freeze the now-shared instructions/context contract and explicitly enumerate the intended presentation differences, including receipts, Journey details and clarification surfaces. The local regression covers controlled equality; formal UI exposure and the participant information contrast still require review.
2. Decide the native-history policy equally for both conditions before collection. Keep the current honest `native_history_frozen=false` until it is implemented and verified; outgoing logs alone cannot satisfy it.
3. Freeze public participant materials independently of authored `expected_sources` and diagnostic trajectories; derive episode intent from words, choices and available evidence with independent coding, then use SQL only for that intent.
4. Freeze the same feasible voice window/budget, understanding questions, missing/unknown rules and assigned-attempt analysis for both conditions. Preserve the historical ablation apparatus without adding it as a participant arm.
5. Verify actual presentation/exposure with the frozen configurations and review real speech/listening only under separate authorization. This offline audit introduces no permission for paid calls.

No additional abstraction, retry, coordinator or production fallback is required by these findings. The immediate useful result is a repeatable parity check plus an explicit list of unresolved study decisions.
