-- name: venue_busyness_rows
-- params: place_keys list[text]
-- returns: place_id text, day_of_week text, hour bigint, busyness_index bigint, retrieved_on date, provider_updated_on date, source_id text
-- order: place_id, day_of_week, hour
SELECT p.place_id, p.day_of_week, p.hour, p.busyness_index, p.retrieved_on, p.provider_updated_on, p.source_id
FROM pub_venue_busyness AS p
WHERE p.place_id = ANY(:place_keys)
ORDER BY p.place_id ASC NULLS LAST, p.day_of_week ASC NULLS LAST, p.hour ASC NULLS LAST
