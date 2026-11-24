-- name: sector_facts_accounts
-- params: activity text
-- returns: activity_code text, period text, indicator text, value numeric, unit text, source_id text
-- order: activity_code, period, indicator
SELECT p.activity_code, p.period, p.indicator, p.value, p.unit, p.source_id
FROM pub_sector_accounts AS p
WHERE p.activity_code = :activity
ORDER BY p.activity_code ASC NULLS LAST, p.period ASC NULLS LAST, p.indicator ASC NULLS LAST
