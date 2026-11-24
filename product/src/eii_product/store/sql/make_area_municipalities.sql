-- name: make_area_municipalities
-- params:
-- returns: municipality_code text, geometry geometry
-- order: municipality_code
SELECT m.municipality_code, m.geometry
FROM municipality AS m
ORDER BY m.municipality_code ASC NULLS LAST
