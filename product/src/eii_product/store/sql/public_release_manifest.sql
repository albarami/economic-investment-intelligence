-- name: public_release_manifest
-- params:
-- returns: release_id text, table_name text, provenance_class text, file text, sha256 text, row_count bigint, schema_sha256 text, release_kind text, release_contract_version text, build_id text, built_at text, code_version text, rules_version_id text, engine_versions text, fc_register_sha256 text
-- order: table_name
SELECT p.release_id, p.table_name, p.provenance_class, p.file, p.sha256, p.row_count, p.schema_sha256, p.release_kind, p.release_contract_version, p.build_id, p.built_at, p.code_version, p.rules_version_id, p.engine_versions, p.fc_register_sha256
FROM release_manifest AS p
ORDER BY p.table_name ASC NULLS LAST
