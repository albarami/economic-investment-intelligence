-- name: scan_places_places
-- params: categories list[text]
-- returns: place_id text, name text, name_ar text, category text, lon numeric, lat numeric, cell bigint, source_release text, source_provider text, licence text, confidence numeric
-- order: place_id
SELECT p.place_id AS place_id, p.name AS name, p.name_ar AS name_ar, p.category AS category, p.lon AS lon, p.lat AS lat, p.cell AS cell, p.source_release AS source_release, p.source_provider AS source_provider, p.licence AS licence, p.confidence AS confidence
FROM pub_place AS p
WHERE p.category = ANY(:categories)
ORDER BY p.place_id ASC NULLS LAST
