-- name: sector_facts_churn_national
-- params: 
-- returns: period text, cancelled_count numeric
-- order: period
SELECT p.period, SUM(p.cancelled_count) AS cancelled_count
FROM pub_licence_cancelled AS p
WHERE p.period <> 'UNDATED'
GROUP BY p.period
ORDER BY p.period ASC NULLS LAST
