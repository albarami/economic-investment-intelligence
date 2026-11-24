-- name: layer_rail_plan
-- params: 
-- returns: feature_key text, feature_kind text, name_en text, name_ar text, geometry geometry, source_id text
-- order: feature_key
SELECT p.feature_key, p.feature_kind, p.name_en, p.name_ar, p.geometry, p.source_id
FROM pub_rail_plan AS p
ORDER BY p.feature_key ASC NULLS LAST
