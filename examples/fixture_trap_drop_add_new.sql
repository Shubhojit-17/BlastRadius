-- New SQL for fixture_trap_drop_add.sql (Drop lifetime_value AND add unrelated created_by column)
SELECT
    u.user_id,
    u.email AS user_email,
    o.created_by
FROM {{ ref('raw_users') }} u
JOIN {{ ref('raw_orders') }} o ON u.user_id = o.user_id
GROUP BY 1, 2, 3
