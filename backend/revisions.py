"""Reference historical evidence without restoring historical analysis conditions."""

from copy import deepcopy

from jsonschema import validate

from .charts import VIEW_IDS, _tool
from .data import SOURCE_SCHEMA


CONDITIONS = ("direct", "bound_revision", "unbound_preview")
EVIDENCE_SCHEMA = {
    "type": ["object", "null"],
    "properties": {
        "revision": {"type": "integer", "minimum": 0},
        "view_id": {"type": "string"},
        "members": {"type": "array", "items": {"type": "string"}, "minItems": 1, "uniqueItems": True},
    },
    "required": ["revision", "view_id"],
    "additionalProperties": False,
}
REVISION_PROPERTIES = {
    "evidence": EVIDENCE_SCHEMA,
    "candidate_id": {"type": "string", "minLength": 1, "description":
        "For use_evidence, omit this field to use the evidence selected at the start of the utterance. "
        "Supply an exact listed ID only when the user requests that source. Equal members do not make versions identical."},
    "view_ids": VIEW_IDS,
    "source_patch": SOURCE_SCHEMA,
    "member_action": {"type": "string", "enum": ["keep_current", "use_evidence", "rerank"]},
    "needs_confirmation": {"type": "boolean"},
    "question": {"type": "string"},
}
REVISION_SCHEMA = {
    "type": "object", "properties": REVISION_PROPERTIES,
    "required": ["view_ids", "source_patch", "member_action"], "additionalProperties": False,
}
MODEL_REVISION_PROPERTIES = {key: value for key, value in REVISION_PROPERTIES.items() if key != "evidence"}
REVISE_ANALYSIS_PROPERTIES = {
    **{key: value for key, value in MODEL_REVISION_PROPERTIES.items() if key != "source_patch"},
    **SOURCE_SCHEMA["properties"],
}
REVISE_ANALYSIS_SCHEMA = {
    "type": "object", "properties": REVISE_ANALYSIS_PROPERTIES,
    "required": ["view_ids", "member_action"], "additionalProperties": False,
}


def normalize_revise_analysis(arguments):
    """Validate flat model arguments and compile the existing private-preview payload."""
    validate(arguments, REVISE_ANALYSIS_SCHEMA)
    return {
        **{key: deepcopy(value) for key, value in arguments.items() if key in MODEL_REVISION_PROPERTIES},
        "source_patch": {key: deepcopy(value) for key, value in arguments.items()
                         if key in SOURCE_SCHEMA["properties"]},
    }


REVISION_TOOL_DEFINITIONS = [
    _tool(
        "revise_analysis",
        "Apply one analytical edit to exact current view_ids in a single call. Supply only changed "
        "query fields directly, such as start, end, region or metric; omitted fields stay current. "
        "keep_current preserves the current membership rule. use_evidence takes an exact candidate_id "
        "from list_evidence_candidates or the user's selected evidence; only category members are "
        "reused, never historical dates, region or metric. rerank releases fixed members and requires "
        "top_n and rank_by. Dates are inclusive start/exclusive end. Set needs_confirmation=true "
        "with a question only for an unresolved user choice; then the edit remains a preview. "
        "Explain success only from a committed result.",
        REVISE_ANALYSIS_PROPERTIES, ["view_ids", "member_action"],
    ),
    _tool(
        "preview_revision",
        "Prepare an analytical edit without publishing it. Select exact current target view_ids. "
        "source_patch changes only the specified current query conditions. keep_current preserves the "
        "existing membership rule unless the patch changes it. use_evidence uses an exact candidate_id "
        "or the user's selected evidence. In direct and bound_revision the exact "
        "members are bound automatically, while current region, dates and metrics stay unchanged "
        "unless explicitly patched. In historical unbound_preview, supply the intended categories and "
        "top_n=null in source_patch yourself; evidence remains inspectable but does not rewrite the patch. "
        "rerank requires source_patch.top_n and rank_by and releases fixed categories. Set "
        "needs_confirmation=true with a concrete question only when the user's choice is unresolved. "
        "The returned proposal is a preview, not a completed edit.",
        MODEL_REVISION_PROPERTIES, ["view_ids", "source_patch", "member_action"],
    ),
    _tool(
        "apply_revision",
        "Publish an existing preview_revision proposal if it is still current. A proposal needing "
        "confirmation must be resolved by the user first. Use the committed result, not the preview, "
        "when explaining what changed.",
        {"proposal_id": {"type": "string", "minLength": 1}}, ["proposal_id"],
    ),
]


def _read_evidence(snapshots, reference):
    if reference is None:
        return None
    snapshot = snapshots[reference["revision"]]
    view = next((view for view in snapshot["views"] if view["id"] == reference["view_id"]), None)
    if view is None:
        raise ValueError("The referenced chart is not present in that saved version.")
    if view["source"]["dimension"] != "category":
        raise ValueError("Historical category references must use a chart grouped by product category.")
    displayed = [row["label"] for row in view["data"]["rows"]]
    members = reference.get("members", displayed)
    if not members or not set(members).issubset(displayed):
        raise ValueError("Select category IDs actually displayed in the referenced chart.")
    return {
        "revision": reference["revision"], "view_id": view["id"],
        "number": view["number"], "title": view["title"],
        "source": deepcopy(view["source"]), "members": list(members),
        "available_members": displayed,
    }


def _membership(source):
    """Describe the query rule, separately from the rows it happened to return."""
    return {
        "mode": "fixed" if source["categories"] is not None else "ranked" if source["top_n"] is not None else "all",
        "dimension": source["dimension"], "categories": deepcopy(source["categories"]),
        "top_n": source["top_n"],
        "rank_by": source["rank_by"] if source["top_n"] is not None else None,
    }


def evidence_source(evidence, candidate=None):
    """Public source identity; members are recorded separately from version identity."""
    if evidence is None:
        return None
    return {"candidate_id": candidate["candidate_id"] if candidate else f"chart:{evidence['revision']}:{evidence['view_id']}",
            "label": candidate["label"] if candidate else f"Chart {evidence['number']} · version {evidence['revision']}",
            "revision": evidence["revision"], "view_id": evidence["view_id"],
            "members": list(evidence["members"])}


def prepare_revision(store, snapshots, payload, condition="bound_revision", resolved_candidate=None,
                     selected_evidence=None):
    """Build one private chart candidate and its observable source/member differences.

    Intent interpretation stays with the user/model. This function resolves an explicit
    evidence selection and patches current sources; it does not infer a desired answer.
    Request permission, proposal lifetime and user confirmation belong to Workspace.
    """
    validate(payload, REVISION_SCHEMA)
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown revision condition: {condition}")
    before = store.snapshot()
    member_action = payload["member_action"]
    if member_action != "use_evidence":
        evidence = None
    elif payload.get("candidate_id"):
        if resolved_candidate is None or resolved_candidate["candidate_id"] != payload["candidate_id"]:
            raise ValueError("Resolve the exact candidate ID from available evidence before preparing the edit.")
        if payload.get("evidence") is not None:
            raise ValueError("Choose either a candidate ID or a chart evidence reference.")
        evidence = deepcopy(resolved_candidate["evidence"])
        evidence["members"] = list(resolved_candidate["members"])
    else:
        evidence = _read_evidence(snapshots, payload.get("evidence") or selected_evidence)
    patch = deepcopy(payload["source_patch"])
    binding_applied = condition in ("direct", "bound_revision") and member_action == "use_evidence"
    if binding_applied:
        if evidence is None:
            raise ValueError("Choose the saved chart whose categories should be used.")
        if "categories" in patch and (patch["categories"] is None or set(patch["categories"]) != set(evidence["members"])):
            raise ValueError("Explicit categories conflict with the chosen evidence. Resolve the selection before applying it.")
        if patch.get("top_n") is not None:
            raise ValueError("Using historical categories cannot also request a new ranking.")
        patch.update(categories=list(evidence["members"]), top_n=None)
    elif member_action == "rerank":
        if patch.get("top_n") is None or "rank_by" not in patch:
            raise ValueError("Re-ranking requires an explicit top_n and rank_by.")
        if patch.get("categories") is not None:
            raise ValueError("Re-ranking releases fixed categories; do not provide a fixed member list.")
        patch["categories"] = None

    prepared = store.prepare("edit_charts", {"view_ids": payload["view_ids"], "patch": {"source": patch}})
    previous = {view["id"]: view for view in before["views"]}
    candidate = {view["id"]: view for view in prepared["candidate"]["views"]}
    selected = evidence_source(selected_evidence)
    executed = evidence_source(evidence, resolved_candidate) if binding_applied else None
    overrides = (selected["candidate_id"] != executed["candidate_id"] if selected and executed else None)
    provenance = {"selected_source_at_onset": selected, "executed_source": executed,
                  "source_basis": ("not_used" if executed is None else
                      "selection" if not payload.get("candidate_id") and not payload.get("evidence") else
                      "explicit_override" if overrides else "explicit_match" if selected else "explicit"),
                  "overrides_selection": overrides,
                  "members_equal": set(selected["members"]) == set(executed["members"]) if selected and executed else None}
    changes = []
    for view_id in payload["view_ids"]:
        old, new = previous[view_id], candidate[view_id]
        if binding_applied:
            new["membership_origin"] = deepcopy(executed)
        elif member_action == "rerank":
            new.pop("membership_origin", None)
        changed = [field for field, value in new["source"].items() if old["source"][field] != value]
        changes.append({
            "view_id": view_id, "number": new["number"],
            "before_source": deepcopy(old["source"]), "after_source": deepcopy(new["source"]),
            "before_members": [row["label"] for row in old["data"]["rows"]],
            "after_members": [row["label"] for row in new["data"]["rows"]],
            "before_membership": _membership(old["source"]),
            "after_membership": _membership(new["source"]),
            "changed_fields": changed,
            "released_fields": [field for field in changed
                                if old["source"][field] is not None and new["source"][field] is None],
            "kept_fields": [field for field in new["source"] if field not in changed],
        })
    card = {
        "execution_provenance": provenance,
        "base_revision": prepared["base_revision"],
        "evidence": evidence, "view_ids": list(payload["view_ids"]),
        "candidate_id": payload.get("candidate_id"),
        "origin": (deepcopy(resolved_candidate) if evidence and payload.get("candidate_id") else
                   {"origin": "chart", "label": f"Chart {evidence['number']}  /  version {evidence['revision']}"}
                   if evidence else None),
        "member_action": member_action, "binding_applied": binding_applied,
        "source_patch": deepcopy(patch),
        "changed_view_ids": [view_id for view_id in payload["view_ids"]
                             if previous[view_id] != candidate[view_id]],
        "kept_view_ids": [view_id for view_id in previous
                          if previous[view_id] == candidate[view_id]],
        "untouched_views": [{
            "view_id": view["id"], "number": view["number"],
            "source": deepcopy(view["source"]),
            "members": [row["label"] for row in view["data"]["rows"]],
            "membership": _membership(view["source"]),
        } for view in prepared["candidate"]["views"] if view["id"] not in payload["view_ids"]],
        "changes": changes, "needs_confirmation": payload.get("needs_confirmation", False),
        "question": payload.get("question", ""),
    }
    prepared["result"]["views"] = [deepcopy(candidate[view_id]) for view_id in payload["view_ids"]]
    prepared["result"]["tool"] = "apply_revision"
    return {"prepared": prepared, "card": card}
