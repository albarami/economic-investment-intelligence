-- name: public_lineage_for_table
-- params: table_name text
-- returns: lineage_id text, table_name text, source_id text, input_class text, transform text
-- order: lineage_id, source_id
SELECT p.lineage_id, p.table_name, p.source_id, p.input_class, p.transform
FROM fact_lineage AS p
WHERE p.table_name = :table_name
ORDER BY p.lineage_id ASC NULLS LAST, p.source_id ASC NULLS LAST
