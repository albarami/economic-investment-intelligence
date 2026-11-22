# 0089 — C8 national census release indicators

| | |
|---|---|
| Status | Proposed by task S2-P48; lead decision and different-maker acceptance owed |
| Date | 2026-11-22 |
| Scope | Documents 03 and 04; PO-S2-48; card C8 of document 07 |

## Context

Document 07 card C8 already binds its national input to the lead-described
`census_2020_workbook` Table 76: Private and Total on the uniquely labelled
Both Sexes block row in column B. Document 04 declares that release table,
but PO-S2-48 R3 FOLLOW-UP records the missing producer and indicator vocabulary.
`est_census` counts establishments and remains a separate source.

## Proposed decision

1. Add exactly `private_employed_residents`/`persons` (Private) and
   `employed_residents`/`persons` (Total) to `pub_census_national` only, period
   `2020`, source `census_2020_workbook`. Retain the period-by-indicator key,
   existing columns and establishment rows. No sex split or activity row is
   released by this producer.
2. Read the selected immutable snapshot with its verified receipt, preserving
   publisher, source address, licence, retrieval date and hash. Reuse the named
   OOXML reader and the C8 national-count parser for production and replay.
   Record producer method `frame.census.table76.v1: Both Sexes Private / Total`.
   Check the declared Table 76 sector headers, unique Both Sexes, Male and Female
   block labels in column B, finite nonnegative integer counts and positive
   Total. A missing sheet, missing or ambiguous block label, missing or invalid
   count, uncached formula, unknown indicator or wrong unit refuses.
3. Leave DAT-128 and PUB-84's audit-count pairs exactly unchanged. The two new
   Public count names do not enable audit selectors or settle applicability.
   DAT-128 and PRV-115's applicability review and fail-closed rules still apply.
   No census value is committed. No rule for a zero-denominator zone is added;
   the existing `C8:zone_denominator` refusal remains.

## Evidence and remaining decisions

The builder uses invented OOXML fixtures in the lead-described shape and
records tests and one-guard plants in PROGRESS.md, **S2-P48 C8 national release
producer — 2026-11-22**. Those checks establish no real-file correctness.
PO-S2-48 remains OPEN for the lead's real-cache replay, this proposal's
acceptance and different-maker acceptance of the implementation. No task box
is ticked by this proposal.
