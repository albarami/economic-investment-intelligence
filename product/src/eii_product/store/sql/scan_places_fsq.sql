-- name: scan_places_fsq
-- params:
-- returns: fsq_place_id text, name text, name_ar text, category_ids text, category_labels text, lon numeric, lat numeric, cell bigint, source_release text, licence text
-- order: fsq_place_id
SELECT p.fsq_place_id AS fsq_place_id, p.name AS name, p.name_ar AS name_ar, p.category_ids AS category_ids, p.category_labels AS category_labels, p.lon AS lon, p.lat AS lat, p.cell AS cell, p.source_release AS source_release, p.licence AS licence
FROM pub_place_fsq AS p
ORDER BY p.fsq_place_id ASC NULLS LAST
