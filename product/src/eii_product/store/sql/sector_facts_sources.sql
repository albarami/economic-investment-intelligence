-- name: sector_facts_sources
-- params: sources list[text]
-- returns: source_id text, kind text, publisher text, title text, url text, licence text, retrieved_on date, sha256 text
-- order: source_id
SELECT p.source_id, p.kind, p.publisher, p.title, p.url, p.licence, p.retrieved_on, p.sha256
FROM source_registry AS p
WHERE p.source_id = ANY(:sources)
ORDER BY p.source_id ASC NULLS LAST
