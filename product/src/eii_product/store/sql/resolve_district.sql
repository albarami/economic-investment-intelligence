-- name: resolve_district
-- params:
-- returns: district_key text, name_en text, name_ar text
-- order: district_key
select d.district_key, d.name_en, d.name_ar
from district as d
order by d.district_key asc nulls last
