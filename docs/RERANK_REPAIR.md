# Ranking contract repair and real post-edit image verification

## What changed

The prior native model returned `top_n: "3"` against an acknowledged integer/null schema.
That original rejection remains a failure. The new wire interface explicitly declares a
positive decimal string or null in six existing model tools. One validated compiler maps
the string to the unchanged domain integer. It does not accept mixed types, trim text,
repair nested JSON, clamp counts, or retry the model.

- `backend/model_contract.py`: derives the model schemas and compiles this one field.
- `backend/app.py`: both model providers enter `execute_model`; raw/compiled arguments
  are recorded, then existing shared private revision and publication rules execute.
- `backend/data.py`: numeric source contract and Olist calculation are unchanged.
- `tests/test_model_contract.py`: wire validation, null/omission, real Olist execution,
  independent SQL, scope preservation and direct/bound parity.

The common successful-edit instruction asks for one short sentence (at most 25 words).
Audio is not truncated to enforce this preference. This prompt and the wire contract were
fixed before either new call, and identical in both study conditions. The previous version
comparison does not isolate the causal effect of either change.

## Actual bounded calls

Evidence: `traces/rerank-repair-20261113/real-two/`. Existing complete natural neural TTS
clips were reused with their original SHA-256 values. Exactly two Realtime connections,
zero new TTS calls, zero automatic retries.

| Authored diagnostic | Connection including cleanup | Input clips | Outcome |
| --- | --- | --- | --- |
| 02 direct: release fixed members and rerank three MG views | 39.937 s | 4.24 / 8.08 s | Correct final sources and data; natural output completion |
| 03 bound: use historical members in selected service views | 27.906 s | 4.24 / 6.64 s | Correct targets and retained scope; natural output completion |

Each call committed revision 7. Offline audits match the new JPEG against the actual native
payload bytes and hashes: commit → all-view rendering → same-revision capture → tool
receipt → native image delivery → next response. Final data is checked with independent
SQL. The detailed audit retains every earlier state as well as the final requested goal.
The review page links original input/output WAVs and before/after images.

Local verification: 52 focused contract/provider checks, 367 full backend tests, 47 frontend
tests, and the production build passed. The full backend suite retains the existing
Starlette deprecation warning; the build retains the existing chart-chunk size advisory.

## Remaining limits

The reranking ASR changed “Release fixed categories” to “These fixed categories”; the
requested reranking still executed correctly. The model also generated a pre-tool future
tense promise before the committed result. Success is based on the actual publication and
data checks, not that promise. A Windows socket-close callback warning is retained in the
first raw stderr; the call and driver closed and the checks passed.

PCM output receipts establish browser output-graph delivery, not human listening.
The final response text can be checked against the receipt, but acoustic semantic quality
and independent human coding remain pending. JPEG transport does not establish visual
inspection or the effect of image input. Two different authored tasks are not a matched
B0/B2 participant comparison. Both manuscripts report these diagnostic boundaries.
