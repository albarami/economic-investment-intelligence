# Decision 0107: A citation page the publisher no longer serves

| | |
|---|---|
| Status | Proposed, 2026-11-24 (task S2-P81); different-maker review and acceptance remain pending |
| Date | 2026-11-24 |
| Scope | [Document 04](../04_PUBLIC_DATA_PACK.md) section Landmark citation publisher rows (S2-P53-cit); the registry row of `landmark_skyscraperpage_com` in `custodian/publicdata/sources.yaml`; the registry parser `custodian/src/eii_custodian/publicdata/fetch/registry.py` |
| Amends | Nothing until accepted. Beside [decision 0093](0093-landmark-hand-list-in-one-reviewed-cache-record.md) item 3, without editing its text |
| Purpose | Let one landmark citation row whose page the publisher no longer serves stay registered as a SKIP by one closed reason word, so that the live build proceeds, while every other fetch failure still refuses assembly |
| Read first | Decision 0093 items 1 to 3; [decision 0026](0026-public-sources-used-in-full-locally.md) items 2, 3 and 5; AGENTS.md rules 5, 7, 19, 36, 37 and 46 |

## Context

Decision 0093 places the landmark hand list in one reviewed cache record and
keeps the citation snapshots and their receipts uncommitted. Each landmark
citation publisher has one registry row per cited page.

The lead's live step LIVE-S2.L2d3 on head `1dba941bcf`, on 2026-11-24, passed
799 entries, reported the registered SKIPs and failed exactly one: the single
page of `landmark_skyscraperpage_com`, check `http_status`. Assembly refused at
its `fetch_archive` stage, as designed. The same page passed a lead probe on
2026-11-23. A lead-shell probe of 2026-11-24, recording status codes only,
found that the page answers 404 to the project transport, to the standard
library with the project agent and with a browser agent, and to a command-line
client with a browser agent, without a redirect; every address variant answers
404 and the site root answers 403. No current page of that citation is
reachable from the build machine. The source has exactly one registry row.

No landmark height row of the reviewed cache record cites this page.

## Decision

1. The row stays in the registry, unchanged except for two fields:
   `skip_reason` is the closed word `page_not_served`, and `basis_note`
   gains one sentence naming the date the page was found not served
   (2026-11-24) and this record.
2. For a landmark citation row (a `source_id` beginning `landmark_`), the
   registry parser accepts an empty `skip_reason` or one word of a closed set
   that holds `page_not_served` alone. Any other reason on such a row is
   refused at load with `citation_skip_reason`. The set of technical reasons
   that let a paged layer omit its layer number is not changed.
3. build-public reports the row as a registered SKIP with that word and sends
   no request for it; assembly proceeds past it. A fetch failure of any row
   without a registered reason, this row included once the word is removed,
   still fails the build and refuses assembly.
4. The lead re-probes the page, status codes only, at each live build. When
   it answers 200 again, the word and the sentence are removed in a new task
   and the row is fetched as before. The re-probe is open item OI-411.
5. Nothing else in decision 0093 changes: no value, calculation, rule, gate or
   check other than item 2 above, and no other registry row.

## Evidence and consequences

The probe evidence is the lead's probe record of 2026-11-24, held outside the
pack. The offline implementation evidence is the S2-P81 row of PROGRESS.md.
While the word stands, the snapshot of this page is absent from a new build,
and a landmark height citing this page refuses with the closed detail
`registry_skipped` before any snapshot is read, so a valid snapshot kept from
an earlier build cannot carry it either. No other landmark source's coverage changes.

## What would change this decision

A second citation page not served, a page that moved to a new address, or a
reason other than a page not served needs its own record; the closed set is
not widened by this one.
