-- name: scan_places_lineage
-- params:
-- returns: lineage_id text, table_name text, source_id text, input_class text, transform text
-- order: lineage_id, source_id
SELECT p.lineage_id AS lineage_id, p.table_name AS table_name, p.source_id AS source_id, p.input_class AS input_class, p.transform AS transform
FROM fact_lineage AS p
ORDER BY p.lineage_id ASC NULLS LAST, p.source_id ASC NULLS LAST
