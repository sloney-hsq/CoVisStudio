"""The six tools advertised to the model; internal store and REST tool names are unchanged.

Fewer routes for the same edit: every analytical query change goes through
revise_analysis (keep_current / use_evidence / rerank), historical and saved-set reuse
goes through its candidate_id, and presentation-only changes cannot alter a query.
Both study conditions advertise exactly this list.
"""
from copy import deepcopy

from .charts import CHART_TYPES, STYLE_SCHEMA, TOOL_DEFINITIONS, VIEW_IDS, _tool
from .evidence_candidates import LIST_CANDIDATES_TOOL
from .revisions import REVISION_TOOL_DEFINITIONS


def _definition(definitions, name):
    return deepcopy(next(tool for tool in definitions if tool["function"]["name"] == name))


READ_DASHBOARD_TOOL = _tool(
    "read_dashboard",
    "Read committed chart state. Omit revision for the current dashboard (stable chart IDs, saved "
    "queries, exact data, rate denominators) plus an index of earlier versions. Give revision to read "
    "that earlier version's complete state. Reading never edits, restores or recalculates charts.",
    {"revision": {"type": "integer", "minimum": 0}},
)
STYLE_CHARTS_TOOL = _tool(
    "style_charts",
    "Change only presentation of exact view_ids: title, chart_type or style. Never changes a query; "
    "use revise_analysis for region, dates, status, metric, categories or ranking.",
    {"view_ids": VIEW_IDS, "title": {"type": "string", "minLength": 1},
     "chart_type": {"type": "string", "enum": CHART_TYPES}, "style": STYLE_SCHEMA},
    ["view_ids"],
)
MANAGE_DASHBOARD_TOOL = _tool(
    "manage_dashboard",
    "Dashboard housekeeping without querying data. action=remove deletes exact view_ids (other chart "
    "numbers stay). action=arrange orders every current chart ID exactly once and sets columns (2 or 3). "
    "action=rename sets the dashboard title.",
    {"action": {"type": "string", "enum": ["remove", "arrange", "rename"]},
     "view_ids": VIEW_IDS, "columns": {"type": "integer", "enum": [2, 3]},
     "title": {"type": "string", "minLength": 1}},
    ["action"],
)

MODEL_TOOL_DEFINITIONS = [
    READ_DASHBOARD_TOOL,
    deepcopy(LIST_CANDIDATES_TOOL),
    _definition(REVISION_TOOL_DEFINITIONS, "revise_analysis"),
    _definition(TOOL_DEFINITIONS, "create_chart"),
    STYLE_CHARTS_TOOL,
    MANAGE_DASHBOARD_TOOL,
]
MODEL_TOOL_NAMES = tuple(tool["function"]["name"] for tool in MODEL_TOOL_DEFINITIONS)


def to_internal(name, arguments):
    """Map one validated, compiled model call to the existing internal tool call.

    Raises ValueError for a combination the flat schema cannot express (for example
    action=remove without view_ids); the caller records it as a failed tool.
    """
    args = deepcopy(arguments)
    if name == "read_dashboard":
        return ("read_history", args) if "revision" in args else ("read_dashboard", {})
    if name in ("list_evidence_candidates", "revise_analysis", "create_chart"):
        return name, args
    if name == "style_charts":
        patch = {key: args[key] for key in ("title", "chart_type", "style") if key in args}
        if not patch:
            raise ValueError("style_charts needs title, chart_type or style.")
        return "edit_charts", {"view_ids": args["view_ids"], "patch": patch}
    if name == "manage_dashboard":
        action = args["action"]
        if action == "remove":
            if "view_ids" not in args:
                raise ValueError("action=remove requires view_ids.")
            return "remove_charts", {"view_ids": args["view_ids"]}
        if action == "arrange":
            if "view_ids" not in args or "columns" not in args:
                raise ValueError("action=arrange requires every current view_id and columns.")
            return "arrange_charts", {"view_ids": args["view_ids"], "columns": args["columns"]}
        if "title" not in args:
            raise ValueError("action=rename requires title.")
        return "set_dashboard", {"title": args["title"]}
    raise ValueError(f"Unknown model tool: {name}")
