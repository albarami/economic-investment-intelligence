# 0088 — Award proof check over the real formats

| | |
|---|---|
| Status | Accepted by the lead under L-1423 |
| Date | 2026-11-22 |
| Scope | Documents 03 and 04; S2-P44, the award proof check of S2-T29 |

## Context

The lead's live probes through the build's own transport and parser supplied the
following shapes and counts under L-1423. These are lead evidence, not a worker
fetch or a new measurement. No company name, registration or award amount is
retained here.

- R1: the intake profile selects `Approved Value`. Of 9048 cells, 8731 match
  `^([0-9]{1,3}(,[0-9]{3})*|[0-9]+)\.[0-9]{2} QAR$`; 317 contain only `QAR`.
  Calling `Decimal` on this text caused all 160 checked links to be mismatches.
- R2: the proof table's value parser reads comma-grouped amounts with two decimal
  places and literal suffix `رق`. Of 120 sampled pages, three had only that
  suffix, previously causing `schema_missing` and stopping source publication.
- R3: registrations are mostly two tokens joined by literal ` | ` on each side;
  one-token, letter-prefix/slash and slash-separated numeric forms also occur.
  Of 55 compared rows, 38 had equal token sets in different orders, 16 were
  disjoint and one overlapped. Raw-string equality lost the equal sets.
- R4: of those 55 rows, 53 had Latin-script intake names and Arabic-script proof
  names. Closed name normalisation cannot establish equality across scripts.

## Decision

1. This amends the proof comparison of decision 0064 item 41 in document 03,
   **S2-T29 cached page and awards contracts**, and document 04's awards check
   paragraph. Both the all-link and independently invoked seeded sample use the
   same reason-returning comparison and link checker. Tests use invented records
   carrying the lead's supplied shapes.
2. Intake values must match R1 exactly; proof values must match the existing
   comma-group/two-decimal/`رق` pattern. Each side removes only its declared
   separators and suffix before exact Decimal comparison. An empty or
   whitespace-only cell, or a currency suffix alone after outer trimming, is
   blank (`None` in parsed proof records), never zero. The proof reader maps
   parsed null to empty text and otherwise supplies canonical nonnegative
   two-decimal text. Other malformed proof-page text still refuses
   `schema_missing`. Malformed intake text, already admitted by the string
   schema, remains retained and yields `proof_mismatch`; it is neither blank nor
   a new source-level refusal. Absence takes precedence over malformed values.
3. Proof registrations compare as sets of nonempty tokens split on literal
   ` | `, with each token stripped. Order and duplicate tokens do not matter;
   unequal, merely overlapping and empty token sets never match. Tokens receive
   no other normalisation. The separate awards-to-public-register join remains
   unchanged, including its ambiguity and exact name-consistency checks.
4. Normalise names by the existing NFKC, case fold, whitespace collapse,
   punctuation removal and second whitespace collapse. Classify the remaining
   Unicode letters using their Unicode names: all `ARABIC` letters is `arabic`,
   all `LATIN` letters is `latin`, no letters is `none`, and any other-script
   letter or combination is `mixed`. Ignore nonletters for classification.
   Compare normalised names exactly only when both classes are equal and not
   `none`, including equal `mixed` classes. Otherwise do not compare the name;
   registration and value still must agree. No fuzzy score, transliteration,
   tolerance or threshold is introduced.
5. A link result is `matched` with reason `matched` or
   `matched_name_not_compared`; `mismatched` with reason, in fixed precedence,
   `intake_value_absent`, `proof_value_absent`, `proof_mismatch`; or `fetch_failed`
   with the unchanged reasons `proof_fetch_failed`, `unreachable`, `http_status`
   or `body_bytes`. Every intake winner on a shared link must match some proof
   candidate. Prefer a `matched` candidate to `matched_name_not_compared`; without
   either, select the fixed mismatch precedence. Any failed winner defeats the
   link under that same precedence; otherwise any name not compared labels the
   matched link. Totals add `matched_name_not_compared`, `intake_value_absent`,
   `proof_value_absent` and `proof_mismatch`; `matched` includes the first of
   these, and `mismatched` is the sum of the three mismatch counts. Samples retain
   the same reasons and counters. Receipt validation recomputes them and binds
   the derived sample to the complete evidence.

## Consequences and unchanged boundaries

The card shows `matched` and its `matched_name_not_compared` subset separately,
so registration/value agreement across scripts cannot imply that names were
checked. The full-link audit summary retains these counters; per-link details
and URLs remain only on the source receipt. This decision specifies the card
contract and does not claim a completed product card.

The match rate remains total matched divided by all checked links, including
failed fetches, with null for an empty frame. Empty all-link frames and fetch
failures remain incomplete; short samples remain incomplete. The sample stays
labelled `sample`, uses the same seed selection, and adds no proof fetch.
Publication and assembly still reject missing or inconsistent evidence, and
assembly still rejects incomplete full-link evidence even if the sample passed.
Transport bounds, retries, trust, archive, source-schema refusals, provenance,
blank retention, register matching and the ban on awarded values as turnover or
sales remain whole. Agent rules are unchanged. The lead still owes the live rate
and registration-match evidence under OI-277; invented tests establish neither.
