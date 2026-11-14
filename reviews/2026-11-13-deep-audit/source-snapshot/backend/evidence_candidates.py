"""Concrete evidence options. Selection belongs to the user or model, never this module."""
from copy import deepcopy

from jsonschema import validate

from .charts import VIEW_IDS, _tool
from .data import SOURCE_SCHEMA
from .revisions import prepare_revision

LIST_CANDIDATES_TOOL = _tool(
    "list_evidence_candidates",
    "List available actual chart category groups and immutable saved sets. Choose an exact returned candidate_id; this list does not select a preferred answer.", {},
)
APPLY_CANDIDATE_TOOL = _tool(
    "apply_evidence_candidate",
    "Reuse an exact listed candidate's category members on CURRENT view_ids. Preserve all current source fields unless explicitly patched. Never restore historical filters. Shared in direct and bound_revision.",
    {"candidate_id": {"type": "string", "minLength": 1}, "view_ids": VIEW_IDS,
     "source_patch": SOURCE_SCHEMA}, ["candidate_id", "view_ids"],
)
EVIDENCE_CANDIDATE_TOOL_DEFINITIONS = [LIST_CANDIDATES_TOOL, APPLY_CANDIDATE_TOOL]


def build_candidates(snapshots, saved_sets):
    candidates = []
    for revision, snapshot in sorted(snapshots.items()):
        for view in snapshot["views"]:
            if view["source"]["dimension"] != "category":
                continue
            members = [row["label"] for row in view["data"]["rows"]]
            if not members:
                continue
            evidence = {"revision": revision, "view_id": view["id"], "number": view["number"],
                        "title": view["title"], "source": deepcopy(view["source"]),
                        "members": list(members), "available_members": list(members)}
            candidates.append({"candidate_id": f"chart:{revision}:{view['id']}", "origin": "chart",
                               "revision": revision, "view_id": view["id"],
                               "label": f"Chart {view['number']} · version {revision} · {view['title']}",
                               "members": members, "source": deepcopy(view["source"]), "evidence": evidence})
    for saved in saved_sets:
        evidence = deepcopy(saved["evidence"])
        evidence.update(members=list(saved["members"]), available_members=list(saved["members"]))
        candidates.append({"candidate_id": f"set:{saved['id']}", "origin": "saved_set",
                           "set_id": saved["id"], "label": f"Saved set: {saved['name']}",
                           "members": list(saved["members"]), "source": deepcopy(evidence["source"]),
                           "evidence": evidence})
    return candidates


def resolve_candidate(candidate_id, candidates):
    for candidate in candidates:
        if candidate["candidate_id"] == candidate_id:
            return deepcopy(candidate)
    raise ValueError("Unknown evidence candidate ID. List available candidates and choose an exact ID.")


def prepare_candidate_apply(store, candidate, args):
    validate(args, APPLY_CANDIDATE_TOOL["function"]["parameters"])
    payload = {"candidate_id": args["candidate_id"], "view_ids": args["view_ids"],
               "source_patch": args.get("source_patch", {}), "member_action": "use_evidence"}
    compiled = prepare_revision(store, {}, payload, "direct", resolved_candidate=candidate)
    prepared = compiled["prepared"]
    prepared["result"].update(tool="apply_evidence_candidate", evidence_candidate=deepcopy(candidate),
                               revision_card=compiled["card"])
    return prepared
