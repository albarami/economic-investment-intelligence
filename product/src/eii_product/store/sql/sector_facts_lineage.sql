-- name: sector_facts_lineage
-- params: lineage text
-- returns: lineage_id text, table_name text, source_id text, input_class text, transform text
-- order: lineage_id, source_id
SELECT p.lineage_id, p.table_name, p.source_id, p.input_class, p.transform
FROM fact_lineage AS p
WHERE p.lineage_id = :lineage
ORDER BY p.lineage_id ASC NULLS LAST, p.source_id ASC NULLS LAST
