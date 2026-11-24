-- name: sector_facts_licence_local
-- params: activity text, geography text
-- returns: municipality_code text, activity_code text, period text, active_count bigint, source_id text
-- order: municipality_code, activity_code, period
SELECT p.municipality_code, p.activity_code, p.period, p.active_count, p.source_id
FROM pub_licence_active AS p
WHERE p.activity_code = :activity AND p.municipality_code = :geography
ORDER BY p.municipality_code ASC NULLS LAST, p.activity_code ASC NULLS LAST, p.period ASC NULLS LAST
