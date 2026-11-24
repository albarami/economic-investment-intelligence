-- name: layer_public_places
-- params: 
-- returns: place_id text, name text, name_ar text, category text, lon numeric, lat numeric, cell bigint, source_release text, source_provider text, licence text, confidence numeric, merged_ids text, source_id text
-- order: place_id
SELECT p.place_id, p.name, p.name_ar, p.category, p.lon, p.lat, p.cell, p.source_release, p.source_provider, p.licence, p.confidence, p.merged_ids, p.source_id
FROM pub_place AS p
ORDER BY p.place_id ASC NULLS LAST
