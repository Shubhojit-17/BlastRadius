-- New SQL for fixture_type_change.sql
SELECT
    CAST(u.user_id AS VARCHAR) AS user_id,
    u.email AS user_email
FROM {{ ref('raw_users') }} u
