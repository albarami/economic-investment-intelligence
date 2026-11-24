-- name: scan_places_neighbours
-- params: categories list[text]
-- returns: edge_id text, edge_type text, from_node_id text, to_node_id text, provenance text, basis text, period text, attr_value numeric, attr_unit text, source_id text
-- order: edge_id
SELECT p.edge_id AS edge_id, p.edge_type AS edge_type, p.from_node_id AS from_node_id, p.to_node_id AS to_node_id, p.provenance AS provenance, p.basis AS basis, p.period AS period, p.attr_value AS attr_value, p.attr_unit AS attr_unit, p.source_id AS source_id
FROM graph_edge AS p
WHERE p.from_node_id = ANY(:categories) AND p.edge_type = 'found_near'
ORDER BY p.edge_id ASC NULLS LAST
