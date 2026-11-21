# Decision 0075: Activity mappings signed by model review

| | |
|---|---|
| Status | Accepted, 2026-11-20 |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner's three answers of 2026-11-20, quoted in item 1 |
| Amends | Document 04 PUB-33 and its sign-off wording in section 6 and PUB-35; the lead's ruling of 2026-11-15 recorded in OI-203 WHY; TASKS.md S2-T04 sign-off wording and document 14's corresponding triage/risk wording; OPEN_ITEMS.md OI-16, OI-172 and OI-203. |
| Purpose | Permit individually judged activity mappings signed as model reviews, subject to an independent seeded batch audit; record the owner's confirmation of the reviewed customs baskets. |
| Read first | Document 04 section 6 and PUB-33 to PUB-40, section 7 and PUB-41; TASKS.md S2-T04; OPEN_ITEMS.md OI-16, OI-172 and OI-203; AGENTS.md rules 19, 21, 33, 35, 36 and 46. |

## Context

The activity spine's reader, queue and guards are built, while its real-feed review remains open under OI-203.
The earlier rule required a person to approve that the Arabic activity name fits the class title; the lead's
ruling of 2026-11-15 prohibited a model from signing a mapping review. The owner's answers now authorise a
recorded model review, judged code by code and checked by another maker before batch admission. This is a
new amendment under rule 46, not a claim that the queued codes have been reviewed.

OI-172 separately asked for confirmation of the customs baskets already reviewed line by line by two expert
persona models of different makers. Its recorded inventory is 74 included and 96 excluded lines. Confirmation
of those baskets does not settle the worked-example reconciliation of OI-03 or any other gate question.

## Decision

1. **Record the owner's three answers verbatim.** The owner's answers of 2026-11-20, supplied with package P25,
   retain their original typing:

   - OI-172, confirmation of the reviewed customs baskets: "i confirm ."
   - OI-16, the proposal for another-maker expert model sign-off with a seeded thirty-row audit at zero errors:
     "i agree to his recoemndation."
   - OI-203, assignment of the queued activity review to the same signer as OI-16: "i agree."

   OI-16 and OI-172 close on those answers. OI-203 stays open for the actual review. OI-03 and the other gate
   questions are outside this decision.

2. **Judge each code independently.** The signer is an expert persona model, a bilingual Arabic-English
   economic-classification specialist, of a maker other than the maker of the lead that prepared the queue.
   For each code it decides only `mapped`, when the Arabic activity name fits the class title of its four-digit
   prefix, or `not_mappable_rejected`. It never chooses another class. Seven-digit candidacy, class existence,
   scope, version and meaning checks remain unchanged. This amends PUB-33 and the contrary ruling recorded
   in OI-203 WHY. A person's signed decision retains its existing admission path.

3. **Admit a batch only after independent audit.** An auditor of a maker other than the signer's re-judges
   thirty codes drawn from the batch by a recorded seed, or every code when the batch has fewer than thirty.
   Admission requires zero errors. One error refuses the whole batch: the signer returns to code-by-code
   review, followed by a fresh audit with a fresh seed. No batch is admitted merely because a model signed it.
   The lead records the preparer's maker and verifies the signer's independence when arranging the signing;
   the audit guard additionally enforces distinct signer and auditor makers from their role strings.

4. **Bind the signed rows and the audit.** Each signed CSV row uses
   `model review: <maker> <model>, <persona>` in `reviewed_by_role`, with its ISO calendar date in `reviewed_on`
   and no personal name. Makers are single role tokens; maker comparison ignores letter case.
   `custodian/publicdata/review/activity_spine_audits.json` is a JSON list, initially empty. Each batch object has
   exactly `batch_id`, `codes`, `review_rows_sha256`, `seed`, `sampled_codes`, `signer_role`, `auditor_role`,
   `errors` and `audit_date`. Both roles use that model-role format. Batch ids are nonempty and unique; codes
   are unique seven-digit strings naming signed model decisions by that batch's signer. Each model-signed
   mapped or rejected code belongs to exactly one batch. The audit date is an ISO calendar date no earlier
   than any signing date in its batch, and `errors` is the integer zero.

   The seed is an integer from 1000000000 through 4294967295, inclusive. The deterministic draw ranks each
   code by SHA-256 of the ASCII string `seed:code`, breaking a hash tie by code, takes the first thirty or the
   whole smaller batch, then sorts the selected codes by code. `sampled_codes` must equal that ordered result.
   The signed-row hash uses every `ReviewRow` field, decoded codes, rows sorted by code and UTF-8 JSON with
   `ensure_ascii=False`, `sort_keys=True`, separators `(',', ':')` and no trailing newline. The canonical form
   and draw are implemented by `audit_rows_sha256` and `audit_sample` in `review/activity.py`.

   The adjacent `activity_spine.binding.json`, written by the lead with the first signed batch, holds `audit_sha256`, the SHA-256 of the audit file's exact bytes,
   alongside the existing code-system version and class-title inputs. Changed signed rows, changed audit bytes,
   missing or overlapping membership, incorrect samples, errors, maker conflicts, invalid seeds or dates refuse
   the spine build with specific reasons. Existing bindings without the new field remain valid for person-signed
   reviews only. The empty audit file admits no model decision. Before real signing the lead fills the class-title
   binding and review rows together with the audited records; this package adds no signed row or populated audit.

5. **Keep the product and gates unchanged.** The product shows no model-written prose. The offline gateway
   remains advisory, provider `none` stays the default, and a gateway suggestion never signs or approves a mapping.
   S2-T04's phrase "human sign-off" becomes "sign-off under decision 0075"; its criteria stay unticked where
   unticked. Recompute the mandatory queue with the reviewed baskets' supplier membership on the real cache,
   then obtain the signing, audit and committed rows and binding as the lead's next step under OI-203. The
   historical queue count is not a claim about that recomputation.

6. **Record basket confirmation without changing the baskets.** The status and reviewer-role metadata of
   `baskets.yaml` record the owner's confirmation on 2026-11-20 while preserving the two model-review roles.
   Included and excluded lines, descriptions, reasons, source hashes and original review dates stay unchanged.
   Confirmation is not a new source reading or an OI-03 reconciliation sign-off.

## Consequences and change triggers

OI-16 is decided and OI-172 is confirmed. OI-203 remains open until the lead's real-cache queue recomputation,
signing and independent audit deliver the reviewed records. Offline invented-fixture success establishes the
guards only, not a completed real review or slice gate. Another signer rule, audit size, nonzero error allowance,
class reassignment, seed range or admission path needs a new decision under rule 46. Other open items remain.

## Sources

- The owner's three verbatim answers of 2026-11-20 and the approved proposal supplied in package P25,
  **Activity mappings signed by model review under the owner's decision of 2026-11-20**.
- [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md), **6. The activity spine**, PUB-33 to PUB-40 and PUB-41;
  [TASKS.md](../../TASKS.md), S2-T04; [OPEN_ITEMS.md](../../OPEN_ITEMS.md), OI-16, OI-172 and OI-203.
- [AGENTS.md](../../AGENTS.md), rules 19, 21, 33, 35, 36 and 46;
  `custodian/src/eii_custodian/publicdata/review/activity.py`, `audit_rows_sha256` and `audit_sample`.
