# Decision 0095: Award pages without an award section or date

| | |
|---|---|
| Status | Proposed; S2-P66 under ruling L-1495; exact non-award heading text and lead review pending |
| Date | 2026-11-22 |
| Scope | PUB-04; S2-T29; document 03 **S2-T29 cached page and awards contracts**; amends decision 0091 item 4 |

## Context and evidence

The lead's S2-P66 diagnosis reports sixteen refused tender portal proof pages:
thirteen have no award heading, only the reviewed opened-technically,
opened-financially, combined and companies-notice headings; three have an award
section and an empty awarded-date span. This is lead-supplied diagnostic
evidence, not a worker observation or a new live result. No stored page is used
as a test fixture. The supplied diagnosis names the heading classes but omits
their exact text; the builder has requested that text rather than inventing it.

## Proposed decision

1. Amend decision 0091 item 4 only for a page with zero exact award-heading
   matches, every h3's stripped complete text in the declaration's closed
   `shape.sections[*].heading` list, and exactly one `span#lblAwardedDate`.
   The parser returns the closed marker
   `[{"proof_outcome": "proof_award_absent"}]`. The proof reader preserves it
   and the all-link and sample checkers record `result: mismatched`,
   `reason: proof_award_absent`. No table or winner is invented. The date span's
   contents are not parsed in this state. An unknown heading, a prefix-only
   heading, multiple award headings, or a missing or duplicate date span
   continues to refuse `schema_missing`. Heading matching has no prefix rule.
2. With exactly one award section and a nonempty validated table, an empty or
   whitespace-only date span yields null `award_date`. A nonempty malformed date
   still refuses `snapshot_date_missing`; an empty table still refuses
   `schema_missing`, including when its date is empty. Date-span cardinality
   remains exactly one in this state too.
3. The proof comparison does not compare dates. In `award_checks.comparison_reason`,
   the declared `value`, `registration` and `company` fields determine the
   comparison; `awards._proof_reader` projects exactly those three fields.
   Preserve that rule when the date is null. No `proof_date_absent` reason is
   introduced, and date absence alone supplies no match or mismatch.
4. Add `proof_award_absent` to the closed mismatch vocabulary and its receipt
   counter. It contributes to `mismatched`, never `matched` or `failed_fetches`.
   The existing counter and result validators recompute it and reject unknown
   reasons. Every other result, comparison precedence, denominator and sample
   rule stays as specified by decision 0088 item 5. A diagnostic refusal still
   blocks publication under decision 0091 item 4.

## Consequences and limits

The two states are explicit outcomes, with the existing source chain and
acquisition checks retained. No trust, archive, transport or publication refusal
is changed into a fetch failure. Invented tests establish neither a real match
rate nor completeness. The production non-award heading list remains empty
until the lead supplies its four exact reviewed strings; the thirteen reported
pages therefore remain unproved by this delivery. Independent different-maker
review and stored-proof replay after merge remain lead-owned. The evidence and
open dependency are recorded under S2-P66 in PROGRESS.md and OPEN_ITEMS.md.
