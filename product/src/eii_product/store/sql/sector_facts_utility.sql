-- name: sector_facts_utility
-- params: periods list[text]
-- returns: zone_code text, period text, utility text, value numeric, unit text, completeness text, source_id text
-- order: zone_code, period, utility
SELECT p.zone_code, p.period, p.utility, p.value, p.unit, CASE WHEN p.partial_year THEN 'partial' ELSE 'complete' END AS completeness, p.source_id
FROM pub_zone_utility AS p
WHERE p.period = ANY(:periods) AND p.utility = 'electricity'
ORDER BY p.zone_code ASC NULLS LAST, p.period ASC NULLS LAST, p.utility ASC NULLS LAST
