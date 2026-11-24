-- name: sector_facts_wages
-- params: table_code text, periods list[text]
-- returns: table_code text, period text, breakdown_key text, indicator text, value numeric, unit text, source_id text
-- order: table_code, period, breakdown_key, indicator
SELECT p.table_code, p.period, p.breakdown_key, p.indicator, p.value, p.unit, p.source_id
FROM pub_wage_table AS p
WHERE p.table_code = :table_code AND p.period = ANY(:periods)
ORDER BY p.table_code ASC NULLS LAST, p.period ASC NULLS LAST, p.breakdown_key ASC NULLS LAST, p.indicator ASC NULLS LAST
