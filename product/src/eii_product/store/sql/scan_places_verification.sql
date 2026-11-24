-- name: scan_places_verification
-- params: places list[text]
-- returns: place_id text, check_date date, reviewer_role text, verification_link text, status text, source_id text
-- order: place_id, check_date
SELECT p.place_id AS place_id, p.check_date AS check_date, p.reviewer_role AS reviewer_role, p.verification_link AS verification_link, p.status AS status, p.source_id AS source_id
FROM pub_place_verification AS p
WHERE p.place_id = ANY(:places)
ORDER BY p.place_id ASC NULLS LAST, p.check_date ASC NULLS LAST
