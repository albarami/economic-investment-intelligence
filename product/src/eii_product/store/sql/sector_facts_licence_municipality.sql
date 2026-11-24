-- name: sector_facts_licence_municipality
-- params: geography text
-- returns: municipality_code text, period text, active_count numeric
-- order: municipality_code, period
SELECT p.municipality_code, p.period, SUM(p.active_count) AS active_count
FROM pub_licence_active AS p
WHERE p.municipality_code = :geography
GROUP BY p.municipality_code, p.period
ORDER BY p.municipality_code ASC NULLS LAST, p.period ASC NULLS LAST
