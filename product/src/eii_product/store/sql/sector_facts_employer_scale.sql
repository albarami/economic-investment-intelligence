-- name: sector_facts_employer_scale
-- params: activity text
-- returns: table_code text, activity_key text, size_class text, period text, indicator text, value numeric, unit text, source_id text
-- order: table_code, activity_key, size_class, period, indicator
SELECT p.table_code, p.activity_key, p.size_class, p.period, p.indicator, p.value, p.unit, p.source_id
FROM pub_establishment_size AS p
WHERE p.activity_key = :activity
ORDER BY p.table_code ASC NULLS LAST, p.activity_key ASC NULLS LAST, p.size_class ASC NULLS LAST, p.period ASC NULLS LAST, p.indicator ASC NULLS LAST
