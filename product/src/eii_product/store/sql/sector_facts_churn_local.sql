-- name: sector_facts_churn_local
-- params: activity text, geography text, months list[text]
-- returns: municipality_code text, activity_code text, period text, cancelled_count bigint, source_id text
-- order: municipality_code, activity_code, period
SELECT p.municipality_code, p.activity_code, p.period, p.cancelled_count, p.source_id
FROM pub_licence_cancelled AS p
WHERE p.activity_code = :activity AND p.municipality_code = :geography AND p.period = ANY(:months) AND p.period <> 'UNDATED'
ORDER BY p.municipality_code ASC NULLS LAST, p.activity_code ASC NULLS LAST, p.period ASC NULLS LAST
