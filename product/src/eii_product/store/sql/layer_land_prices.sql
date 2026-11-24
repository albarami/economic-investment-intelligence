-- name: layer_land_prices
-- params: 
-- returns: district_key text, period text, use_category text, guide_price numeric, price_basis text, source_id text
-- order: district_key, use_category, period
SELECT p.district_key, p.period, p.use_category, p.guide_price, p.price_basis, p.source_id
FROM pub_land_price AS p
ORDER BY p.district_key ASC NULLS LAST, p.use_category ASC NULLS LAST, p.period ASC NULLS LAST
