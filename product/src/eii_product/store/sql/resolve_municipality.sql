-- name: resolve_municipality
-- params:
-- returns: municipality_code text, geometry geometry
-- order: municipality_code
select m.municipality_code, m.geometry
from municipality as m
order by m.municipality_code asc nulls last
