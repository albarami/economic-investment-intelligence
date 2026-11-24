-- name: layer_address_points
-- params: 
-- returns: feature_key text, zone_number text, street_number text, building_number text, building_subtype text, survey_date date, lon numeric, lat numeric, cell bigint, source_id text
-- order: feature_key
SELECT p.feature_key, p.zone_number, p.street_number, p.building_number, p.building_subtype, p.survey_date, p.lon, p.lat, p.cell, p.source_id
FROM pub_address_point AS p
ORDER BY p.feature_key ASC NULLS LAST
