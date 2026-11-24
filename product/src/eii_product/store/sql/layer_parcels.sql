-- name: layer_parcels
-- params: 
-- returns: feature_key text, area_m2 numeric, start_date date, end_date date, geometry geometry, source_id text
-- order: feature_key
SELECT p.feature_key, p.area_m2, p.start_date, p.end_date, p.geometry, p.source_id
FROM pub_parcel AS p
ORDER BY p.feature_key ASC NULLS LAST
