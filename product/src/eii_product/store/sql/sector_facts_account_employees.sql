-- name: sector_facts_account_employees
-- params: activity text, indicators list[text]
-- returns: activity_code text, period text, unit text, value numeric
-- order: activity_code, period, unit
SELECT p.activity_code, p.period, p.unit, SUM(p.value) AS value
FROM pub_sector_accounts AS p
WHERE p.activity_code = :activity AND p.indicator = ANY(:indicators)
GROUP BY p.activity_code, p.period, p.unit
ORDER BY p.activity_code ASC NULLS LAST, p.period ASC NULLS LAST, p.unit ASC NULLS LAST
