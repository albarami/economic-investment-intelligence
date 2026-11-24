-- name: scan_places_visits
-- params: places list[text]
-- returns: venue_key text, place_id text, venue_kind text, name_en text, name_ar text, region text, period text, indicator text, value bigint, unit text
-- order: venue_key, period, indicator
SELECT p.venue_key AS venue_key, p.place_id AS place_id, p.venue_kind AS venue_kind, p.name_en AS name_en, p.name_ar AS name_ar, p.region AS region, p.period AS period, p.indicator AS indicator, p.value AS value, p.unit AS unit
FROM pub_venue_visits AS p
WHERE p.place_id = ANY(:places)
ORDER BY p.venue_key ASC NULLS LAST, p.period ASC NULLS LAST, p.indicator ASC NULLS LAST
