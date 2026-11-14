# Independent intent review before outcome inspection

This offline handout separates intent coding from outcome inspection. It makes no API calls, opens no active workspace, reads no credentials, and does not change archived evidence or approve human results. The eight existing authored trials can demonstrate packet construction only; they are not participant observations or a B0/B2 study.

```powershell
.\.venv\Scripts\python.exe scripts\prepare_intent_review.py --session-dir traces\real-study-20261113-224313\01-direct\sessions\16fc7d080f7d --onset-index 2214 --utterance-end-index 3281 --evidence-kind authored_diagnostic --output-dir traces\intent-review-example
```

Choose one explicit archived session folder containing `events.jsonl` and `state-r*.json`. A trial root can contain multiple sessions; identify the correct session explicitly rather than selecting the latest or most successful attempt. Output files are created exclusively; use a new folder for a new export. Original files are never overwritten.

## Boundary and evidence

An examiner selects the actual revision speech onset and last transcription-arrival event for that utterance from the original event indices, without choosing by success. The end is an arrival window, not an acoustic end. It must cover every raw fragment belonging to that utterance, including a late prefix that the application discarded. If another utterance overlaps this window, mark attribution unknown and inspect item IDs; the exporter does not concatenate or infer speech intent. Text input uses the explicit user-input/request-accepted event as its boundary. Preserve the selected indices in the research episode ledger before outcome coding.

`intent-packet.json` contains pre-onset assistant text, selection, original evidence references, chart-render/visibility and playback observations, plus user words through the chosen arrival end. Raw provider transcription completions are retained alongside accepted/application text. Differences require listening and human verification, not automatic text repair. Public state views are included only when a pre-onset render cites them or an explicit evidence selection references them. Historical state and current state are evidence candidates, never a gold intended member set. A render does not establish visibility or reading; inspect the separate visibility events.

Only generated words archived before onset are available as prior assistant context. They are explicitly marked generated, not heard. Received and played sample counters remain separate; no word-level semantic alignment or acoustic perception is inferred. Output WAVs can contain unplayed future speech, so the handout deliberately does not link whole assistant WAVs. Input speech verification must use an examiner-prepared, utterance-only audio excerpt with documented source offsets; that extraction/alignment remains manual. No post-onset assistant completion, tool proposal, tool result, final chart, automatic score or private expected source enters the handout. Original raw clocks and available calibration fields remain attached; do not subtract unaligned clocks.

## Independent coding and later unblinding

1. Give each independent coder only `intent-packet.json` and any separately verified user-only speech excerpt. Keep the private mapping and original archive inaccessible during coding. Condition names and archive paths are withheld, but visible content may still reveal the interface; this is outcome blinding, not guaranteed condition blinding.
2. Each coder copies the handout to a new reviewer-specific file and fills `coding`: member origin and exact members, current target IDs, changes, retained conditions, released conditions, unknowns and reasons. Cite source event/evidence IDs and raw timestamps. Null starts every semantic field; do not replace ambiguity with an old saved set or a model choice.
3. Compare independent codings and adjudicate against user words and contemporaneous evidence. Preserve disagreements and unknowns. Freeze and hash the adjudicated intent file with reviewer identities/pseudonyms and lock time. The exporter does not produce or approve this lock.
4. Only after intent is locked, release `unblinding-private.json`. It maps the packet to its original session and outcome event IDs. Inspect proposals, commits, final charts, automatic checks and later explanation separately. Calculate expected SQL from the independently established intent; SQL cannot discover intended scope. Never feed reviewer files or private expected sources to the model.

The private file records fingerprints and outcome pointers, not an approved judgment. Keep both files under ignored `traces/`; distribute only the handout to intent coders. Later understanding answers and repair outcomes belong to separate outcome review. No trial, condition or manipulated variable is added by this workflow. See [unified protocol](UNIFIED_RESEARCH_PROTOCOL.md), [existing draft coding](REVIEW_CODING.md), and [offline delivery audit](JARVIS_ADAPTATION.md).
