-- name: make_area_grid_cells
-- params:
-- returns: cell bigint, resolution bigint
-- order: cell
SELECT c.cell, c.resolution
FROM grid_cell AS c
ORDER BY c.cell ASC NULLS LAST
