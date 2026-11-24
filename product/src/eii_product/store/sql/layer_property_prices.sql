-- name: layer_property_prices
-- params: 
-- returns: district_key text, municipality_code text, period text, property_type text, deal_count bigint, median_price_per_m2 numeric, source_id text
-- order: district_key, period, property_type
SELECT p.district_key, p.municipality_code, p.period, p.property_type, p.deal_count, p.median_price_per_m2, p.source_id
FROM pub_property_sale AS p
ORDER BY p.district_key ASC NULLS LAST, p.period ASC NULLS LAST, p.property_type ASC NULLS LAST
