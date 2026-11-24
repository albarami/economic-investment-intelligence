-- name: sector_facts_churn_total
-- params:
-- returns: cancelled_count numeric
-- order:
SELECT SUM(p.cancelled_count) AS cancelled_count
FROM pub_licence_cancelled AS p
