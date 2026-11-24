-- name: sector_facts_census
-- params: geography text
-- returns: municipality_code text, period text, indicator text, value numeric, unit text, source_id text
-- order: municipality_code, period, indicator
SELECT p.municipality_code, p.period, p.indicator, p.value, p.unit, p.source_id
FROM pub_census_2015_municipality AS p
WHERE p.municipality_code = :geography
ORDER BY p.municipality_code ASC NULLS LAST, p.period ASC NULLS LAST, p.indicator ASC NULLS LAST
