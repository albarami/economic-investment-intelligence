-- name: layer_public_places_fsq
-- params: 
-- returns: fsq_place_id text, name text, name_ar text, category_ids text, category_labels text, lon numeric, lat numeric, cell bigint, source_release text, licence text, date_created date, date_refreshed date, date_closed date, source_id text
-- order: fsq_place_id
SELECT p.fsq_place_id, p.name, p.name_ar, p.category_ids, p.category_labels, p.lon, p.lat, p.cell, p.source_release, p.licence, p.date_created, p.date_refreshed, p.date_closed, p.source_id
FROM pub_place_fsq AS p
ORDER BY p.fsq_place_id ASC NULLS LAST
