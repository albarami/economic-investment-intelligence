# 0034 — Licence questions of public sources are answered at a go-live: what was found and done on 2026-11-15, and the places that stand until then

| | |
|---|---|
| Status | Accepted, 2026-11-15, on the owner's words of 2026-11-14 and 2026-11-15, the second relayed by the owner's advisor under the owner's delegation; recorded by the lead, who adds no choice of its own |
| Date | 2026-11-15 |
| Owner | Project owner |
| Decided by | The project owner |
| Amends | No passage of the pack. It records that the places of item 3, which [decision 0026](0026-public-sources-used-in-full-locally.md) item 5 read strictly would not allow, stand as they are until a go-live; item 5 is unchanged for every new commit |
| Purpose | Record that version 1 is a personal, local project whose licence questions are answered when a go-live is prepared and not before; what an audit found and what repair task S2-T22 removed; what a reading of licence statements found; and the places where a figure, name or key rests on a source whose licence is not open or not confirmed, so that a go-live starts from one list. |
| Read first | [Decision 0026](0026-public-sources-used-in-full-locally.md) items 3 and 5; PUB-11, PUB-12 and PUB-13 of [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md) |

## Context

Decision 0026 item 5 says that the repository is public even though the product is local, and that no record, name or value of a source not under an open licence appears in the repository, a test, a fixture, a committed screenshot, a brief or a document. PUB-12 and PUB-13 repeat it.

On 2026-11-15 an audit of the base branch found three places that broke item 5: five expected figures of one regression row in the code of the `public_data` stage, the figures of a research regression in one row of document 07, and one name in a committed review file. The audit also named seven groups that it could not classify. Repair task S2-T22 removed the three and, after its review, a fourth (a share in the sentence on hypothesis H2 of section 16 of document 05), and added a guard with a planted violation so that an expected figure of such a source cannot be committed again. Finding F3 of that review named two further places that the repair could not remove without changing what the pack means; they are (a) and (b) of item 3.

On the same day the lead had the licence statements of five sources read live ("the reading"; see Sources). The reading took metadata and terms pages only and no record of any dataset. What it found is set out with the rows it concerns under (g) of item 3.

The lead first prepared these matters as questions for the owner. The owner answered, through the advisor, that this is a personal, local project and that such matters are not weighed at this stage; on 2026-11-14 the owner had said that the legal route is followed when the project is made for real. This record therefore asks nothing. It writes no value of any source: it names each place by document and anchor and gives the count and kind of the figures only.

## Decision

1. **Licence questions wait for a go-live.** Version 1 is a personal, local project. Whether the licence or the terms of a source allow a figure, name or key of that source to stand in the repository, in a record or in a test is not decided in version 1. It is answered when the owner prepares a go-live, by the legal route of that day. Until then no such matter is put to the owner as a question, an option or a finding.
   Amended 2026-11-18 on the owner's words of 20:23: the owner's own go-live is personal and is not the trigger; "a go-live" in this record reads as "a deployment of the system with real data integrated", and the owner raises licence and terms matters on that day.

2. **What was done stands.** The repair of task S2-T22 stands: the four places it changed stay as it left them, no figure it removed is put back, and its guard stays. Decision 0026 stands whole, and its item 5 stays the rule for every new commit: fetched data stays in the uncommitted cache, tests use invented stand-ins, and every registry row keeps `commit_allowed: false`.

3. **These places stand as they are until a go-live.** Each is a place where a figure, name or key rests on a source whose licence is not open or was not confirmed on 2026-11-15. No task changes any of them for a reason of licence or terms in version 1, and tasks build from the pack as it is written, the band file that DAT-16 asks for among them.
   - (a) The wage-band scheme. Section 5 of [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md) prints the table of twelve bands with their edges and one sentence that quotes five of the publisher's band labels; DAT-16 states the publisher's first band value and extends that band downwards as an ASSUMPTION; DAT-17's boundary fixtures and PRV-25 of document 06 rest on the same edges. The source is the registry row `wage_bands_priv`.
   - (b) The statutory minimum. The use row of `ref_min_wage` in section 2.2 of document 04 and the row `wage.minimum` of the calibration manifest in section 3 of document 05 each print three sums of a cited law; card C10 and MTH-42 of document 07 show the minimum as a rule row. The registry row is citation-only with an unconfirmed licence.
   - (c) The year bounds of the two investment rows. `custodian/publicdata/investment_pages.yaml` and the registry rows of `fdi_projects` and `investqa_pages` hold `period_first` and `period_last`; the row `fdi_projects` of section 2.2 of document 04 prints the range of announcement years with counts of records, as the lead's measurement of 2026-11-13. Both rows are on basis `owner_decision`.
   - (d) `custodian/publicdata/review/municipality_names.csv`: 59 spellings for 8 municipality codes, with no column that names the source of a spelling. PUB-27 requires the file committed.
   - (e) `custodian/publicdata/review/showcase_gazetteer.yaml` (4 entries) and `flagship_candidates.yaml` (7 entries): every entry has names in two languages and `source_id: null`.
   - (f) `custodian/publicdata/review/zone_crosswalk.csv`: 94 rows and eleven source columns, seven of them of sources on basis `owner_decision`. PUB-25 requires the file committed with one column per source.
   - (g) The registry rows on basis `none_stated`, 17 on that day: three portal datasets, two files and twelve citation-only `ref_*` rows. The reading found: the catalogue records of the three portal datasets `wage_bands_priv`, `work_hours_act` and `accident` each state the licence "CC BY" with the address of CC BY 4.0, in the same fields and words as a neighbouring row that the registry holds on basis `dataset`, and the portal's licence page says its licence "is based on" CC BY 4.0; the full licence text, on another host, was not read, and the portal's terms page holds a general sentence against reproduction "Except as otherwise provided". The archived "Copyrights" page of the publisher of `census_2020_workbook` reserves all rights and lists exceptions, personal purposes among them: not an open licence. For `cls_isic4` and the twelve citation-only rows no terms were read. A catalogue field and a licence page are what was read, not a full legal text. The registry rows stay as they are; the reading is recorded here for the go-live.
   - (h) The public history. A forward repair removes a value from the head of the base branch only; every value the audit named stays readable in the history. The history is not rewritten: rule 40 of AGENTS.md forbids it to every agent, and it is not weighed before a go-live.

4. **No further work for a reason of licence in version 1.** No further audit, repair task or review lens is opened because of a source's licence or terms. The lead keeps one list of the places above for the go-live, outside the pack.

5. **What stays strict in version 1.** A secret, a person's data, a real custodian record or any value of a file outside the public sources never enters the repository (rules 3, 13, 14 and 15 of AGENTS.md). A wrong number or claim is a defect whatever its source. Nothing in this record changes a gate, a review rule, a privacy rule or a test.

## What does not change

No requirement, registry row, band boundary, tolerance, test or guard changes by this record. Decision 0026 is not rewritten. Rule 10 of AGENTS.md is untouched: the reading notes that two of the three portal datasets hold fields of sex, nationality group or birth year, and a licence, open or not, does not settle the use of such fields.

## Passages amended

None. OPEN_ITEMS.md gains one open item that names this record and its item 3, entered by the ledger of task S2-T22, and the documentation index gains this record's line.

## Sources

- The owner's words of 2026-11-14 and of 2026-11-15, the second relayed by the owner's advisor on 2026-11-15 (project records of the run, outside the pack).
- The audit of the base branch of 2026-11-15, and the review of task S2-T22 with its finding F3 (project records of the run; no value of a source is written in either).
- The reading of 2026-11-15 (a project record of the run): thirteen requests made as a visitor, with no key and no sign-in, to three hosts. On `www.data.gov.qa`: the catalogue records of `wage_bands_priv`, `work_hours_act`, `accident` and of the comparison row `util_elec`, the licence page and the terms-of-use page. On `web.archive.org`: the headers of the workbook that the row of `census_2020_workbook` names, and the archived copies of the publisher's home page and "Copyrights" page. On `unstats.un.org`: the landing page of the classification. Only metadata and terms pages were read; no record of any dataset was requested, and the full licence text and the terms pages that stand on other hosts were not requested.
- Decision 0026 items 3 and 5, PUB-11, PUB-12, PUB-13, PUB-25, PUB-27, DAT-16, DAT-17, section 5 of document 03, card C10 and MTH-42, as they stand on the base branch; the registry `custodian/publicdata/sources.yaml`.
