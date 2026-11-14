# Real API findings and the next research steps

Date: 2026-11-13. Evidence: `traces/real-study-20261113-224313/`.

## What was actually completed

Eight authored diagnostics used Qwen3.8-Omni-Flash-Realtime, the actual browser microphone/playback path, native JPEG delivery, real Olist tools and independent SQL. Four task families each ran once in `direct` and `bound_revision`, in the order frozen in `matrix-plan.json`. These runtime names are not a completed, input-matched B0/B2 user experiment.

Each provider connection lasted 15.795–55.264 seconds; the total connected interval was 259.299 seconds. Each source utterance was 4.24–8.56 seconds. Three new neural TTS calls produced complete, brisk English speech; existing complete clips were reused. No connection, failed tool or failed task was automatically retried. All eight attempts remain in the report. Temporary services and model connections were closed.

| Task | direct | bound_revision |
| --- | --- | --- |
| Historical members, first half → Q1 | Correct final state and natural final playback; watchdog fired during shutdown | Still first half; claimed Q1 without a revision tool call |
| Release fixed cohort and rank local top three | Tool rejected string `"3"` for integer `top_n` | Same parameter rejection |
| Historical Q1 members in current Q3 analysis | Correct final state and natural final playback | Provider rejected continuation after a cancelled tool turn |
| Replace orders with revenue, preserve cohort and other views | Correct final state and natural final playback | Correct final state and natural final playback |

Final goal correctness is **4/8** in this small authored matrix; raw driver status is **3 passed / 5 failed**. The fourth correct attempt is not silently rewritten: its final playback finished at 54.634 seconds, then the 55-second watchdog fired while normal shutdown was in progress. Separately, all **24 actual final charts** match independent SQL for their **actual** queries. This does not make an unchanged or wrongly scoped query satisfy the user's request.

All eight had measured speech onset during unfinished assistant playback and native image delivery. This establishes overlap and transmission, not that images were necessary for the decision. Human listening, transcript-to-audio alignment, user comprehension and collaboration benefit remain pending.

## Concrete failures, with evidence and the next minimal fix

1. **One complete utterance can span several VAD fragments.** In both local-ranking cases, the correct first-fragment ASR arrived 40.69 / 101.82 ms after the second onset. Epoch advancement caused the application to discard that earlier transcript. Native provider history retained more information than the application's displayed conversation. Fix fragment-to-request association in `backend/providers.py`; preserve the late transcript without restoring old publication permission. Reproduce this exact ordering locally. Do not replace natural speech with forced single-segment transcripts.
2. **Cancellation can leave a native tool turn unusable.** In `03-bound_revision`, a late response was cancelled and a subsequent bare `response.create` produced `Cannot continue a cancelled tool turn; submit new input`. Repair this protocol sequence using the recorded item/response IDs. Do not silently resend input or add retry loops. The present attempt is a transport/protocol failure, not evidence that the model refused the analytical change.
3. **A spoken success is still not an executed edit.** In `01-bound_revision`, the Q1 request was correctly transcribed, but no revision tool ran. The answer claimed completion while reciting first-half values. The UI correctly retained `No chart changes`. Next, make the model's short completion explanation depend on the current request's successful tool receipt; continue scoring no-tool promises as failures rather than force-committing an inferred intention. Both research conditions must use the same execution policy.
4. **Flat tools still have model-side typing failures.** Both ranking calls used `top_n: "3"`. Keep the integer schema and failure record. Review the numeric example and redundant edit routes in the model-facing contract before changing it; do not silently coerce arbitrary strings or add tools solely to pass this case.
5. **Measurement must separate a drained queue from completed delivery.** A budget-interrupted queue can be empty. The offline report now checks received/played samples and non-interrupted ends. The diagnostic driver was locally corrected after the matrix to cancel the watchdog before ordinary shutdown, follow the newest fragment, and report transport errors. Four focused local tests passed; no paid rerun followed. The frozen original driver and original results remain archived.

The TTS provider's original WAV headers contain a placeholder frame count. A metadata calculation previously reported 44,739 seconds. Actual PCM and converted inputs were complete and short. `tts-duration-correction.json` preserves the header/actual distinction; the metadata-only correction produces byte-identical 16 kHz audio. No synthesis or audio truncation was repeated.

## What this means for the paper

Keep the research question fixed:

> In full-duplex collaborative visual analysis, does making the evidence source, current edit targets, and retained/released conditions explicit improve revision correctness and users' understanding, and at what interaction cost?

These eight calls establish real execution examples and concrete limitations. They do **not** establish that the revision card improves the model or the user. Historical references were selected by the test setup, so these cases cannot prove that the model resolved “the group you just mentioned” from the actually played explanation. Most successful changes used `preview_revision` followed by `apply_revision`; exposing a single-call tool does not mean the model chose it.

The strongest present result is methodological: a chart can be numerically correct, the speech can sound successful, and the requested analytical revision can still be wrong. This is a useful reason to measure source/target/retained-condition correctness separately from computation and playback. It is not, on its own, a new model or a demonstrated human benefit.

## Next delivery sequence — keep the existing two conditions

### 1. Fix the observed runtime faults

Use the saved VAD and cancellation sequences as local regression inputs. Keep onset revocation and stopping old playback. Do not add models, experimental arms or recovery frameworks. Acceptance: both fragments remain visible and associated; cancelled work cannot publish; current-request continuation follows the real protocol; no old receipt certifies a new promise. A later paid check must be explicitly budgeted, not automatically triggered by tests.

### 2. Freeze the fair comparison

Audit both conditions' actual outgoing context, candidate/history/saved-set access, tool schemas, successful receipt content, clarification rule and budget. Their intended difference remains the explicit, correctable revision support. Store this audit with the protocol. Do not hand correct member identities to one condition only, and do not treat private evaluator expectations as model inputs.

### 3. Use the four business families for the user study

Keep regional service review, local priority reselection, seasonal comparison and metric replacement. Give business goals and necessary constraints; let participants choose whether to reuse or release a cohort. Independent intent coding comes before independent SQL. Preserve every assigned trial, including non-interruption, unknown intent, transport failure and incomplete work. All final understanding and repair-effort labels require independent human evidence.

### 4. Write only the supported conclusion

The current Chinese manuscript has real technical results plus a prospective B0/B2 user-study protocol. The eventual contribution must be supported by differences in correctly implemented revisions, understanding and repair cost. If only understanding improves, claim that narrower benefit. If intervals remain wide or cases rarely depend on partially played evidence, report the limitation; do not replace missing evidence with more scripted calls.

## Evidence index and usage

- `matrix-plan.json`: frozen order, audio/source hashes and limits.
- `aggregate.json`, `RESULTS.md`: all eight attempts, separate raw/goal/delivery outcomes, transcripts, tools and usage.
- Each trial directory: original report, before/after screenshots, browser recording/trace, native input/output archives and audio.
- `actual-source-sql-audit.json`: 24 actual-query checks, independently recomputed.
- `tts-duration-correction.json`: complete-source audio duration audit.
- `driver-original.py`: original driver matching the frozen plan; local driver fixes do not change these results.

The 13 recorded response-usage events sum to 271,286 input and 2,475 output tokens. Detail fields overlap their parent totals. Interrupted/failed provider calls may omit final usage. These counters and connected seconds are not a bill; actual monetary cost was not retrieved. Source utterances total 96.48 seconds; streamed microphone PCM totals 250.60 seconds including silence. They are separate measures.

No additional API calls are scheduled by this report.
