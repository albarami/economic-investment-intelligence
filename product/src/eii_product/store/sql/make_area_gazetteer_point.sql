-- name: make_area_gazetteer_point
-- params: place_key text
-- returns: place_key text, lon numeric, lat numeric
-- order: place_key
SELECT g.place_key, g.lon, g.lat
FROM gazetteer AS g
WHERE g.place_key = :place_key
ORDER BY g.place_key ASC NULLS LAST
