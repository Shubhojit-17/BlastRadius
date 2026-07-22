-- New SQL for fixture_rename.sql
SELECT
    u.user_id,
    u.email AS user_email,
    SUM(o.order_amount) AS ltv
FROM {{ ref('raw_users') }} u
JOIN {{ ref('raw_orders') }} o ON u.user_id = o.user_id
GROUP BY 1, 2
