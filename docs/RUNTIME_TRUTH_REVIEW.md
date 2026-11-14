# Runtime review after the external critique

This review checks the local source and the retained complete-flow failure.
It makes no new literature or novelty claim and does not run a paid model.

## Findings

- False completion is broader than supersession. Earlier Q1 failures must remain
  in the evidence record. A stale-receipt-specific fix cannot prove they are solved.
- Current code already refreshes instructions, chart context and eligible images
  in `Workspace.provider_event(response_prepare)` before native `response.create`.
  The failed archive also contains the v6 current dashboard in the sent
  `session.update` immediately before request 5. Its three charts still contain
  bed_bath_table, sports_leisure and health_beauty. Missing state is not established
  as the cause. Native internal interpretation cannot be reconstructed from this.
- The driver already had a no-commit terminal check. Its request association could
  remain on the prefix of a clip after a later VAD fragment superseded it. The
  wait now follows the latest onset/accepted request within that input stage.
  The archived failed stage itself records request 5, not request 4; this change
  is not evidence that a stale request ID caused that particular timeout. Replaying
  the archived events through the current terminal check finds `no_changes` at
  event 5147, server 34545.341 ms. That is an offline stop decision, not a measured
  reduction in paid connection time.
- A completed response with no commit may be legitimate discussion. It is not
  automatically a false claim, and the presence of a superseded call does not
  prove a semantic contradiction either.

## Changes

`Workspace.execution_state` derives the current request's actual commit revisions,
the current public version and six recent settled request outcomes from the
existing ledger. `context()` exposes it for every response preparation in both
conditions. The current dashboard remains the full source of current chart facts.
Shared instructions require using this record instead of assuming an earlier
spoken promise was executed. No additional model call or native-history deletion
is introduced.

`QwenRealtime._finish_stale_turn` asks the workspace for an authoritative receipt:
the current public revision, whether execution was attempted, and no public commit.
Never-invoked calls additionally say `executed:false`. Computed-but-uncommitted
work is not called unexecuted. Previously legal commits retain their committed
receipt and revision; subsequent supersession does not undo them. The original
request/response/call association remains intact.

The driver follows a clip's continuing VAD request until a commit or terminal
no-commit outcome. Explanation-only turns remain allowed. No tool is auto-issued,
and the runtime does not extend the 60-second budget or retry the test.

AGENTS.md now has one current agreement. B0/B2 are the primary conditions;
unbound_preview is historical diagnostic apparatus. Completed API authorizations
are not reusable authorization. Earlier recorded results remain in TASKS.md.

## Deliberately not implemented

- No keyword-based `claim_without_commit` semantic verdict. All terminal outcomes
  are already measured; subsequent model context now carries their execution
  facts. Human review is still required to label an utterance a false completion.
- No VAD threshold change, artificial delay, forced-tool mode, silent repair,
  extra coordinator model or new study condition.
- No claim that runtime context can guarantee truthful native speech. Audio may
  already have played before settlement. The patch supplies facts for the next
  response; whether the model uses them correctly still needs real verification.
- No new claim about UI legibility or participant benefit. The quoted review did
  not inspect source or screenshots; those observations remain review questions.

## Verification

Local native-handler tests script the same late old-tool sequence in B0 and B2.
One model behavior reissues the edit; the other only claims success. The tests
check actual Olist commits, unchanged state in the second case, truthful receipts,
next-response wire instructions and independent SQL. They do not estimate Qwen's
tool-selection success rate. The driver regression checks a terminal result on a
superseding VAD fragment, while ignoring the old fragment's outcome.

Actual checks in this delivery: the initial full backend run returned 389 passed
and two failed legacy assertions. One expected the old three-field receipt; the
other compared random session prefixes in newly exposed request IDs. The receipt
test now checks attempted computation without publication and absence of obsolete
rows. The parity audit normalizes only the random session prefix, preserving
request numbers and all execution facts. After those updates, all **46 tests** in
the affected seven test modules passed. The full suite was not repeated after
these updates. `git diff --check` passed. No paid model, UI redesign, human review
or participant experiment was run.

Future authorized real diagnostics should inspect one focused edit chain at a
time, with complete <=10-second input clips and <=60-second connections. Do not
claim the three-step real flow passed based on these offline checks.
