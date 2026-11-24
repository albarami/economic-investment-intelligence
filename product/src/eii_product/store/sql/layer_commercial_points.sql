-- name: layer_commercial_points
-- params: 
-- returns: feature_key text, name text, name_ar text, category text, lon numeric, lat numeric, cell bigint, source_id text
-- order: feature_key
SELECT p.feature_key, p.name, p.name_ar, p.category, p.lon, p.lat, p.cell, p.source_id
FROM pub_poi_comm AS p
ORDER BY p.feature_key ASC NULLS LAST
