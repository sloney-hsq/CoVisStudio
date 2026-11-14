"""One transactional chart surface, shared by direct manipulation and model tools."""

from copy import deepcopy
from threading import RLock

from jsonschema import validate

from .data import METRICS, SOURCE_SCHEMA, normalize_source


CHART_TYPES = ["bar", "line", "area", "pie", "scatter", "heatmap"]
STYLE_SCHEMA = {"type": "object", "properties": {
    "color": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
    "show_labels": {"type": "boolean"},
    "sort": {"type": "string", "enum": ["source", "ascending", "descending"]},
}, "additionalProperties": False}
PATCH_SCHEMA = {"type": "object", "minProperties": 1, "properties": {
    "title": {"type": "string", "minLength": 1},
    "chart_type": {"type": "string", "enum": CHART_TYPES},
    "source": SOURCE_SCHEMA, "style": STYLE_SCHEMA,
}, "additionalProperties": False}
VIEW_IDS = {"type": "array", "items": {"type": "string"}, "minItems": 1, "uniqueItems": True}


def _tool(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}}}


TOOL_DEFINITIONS = [
    _tool("read_dashboard", "Read the committed dashboard, stable chart IDs, saved queries, exact data and actual rate denominators. Does not recalculate or modify charts.", {}),
    _tool("create_chart", "Create one chart from real Olist. Numeric values cannot be supplied. Dates are inclusive start/exclusive end. Use the same explicit categories and top_n=null across comparison charts; a dynamic top_n re-ranks when the scope changes. Pie supports revenue, or order counts grouped by month/state; rates and means are not parts of a whole.",
          {"title": {"type": "string", "minLength": 1}, "chart_type": {"type": "string", "enum": CHART_TYPES}, "source": SOURCE_SCHEMA, "style": STYLE_SCHEMA}, ["title", "chart_type", "source"]),
    _tool("edit_charts", "Edit the exact listed chart IDs atomically. Source/style patches preserve all unspecified keys. Query changes recompute real data. To keep current categories, read their IDs then set categories and top_n=null; to re-rank set categories=null and top_n. Chart IDs never mean array positions. A selected reference identifies objects; it does not silently widen editing to other charts.",
          {"view_ids": VIEW_IDS, "patch": PATCH_SCHEMA}, ["view_ids", "patch"]),
    _tool("remove_charts", "Remove only the exact chart IDs; remaining chart numbers stay unchanged.", {"view_ids": VIEW_IDS}, ["view_ids"]),
    _tool("set_dashboard", "Rename the dashboard without changing chart data or filters.", {"title": {"type": "string", "minLength": 1}}, ["title"]),
    _tool("arrange_charts", "Arrange the dashboard without querying data. Supply every current chart ID exactly once in display order, and choose two or three columns. Stable chart numbers and analysis conditions are unchanged.",
          {"view_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
           "columns": {"type": "integer", "enum": [2, 3]}}, ["view_ids", "columns"]),
]
_SCHEMAS = {tool["function"]["name"]: tool["function"]["parameters"] for tool in TOOL_DEFINITIONS}


class ChartStore:
    def __init__(self, data):
        self.data = data
        self.state = {"revision": 0, "title": "Untitled dashboard", "views": [], "layout": {"columns": 3}}
        self._next_number = 1
        self._lock = RLock()

    def snapshot(self):
        with self._lock:
            return deepcopy(self.state)

    def prepare(self, name, args, reference=None):
        validate(args, _SCHEMAS[name])
        before = self.snapshot()
        if name == "read_dashboard":
            return {"base_revision": before["revision"], "candidate": None, "result": {"tool": name, "summary": "Read current dashboard", **before}}
        candidate = deepcopy(before)
        changed = []
        if name == "create_chart":
            with self._lock:
                number = self._next_number
                self._next_number += 1
            view = {"id": f"v{number}", "number": number, "title": args["title"],
                    "chart_type": args["chart_type"], "source": normalize_source(args["source"]),
                    "style": {"color": "#238579", "show_labels": False, "sort": "source", **args.get("style", {})}}
            self._validate_chart(view)
            view["data"] = self.data.query(view["source"])
            candidate["views"].append(view)
            changed = [view["id"]]
            summary = f"Created chart {number}: {view['title']}"
        elif name in ("edit_charts", "remove_charts"):
            lookup = {view["id"]: view for view in candidate["views"]}
            unknown = set(args["view_ids"]) - lookup.keys()
            if unknown:
                raise ValueError(f"Unknown chart IDs: {', '.join(sorted(unknown))}. Read the dashboard to find current IDs.")
            changed = list(args["view_ids"])
            if name == "remove_charts":
                candidate["views"] = [view for view in candidate["views"] if view["id"] not in changed]
                summary = f"Removed {len(changed)} chart(s)"
            else:
                patch = args["patch"]
                for view_id in changed:
                    view = lookup[view_id]
                    old_source = deepcopy(view["source"])
                    for field in ("title", "chart_type"):
                        if field in patch:
                            view[field] = patch[field]
                    if "source" in patch:
                        view["source"] = normalize_source({**view["source"], **patch["source"]})
                        if "metric" in patch["source"] and "title" not in patch:
                            view["title"] = METRICS[view["source"]["metric"]]["label"]
                    if "style" in patch:
                        view["style"].update(patch["style"])
                    self._validate_chart(view)
                    if view["source"] != old_source:
                        view["data"] = self.data.query(view["source"])
                summary = f"Updated {len(changed)} chart(s)"
        elif name == "arrange_charts":
            lookup = {view["id"]: view for view in candidate["views"]}
            if set(args["view_ids"]) != lookup.keys():
                raise ValueError("Supply every current chart ID exactly once to arrange the dashboard.")
            candidate["views"] = [lookup[view_id] for view_id in args["view_ids"]]
            candidate["layout"] = {"columns": args["columns"]}
            changed = list(args["view_ids"])
            summary = f"Arranged {len(changed)} chart(s) in {args['columns']} columns"
        else:
            candidate["title"] = args["title"]
            summary = f"Renamed dashboard to {args['title']}"
        return {"base_revision": before["revision"], "candidate": candidate,
                "result": {"tool": name, "summary": summary, "changed_view_ids": changed,
                           "views": [deepcopy(view) for view in candidate["views"] if view["id"] in changed]}}

    @staticmethod
    def _validate_chart(view):
        source = view["source"]
        if view["chart_type"] == "pie" and (source["metric"] in ("low_review_rate", "avg_delivery_days") or source["metric"] == "orders" and source["dimension"] == "category"):
            raise ValueError("Pie slices require additive values. Use revenue, or orders grouped by month/state; category order counts can overlap and rates/means are not additive.")

    def commit(self, prepared):
        with self._lock:
            if prepared["candidate"] is None:
                return {"state": deepcopy(self.state), "result": {**prepared["result"], "committed": False}}
            if prepared["base_revision"] != self.state["revision"]:
                raise ValueError("The dashboard changed while this edit was being prepared. The edit was not committed.")
            self.state = deepcopy(prepared["candidate"])
            self.state["revision"] += 1
            return {"state": deepcopy(self.state), "result": {**prepared["result"], "committed": True, "revision": self.state["revision"]}}

    def restore(self, snapshot):
        with self._lock:
            revision = self.state["revision"] + 1
            self.state = deepcopy(snapshot)
            self.state["revision"] = revision
            self._next_number = max(self._next_number, max((v["number"] for v in self.state["views"]), default=0) + 1)
            return {"state": deepcopy(self.state), "result": {"tool": "restore", "summary": "Restored an earlier dashboard", "committed": True, "revision": revision,
                                                             "changed_view_ids": [v["id"] for v in self.state["views"]]}}
