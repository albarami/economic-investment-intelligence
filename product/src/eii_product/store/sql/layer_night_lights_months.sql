-- name: layer_night_lights_months
-- params: 
-- returns: period text
-- order: period
SELECT p.period
FROM pub_night_lights AS p
GROUP BY p.period
ORDER BY p.period ASC NULLS LAST
