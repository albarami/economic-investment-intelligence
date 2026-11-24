-- name: control_shape
-- params:
-- returns: shape_id text, shape geometry
-- order: shape_id
SELECT g.shape_id, g.shape
FROM control_shape AS g
ORDER BY g.shape_id ASC NULLS LAST
