-- name: night_lights_cells
-- params: month_key text
-- returns: cell bigint, period text, radiance numeric, source_id text
-- order: cell, period
SELECT p.cell, p.period, p.radiance, p.source_id
FROM pub_night_lights AS p
WHERE p.period = :month_key
ORDER BY p.cell ASC NULLS LAST, p.period ASC NULLS LAST
