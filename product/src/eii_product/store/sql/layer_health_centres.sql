-- name: layer_health_centres
-- params: 
-- returns: feature_key text, feature_kind text, name_en text, name_ar text, period text, geometry geometry, source_id text
-- order: feature_key
SELECT p.feature_key, p.feature_kind, p.name_en, p.name_ar, p.period, p.geometry, p.source_id
FROM pub_health_centre AS p
ORDER BY p.feature_key ASC NULLS LAST
