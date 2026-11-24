-- name: layer_district_geometry
-- params: 
-- returns: district_key text, name_en text, name_ar text, municipality_code text, geometry geometry, source_id text
-- order: district_key
SELECT p.district_key, p.name_en, p.name_ar, p.municipality_code, p.geometry, p.source_id
FROM district AS p
ORDER BY p.district_key ASC NULLS LAST
