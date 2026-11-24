-- name: sector_facts_visitors
-- params: 
-- returns: table_code text, period text, nationality_group text, breakdown_key text, indicator text, value numeric, unit text, source_id text
-- order: table_code, period, nationality_group, breakdown_key, indicator
SELECT p.table_code, p.period, p.nationality_group, p.breakdown_key, p.indicator, p.value, p.unit, p.source_id
FROM pub_visitor_markets AS p
ORDER BY p.table_code ASC NULLS LAST, p.period ASC NULLS LAST, p.nationality_group ASC NULLS LAST, p.breakdown_key ASC NULLS LAST, p.indicator ASC NULLS LAST
