-- name: venue_busyness_places
-- params: 
-- returns: place_id text
-- order: place_id
SELECT p.place_id
FROM pub_place AS p
GROUP BY p.place_id
ORDER BY p.place_id ASC NULLS LAST
