-- name: sector_facts_licence_national
-- params: 
-- returns: period text, active_count numeric
-- order: period
SELECT p.period, SUM(p.active_count) AS active_count
FROM pub_licence_active AS p
GROUP BY p.period
ORDER BY p.period ASC NULLS LAST
