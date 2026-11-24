-- name: sector_facts_bulk_months
-- params: flag bool
-- returns: period text
-- order: period
SELECT p.period
FROM pub_licence_cancelled AS p
WHERE p.bulk_month = :flag
GROUP BY p.period
ORDER BY p.period ASC NULLS LAST
