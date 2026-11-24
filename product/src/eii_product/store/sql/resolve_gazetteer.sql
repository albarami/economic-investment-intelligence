-- name: resolve_gazetteer
-- params:
-- returns: place_key text, kind text, name_en text, name_ar text, aliases text, lon numeric, lat numeric, cell bigint
-- order: place_key
select g.place_key, g.kind, g.name_en, g.name_ar, g.aliases, g.lon, g.lat, g.cell
from gazetteer as g
order by g.place_key asc nulls last
