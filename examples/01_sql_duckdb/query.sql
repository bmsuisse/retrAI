-- Top 10 customers by total revenue with product breakdown.
-- This query is intentionally suboptimal — the agent should optimize it.

SELECT
    c.name,
    c.region,
    sub.total_revenue,
    sub.order_count,
    sub.top_product
FROM customers c
JOIN (
    SELECT
        o.customer_id,
        SUM(o.quantity * o.unit_price) AS total_revenue,
        COUNT(*)                       AS order_count,
        (
            SELECT o2.product
            FROM orders o2
            WHERE o2.customer_id = o.customer_id
            GROUP BY o2.product
            ORDER BY SUM(o2.quantity * o2.unit_price) DESC
            LIMIT 1
        ) AS top_product
    FROM orders o
    WHERE o.status != 'returned'
    GROUP BY o.customer_id
) sub ON c.customer_id = sub.customer_id
WHERE c.is_active = true
ORDER BY sub.total_revenue DESC
LIMIT 10;
