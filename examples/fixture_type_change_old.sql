-- Old SQL for fixture_type_change.sql
SELECT
    CAST(u.user_id AS INT) AS user_id,
    u.email AS user_email
FROM {{ ref('raw_users') }} u
