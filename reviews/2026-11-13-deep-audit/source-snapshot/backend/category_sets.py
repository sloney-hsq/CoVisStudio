"""Reusable historical category members, independent of current query scope."""

from copy import deepcopy

from jsonschema import validate

from .charts import VIEW_IDS, _tool
from .data import SOURCE_SCHEMA
from .revisions import EVIDENCE_SCHEMA, _read_evidence


CATEGORY_SET_TOOL_DEFINITIONS = [
    _tool(
        "save_category_set",
        "Save an immutable named category set from an actual saved chart version. "
        "Use revision and view_id from read_history or the current saved dashboard. "
        "Omit members to save all displayed categories, or select an exact displayed subset. "
        "The returned stable set ID can be reused without copying category names. "
        "Saving does not edit charts or restore the source version.",
        {"name": {"type": "string", "minLength": 1, "pattern": "\\S"},
         **EVIDENCE_SCHEMA["properties"]},
        ["name", "revision", "view_id"],
    ),
    _tool(
        "list_category_sets",
        "Read the saved category sets in this session, including stable IDs, members "
        "and historical provenance. Does not edit charts.",
        {},
    ),
    _tool(
        "apply_category_set",
        "Apply a saved category set to exact CURRENT view_ids. All conditions support "
        "this same deterministic reuse. Preserve each current chart's region, dates, "
        "status, dimension and metric unless explicitly changed in source_patch. "
        "Set fixed categories from the saved set and clear top_n; do not restore the "
        "historical source. Do not request a conflicting category list or ranking. "
        "This is a direct edit through the normal chart commit, without a revision preview.",
        {"set_id": {"type": "string", "minLength": 1}, "view_ids": VIEW_IDS,
         "source_patch": SOURCE_SCHEMA},
        ["set_id", "view_ids"],
    ),
]
_SCHEMAS = {tool["function"]["name"]: tool["function"]["parameters"]
            for tool in CATEGORY_SET_TOOL_DEFINITIONS}


class CategorySets:
    """Session-local immutable sets; Workspace owns permission and commit timing."""

    def __init__(self):
        self._sets = {}

    def save(self, snapshots, args):
        validate(args, _SCHEMAS["save_category_set"])
        if args["revision"] not in snapshots:
            raise ValueError("The referenced version is not saved. Read history to find an available revision.")
        reference = {key: args[key] for key in ("revision", "view_id", "members") if key in args}
        evidence = _read_evidence(snapshots, reference)
        saved = {
            "id": f"cs{len(self._sets) + 1}", "name": args["name"].strip(),
            "members": list(evidence["members"]),
            "evidence": {key: deepcopy(evidence[key])
                         for key in ("revision", "view_id", "number", "title", "source")},
        }
        self._sets[saved["id"]] = saved
        return deepcopy(saved)

    def list(self):
        return deepcopy(list(self._sets.values()))

    def prepare_apply(self, store, args):
        validate(args, _SCHEMAS["apply_category_set"])
        if args["set_id"] not in self._sets:
            raise ValueError("Unknown category set ID. List saved category sets to choose an available set.")
        saved = self._sets[args["set_id"]]
        from .evidence_candidates import build_candidates, prepare_candidate_apply
        candidate = build_candidates({}, [saved])[0]
        prepared = prepare_candidate_apply(store, candidate, {
            "candidate_id": candidate["candidate_id"], "view_ids": args["view_ids"],
            "source_patch": args.get("source_patch", {}),
        })
        prepared["result"].update(
            tool="apply_category_set",
            summary=f"Applied category set {saved['name']} to {len(args['view_ids'])} chart(s)",
            category_set=deepcopy(saved),
        )
        return prepared
