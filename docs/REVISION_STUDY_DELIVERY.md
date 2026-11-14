# Revision support and independent study scoring

This delivery implements the three agreed priorities in the existing CoVisStudio project.
No paid model/TTS call, participant recruitment, human annotation or listening review is
performed by this delivery. Local verification uses real Olist with explicitly authored
provider decisions or coding fixtures. Original failure records remain available.

## What the comparison means

The question is whether visible, correctable separation of **evidence origin**, **current
targets/changes**, and **retained/released conditions** helps users understand and correct
analysis revisions. Direct and bound_revision share prompts, model, history, saved sets,
candidate resolution, execution, cancellation and budget. The extra support is a participant
interface treatment. Its existence is not evidence of improvement; first model actions before
users see the support cannot establish its benefit. Both groups have basic clarification,
Apply and Modify controls. Explicit, unambiguous model changes still commit directly.

Full-duplex voice provides the common interaction setting. Neither the assignment nor the
new scoring estimates voice-versus-text superiority. Native provider history is retained,
not described as frozen to what the participant actually heard.

## Normal flow and trustworthy records

- A failed ASR fragment ends its whole pending utterance group consistently. Neither event
  order nor a surviving suffix creates an unintended partial analytical request.
- Apply rechecks the proposal after awaiting cancellation. The original source/targets and
  patch are carried into Modify, rather than resetting the form.
- A failed tool batch closes its remaining native call IDs as unexecuted, without an automatic
  retry or follow-up. Already committed work remains a real publication even if a later edit fails.
- PTT first input, late render acknowledgements and superseded tool receipts retain their
  originating request. Shutdown registers one cleanup before awaiting network/browser work.
- Journey uses the revision card's actual evidence source. Direct editor arguments are recorded
  before execution as `manual_edit_requested`, making intentional manual changes codable.
- Missing playback receipts are unknown, not evidence of silence. Undo and Restore appear in
  the publication ledger. Empty-canvas rendering sends an explicit current empty context.
- Finished assigned `session.json` is preserved through review, export, browser close and shutdown.
  Coding, endpoint declarations and scores are separate artifacts; they never rewrite that record.

These are normal execution/measurement corrections. There is no reconnect loop, argument
coercion, additional model coordinator or production fake model.

## Workspace

Bound revision shows the three-part summary beside the charts, without a modal or mandatory
extra approval. Full fields expand under Details. The actual source version, selected targets,
changes and unaffected charts are visible; Apply/Modify remain reachable at 1920, 2560 and
3840 CSS widths. Direct retains basic actions without the structured summary.

Exposure, explicit expansion, correction request, successful user Apply, commit and rendering
remain different records. None automatically means reading or understanding. Closing a card
is not counted as requesting a correction. Task preparation creates no chart exposure; Finish
saves the current answers first, and participant completion does not open researcher settings.
See [the UI delivery](WORKSPACE_REVISION_DELIVERY.md) for component details.

## Formal material and assignment workflow

1. Open **Experiment** and select **Formal study · business decisions**.
2. Enter a pseudonymous participant/slot and choose local authored check or an actual participant
   session. Load the assignment, prepare its task and explicitly Begin.
3. Each task has 480 seconds. A participant chooses when to open one Realtime connection, capped
   at 60 seconds; direct chart work and written answers remain available afterward. Text/PTT and
   a second model window cannot silently change this contract.
4. Submit a recommendation, evidence, object origin, target charts, calculation scope and
   retained/released conditions. Filled answers establish submission, not correct understanding.
5. Finish retains completed, incomplete, abandoned and timed-out records. The formal report uses
   the first actual Begin per registered assignment, keeping repeats and missing trials explicit.

The eight `study_*` briefs permit participant-selected members or a ranking rule. They use only
public business constraints for live checks. Older `biz_`, `rev_` and `exp_` expected answers
remain authored diagnostics. A local-authored formal rehearsal is not a participant and does
not contribute to primary condition summaries.

Relevant endpoints:

| Endpoint | Meaning |
| --- | --- |
| `GET /api/experiment/plan?protocol=formal&slot=1` | Four assigned tasks and public briefs |
| `GET /api/experiment/formal-manifest` | Candidate materials, hashes, allocation and pending reviews |
| `POST /api/experiment/register` | Actual pseudonymous roster; includes people with no attempted tasks |
| `POST /api/experiment/start` with `protocol: formal` | Prepare the assigned condition and live-voice contract |
| `GET /api/experiment/report?protocol=formal` | First-attempt accounting plus independent outcomes |
| `GET /api/experiment/export?protocol=formal&format=json` | Original attempts, repeats, missing assignments and coding scores |
| `GET /api/experiment/export?protocol=formal&format=csv` | One row per registered assignment, including missing outcomes |

Registration body is `{participant_id, participant_slot}`. Start uses
`{participant_id, slot, trial_index, evidence_kind, protocol}`. The 30-slot plan is a schedule,
not a claim of thirty registered or observed people. See [FORMAL_STUDY.md](FORMAL_STUDY.md).

## Independent intent → SQL → report

Open an archived attempt and choose **Independent intent review**. This is a researcher
control surface; only the downloaded blinded packet and blank templates go to independent
coders. Do not ask blinded coders to browse the outcome-bearing archive first.

1. Declare the input onset, last input arrival and episode end using actual event indices.
   An episode can contain multiple repair requests. A genuine later goal change needs its own
   coding; the original intent is not retroactively imposed on the new goal.
2. Download the packet and two blank coder files. The packet contains prior user words, saved
   subsets, explicit choices, the public task, eligible prior states and current input. It excludes
   the focus request's model proposal, subsequent charts, expected answers and scores. Generated
   prior text is labelled as generated, not assumed heard.
3. Each coder independently labels targets, scope changes, membership rule, retained/released
   fields, evidence indices and rationale. `keep_current` preserves a selection rule; it does not
   freeze the current rows of a dynamic ranking. `fixed` needs explicit category IDs; `rank`
   needs a count and measure. Unresolved interpretations stay `unknown`.
4. Import both codings and an adjudicator's explicit resolution. Locking stores both originals,
   the resolution and a hash. Contradictory keep/change/release labels are rejected rather than
   silently ignored. Locking is an explicit human action, never a software-generated approval.
5. Before scoring, designate the final task episode. Its end must equal `trial_finished`, so an
   early successful edit cannot substitute for an incorrect final task state. Other episodes
   remain diagnostic; selecting the best score is not allowed.
6. Score using independent raw-table SQL. Scope and member equality, numeric values and
   denominators are checked separately. First-publication and final correctness are retained;
   intermediate partial changes are not automatically counted as repairs/errors. The scorer
   never uses `expected_sources`, the runtime revision compiler or model success wording.
7. Understanding is a separate explicit human review of four dimensions. Missing/stale answers
   are not graded as correct. An incorrect dimension makes the all-correct endpoint false;
   otherwise an unresolved dimension keeps it unknown. Acoustic listening and repair cost
   remain pending; event counts do not fill them.

The automatic endpoint covers intended analytical objects, scope and data. It does not prove
that the model reasoned from a particular historical source when two sources have identical
members. Origin is preserved in coding and operational provenance; the participant's account
of origin is separately reviewed. Presentation preferences, generated explanation truth and
acoustic listening are outside this SQL score.

Artifacts are stored under `traces/.../<session>/intent-episodes/<packet-id>/`:
`packet.json`, blank `coder-a.json`/`coder-b.json`/`adjudication.json`, `private.json`,
the explicit `locked.json`, `score.json`, and optional `understanding.json`.
The per-session `intent-episodes/primary.json` records the pre-score endpoint declaration.
These files are not read by model context builders or tools.

An offline equivalent is available without starting the app:

```powershell
.\.venv\Scripts\python.exe scripts\score_intent_episodes.py prepare --session-dir <archive> --onset 100 --utterance-end 108 --episode-end 150
# Two independent coders and an adjudicator complete the generated files.
.\.venv\Scripts\python.exe scripts\score_intent_episodes.py lock --session-dir <archive> --episode <packet-id>
.\.venv\Scripts\python.exe scripts\score_intent_episodes.py score --session-dir <archive> --episode <packet-id>
```

For the formal primary endpoint, use the UI's designation step before scoring. The offline
command can also score diagnostic episodes, which do not automatically enter the formal report.

## Analysis boundary

The formal report includes all registered assignments. It reports known success, known failure
and unknown counts, with lower/upper success bounds under unknown-as-failure/success. Original
failed and repeated attempts are retained; no successful-only duration estimate is generated.
Two tasks from the same participant in one condition are not independent participants.

Participant-level effect estimates, interval precision, joint primary-test adjustment and
repair coding follow the frozen analysis plan after human review. This delivery supplies the
data and independent outcome pipeline, not fabricated user-study statistics. Six-field response
rubrics, material difficulty, the one-minute speech fit, consent and meaningful-effect/precision
thresholds still require actual review before collection. The manuscript's empirical claims
must wait for those data.

Verification artifacts: `traces/route-delivery/`, `traces/normal-flow-fixes-20261113/`,
`traces/workspace-revision-20261113/`, `traces/formal-study-materials/` and
`traces/intent-review-ui-20261113/`. All local failures are retained alongside later checks.
