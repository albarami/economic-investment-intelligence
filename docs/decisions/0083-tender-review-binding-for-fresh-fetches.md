# Decision 0083 — Tender review binding for fresh fetches

| | |
|---|---|
| Status | Proposed, for owner review |
| Date | 2026-11-21 |
| Scope | S2-T13 confirmation of `tenders_pub`; PUB-93 and PLN-25 |

## Context

The committed S2-T13 confirmation records one historical review of the portal root and terms body. The normal fetch reads six bilingual lists and archives their assembled envelope. Its retrieval time, URL and envelope hash cannot equal that historical root-page snapshot. The registry URL is the first list page and its basis note describes fetch mechanics, rather than repeating the review reason. Requiring those equalities refuses every fresh fetch.

## Decision

For a recorded tender source, the release handoff compares the archive receipt's source and key, publisher, licence basis and ID, decision record, periods, release tables, fetch URL and host, switched-off state and verified visible-text terms SHA-256 with the committed registry and confirmation. The current fetch URL must equal the registry URL. The registry's fetch host is compared case-insensitively with that URL's host, and the confirmation's reviewed page and terms URLs must name the same HTTPS origin and effective port as the registry URL. One trailing DNS dot is equivalent. A reviewed URL with user-info, a query or fragment, a backslash or non-ASCII netloc is refused. The archive's SHA-256 and UTC retrieval time must be well formed. The registry must retain a nonempty basis note and an empty skip reason. The confirmation's historical page hash, retrieval time, page URL and review reason remain review evidence; they are not compared to a new archive's envelope hash, time, first-list URL or registry mechanics note.

The existing build-public terms read records a visible-text fingerprint and archives the terms body. For this tender handoff it verifies the raw terms-body SHA-256 against the immutable terms snapshot and carries that run's verified visible-text SHA-256 into both the tender archive body and receipt, so equal page bytes with changed terms have a new archive identity. The committed confirmation's `terms_sha256` hashes the reviewed visible text. A missing terms read, changed raw body, changed visible text or absent hash refuses the handoff with `assembly_tender_terms_incomplete`. The publisher's terms wording remains a recorded fact and never decides whether tenders are permitted to be fetched or shown; this is a source-review evidence check, amending decision 0026 item 8 only to that extent. The build-level effect of this exception to decision 0059 item 1 remains an open owner decision.

## Limits

This change does not confirm a live fetch, grant reuse permission, change the tender parser, or approve the slice S2 gate. The historical confirmation and registry rows are unchanged. A changed terms body requires a new human review and confirmation rather than an automatic hash update.

The 2026-11-22 correction records the committed confirmation's `terms_sha256` as the SHA-256 of the normalised visible text of terms snapshot 52cc0c2ca6 retrieved 2026-11-21, re-read on 2026-11-22 as the same clause. It is not the raw terms-body digest. A changed visible text needs a new review. The raw terms-body digest remains the proof of the immutable snapshot. The limits sentence that the historical confirmation row is unchanged described the record before this re-review.
