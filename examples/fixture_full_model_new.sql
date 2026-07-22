-- Full dbt model file with 10+ surrounding SELECT lines (New version: lifetime_value dropped)
{{ config(materialized='table') }}

SELECT
    u.user_id,
    u.email AS user_email,
    u.first_name,
    u.last_name,
    u.city,
    u.state,
    u.country,
    u.signup_timestamp,
    COUNT(o.order_id) AS total_orders,
    MIN(o.created_at) AS first_order_at,
    MAX(o.created_at) AS last_order_at,
    AVG(o.order_amount) AS avg_order_value,
    u.status AS user_status
FROM {{ ref('raw_users') }} u
LEFT JOIN {{ ref('raw_orders') }} o ON u.user_id = o.user_id
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 13
