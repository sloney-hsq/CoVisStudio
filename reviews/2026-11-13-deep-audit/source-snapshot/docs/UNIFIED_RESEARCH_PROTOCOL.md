# CoVisStudio: unified revision-episode protocol

Version: `covis-revision-0.2-draft`, 2026-11-13. This document reconciles the current research direction and the implementation sequence. **Stage 1 instrumentation and the Jarvis-inspired application evidence/shared execution extensions are implemented; the full study protocol is not yet ready for participant collection.** It does not relabel old traces or claim that current `direct` and `bound_revision` already implement the comparison below.

Implementation update: `RESEARCH_EXECUTION_PLAN.md` fixes the next delivery sequence. Direct and bound now use the same analytical instructions and omit redundant treatment identifiers from model context/cards; application-level pre/post-context, reads, receipts and final-state parity passed offline. The shared native history policy remains retention with exact outbound archives, not a claim that all native content is frozen to playback. Independent intent packets are implemented and remain pending human coding. Full formal study readiness and real acceptance of the repaired transport sequence are not claimed.

## 1. Fixed question and scope

When a user verbally revises an ongoing analysis during assistant playback, does explicitly separating **referenced evidence, current computation scope, and requested changes** improve revision correctness and the user's understanding of the change, and at what interaction cost?

Both conditions use full-duplex voice. The experiment concerns support for revision within that environment, not whether full duplex is superior to text or turn-taking. Qwen `qwen3.8-omni-flash-realtime` is the shared voice model. Images, tools, saved category sets, history access, cancellation, commit rules and budget ceilings must be equivalent. Full duplex permits speech input while output plays; this does not establish incremental semantic understanding before a completed utterance.

The specific difficulty is that received/generated content, committed charts, visible charts and browser-played speech need not coincide. A reference to earlier evidence selects objects; it does not automatically restore the earlier region, dates or measures. The proposed support makes that distinction inspectable and correctable. Its value is an empirical question.

## 2. Two conditions only

| Condition | Shared capability | Planned difference |
| --- | --- | --- |
| B0: strong direct baseline | Current and historical evidence, exact saved-set creation/listing/reuse, same rendering and playback facts, same preservation guidance and clarification policy | Interprets the request and executes through shared tools; no structured revision card |
| B2: explicit revision support | Everything available to B0 | Exposes a correctable structure: evidence/object origin; current target views and changes; retained and released conditions |

The contrast estimates the effect of the support package. It cannot separately attribute an effect to a card, structured interpretation or verification. No extra condition, modality factor, artificial display delay or feedback policy comparison is added.

Current code-level clarification: both main conditions share member binding and the operation compiler. The treatment is visible, correctable revision support, not a stronger binding algorithm. An explicit unambiguous edit may commit before its card is inspected; that card supports understanding and subsequent repair, not guaranteed pre-commit prevention. Before any user response to the support, first-action model correctness cannot be attributed to seeing the card. See [the source-grounded claim review](RESEARCH_CLAIM_REVIEW.md) for the DataTone/CLEO/VoCa comparison and the unchanged two-condition analysis.

The current runtime still has `direct`, `bound_revision`, and historical `unbound_preview`. Direct and bound paths now share candidate resolution and member compilation. They are existing apparatus configurations, not yet a frozen participant-study contract: native-context parity, task materials and independent intent outcomes still require completion. The historical ablation remains available for old records but is not an added participant arm.

The execution update in `GOAL_EXECUTION.md` provides the same single-call `revise_analysis` route in both main conditions. Both may receive actual source/member differences in tool receipts; the B2 UI exposes the revision card while B0 retains its direct presentation. An internally generated card is not evidence that a participant saw or understood it. Request-outcome notices and failed-tool stop rules are shared infrastructure, not a new experimental treatment. The resulting UI/information contrast must still be audited when freezing participant materials.

Unambiguous requests do not require an extra confirmation click. Both conditions ask for clarification under the same unresolved-choice rule. Selecting an evidence card or saving a set does not authorize restoration of its old filters.

## 3. Business task and episode

Use the existing three-chart Olist workspace: orders, low-review rate, and delivery time. A business brief provides a purpose and genuine hard constraints, not a prescribed reference phrase or a preselected correct cohort. Participants can choose objects, examine evidence, preserve a previous selection, select a new one, or release it.

Example: investigate service issues in MG while comparing categories selected from a previous analysis. A participant may ask, during explanation, to use the group just discussed in the two service charts while retaining the current MG/date scope and leaving the orders chart unchanged. The saved historical group is one available candidate, not automatically the answer. Subsequent user statements can change that choice.

The four business families and existing matched versions are retained for task development. Existing `expected_sources` and scripted diagnostic answers must not be treated as participant intent. They remain valid only for the authored fixtures they describe.

An episode links preparation, delivered evidence, a user revision, clarification/repair if any, actual publications, and a subsequent understanding response. A request ID is transport/operation identity; it is not by itself an independently sampled research episode. An annotated episode may contain multiple requests and responses.

| Phase | Activity | Evidence |
| --- | --- | --- |
| A | Read business goal, inspect data and optionally save sets | Exact choices and their source versions |
| B | Move to current computation scope | Committed state and actual render/visibility |
| C | Listen and inspect during the designated voice window | Received chunks, browser playback positions and visible chart intervals |
| D | Speak a revision at a participant-chosen moment | One normalized onset, provider audio offsets, words and selected reference |
| E | Execute, clarify, correct or finish | Actual tool proposals, commits, rendered state and speech delivery |
| F | Answer the same understanding questions in both conditions | Participant account of object origin, targets, retained/released scope |

Do not force a natural-use participant to interrupt or produce a particular deictic phrase. Local authored playback tests deliberately inject an interruption and are separately labelled. A fixed ordinary presentation flow is shared by conditions; timing and candidate counts are not new manipulated variables.

The existing 480-second task timer and 60-second development voice-session cap are distinct. Stage 1 does not expand either. A future participant protocol must explicitly place the intended revision window within that cap; it cannot silently treat an eight-minute trial as eight minutes of voice access. There are no paid calls in this implementation verification.

## 4. Execution and evidence semantics

1. Speech onset immediately invalidates old local publication authority and sends playback stop. Upstream cancellation follows; it cannot gate local revocation.
2. Revocation does not undo a previously legal commit. An old result committed before onset remains legitimate evidence. Rejecting a later stale publication is different from rolling back an earlier one.
3. Browser playback progress estimates samples delivered on its AudioContext timeline. Received PCM and archived WAVs include unplayed material. Neither telemetry nor a WAV proves acoustic perception or comprehension.
4. Chart commit, ECharts render completion and exposure of a rendered plot are separate events. Visibility means positive plot intersection on a visible, enabled surface; it has no reading threshold.
5. Each event keeps raw time and origin. A calibrated timestamp is an estimate with its calibration record and uncertainty, never a replacement for raw clocks. No calibrated estimate means timing relation unknown.
6. The later evidence package must distinguish interpretation-time evidence from the actual current state used for execution. It must cover images, history, sets, tool reads and native provider conversation. A frozen JSON object alone does not freeze provider context.

The current extension implements points 1–5 with output-worklet receipts and archives dual-time application evidence for point 6. Actual outbound inputs are recorded, but native provider history is not isolated. Speech-to-semantic-segment alignment and an independent intent episode scorer remain pending. The new offline delivery/numeric audit does not substitute for intent scoring. See [JARVIS_ADAPTATION.md](JARVIS_ADAPTATION.md).

## 5. Ground truth and outcomes

Ground truth begins with the user's words, explicit choices and contemporaneously available evidence. Two independent human coders identify: referenced members/source, target views, requested changes, retained conditions, released conditions and unresolved ambiguity. They must not infer intended choices from the model's proposal or final chart. Resolve disagreements using the source evidence and retain uncertainty when it cannot be resolved.

Only after that intent specification is available does independent SQL calculate expected data. SQL validates data and scope; it cannot infer intent. Private annotations, expected results and coding decisions must never enter model inputs. Human listeners may inspect the original speech; hearing/understanding fields remain pending until actually reviewed.

| Outcome | Definition | Current status |
| --- | --- | --- |
| Revision correctness | Latest explicit request fulfilled on the intended views; still-valid conditions preserved; values match independent SQL | Existing authored trial checks only; new episode scorer pending |
| Understanding | Participant correctly identifies object origin, affected views and current computation scope | Responses can be captured; human assessment pending |
| Repair cost | Additional interaction attributable to correcting an identified misunderstanding or execution mistake | Requires human coding; Undo/edit counts alone are insufficient |
| Interaction time | Recorded expression, execution/response and repair intervals; incomplete outcomes retained | Stage 1 supplies aligned timing, not a completed statistical analysis |
| Playback/reference relevance | Evidence that a reference depends on the actually played portion, rather than just an explicit source label | Requires semantic alignment and annotation, pending |

A revision can be correct while later explanation is inaccurate. Record those separately. Ordinary exploration, intentional goal changes and intermediate unsynchronized views are not automatically failures or repair.

## 6. Analysis without selecting favorable episodes

All assigned tasks belong in the primary analysis, including non-overlap, failed, incomplete and intent-unknown cases. Do not restrict the primary B0/B2 comparison to episodes that happen to demonstrate the desired phenomenon. B2 itself may alter what users say or inspect.

Preserve original attempts. The existing apparatus selects the latest attempt for its descriptive archive summary; that is not automatically a valid primary research rule. Formal collection should use the assigned attempt as primary, retain repeats as repeats, and document rerun reasons independently of score. An unresolvable outcome is unknown, not automatically failure and not a silently excluded row. Report known-success and unknown counts, plus lower/upper success bounds under unknown-as-failure/success.

The existing four-trial within-participant allocation is the starting schedule, with two trials per condition, matched families/versions and balanced order. Thirty slots is an existing recruitment target, not a power guarantee. Participants remain the independent sampling units; four tasks from one person are not four participants.

Before formal collection, freeze an analysis plan based on the task definitions and feasibility variance, without inspecting B0–B2 benefit to tune materials. A concrete plan is: participant-level paired differences in correctness and understanding, with task-family/version/order accounted for using the balanced assignment; report effect sizes and participant-clustered uncertainty. If both are confirmatory endpoints, adjust the two tests together (e.g. Holm). Repair and time are secondary, with incomplete/time-limited cases explicitly retained. Do not use successful-only time means or non-significance as equivalence. Exact coding rubrics, meaningful-effect threshold and precision rationale remain required freeze items, not software defaults.

Within the same data, descriptive diagnostics may compare “latest set,” “set visible at onset,” and “earliest saved set.” They add no experimental arm. Different candidate results only prove that selection matters. They do not prove playback information is necessary; explicit references such as “the SP set” can be resolved without playback position. A playback-relevant case requires an independently supported reference whose interpretation actually depends on the delivered speech context.

Feasibility work checks timing coverage, missing telemetry, speech-window fit, intent ambiguity and whether ordinary materials offer opportunities for reference changes. It does not weaken B0 or exclude inconvenient episodes. If few episodes require playback evidence, report that limitation rather than claiming full-duplex-specific benefit.

## 7. Contribution and conclusion boundaries

The candidate contribution is a support mechanism and controlled evidence about revision correctness, understanding and cost in full-duplex analytical collaboration. Shared speech, pictures, saved sets and interruptibility are infrastructure; their existence is not the novelty claim.

If B2 improves correctness and understanding with measured costs, claim the package's benefit under the tested conditions. If only understanding improves, restrict the claim accordingly. If reliability improves with extra time, report the tradeoff. A precise null can bound the package's value relative to a strong baseline; an imprecise null or invalid measurement cannot. No result here establishes that a non-full-duplex system cannot perform the task.

## 8. Delivery gates

| Stage | Deliverable | Gate |
| --- | --- | --- |
| 1: implemented | Event identity, origin correlation, output-worklet sample receipts, chart exposure, clock calibration, single onset | Local units and actual-browser protocol-peer verification |
| 2: application layer implemented | Immutable dual-time package, source chain, shared history/set/image selection and exact outgoing payload archives | Native conversation is not isolated; do not claim complete provider-context freezing |
| 3: technical audit implemented | Independent delivery ledger and optional numeric SQL audit; participant-intent scorer pending | Technical report recomputes without model access; keep semantic outcomes pending |
| 4: compiler implemented | Shared candidate/set resolution and execution with origin/targets/kept-released card | Local parity verified; full participant configuration still needs freezing |
| 5 | Business-goal stages, interpretation response, participant/examiner split | Normal flow usable; real speech/listening and task annotations reviewed |
| 6 | Offline diagnostics and frozen analysis | No online mutation; reproducible outcomes and explicit unknowns |

The function-level implementation and current verification boundary are in [STAGE1_IMPLEMENTATION.md](STAGE1_IMPLEMENTATION.md). Old study and experiment documents remain historical apparatus specifications; this document takes priority for the next study design.
