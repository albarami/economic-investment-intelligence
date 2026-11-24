-- name: sector_facts_licence_activity
-- params: activity text
-- returns: activity_code text, period text, active_count numeric
-- order: activity_code, period
SELECT p.activity_code, p.period, SUM(p.active_count) AS active_count
FROM pub_licence_active AS p
WHERE p.activity_code = :activity
GROUP BY p.activity_code, p.period
ORDER BY p.activity_code ASC NULLS LAST, p.period ASC NULLS LAST
