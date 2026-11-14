"""Contract checks exercise real SQL, preservation and transactional publication."""

import csv
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import ValidationError

from backend.charts import ChartStore
from backend.data import OlistData


@pytest.fixture(scope="module")
def small_data(tmp_path_factory):
    path = tmp_path_factory.mktemp("olist")
    tables = {
        "olist_orders_dataset.csv": (["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_delivered_customer_date"], [
            ["o1", "c1", "delivered", "2017-01-01 00:00:00", "2017-01-03 00:00:00"],
            ["o2", "c1", "delivered", "2017-01-02 00:00:00", "2017-01-06 00:00:00"],
            ["o3", "c1", "delivered", "2017-01-03 00:00:00", "2017-01-09 00:00:00"],
            ["o4", "c2", "delivered", "2017-02-01 00:00:00", "2017-02-04 00:00:00"],
            ["o5", "c1", "canceled", "2017-01-04 00:00:00", ""],
        ]),
        "olist_customers_dataset.csv": (["customer_id", "customer_state"], [["c1", "SP"], ["c2", "RJ"]]),
        "olist_order_items_dataset.csv": (["order_id", "product_id", "price"], [
            ["o1", "pa", 10], ["o1", "pa", 20], ["o1", "pb", 40], ["o2", "pa", 30], ["o3", "pb", 50], ["o4", "pa", 100],
        ]),
        "olist_products_dataset.csv": (["product_id", "product_category_name"], [["pa", "aa"], ["pb", "bb"]]),
        "product_category_name_translation.csv": (["product_category_name", "product_category_name_english"], [["aa", "alpha"], ["bb", "beta"]]),
        "olist_order_reviews_dataset.csv": (["order_id", "review_id", "review_creation_date", "review_score"], [
            ["o1", "r1", "2017-01-04 00:00:00", 1], ["o1", "r2", "2017-01-05 00:00:00", 5],
            ["o2", "r3", "2017-01-07 00:00:00", 2], ["o4", "r4", "2017-02-05 00:00:00", 1],
        ]),
    }
    for filename, (header, rows) in tables.items():
        with (path / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
    data = OlistData(path)
    yield data
    data.close()


def create(store, metric="orders", **source):
    return store.commit(store.prepare("create_chart", {"title": "Categories", "chart_type": "bar", "source": {"metric": metric, **source}}))


def test_category_orders_reviews_and_delivery_are_not_item_weighted(small_data):
    rows = small_data.query({"metric": "low_review_rate", "top_n": None})["rows"]
    alpha, beta = rows
    assert (alpha["label"], alpha["orders"], alpha["revenue"]) == ("alpha", 2, 60)
    assert (alpha["reviewed_orders"], alpha["low_review_count"], alpha["value"]) == (2, 1, .5)
    assert alpha["avg_delivery_days"] == 3
    assert (beta["orders"], beta["reviewed_orders"], beta["low_review_count"], beta["value"]) == (2, 1, 0, 0)
    assert beta["avg_delivery_days"] == 4


def test_month_deduplicates_categories_and_includes_orders_without_items(small_data):
    month = small_data.query({"dimension": "month", "top_n": None})["rows"][0]
    assert (month["orders"], month["revenue"], month["avg_delivery_days"]) == (3, 150, 4)
    canceled = small_data.query({"dimension": "month", "status": "canceled", "top_n": None})["rows"][0]
    assert (canceled["orders"], canceled["revenue"], canceled["low_review_rate"]) == (1, 0, None)


def test_fixed_entities_preserve_order_while_dynamic_ranking_changes(small_data):
    assert small_data.query({"top_n": 1})["selection"]["members"] == ["alpha"]
    assert small_data.query({"metric": "revenue", "rank_by": "revenue", "top_n": 1})["selection"]["members"] == ["beta"]
    fixed = small_data.query({"metric": "revenue", "categories": ["beta", "alpha"], "top_n": None})
    assert fixed["selection"]["members"] == ["beta", "alpha"]
    assert fixed["selection"]["mode"] == "fixed"
    with pytest.raises(ValueError, match="Fixed categories"):
        small_data.query({"categories": ["alpha"]})


def test_date_end_is_exclusive_and_categories_filter_order_grain(small_data):
    january = small_data.query({"dimension": "month", "region": None, "start": "2017-01-01", "end": "2017-02-01", "top_n": None})
    assert [r["label"] for r in january["rows"]] == ["2017-01"]
    subset = small_data.query({"dimension": "month", "categories": ["alpha"], "top_n": None})["rows"][0]
    assert (subset["orders"], subset["revenue"], subset["avg_delivery_days"]) == (2, 60, 3)


def test_prepare_does_not_publish_and_stale_candidate_cannot_commit(small_data):
    store = ChartStore(small_data)
    first = store.prepare("create_chart", {"title": "First", "chart_type": "bar", "source": {}})
    stale = store.prepare("set_dashboard", {"title": "Stale"})
    assert store.snapshot()["views"] == []
    assert store.commit(first)["state"]["revision"] == 1
    with pytest.raises(ValueError, match="changed while"):
        store.commit(stale)
    assert store.snapshot()["title"] == "Untitled dashboard"


def test_multi_chart_patch_preserves_conditions_and_recalculates(small_data):
    store = ChartStore(small_data)
    create(store, categories=["alpha"], top_n=None)
    create(store, metric="low_review_rate", categories=["alpha"], top_n=None)
    store.commit(store.prepare("edit_charts", {"view_ids": ["v1", "v2"], "patch": {"source": {"region": "RJ"}}}))
    for view in store.snapshot()["views"]:
        assert view["source"]["categories"] == ["alpha"]
        assert view["source"]["start"] == "2017-01-01"
        assert view["data"]["rows"][0]["orders"] == 1
    assert store.snapshot()["views"][1]["data"]["rows"][0]["value"] == 1


def test_failed_batch_leaves_every_chart_unchanged(small_data):
    store = ChartStore(small_data)
    create(store, metric="revenue")
    create(store, metric="low_review_rate")
    before = store.snapshot()
    with pytest.raises(ValueError, match="additive"):
        store.prepare("edit_charts", {"view_ids": ["v1", "v2"], "patch": {"chart_type": "pie"}})
    assert store.snapshot() == before


def test_presentation_only_patch_does_not_requery(small_data, monkeypatch):
    store = ChartStore(small_data)
    create(store)
    before = store.snapshot()["views"][0]
    def unexpected_query(_):
        pytest.fail("A color-only edit must reuse its saved query result")
    monkeypatch.setattr(small_data, "query", unexpected_query)
    after = store.commit(store.prepare("edit_charts", {"view_ids": ["v1"], "patch": {"style": {"color": "#f1733c"}}}))["state"]["views"][0]
    assert after["data"] == before["data"]
    assert after["source"] == before["source"]
    assert after["style"]["color"] == "#f1733c"


def test_restore_is_new_revision_and_ids_are_never_reused(small_data):
    store = ChartStore(small_data)
    first = create(store)["state"]
    create(store)
    assert store.restore(first)["state"]["revision"] == 3
    create(store)
    assert [v["id"] for v in store.snapshot()["views"]] == ["v1", "v3"]
    assert store.snapshot()["revision"] == 4


def test_manual_numeric_override_is_not_in_tool_contract(small_data):
    store = ChartStore(small_data)
    create(store)
    with pytest.raises(ValidationError):
        store.prepare("edit_charts", {"view_ids": ["v1"], "patch": {"data": [{"value": 999}]}})


def test_arranging_views_preserves_their_data_and_stable_numbers(small_data, monkeypatch):
    store = ChartStore(small_data)
    create(store)
    create(store, metric="revenue")
    create(store, metric="low_review_rate")
    before = store.snapshot()
    def unexpected_query(_):
        pytest.fail("Arranging views must not query or alter data")
    monkeypatch.setattr(small_data, "query", unexpected_query)
    after = store.commit(store.prepare("arrange_charts", {"view_ids": ["v3", "v1", "v2"], "columns": 2}))["state"]
    assert after["layout"] == {"columns": 2}
    assert [v["number"] for v in after["views"]] == [3, 1, 2]
    assert {v["id"]: v for v in after["views"]} == {v["id"]: v for v in before["views"]}
    with pytest.raises(ValueError, match="every current chart"):
        store.prepare("arrange_charts", {"view_ids": ["v1"], "columns": 3})
    assert store.snapshot() == after


@pytest.fixture(scope="module")
def real_data():
    data = OlistData(Path("C:/VerbalVis/datasets/olist/data"))
    yield data
    data.close()


def test_real_olist_against_independent_raw_csv_sql(real_data):
    rows = real_data.query({"metric": "low_review_rate", "top_n": 3})["rows"]
    assert [r["label"] for r in rows] == ["bed_bath_table", "sports_leisure", "furniture_decor"]
    for row in rows:
        oracle = real_data.connection.execute("""
            WITH latest_reviews AS (
                SELECT order_id, review_score FROM raw_reviews
                QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY review_creation_date DESC NULLS LAST, review_id DESC) = 1
            ), cohort AS (
                SELECT DISTINCT o.order_id, o.order_purchase_timestamp, o.order_delivered_customer_date, r.review_score
                FROM raw_orders o JOIN raw_customers c USING(customer_id)
                JOIN raw_items i USING(order_id) JOIN raw_products p USING(product_id)
                LEFT JOIN raw_translations t USING(product_category_name)
                LEFT JOIN latest_reviews r USING(order_id)
                WHERE o.order_status='delivered' AND c.customer_state='SP'
                  AND o.order_purchase_timestamp >= '2017-01-01' AND o.order_purchase_timestamp < '2018-01-01'
                  AND coalesce(t.product_category_name_english,p.product_category_name,'unknown')=?
            ) SELECT count(*),count(*) FILTER(WHERE review_score BETWEEN 1 AND 5),count(*) FILTER(WHERE review_score BETWEEN 1 AND 2),
                     avg(CASE WHEN order_delivered_customer_date>=order_purchase_timestamp THEN epoch(order_delivered_customer_date-order_purchase_timestamp)/86400.0 END)
            FROM cohort
        """, [row["label"]]).fetchone()
        assert (row["orders"], row["reviewed_orders"], row["low_review_count"]) == oracle[:3]
        assert row["value"] == pytest.approx(oracle[2] / oracle[1])
        assert row["avg_delivery_days"] == pytest.approx(oracle[3])
    assert rows[0]["orders"] == 1891
    assert rows[0]["revenue"] == pytest.approx(204224.73)


def test_all_six_chart_forms_use_real_queries(real_data):
    store = ChartStore(real_data)
    for form in ("bar", "line", "area", "pie", "scatter", "heatmap"):
        receipt = store.commit(store.prepare("create_chart", {"title": form, "chart_type": form, "source": {"metric": "revenue"}}))
        assert receipt["state"]["views"][-1]["data"]["rows"]
    assert store.snapshot()["revision"] == 6
