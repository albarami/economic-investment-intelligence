-- name: sector_facts_residents
-- params: geography text
-- returns: municipality_code text, period text, indicator text, value numeric, unit text, source_id text
-- order: municipality_code, period, indicator
SELECT p.municipality_code, p.period, p.indicator, p.value, p.unit, p.source_id
FROM pub_population_municipality AS p
WHERE p.municipality_code = :geography AND p.indicator = 'residents'
ORDER BY p.municipality_code ASC NULLS LAST, p.period ASC NULLS LAST, p.indicator ASC NULLS LAST
