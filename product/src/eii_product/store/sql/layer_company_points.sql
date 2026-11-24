-- name: layer_company_points
-- params:
-- returns: registration_number text, registered_cell bigint, establishment_nationality text, source_id text
-- order: registration_number
SELECT p.registration_number, p.registered_cell, p.establishment_nationality, p.source_id
FROM pub_register_company AS p
WHERE p.registered_cell IS NOT NULL
ORDER BY p.registration_number ASC NULLS LAST
