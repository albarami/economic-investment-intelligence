-- name: resolve_zone
-- params:
-- returns: zone_code text, name_en text, name_ar text
-- order: zone_code
select z.zone_code, z.name_en, z.name_ar
from zone as z
order by z.zone_code asc nulls last
