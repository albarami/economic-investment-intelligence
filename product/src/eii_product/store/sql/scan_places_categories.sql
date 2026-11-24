-- name: scan_places_categories
-- params: categories list[text]
-- returns: node_id text, node_type text, code text, label_en text, label_ar text, provenance text, source_id text
-- order: node_id
SELECT p.node_id AS node_id, p.node_type AS node_type, p.code AS code, p.label_en AS label_en, p.label_ar AS label_ar, p.provenance AS provenance, p.source_id AS source_id
FROM graph_node AS p
WHERE p.node_id = ANY(:categories) AND p.node_type = 'place_category'
ORDER BY p.node_id ASC NULLS LAST
