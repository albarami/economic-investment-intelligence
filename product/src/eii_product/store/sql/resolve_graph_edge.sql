-- name: resolve_graph_edge
-- params:
-- returns: edge_id text, edge_type text, from_node_id text, to_node_id text
-- order: edge_id
select e.edge_id, e.edge_type, e.from_node_id, e.to_node_id
from graph_edge as e
order by e.edge_id asc nulls last
