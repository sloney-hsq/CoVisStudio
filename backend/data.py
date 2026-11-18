"""Olist queries at order and order-category grain; no user supplied values."""

from copy import deepcopy
from datetime import date
from difflib import get_close_matches
from pathlib import Path
from threading import Lock

import duckdb
from jsonschema import validate


METRICS = {
    "orders": {"label": "Orders", "unit": "orders", "definition": "Distinct orders within each displayed group. Category groups can overlap; do not sum their order counts."},
    "revenue": {"label": "Revenue", "unit": "BRL", "definition": "Sum of selected item prices, excluding freight."},
    "low_review_rate": {"label": "Low-review rate", "unit": "ratio", "definition": "Orders with canonical review score 1 or 2 divided by orders with a valid score from 1 to 5. One review per order, selected by latest creation date then review ID. Missing reviews are excluded."},
    "avg_delivery_days": {"label": "Average delivery time", "unit": "days", "definition": "Mean elapsed days between purchase and customer delivery, with one weight per order per group. Only delivered orders with non-negative duration enter the mean."},
}
# Olist customer states. Spoken names must be resolved to these codes; an unknown
# region used to return an empty chart silently.
STATES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso", "PA": "Pará",
    "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima", "RS": "Rio Grande do Sul",
    "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins",
}
DIMENSIONS = {"category": "Product category", "month": "Purchase month", "state": "Customer state"}
DEFAULT_SOURCE = {
    "metric": "orders", "dimension": "category", "region": "SP",
    "start": "2017-01-01", "end": "2018-01-01", "status": "delivered",
    "categories": None, "top_n": 5, "rank_by": "orders",
}
SOURCE_PROPERTIES = {
    "metric": {"type": "string", "enum": list(METRICS), "description":
        "orders = distinct orders; revenue = item revenue excluding freight; "
        "low_review_rate = reviewed orders scoring 2 or below divided by valid reviewed orders; "
        "avg_delivery_days = mean elapsed delivery days. Rates and means are within-group values: "
        "never sum, average or renormalize them across groups."},
    "dimension": {"type": "string", "enum": list(DIMENSIONS)},
    "region": {"type": ["string", "null"], "enum": [*STATES, None], "description":
        "Two-letter customer-state code, or null for all regions. Map spoken names to codes: "
        + ", ".join(f"{name} = {code}" for code, name in STATES.items()) + "."},
    "start": {"type": "string", "description": "Inclusive ISO date."},
    "end": {"type": "string", "description": "Exclusive ISO date."},
    "status": {"type": "string", "enum": ["delivered", "shipped", "canceled", "unavailable", "invoiced", "processing", "approved", "created"]},
    "categories": {"type": ["array", "null"], "items": {"type": "string"}, "minItems": 1, "uniqueItems": True, "description":
        "Exact snake_case category IDs as shown by read_dashboard or list_evidence_candidates "
        "(a spoken \"health and beauty\" is health_beauty). Unknown IDs are rejected, never shown as an "
        "empty chart. Set top_n to null when supplying a fixed list."},
    "top_n": {"type": ["integer", "null"], "minimum": 1, "description": "Dynamic ranking size; null shows all matching groups. Cannot be combined with fixed categories."},
    "rank_by": {"type": "string", "enum": list(METRICS), "description":
        "Rank by the same metric definitions as metric; ranks are computed within each group."},
}
SOURCE_SCHEMA = {"type": "object", "properties": SOURCE_PROPERTIES, "additionalProperties": False}


def normalize_source(source):
    validate(source, SOURCE_SCHEMA)
    normalized = {**DEFAULT_SOURCE, **deepcopy(source)}
    if date.fromisoformat(normalized["start"]) >= date.fromisoformat(normalized["end"]):
        raise ValueError("The start date must precede the exclusive end date.")
    if normalized["categories"] is not None and normalized["top_n"] is not None:
        raise ValueError("Fixed categories and dynamic top_n are different selections. Set top_n to null to preserve category IDs.")
    return normalized


class OlistData:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.connection = duckdb.connect(":memory:")
        self._lock = Lock()
        files = {
            "orders": "olist_orders_dataset.csv", "customers": "olist_customers_dataset.csv",
            "items": "olist_order_items_dataset.csv", "products": "olist_products_dataset.csv",
            "reviews": "olist_order_reviews_dataset.csv", "translations": "product_category_name_translation.csv",
        }
        for table, filename in files.items():
            self.connection.execute(f"CREATE TABLE raw_{table} AS SELECT * FROM read_csv_auto(?, sample_size=-1)", [str(self.data_dir / filename)])
        self.connection.execute("""
            CREATE TABLE orders AS
            WITH review AS (
                SELECT order_id, CASE WHEN review_score BETWEEN 1 AND 5 THEN review_score END AS review_score
                FROM raw_reviews
                QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY review_creation_date DESC NULLS LAST, review_id DESC) = 1
            )
            SELECT o.order_id, o.order_status, o.order_purchase_timestamp AS purchased_at,
                   c.customer_state AS region, r.review_score,
                   CASE WHEN o.order_status = 'delivered' AND o.order_delivered_customer_date >= o.order_purchase_timestamp
                        THEN epoch(o.order_delivered_customer_date - o.order_purchase_timestamp) / 86400.0 END AS delivery_days
            FROM raw_orders o LEFT JOIN raw_customers c USING (customer_id)
            LEFT JOIN review r USING (order_id);
            CREATE TABLE items AS
            SELECT i.order_id, COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
                   i.price::DOUBLE AS revenue
            FROM raw_items i LEFT JOIN raw_products p USING (product_id)
            LEFT JOIN raw_translations t USING (product_category_name);
        """)
        first_day, end_day = self.connection.execute("SELECT min(purchased_at)::DATE, max(purchased_at)::DATE + 1 FROM orders").fetchone()
        self._catalog = {
            "name": "Olist Brazilian E-Commerce", "version": "covis-olist-v1",
            "metrics": [{"key": key, "id": key, **value} for key, value in METRICS.items()],
            "dimensions": [{"key": key, "id": key, "label": value} for key, value in DIMENSIONS.items()],
            "states": [r[0] for r in self.connection.execute("SELECT DISTINCT region FROM orders WHERE region IS NOT NULL ORDER BY region").fetchall()],
            "categories": [r[0] for r in self.connection.execute("SELECT DISTINCT category FROM items ORDER BY category").fetchall()],
            "date_range": {"start": first_day.isoformat(), "end": end_day.isoformat()},
        }

    def catalog(self):
        return deepcopy(self._catalog)

    def close(self):
        self.connection.close()

    def check_scope(self, source):
        """Reject inputs that would otherwise render a silently empty chart."""
        known = self._catalog["categories"]
        if source["categories"] is not None:
            unknown = [name for name in source["categories"] if name not in known]
            if unknown:
                hints = []
                for name in unknown:
                    close = get_close_matches(name.lower().replace(" and ", "_").replace(" ", "_"), known, n=2, cutoff=.6)
                    hints.append(f"{name}" + (f" (closest: {', '.join(close)})" if close else ""))
                raise ValueError("Unknown category IDs: " + "; ".join(hints) +
                                 ". Use exact IDs from read_dashboard or list_evidence_candidates.")
        first, end = self._catalog["date_range"]["start"], self._catalog["date_range"]["end"]
        if source["end"] <= first or source["start"] >= end:
            raise ValueError(f"No Olist purchases fall in {source['start']} to {source['end']}; "
                             f"the data covers {first} to {end} (exclusive).")

    def query(self, source):
        source = normalize_source(source)
        self.check_scope(source)
        metric, dimension = source["metric"], source["dimension"]
        parameters = []
        item_filter = ""
        if source["categories"] is not None:
            item_filter = "WHERE category IN (" + ",".join("?" for _ in source["categories"]) + ")"
            parameters.extend(source["categories"])
        grouping = ", category" if dimension == "category" else ""
        label = {"category": "i.category", "month": "strftime(o.purchased_at, '%Y-%m')", "state": "o.region"}[dimension]
        join = "JOIN" if dimension == "category" or source["categories"] is not None else "LEFT JOIN"
        filters = ["o.order_status = ?", "o.purchased_at >= ?::DATE", "o.purchased_at < ?::DATE"]
        parameters.extend([source["status"], source["start"], source["end"]])
        if source["region"] is not None:
            filters.append("o.region = ?")
            parameters.append(source["region"])
        sql = f"""
            WITH item_scope AS (
                SELECT order_id{grouping}, sum(revenue)::DOUBLE AS revenue
                FROM items {item_filter} GROUP BY order_id{grouping}
            ), grouped AS (
                SELECT {label} AS label, count(*)::BIGINT AS orders,
                       coalesce(sum(i.revenue), 0)::DOUBLE AS revenue,
                       count(o.review_score)::BIGINT AS reviewed_orders,
                       count(*) FILTER (WHERE o.review_score <= 2)::BIGINT AS low_review_count,
                       count(o.delivery_days)::BIGINT AS delivery_order_count,
                       avg(o.delivery_days)::DOUBLE AS avg_delivery_days
                FROM orders o {join} item_scope i USING (order_id)
                WHERE {' AND '.join(filters)} GROUP BY {label}
            )
            SELECT *, low_review_count::DOUBLE / nullif(reviewed_orders, 0) AS low_review_rate FROM grouped
        """
        with self._lock:
            cursor = self.connection.execute(sql, parameters)
            names = [column[0] for column in cursor.description]
            rows = [dict(zip(names, values)) for values in cursor.fetchall()]
        if source["categories"] is not None and dimension == "category":
            positions = {name: position for position, name in enumerate(source["categories"])}
            rows.sort(key=lambda row: positions[row["label"]])
        elif source["top_n"] is not None:
            ranking = source["rank_by"]
            rows.sort(key=lambda row: (row[ranking] is None, -(row[ranking] or 0), row["label"]))
            rows = rows[:source["top_n"]]
        else:
            rows.sort(key=lambda row: row["label"])
        if dimension == "month":
            rows.sort(key=lambda row: row["label"])
        for row in rows:
            row["value"] = row[metric]
        mode = "fixed" if source["categories"] is not None and dimension == "category" else "ranked" if source["top_n"] is not None else "all"
        return {
            "rows": rows,
            "columns": [{"key": "label", "label": DIMENSIONS[dimension], "type": "temporal" if dimension == "month" else "nominal"},
                        {"key": "value", "metric": metric, "type": "quantitative", **METRICS[metric]}],
            "selection": {"mode": mode, "field": dimension, "members": [row["label"] for row in rows],
                          "categories": source["categories"], "rank_by": source["rank_by"] if mode == "ranked" else None,
                          "n": source["top_n"], "tie_break": "label ascending"},
            "definition": METRICS[metric]["definition"],
        }
