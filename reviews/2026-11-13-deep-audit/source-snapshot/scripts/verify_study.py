"""Run authored local study paths through HTTP. This is NOT model evaluation."""

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import create_app
from backend.study import legacy_tasks


def modifications(task_id, views):
    family, kind = task_id.rsplit("_", 1)
    regions = ["MG"] * 3 if kind == "linked" else ["MG", "RJ", "PR"]
    periods = [("2017-01-01", "2017-04-01")] * 3 if kind == "linked" else [
        ("2017-01-01", "2017-04-01"), ("2017-04-01", "2017-07-01"), ("2017-07-01", "2017-10-01")]
    for index, view in enumerate(views):
        patch = {}
        if family in ("region", "rerank", "metric", "scope"):
            patch["region"] = regions[index]
        if family in ("quarter", "quarter_rank", "scope"):
            patch.update(start=periods[index][0], end=periods[index][1])
        if family in ("rerank", "quarter_rank"):
            patch.update(categories=None, top_n=3, rank_by="orders")
        if family == "metric":
            patch["metric"] = ["revenue", "avg_delivery_days", "low_review_rate"][index]
        yield {"name": "edit_charts", "arguments": {"view_ids": [view["id"]], "patch": {"source": patch}},
               "label": "Authored local validation edit"}


def main():
    output = ROOT / "traces" / "study-verification"
    settings = {"api_key": "", "text_model": "not-called", "realtime_model": "not-called", "voice": "Maia",
                "text_url": "http://127.0.0.1:9/not-called", "realtime_url": "ws://127.0.0.1:9/not-called",
                "data_dir": Path("C:/VerbalVis/datasets/olist/data"), "trace_dir": output / "sessions"}
    results = []
    member_contrast = {}
    with TestClient(create_app(settings)) as client:
        for mode in ("text", "push_to_talk", "live_voice"):
            for task in legacy_tasks():
                if task["id"] == "starter":
                    continue
                response = client.post("/api/session", json={"mode": mode, "task_id": task["id"], "participant_id": "local-author-validation"})
                response.raise_for_status()
                bootstrap = response.json()
                for operation in modifications(task["id"], bootstrap["state"]["views"]):
                    edited = client.post("/api/tools", json=operation)
                    edited.raise_for_status()
                report = client.post("/api/finish").json()["report"]
                exported = client.get("/api/export").json()
                if mode == "text" and task["id"] in ("region_linked", "rerank_linked"):
                    member_contrast[task["id"]] = {"region": exported["final"]["views"][0]["source"]["region"],
                        "members": [row["label"] for row in exported["final"]["views"][0]["data"]["rows"]]}
                (output / f"{mode}-{task['id']}.json").write_text(json.dumps(exported, indent=2), encoding="utf-8")
                results.append({"mode": mode, "task_id": task["id"], "completed": report["completed"],
                                "checks": len(report["checks"]), "review_status": report["review_status"],
                                "session_id": bootstrap["session"]["id"]})
        # Preserve an intentionally unfinished trajectory to check reporting semantics.
        client.post("/api/session", json={"mode": "text", "task_id": "region_linked"}).raise_for_status()
        client.post("/api/tools", json={"name": "edit_charts", "arguments": {"view_ids": ["v1"], "patch": {"source": {"region": "MG"}}}}).raise_for_status()
        failed_report = client.post("/api/finish").json()["report"]
        (output / "unfinished-example.json").write_text(json.dumps(client.get("/api/export").json(), indent=2), encoding="utf-8")
    summary = {"kind": "authored-local-tool-validation", "paid_api_calls": 0, "results": results,
               "passed_paths": sum(r["completed"] for r in results), "total_paths": len(results),
               "unfinished_example_completed": failed_report["completed"],
               "real_member_contrast": member_contrast,
               "task_design_note": "SP and RJ 2017 order Top-3 coincide. The linked target is MG so retaining the original three and re-ranking yield different real category sets. Independent targets are MG/RJ/PR; their difficulty is not claimed matched without a participant pilot.",
               "limits": "The three mode labels only verify the same task/tool feasibility under each session setting. They do not exercise different input protocols or compare modes. No speech recognition, model reasoning, real audio or human listening was tested. All human reviews remain pending."}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    assert summary["passed_paths"] == 36 and summary["unfinished_example_completed"] is False
    assert set(member_contrast["region_linked"]["members"]) != set(member_contrast["rerank_linked"]["members"])


if __name__ == "__main__":
    main()
