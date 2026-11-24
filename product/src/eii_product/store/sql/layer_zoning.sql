-- name: layer_zoning
-- params: 
-- returns: feature_key text, zoning_code text, source_layer text, permitted_uses text, height_rule text, setback_rule text, geometry geometry, source_id text
-- order: feature_key
SELECT p.feature_key, p.zoning_code, p.source_layer, p.permitted_uses, p.height_rule, p.setback_rule, p.geometry, p.source_id
FROM pub_zoning AS p
ORDER BY p.feature_key ASC NULLS LAST
