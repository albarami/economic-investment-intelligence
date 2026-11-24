-- name: layer_landmarks
-- params: 
-- returns: place_key text, kind text, name_en text, name_ar text, aliases text, lon numeric, lat numeric, cell bigint, source_id text
-- order: place_key
SELECT p.place_key, p.kind, p.name_en, p.name_ar, p.aliases, p.lon, p.lat, p.cell, p.source_id
FROM gazetteer AS p
WHERE p.kind = 'landmark'
ORDER BY p.place_key ASC NULLS LAST
