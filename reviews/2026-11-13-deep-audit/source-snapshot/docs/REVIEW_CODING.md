# Reviewing assigned trial evidence

This workspace supports inspection and **draft** human coding. It does not approve participants' reasoning, mark audio as heard, or turn event counts into repair scores. Human review remains pending in the trial report and unified exports.

## Evidence packet

Open an assigned attempt from Experiment records. The review packet retains the original session and assignment, exact archived task brief, task response and its revision, automatic report, full event timeline, committed version nodes and saved states. New exports snapshot the public task brief. Earlier frozen materials use their task ID and are explicitly labelled `materials_lookup`; they are not presented as an archived brief.

The packet includes input/output WAV recordings and captured JPEG frames when these actually exist. Media entries identify their recorded event indices. Completed user/assistant transcript events are shown once; streamed text deltas are not duplicate utterances. A transcript is provider text, not human-verified recognition. Recordings and playback callbacks do not establish what a participant heard.

Original event indices, server timestamps and browser timestamps are retained. Do not subtract one clock domain from another. The measured window starts at `trial_started` and ends at `trial_finished`. Preparation and post-task inspection remain visible for context but cannot be labelled as measured task repair. A prepared attempt with no Begin has no measured interval.

## Draft coding procedure

1. Check participant label, evidence kind, assigned condition, task version and terminal status. Local authored checks are not participant observations.
2. Read the business goal and current response. Compare the archived final state with the actual automatic checks; inspect earlier nodes when an object or scope changed.
3. Inspect relevant requests, tool proposals, public commits, rendered frames and speech. Use original event indices to cite evidence. A correct final chart alone does not establish correct explanation or intention.
4. Enter a reviewer label and notes. For each proposed episode, select an ordered start/end event within the measured window and explain the evidence for its classification.
5. Save a new draft. Later revisions append another draft; previous drafts and original evidence are retained. Different reviewers use different labels. Do not treat the latest draft as adjudicated truth.

| Episode label | Meaning | Required evidence |
| --- | --- | --- |
| `repair` | Additional activity correcting a communication misunderstanding or execution error | The error, the user's correction or other explicit evidence of repair, and the corrective action |
| `exploration` | Trying or comparing alternatives while developing the analysis | Evidence of an exploratory choice; repeated changes alone are insufficient |
| `intent_change` | A user deliberately changes an analytical goal or valid earlier choice | The expressed change and its scope; do not infer motivation from the final chart |
| `unclear` | Available evidence does not support the distinction | Explain which information is absent or ambiguous |

Undo, a tool failure, opening a card, or a new request does not automatically count as repair. One repair may span multiple tools; several draft segments may overlap. The system therefore does not sum segment counts or durations into the study's repair outcome. Formal episode units, independent coding and adjudication must precede that analysis.

Business interpretation labels are `pending`, `supported`, `unsupported`, or `unclear`. Judge whether the written conclusion is supported by its cited chart evidence and respects the data scope, without assuming one gold business recommendation. Speech labels are `pending`, `consistent`, `inconsistent`, `not_available`, or `unclear`. They describe a reviewer's proposed assessment; `not_available` is distinct from a passing judgement. Non-pending labels require explanatory review notes.

## Storage and scoring boundary

Each save appends a timestamped, uniquely identified record to `review-drafts.jsonl` inside that attempt directory. It records reviewer, proposed interpretation/speech labels and event-linked episodes. `session.json`, `events.jsonl`, chart snapshots and automatic scores remain unchanged. Review data never enters the assistant context or alters the next trial assignment.

The packet and experiment export retain draft provenance separately. Human interpretation, spoken correctness and repair scores remain null/pending. This release provides a review entry point and evidence linkage, not a completed review or a statistical finding.
