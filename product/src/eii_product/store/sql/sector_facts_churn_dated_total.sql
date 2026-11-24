-- name: sector_facts_churn_dated_total
-- params:
-- returns: cancelled_count numeric
-- order:
SELECT SUM(p.cancelled_count) AS cancelled_count
FROM pub_licence_cancelled AS p
WHERE p.period <> 'UNDATED'
