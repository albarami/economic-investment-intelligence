-- name: sector_facts_utility_national
-- params: periods list[text]
-- returns: period text, utility text, value numeric
-- order: period, utility
SELECT p.period, p.utility, SUM(p.value) AS value
FROM pub_zone_utility AS p
WHERE p.period = ANY(:periods) AND p.utility = 'electricity'
GROUP BY p.period, p.utility
ORDER BY p.period ASC NULLS LAST, p.utility ASC NULLS LAST
