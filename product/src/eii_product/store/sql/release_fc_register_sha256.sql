-- name: release_fc_register_sha256
-- params:
-- returns: table_name text, fc_register_sha256 text
-- order: table_name
SELECT p.table_name, p.fc_register_sha256
FROM release_manifest AS p
ORDER BY p.table_name ASC NULLS LAST
