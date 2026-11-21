# Decision 0083 — Tender review binding for fresh fetches

| | |
|---|---|
| Status | Proposed, for owner review |
| Date | 2026-11-21 |
| Scope | S2-T13 confirmation of `tenders_pub`; PUB-93 and PLN-25 |

## Context

The committed S2-T13 confirmation records one historical review of the portal root and terms body. The normal fetch reads six bilingual lists and archives their assembled envelope. Its retrieval time, URL and envelope hash cannot equal that historical root-page snapshot. The registry URL is the first list page and its basis note describes fetch mechanics, rather than repeating the review reason. Requiring those equalities refuses every fresh fetch.

## Decision

For a recorded tender source, the release handoff compares the archive receipt's source and key, publisher, licence basis and ID, decision record, periods, release tables, fetch URL and host, switched-off state and terms-body SHA-256 with the committed registry and confirmation. The current fetch URL must equal the registry URL; the registry's fetch host must equal the hosts of its URL and the confirmation's reviewed page and terms URL. The archive's SHA-256 and UTC retrieval time must be well formed. The registry must retain a nonempty basis note and an empty skip reason. The confirmation's historical page hash, retrieval time, page URL and review reason remain review evidence; they are not compared to a new archive's envelope hash, time, first-list URL or registry mechanics note.

The existing build-public terms read records a visible-text fingerprint and archives the terms body. For this tender handoff it also carries the SHA-256 of that run's raw terms body into the archive receipt, because the committed confirmation's `terms_sha256` hashes the reviewed raw body. A missing terms read, changed raw body or absent hash refuses the handoff. The publisher's terms wording remains a recorded fact and never decides whether tenders are permitted to be fetched or shown; this is a source-review evidence check, amending decision 0026 item 8 only to that extent.

## Limits

This change does not confirm a live fetch, grant reuse permission, change the tender parser, or approve the slice S2 gate. The historical confirmation and registry rows are unchanged. A changed terms body requires a new human review and confirmation rather than an automatic hash update.
