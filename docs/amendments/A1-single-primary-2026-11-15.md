# Amendment A1 — single primary outcome

- Date: 2026-11-15
- Status: confirmed
- Integrity: no participant outcomes, human intent labels, understanding judgments,
  or formal report rows were inspected to reach this decision.

## Decision

**Terminal intent-consistency** is the sole primary outcome of the B2-vs-B0 comparison.

## Outcomes

### Primary (one)

- **Terminal intent-consistency** — whether the terminal committed state matches the
  participant's independently coded, cumulative, still-active intent, scored against
  the trial-start state, across all assigned tasks.

### Secondary

- Interface-assisted interpretation accuracy, scored against the actual committed
  state, not desired intent.
- Repair funnel: detection, repair initiation, repair success.
- Interaction cost / time: time to terminal commit, turns, manual operations.
- Public-constraint completion.

### Descriptive only

- Overlap incidence.
- Reference dependence.
- `first_publication_consistent`.
- Window expiry.

## Estimand and inference

- Participant-level paired difference (B2 minus B0), two tasks per condition across
  four families.
- Cluster bootstrap over participants; Manski-style lower/upper bounds for unknown
  outcomes.
- Single primary outcome, so no Holm (or other joint) adjustment applies.

## Scope guards

- No post-hoc subset inference from overlap or reference-dependence strata.
- No component attribution within the B2 support package.
- No participant-benefit claims from implementation tests.
- Descriptive-only strata are never used to filter the primary sample.
