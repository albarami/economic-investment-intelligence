-- name: scan_places_sources
-- params:
-- returns: source_id text, publisher text, title text, url text, licence text, licence_basis text, retrieved_on date, sha256 text, attribution text
-- order: source_id
SELECT p.source_id AS source_id, p.publisher AS publisher, p.title AS title, p.url AS url, p.licence AS licence, p.licence_basis AS licence_basis, p.retrieved_on AS retrieved_on, p.sha256 AS sha256, p.attribution AS attribution
FROM source_registry AS p
ORDER BY p.source_id ASC NULLS LAST
