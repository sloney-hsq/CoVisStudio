"""Evaluator-only SQL over raw Olist tables; independent of the runtime query path.

This module never calls OlistData.query, and is never sent to a provider.  The
shared connection is used only to read the original CSV tables under its lock.
"""


def category_rows(data, source):
    """Reference category aggregates for the bounded revision study."""
    if source['dimension'] != 'category':
        raise ValueError('Revision-study oracle covers category charts only.')
    filters = ['o.order_status = ?', 'o.order_purchase_timestamp >= ?::DATE',
               'o.order_purchase_timestamp < ?::DATE']
    parameters = [source['status'], source['start'], source['end']]
    if source['region'] is not None:
        filters.append('c.customer_state = ?')
        parameters.append(source['region'])
    category_filter = ''
    if source['categories'] is not None:
        category_filter = 'WHERE category IN (' + ','.join('?' for _ in source['categories']) + ')'
        parameters.extend(source['categories'])
    sql = f"""
        WITH canonical_reviews AS (
            SELECT order_id, review_score FROM raw_reviews
            QUALIFY row_number() OVER (
                PARTITION BY order_id
                ORDER BY review_creation_date DESC NULLS LAST, review_id DESC
            ) = 1
        ), eligible_orders AS (
            SELECT o.order_id, o.order_status, o.order_purchase_timestamp,
                   o.order_delivered_customer_date, r.review_score
            FROM raw_orders o LEFT JOIN raw_customers c USING(customer_id)
            LEFT JOIN canonical_reviews r USING(order_id)
            WHERE {' AND '.join(filters)}
        ), item_labels AS (
            SELECT i.order_id,
                   coalesce(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
                   i.price::DOUBLE AS price
            FROM raw_items i LEFT JOIN raw_products p USING(product_id)
            LEFT JOIN raw_translations t USING(product_category_name)
        ), selected_items AS (
            SELECT * FROM item_labels {category_filter}
        ), membership AS (
            SELECT DISTINCT order_id, category FROM selected_items
        ), counts AS (
            SELECT m.category AS label, count(*)::BIGINT AS orders,
                   count(*) FILTER(WHERE o.review_score BETWEEN 1 AND 5)::BIGINT AS reviewed_orders,
                   count(*) FILTER(WHERE o.review_score BETWEEN 1 AND 2)::BIGINT AS low_review_count,
                   count(*) FILTER(WHERE o.order_status='delivered' AND
                       o.order_delivered_customer_date >= o.order_purchase_timestamp)::BIGINT AS delivery_order_count,
                   avg(CASE WHEN o.order_status='delivered' AND
                       o.order_delivered_customer_date >= o.order_purchase_timestamp
                       THEN epoch(o.order_delivered_customer_date-o.order_purchase_timestamp)/86400.0
                       END)::DOUBLE AS avg_delivery_days
            FROM membership m JOIN eligible_orders o USING(order_id) GROUP BY m.category
        ), money AS (
            SELECT i.category AS label, sum(i.price)::DOUBLE AS revenue
            FROM selected_items i JOIN eligible_orders o USING(order_id) GROUP BY i.category
        )
        SELECT c.*, m.revenue,
               c.low_review_count::DOUBLE / nullif(c.reviewed_orders, 0) AS low_review_rate
        FROM counts c JOIN money m USING(label)
    """
    with data._lock:
        cursor = data.connection.execute(sql, parameters)
        names = [column[0] for column in cursor.description]
        rows = [dict(zip(names, values)) for values in cursor.fetchall()]
    if source['categories'] is not None:
        positions = {member: i for i, member in enumerate(source['categories'])}
        rows.sort(key=lambda row: positions[row['label']])
    elif source['top_n'] is not None:
        rank = source['rank_by']
        rows.sort(key=lambda row: (row[rank] is None, -(row[rank] or 0), row['label']))
        rows = rows[:source['top_n']]
    else:
        rows.sort(key=lambda row: row['label'])
    for row in rows:
        row['value'] = row[source['metric']]
    return rows


def members(data, source):
    return [row['label'] for row in category_rows(data, source)]


def numeric_rows_equal(actual, expected):
    """Check labels and every recorded aggregate, including rate denominators."""
    actual_by_label = {row['label']: row for row in actual}
    expected_by_label = {row['label']: row for row in expected}
    if actual_by_label.keys() != expected_by_label.keys() or len(actual) != len(expected):
        return False
    for label, row in expected_by_label.items():
        observed = actual_by_label[label]
        for field, value in row.items():
            if field == 'label':
                continue
            if field not in observed:
                return False
            other = observed.get(field)
            if value is None:
                if other is not None:
                    return False
            elif other is None or abs(other - value) > max(1e-7, abs(value) * 1e-10):
                return False
    return True
