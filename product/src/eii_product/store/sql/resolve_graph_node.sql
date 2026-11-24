-- name: resolve_graph_node
-- params:
-- returns: node_id text, node_type text, code text, label_en text, label_ar text
-- order: node_id
select n.node_id, n.node_type, n.code, n.label_en, n.label_ar
from graph_node as n
order by n.node_id asc nulls last
