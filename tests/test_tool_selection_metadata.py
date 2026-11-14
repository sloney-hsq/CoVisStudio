from pathlib import Path

import pytest

from backend.data import OlistData


@pytest.fixture(scope="module")
def data():
    result = OlistData(Path("C:/VerbalVis/datasets/olist/data"))
    yield result
    result.close()


@pytest.mark.parametrize("dimension, expected_mode", [("category", "fixed"), ("month", "all"), ("state", "all")])
def test_fixed_category_filter_does_not_claim_fixed_month_or_state_members(data, dimension, expected_mode):
    source = {"dimension": dimension, "categories": ["bed_bath_table"], "top_n": None,
              "start": "2017-01-01", "end": "2017-04-01"}
    result = data.query(source)
    assert result["selection"] == {
        "mode": expected_mode, "field": dimension,
        "members": [row["label"] for row in result["rows"]],
        "categories": ["bed_bath_table"], "rank_by": None, "n": None,
        "tie_break": "label ascending",
    }
    if dimension == "month":
        expected = data.connection.execute("""
            SELECT strftime(o.order_purchase_timestamp, '%Y-%m'), count(DISTINCT o.order_id), sum(i.price)
            FROM raw_orders o JOIN raw_customers c USING(customer_id)
            JOIN raw_items i USING(order_id) JOIN raw_products p USING(product_id)
            LEFT JOIN raw_translations t USING(product_category_name)
            WHERE o.order_status='delivered' AND c.customer_state='SP'
              AND o.order_purchase_timestamp >= '2017-01-01'
              AND o.order_purchase_timestamp < '2017-04-01'
              AND coalesce(t.product_category_name_english,p.product_category_name,'unknown')='bed_bath_table'
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        assert len(result["rows"]) == len(expected)
        for row, (label, orders, revenue) in zip(result["rows"], expected):
            assert (row["label"], row["orders"]) == (label, orders)
            assert row["revenue"] == pytest.approx(revenue)
