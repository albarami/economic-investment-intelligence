# 0024 — One name of the private registry passes in two places

| | |
|---|---|
| Status | Accepted, 2026-11-14 |
| Date | 2026-11-14 |
| Owner | albarami |
| Decided by | The owner, in his note of 2026-11-14 on the satellite imagery provider's name (ruling L-151) |
| Amends | [decision 0012](0012-neutral-source-labels-and-no-product-comparisons.md) (consequences: the public repository never lists the names of the private registry) |
| Purpose | Record that one name of the private forbidden-name registry may appear in the public repository in two places only, and how the documentation check enforces that. |
| Read first | [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md) TST-263, [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md) REV-25, [10_FRONTEND.md](../10_FRONTEND.md) section "7. The basemap" |

## Context

The private registry of names that must not appear in the repository is a patterns file outside it, which `scripts/check_docs.py` loads when the environment names it (REV-25). Public data attribution is required (AGENTS.md rule 15) and every Public input is cited in the source registry of document 04 (rule 5), so the satellite imagery source that a later task adds needs its provider's credit on the map and its rows in document 04; that provider's name is on the private registry. Without an exception the commit hook refuses both.

## Decision

1. One name of the private registry may appear in the two places of TST-263, and nowhere else: a source row of document 04 section "2. Source registry" whose source ids are listed for it, and the map attribution line of `web/src/stage/attribution.ts`.
2. The repository knows the name only by the SHA-256 of its case-folded text, listed in `scripts/check_docs_place_exceptions.toml`, a configuration of at most one entry with exactly `sha256`, `reason` and `source_ids`. A second name needs a new owner note and a reviewed change of that limit.
3. Whenever a digest is listed, the check refuses the name in identifier forms anywhere in the files git lists and in paths, with or without the private list (check 8 of `scripts/check_docs.py`).
4. The configuration is committed with no entry by task S1-T14. The one real entry is the first commit of the task that adds the imagery source, made before its builder starts; that task's reviewer checks the digest against the name as written in its places.
5. The digest stands in for the name but does not hide it: anyone holding a list of candidates can confirm it.

## Evidence

The planted cases of TST-263 in `scripts/tests/test_check_docs_exceptions.py`, with invented names only, and the run recorded for task S1-T14 in [PROGRESS.md](../../PROGRESS.md).

## Consequences

- Decision 0012's consequence that the public repository never lists the names of the private registry now reads: it lists none of them, except one name in the two places of TST-263.
- No check sees commit messages, branch names, pull-request text, images or translated, transliterated or shortened forms of the name; the task that adds the imagery source carries the rules of the scope of S1-T14 in [TASKS.md](../../TASKS.md) for them.

## Amended passages

TST-140 and TST-263 of document 12, REV-25 of document 15, the Attribution paragraph of document 10 section "7. The basemap".

## What would change this decision

A new owner note: a second name, the removal of the provider, or a change of the two places.

## Open questions and assumptions

The lead confirms in private that the name has at most four parts and at most 64 bytes, so that check 8 sees its identifier forms, and confirms once that the run fails without the private list when the name is planted in a refused place.

## Sources

The owner's note of 2026-11-14 (ruling L-151); task S1-T14.
