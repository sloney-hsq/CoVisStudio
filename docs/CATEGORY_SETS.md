# Reusable category sets

`save_category_set`, `list_category_sets` and `apply_category_set` provide the same deterministic member reuse in every study condition. A user or model can save displayed historical categories and apply the returned set ID without transcribing category names. This supplies a simple direct-edit alternative to the full evidence-linked revision card.

The session owns one `CategorySets` instance. `save(snapshots, args)` accepts `{name, revision, view_id, members?}`. The version must be saved and the chart must be grouped by category. Omit `members` to save every displayed category, or provide a subset actually present in that chart. Saving does not publish a chart edit.

Saved entries are `{id, name, members, evidence: {revision, view_id, number, title, source}}`. IDs such as `cs1` are stable within the session; names are labels, not lookup keys. Members and provenance are copied at save time and remain unchanged when the original chart is edited or reranked. `list()` returns copies. A new session starts a new collection.

`prepare_apply(store, args)` accepts `{set_id, view_ids, source_patch?}` and returns a normal `ChartStore.prepare` result. `view_ids` must explicitly identify current target charts. Each chart keeps its current source except for fields explicitly patched, saved `categories`, and `top_n=null`. Historical region, dates and metrics are provenance only. A conflicting category list or new ranking is rejected. The same saved members supplied in another order are accepted; the saved order is used.

Workspace owns request permission, logging and publication. Application uses the existing `edit_charts` preparation and `ChartStore.commit` checks. The result identifies `apply_category_set` and includes the saved `category_set`. It creates no separate proposal or revision card. Normal edits can later release fixed membership and request a new ranking without altering the saved set.

Local validation: `tests/test_category_sets.py` uses real Olist and independent raw-table numeric checks. It covers subset saving without public mutation, immutable member reuse, current MG/source preservation, explicit metric changes, exact target scope, ordinary invalid references and member conflicts, and stale candidate rejection. This verifies execution semantics, not model understanding, participant benefit or the effectiveness of the complete revision mechanism.
