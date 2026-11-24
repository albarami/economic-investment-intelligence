-- name: layer_fdi_gazetteer
-- params: place_key text
-- returns: place_key text, lon numeric, lat numeric
-- order: place_key
SELECT p.place_key, p.lon, p.lat
FROM gazetteer AS p
WHERE p.place_key = :place_key
ORDER BY p.place_key ASC NULLS LAST
