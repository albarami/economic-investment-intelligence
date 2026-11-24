-- name: layer_zone_geometry
-- params: 
-- returns: zone_code text, name_en text, name_ar text, municipality_code text, geometry geometry, source_id text
-- order: zone_code
SELECT p.zone_code, p.name_en, p.name_ar, p.municipality_code, p.geometry, p.source_id
FROM zone AS p
ORDER BY p.zone_code ASC NULLS LAST
