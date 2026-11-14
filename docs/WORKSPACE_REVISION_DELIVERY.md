# Workspace revision support — local delivery

The main assistant pane now shows **Sources / Change / Keep & release** for `bound_revision`. The default card uses actual proposal values in a compact summary; **Details** expands the original before/after values without covering the charts. Modify and Apply remain visible in the assistant viewport at 1920, 2560 and 3840 CSS widths. The existing chart layout, history, saved sets and execution paths are retained.

Both direct and bound conditions expose the same Apply, Modify and Close controls. Direct omits the structured card. Explicit edits still use the existing automatic execution rule; no new mandatory confirmation is added. Publication/rendering is explicitly distinguished from the user's Apply confirmation.

## Normal-flow changes

- Modify reconstructs the original candidate, target IDs and source patch, including model proposals and reranking. A local authored patch is preserved exactly. The editor can choose another saved category set without resetting the other fields.
- Close records `revision_panel_closed`; only Modify records `revision_card_revision_requested`. Existing visible/hidden intervals, explicit openings and successful Apply observations remain separate.
- A request that commits and then fails or awaits a further choice keeps its committed revision, affected chart numbers and Displayed fact. A later action cannot erase the earlier legal publication.
- Removing the final chart acknowledges the post-DOM empty canvas, releases existing render waiters and sends the existing explicit empty context. It records `canvas_rendered {empty:true}` without inventing a chart-render event.
- Hidden preparation canvases do not produce chart/card exposure. Participant settings, researcher reports and assignment controls remain outside the participant finish/next-task flow.
- Finish saves the current response before the terminal request. Participant Finish opens the answer form, then **Save response and finish** completes it. Draft edits are separately recorded as `task_response_draft`; an unsaved timeout draft is not described as submitted.

## Formal material integration

The researcher can select formal business-decision materials or historical authored diagnostics. Formal assignments use the shared live-voice mode, lock the mode switches and consume `voice_window_used` from bootstrap and voice receipts. A completed voice window shows **Voice window complete. Continue with chart controls.** This UI verification does not establish a real provider connection or acoustic listening.

Formal responses retain the four existing fields and add affected charts and kept/released conditions. Formal reports display known correct, known incorrect and unknown outcomes plus missing assignments. Local authored formal records remain inspectable outside the participant denominator. JSON/CSV export requests carry the selected protocol.

## Files

`App.vue` owns orchestration and surface state. `RevisionSupport.vue`, `RevisionSummary.vue` and `RevisionDetails.vue` reuse actual proposal data for shared controls and the bound presentation. `RevisionPanel.vue` remains the local editor. `revision.js` handles correction seeding; `revisionDisplay.js` centralizes value labels. `toolFeedback.js` preserves actual partial publications. `ExperimentPanel.vue` presents formal setup/reporting; `style.css` keeps response/editor values readable. Focused regressions are in `revision.test.js` and `toolFeedback.test.js`.

No backend code, shared README/TASKS, model configuration or credentials were changed by this frontend delivery.

## Actual verification and limits

Evidence index: `traces/workspace-revision-20261113/verification-index.json`.

- Frontend suite: **47 passed**, including the concurrently delivered intent-review tests; the four tests added in this work cover correction seeding and partial receipts.
- Production build passed. The existing ECharts chunk-size advisory remains.
- Final actual browser flow: **32/32 checks passed**, no page errors. `browser-010843/report.json` and screenshots cover the three desktop widths, shared confirmation, correction, real Olist commits, empty context, observation distinctions, response-before-terminal ordering, participant flow and formal unknown/archival presentation.
- The isolated browser service used port 8079, explicitly disabled model endpoints and a blank key. It closed after verification. No existing user service was restarted.

These are authored local checks. The formal voice-window UI test consumes an authored closure receipt; it is not a real voice-budget test. A historical participant-surface fixture uses participant metadata solely to exercise that interface inside the isolated test directory; no participants were recruited. Business correctness, intent, understanding, listening and support effectiveness remain human/research questions.

Original failures remain: the first run exposed the overly broad backend `revision_card_*` observation prefix, so the frontend Close event was named outside that prefix; it also used an incorrect harness image-field name. A later harness rewrite corrupted one Unicode locator, and an added voice-closure fixture was initially injected before Begin's HTTP hydration finished. The final harness waits for the normal enabled controls. No retry/recovery layer was added to the application.
