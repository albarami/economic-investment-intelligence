-- name: layer_accidents
-- params: 
-- returns: period text, source_zone text, zone_code text, accident_count bigint, coverage_key text, source_id text
-- order: period, source_zone
SELECT p.period, p.source_zone, p.zone_code, p.accident_count, p.coverage_key, p.source_id
FROM pub_accident_zone AS p
ORDER BY p.period ASC NULLS LAST, p.source_zone ASC NULLS LAST
