-- name: sector_facts_hotels
-- params: geography text
-- returns: municipality_code text, period text, facility_type text, facility_count bigint, source_id text
-- order: municipality_code, period, facility_type
SELECT p.municipality_code, p.period, p.facility_type, p.facility_count, p.source_id
FROM pub_hotels_municipality AS p
WHERE p.municipality_code = :geography
ORDER BY p.municipality_code ASC NULLS LAST, p.period ASC NULLS LAST, p.facility_type ASC NULLS LAST
