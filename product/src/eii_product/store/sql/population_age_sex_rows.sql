-- name: population_age_sex_rows
-- params: 
-- returns: grid_key text, lon numeric, lat numeric, age_band text, sex text, people numeric, period text, source_id text
-- order: grid_key, age_band, sex, period
SELECT p.grid_key, p.lon, p.lat, p.age_band, p.sex, p.people, p.period, p.source_id
FROM pub_pop_agesex_grid AS p
ORDER BY p.grid_key ASC NULLS LAST, p.age_band ASC NULLS LAST, p.sex ASC NULLS LAST, p.period ASC NULLS LAST
