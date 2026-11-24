-- name: population_age_sex_bands
-- params: 
-- returns: age_band text, period text
-- order: age_band, period
SELECT p.age_band, p.period
FROM pub_pop_agesex_grid AS p
GROUP BY p.age_band, p.period
ORDER BY p.age_band ASC NULLS LAST, p.period ASC NULLS LAST
