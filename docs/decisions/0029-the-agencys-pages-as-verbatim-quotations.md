# 0029 — The agency's pages as verbatim quotations

| | |
|---|---|
| Status | Accepted, 2026-11-19, the owner's acceptance relayed by the owner's advisor |
| Date | 2026-11-19 |
| Owner | Project owner |
| Decided by | The owner's acceptance of 2026-11-19, relayed by the owner's advisor at 05:49, in the owner's exact words "all yes and the rotation i will tell you when", answering yes to accepting this record and yes to option (a) of finding F3. The owner's own decision is [decision 0064](0064-the-narrowing-rows-decided.md) items 3 and 32: the agency's page text is shown in full, unchanged, as a quotation with the date read, and the full-page column is added once this record settles it. |
| Amends | DAT-143 and the `pub_investqa_record` row of section 7.3 of [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), through the appendix that part B of task S2-T39 applies once; AGENTS.md and CLAUDE.md rule 23 and their Status row, byte-identical, applied when this record is accepted (appendix item 6); DAT-155 of [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), the numeral rule of section 5, check 1 of the provenance audit of section 13, the "Digits are Western" line and FE-62 of [10_FRONTEND.md](../10_FRONTEND.md), the "Digits are Western" line and DES-30 of [11_DESIGN_DIRECTION.md](../11_DESIGN_DIRECTION.md), TST-94 of [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md), REV-24 of [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md), and BE-114 of [08_BACKEND.md](../08_BACKEND.md), applied when this record is accepted (appendix item 7); PUB-88 of [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md), applied when this record is accepted (appendix item 8); the decision index of docs/README.md. Nothing else. |
| Purpose | Settle the full-page quotation of the agency's pages: its release column and grain, what "in full and unchanged" means for stored text, the rendering and its named numeral exception, the two languages, the checks the column passes before release, and what part B of task S2-T39 builds, so that the task's second acceptance criterion can be built and the column list of document 03 section 7.3 is written once (OI-178). |
| Read first | [Decision 0064](0064-the-narrowing-rows-decided.md) items 3 and 32; DAT-143, DAT-155 and the `pub_investqa_record` row of section 7.3 of [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md); PUB-88 of [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md); AI-27, AI-37 and AI-111 of [09_AI_ASSISTANT.md](../09_AI_ASSISTANT.md); FE-40, FE-62, FE-121 and FE-122 of [10_FRONTEND.md](../10_FRONTEND.md); BE-114 of [08_BACKEND.md](../08_BACKEND.md); DES-30 of [11_DESIGN_DIRECTION.md](../11_DESIGN_DIRECTION.md) and REV-24 of [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md); PRV-72 and PRV-115 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md); TST-94 and TST-142 of [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md); OI-178 and OI-181 of OPEN_ITEMS.md; AGENTS.md rules 5, 7, 8, 15, 19, 21, 22, 23, 24 and 25 |

## Context

- Decision 0017 item 7 loads the sector, opportunity, incentive, set-up and law pages of the agency's site into structured records (`pub_investqa_record`, PUB-88). DAT-143 fixes their shape: keys, titles, order, references, links and typed incentive parameters, "never a page's paragraphs"; screen text is rendered by application templates with a link to each page.
- [Decision 0064](0064-the-narrowing-rows-decided.md) item 3 keeps the full-page quotation — the agency's page text shown in full, unchanged, as a quotation with the date read, with no model-written summary or translation (rule 21) — and item 32 restores the rest of the investment sources: the agency's Arabic pages are read, the full-page column is added once this record settles it, and the FDI project-to-area crosswalk is filled by lead review, carried by task S2-T39.
- Part A of task S2-T39, not merged at this record's date, is planned to keep the original page bytes in the uncommitted cache with page language, order, hash and retrieval date, and to read them back unchanged through an explicitly selected manifest; it chose no serialization, release column or rendering. The interim row of section 7.3 still describes the earlier keys and says "In this task the release table `pub_investqa_record` still keeps the rule of DAT-143 (no paragraph column)" (OI-178).
- OI-181 records that the task's inventory holds the English pages only and recommends the Arabic reading once this record lands, because each language shows the agency's own text.
- The tension this record settles: rules 21 to 23, AI-37, AI-111 and FE-121 send every rendered numeral through the Fact chip family, while a verbatim page text holds numerals inside the publisher's own prose that cannot become chips without parsing the text — and parsing is a change.
- [Decision 0026](0026-public-sources-used-in-full-locally.md) item 5 keeps every value of the source out of the repository; the release is not the repository, so the page text lives in the release and the uncommitted cache, and tests keep using synthetic pages of the same shape (DAT-143; [decision 0034](0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md)).

## Decision

1. **The release column: a new Public table `pub_investqa_page`, one row per page and language (RECOMMENDED).**
   Options: A — this table; B — a `page` record type and a `page_text` column on `pub_investqa_record`; C — paired `page_text_en` and `page_text_ar` columns on a page row.
   A is RECOMMENDED: the grain of `pub_investqa_record` is a typed record, not a page; a separate table leaves the closed `record_type` list untouched and keeps DAT-143's "no paragraph column" literally true of the record table. B is refused: it widens the closed list, leaves most record columns null on page rows, and makes the paragraph check need a carve-out on the same table. C is refused: paired columns hide a missing language and invite filling one language from the other, which item 4 forbids.
   Columns (written out in appendix item 2): `page_key` string (lower snake case from the page's path, as `record_key` forms it); `page_language` (`en`, `ar`: the language of the fetched page as the page itself states it); `sequence` int (Y: the page's order in the site's own page list; null where the list gives none); `page_title` string (Y: the page's own title as published; null where the page gives none); `page_url` string (the page's own address, shared with `pub_investqa_record.page_url`); `retrieved_on` date (the retrieval date of the fetched snapshot the row is built from, selected through the explicitly selected manifest of the fetch path); `page_sha256` string (the SHA-256 of the original fetched page bytes, 64 lowercase hexadecimal characters); `extractor` string (`investqa_page_text@1`, the version of the deterministic extraction that produced `page_text`); `page_text` string (the page's own text under item 2; a page whose text fails a release text check of item 5 has no row). The table's provenance is `public`, its evidence status Observed, and `source_id` joins `source_registry` as on every Public table. The Arabic and English rows of one page carry the same `page_key`, taken from the English page's path; the pairing is the one the page itself declares (its alternate-language link) or, where it declares none, the reviewed page list of OI-181; a page with no declared or listed counterpart is shown in its own language with the missing-page state for the other. A page that states no language, or one that differs from its list entry, is refused per page as in item 5. The page rows join the record rows through `page_url`; no record column changes. DAT-143 is amended by the exact word changes of appendix items 3 and 4.

2. **"In full and unchanged": the versioned deterministic extraction `investqa_page_text@1` over the archived page bytes (RECOMMENDED).**
   The stored text is produced from the original fetched page bytes that the explicitly selected manifest names, never a latest file or mutable pointer, by a deterministic, versioned extraction. The bytes are decoded by their byte-order mark, else the charset of the fetch receipt, else the page's `<meta charset>`; a page that fails to decode, or declares none, is refused per page as in item 5. Before extraction the build recomputes SHA-256 over the bytes it read and requires equality with `page_sha256` and with the hash the selected manifest records; a difference refuses the page. The page's text is the visible text of the page's own content region — the element holding the heading-led blocks the record reader parses. Navigation, header, footer, side menus, cookie and consent blocks, scripts, styles, vector graphics, comments and form controls are not the page's text. 'Visible' is structural: no style sheet or script is evaluated; a node inside an element of the recorded exclusion list, or under an element with the `hidden` attribute or `aria-hidden="true"`, is not text. The extraction takes the region's visible text nodes in document order; text is normalized to Unicode NFC; a whitespace run collapses to one space and a node's ends are trimmed; a node empty after trimming is dropped; a block boundary becomes one newline. Nothing is added, dropped, reordered or reworded beyond that rule; anchor text is kept, and a link's address is not text. A reader proves the text unchanged: `page_sha256` names the original bytes, `extractor` names the version, and the release build re-reads the selected snapshot's bytes, re-runs the recorded version and requires byte-equality with `page_text`; a planted difference fails. Refused alternatives: storing the raw page markup, which is not the page's text and would need run-time sanitization, and storing a picture of the page, which is not text, carries no language mark and fails accessibility.

3. **Rendering: the `source_quotation` component and the `verbatim-quotation` exception to rule 23 (RECOMMENDED).**
   Application templates render the quotation as a quotation block with the source, the date read and the link: the body is the stored `page_text` as one bidirectionally isolated run marked with `lang` and `dir`; the caption is template text — the publisher, the page title, `retrieved_on` by the `reference` variant of the Fact chip family, not a fact (FE-122), and `page_url` as the link; the caption template states that the quotation is the agency's own words, and nothing in it is a figure, forecast or advice of this product. AI-27 stands: the page's body text never reaches the model; a model may name a record or page key at most, and never receives or emits a character of the text.
   Numerals inside the quotation are the publisher's own words and cannot become Fact chips without parsing, which item 2 forbids. The narrow, named exception **`verbatim-quotation`** to rule 23 applies: a numeral that is a character of the stored text of `pub_investqa_page.page_text` may render inside the body element of the `source_quotation` component, and nowhere else. Its limits: the exception is bound to that one element of that one component; the text passes to it as one opaque run, so nothing parses, extracts, re-renders or reuses a numeral from it; it fills no fact slot, claim slot, question slot, stage directive or model input; every numeral outside it stays in the Fact chip family, with the build-time lint unchanged and the running-page provenance audit narrowed only by appendix item 7; and the body is visually and structurally a quotation under its source and date, so its numbers are visibly the publisher's own words. Refused alternatives: extracting the numerals of the quotation into chips (a derivation over text, which changes what is shown and lets code compute on words) and removing digits (not "in full"). Tests the exception carries: a component test renders the body byte-equal to the stored text inside the isolate; a planted numeral outside the element fails the unchanged lint; a planted brief, claim, question or directive carrying page text or a slice of it is refused; AI-37's template numeral scan is unchanged and a planted template numeral fails; a `page_text` value planted as a fact's value is refused by the fact schema, because it is no `published_text` of DAT-155's closed form.

4. **Both languages.** Each language shows the agency's own text of that language, and never a translation: a translated line is not the agency's own words, and it is generated text no rule admits (rule 21; the KEEP's "no translation" of decision 0064 item 3). The Arabic quotation renders right-to-left in its own isolate, `dir="rtl"` and `lang="ar"`, in the publisher's order; digits and Latin runs inside it stay exactly as published, with no conversion, and only the chrome around the quotation mirrors — Arabic mirrors chrome and reading order, not numerals. A page missing in one language has no row for it: the catalogue's missing-page sentence, a template, shows the page as missing with its link and the date read, and the text is never filled from the other language (OI-181).

5. **The checks the column passes before release.** `page_text` is a string column like every other and keeps every scan a string column keeps: the release text-token scan reads it as text, so a bare run of exactly eight or eleven digits fails it (TST-142; rule 9). For `page_text`, a digit is any character of Unicode category Nd (Western, Arabic-Indic and Extended Arabic-Indic), read after NFC; a run of exactly eight or eleven such characters, mixed scripts included, is a hit. This record applies to `page_text` the release contact scan that the `pub_tender` row of section 7.3 applies to that table's string columns: e-mail-address and telephone-number shapes. The release scan of PRV-72 reads it for synthetic identifiers, canary markers and register numbers. A page whose text holds such a token is refused whole: its `pub_investqa_page` row is not written, the build report records the page key, the check and the reason, and the page's typed records still show with their link. Nothing is cleaned into the column: unlike a tender's title fields, which are record text cleaned under a stated rule, this column is the page itself, and verbatim admits no redaction. Refusal per page is RECOMMENDED over refusing the whole build — one contact block on one page would remove every page's quotation while the shipped release still carries no token, so the guard is unweakened — and over exempting the column, a weakening rule 12 forbids: a planted token must still refuse. On a refusal the release ships without that page's text, the build report names the page and the reason, and the display shows the missing-page state of item 4. The table's rows enter the public-totals inventory of PRV-115 as `row:` entries with status `not_applicable` and reason `source_only` — a page text is no applicable total — beside the registry row's `source:` entry.

6. **What part B builds and tests.** Part B of task S2-T39 lists and reads the agency's Arabic pages through the normal seam (OI-181); runs `investqa_page_text@1` over the bytes of each explicitly selected snapshot for both languages and writes `pub_investqa_page`; applies this record's appendix to document 03 once (OI-178); and adds the `source_quotation` component, its caption templates, the missing-page template and the `verbatim-quotation` exception to the catalogue and to the lint's allow-list. Its tests use synthetic pages of the same shape in both languages, and nothing fetched is committed: determinism — the same bytes give the same text, re-extraction is byte-equal with the stored column, and a planted reordered element changes the text; refusals — a planted bare run of exactly eight and one of exactly eleven digits, an Arabic-Indic run of exactly eight digits built at run time (TST-09), a planted e-mail-shaped token, a planted text that differs from the bytes the hash names, and bytes whose hash differs from the manifest's each refuse the page; keys — a duplicated `(page_key, page_language)` pair is refused, and a planted row whose `page_language` differs from the language the page states is refused (item 1); languages — a page with no Arabic row shows the missing template, and the Arabic quotation renders right-to-left inside its isolate against a reviewed screenshot; rendering — the body is byte-equal, a planted numeral outside the component fails the lint, a numeral in a `source_quotation` body that differs from the stored text fails the provenance audit, page text planted in a claim, slot or directive is refused, a planted template numeral fails AI-37's scan, and an Arabic quotation holding Arabic-Indic digits passes FE-62's scan, and a planted Arabic-Indic digit outside the `source_quotation` body fails it; and the inventory — every row enters PRV-115 as a `row:` entry with status `not_applicable` and reason `source_only`.

7. **Forward-looking statements inside the quotation (option (a), confirmed by the owner on acceptance).**
   A page shown in full may state a figure for a future period, a forecast or a call to invest, and the pack's rules on them must be settled for the quotation: DAT-143 loads no figure "a page states for a future period, or as a forecast" and its check fails "a forward-looking figure"; PUB-88 loads no page-stated forecast as a figure and links to the page instead; rules 24 and 25 forbid claiming a forecast, an estimate or a base rate that tested code did not compute and any advice to act; and FE-40 keeps the words "will", "likely", "best" and "forecast" out of the string catalogues. The open choice is whether those rules reach the quotation.
   - (a) Show them as the publisher's own words — DECIDED: the owner confirmed this option on 2026-11-19, the acceptance relayed by the owner's advisor. It follows decision 0064 item 3, the page text in full and unchanged: a forecast inside the quotation body is the publisher's own statement, never a figure, fact or advice of this product. The edits it carries are written out: the caption template of item 3 states that nothing in the quotation is a figure, forecast or advice of this product; the rule 23 text of appendix item 6 names a quotation under the exception no forecast, estimate or advice of the product; DAT-143's forward-looking sentence and check gain the clauses of appendix items 3 and 4 so that a forward-looking figure is still never loaded as a record field or a fact; PUB-88 gains the same clause (appendix item 8); and FE-40's word list applies to catalogues and templates and not to `page_text`.
   - (b) Refuse the page per page through a reviewed list of forward-looking markers. Its reason: it keeps a publisher's forecast or call to invest off the screen entirely. Its cost: it removes part of the page, so the text is no longer shown in full as decision 0064 item 3 keeps it, and the reviewed list and its planted test would first have to be defined in the change that accepts this record.
   The lead's recommendation was (a); the owner confirmed the choice on acceptance, 2026-11-19. Under (a) a publisher's forecast reaches the screen only as opaque quoted text under the caption of item 3, and the typed record columns still load no such figure.

## Evidence

- [Decision 0064](0064-the-narrowing-rows-decided.md) item 3 (KEEP: the quotation in full, unchanged, with the date read; no model-written summary or translation) and item 32 (the full-page column once this record settles it; the Arabic pages; task S2-T39).
- DAT-143 and the `pub_investqa_record` row of section 7.3 of [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md); PUB-88 of [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md); OI-178 and OI-181 of OPEN_ITEMS.md.
- AGENTS.md rules 21, 22 and 23; AI-27 (the page's body text never reaches the model), AI-37 (the build-time template numeral scan), AI-111 and FE-121 (a record's text is an isolated run with its language marked, and every number in a record is a Fact chip — the structured records, not the page quotation).
- TST-142 of [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md) (the release text-token scan), the contact scan this record applies to `page_text` (the scan the `pub_tender` row of section 7.3 applies to that table's string columns: e-mail-address and telephone-number shapes), and PRV-72 and PRV-115 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md) (the release scan and the public-totals inventory).
- [Decision 0026](0026-public-sources-used-in-full-locally.md) item 5 and [decision 0034](0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md) (values of a source without an open licence stay out of the repository; the release is not the repository).
- DAT-155 of [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md) (the closed `published_text` form that a page's whole text cannot meet).

## Consequences

- DAT-143 is amended by the exact word changes of appendix items 3 and 4; the `pub_investqa_record` row of the section 7.3 Columns table is rewritten and the `pub_investqa_page` row added, each applied once by part B of task S2-T39; the catalogue row of section 7.2 (appendix item 5) goes with the same change.
- The `source_quotation` component, its caption templates and the `verbatim-quotation` exception enter the closed catalogues in part B's own reviewed change; rule 23 reads with the named exception, and nothing else about it changes — AI-37's build-time scan is unchanged.
- OI-178 is settled for the page column only; the typed record columns stand as written. OI-181's Arabic reading runs in part B.
- AGENTS.md and CLAUDE.md rule 23 is amended, byte-identical in both files, in the change that accepts this record (appendix item 6); the same change applies appendix items 7 and 8 to DAT-155, documents 10, 11, 12 and 15, BE-114 and PUB-88; no fetched page, record or value is committed; no fact, figure or gate changes.

## What would change this decision

- A changed page structure the recorded extractor cannot read: the recorded version stays, and a new element set is a new extractor version named on the rows, with the contract revision of DAT-120 and DAT-121 where the column list changes.
- A publisher terms change on the going-live list of decision 0026 item 4 and decision 0034 item 1.
- An owner decision on the quotation or on the named exception.

## What is not decided

- The exact element list of `investqa_page_text@1` is fixed in part B's reviewed parser change on the synthetic page of the same shape; this record fixes the rule it follows — the page's own content region, its visible text nodes in document order and the stated whitespace rule — and that its version is recorded on every row.
- A page's own heading-led blocks may repeat inside `page_text` what `pub_investqa_record` holds as typed fields: they do, because the quotation holds the whole content region, and the typed fields still come only from the record table.
- The going-live position of the source, which stays on the list of [17_DEPLOYMENT_HARDENING.md](../17_DEPLOYMENT_HARDENING.md) (decision 0026 item 4).

## Appendix: the exact edits — items 1 to 5 applied once to document 03 by part B of task S2-T39; items 6 to 8 applied by the change that accepts this record

1. In the Columns table of section 7.3, the `pub_investqa_record` row is replaced by:

   ```
   | `pub_investqa_record` | The reader writes into the uncommitted cache page records and heading-led block records with their text items, links, order and parent. In this task the release table `pub_investqa_record` still keeps the rule of DAT-143 (no paragraph column). This record does not change the typed record columns, which the release build fills from those cache records. The release table `pub_investqa_record` holds the typed records of the agency's pages under DAT-143; the verbatim text of a page is held by `pub_investqa_page` ([decision 0029](decisions/0029-the-agencys-pages-as-verbatim-quotations.md)), never by this table. Release columns: `record_type` (`sector`, `opportunity`, `incentive`, `incentive_parameter`, `setup_step`, `law`); `record_key` string (lower snake case from the page's path; for an `incentive_parameter`, the package key and the parameter kind joined by a colon); `parent_key` (Y: the sector of an opportunity or the package of a parameter; null otherwise); `sequence` int (Y: the order of a set-up step on its page; null otherwise); `title_en` string; `title_ar` string (Y: null when the page has no Arabic version); `reference` string (Y: a law's number and year as the page states it; null otherwise); `link_url` string (Y: the link a law page gives; null otherwise); `activity_keys` string (Y: semicolon-separated activity spine keys of a sector or opportunity, through a committed, reviewed crosswalk; null otherwise); `parameter_key` (Y: on `incentive_parameter` rows only, one of the four parameter kinds of the break-even card of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md), or `other` for a parameter that the calculator does not use); `value` decimal(18,4) (Y: on `incentive_parameter` rows only; null when the page states no number); `unit` (Y: `ratio` for a share from 0 to 1, `qar_per_month` for a monthly amount, or as the page states it for `other`); `duration_months` int (Y: the duration the page states; null when it states none); `as_stated` string (Y: the page's own wording of a parameter, kept for the reviewer's check; screens render template text); `period` (Y: the period the page states for a figure; null when it states none, and the fact then takes the retrieval date); `page_url` string (the page's own address; it joins `pub_investqa_page.page_url`) |
   ```

2. Directly after it, the row:

   ```
   | `pub_investqa_page` | `page_key` string (lower snake case from the page's path, as `record_key` forms it); `page_language` (`en`, `ar`: the language of the fetched page as the page itself states it); `sequence` int (Y: the page's order in the site's own page list; null where the list gives none); `page_title` string (Y: the page's own title as published; null where the page gives none); `page_url` string (the page's own address, shared with `pub_investqa_record.page_url`); `retrieved_on` date (the retrieval date of the fetched snapshot the row is built from, which the explicitly selected manifest of the fetch path names); `page_sha256` string (the SHA-256 of the original fetched page bytes, 64 lowercase hexadecimal characters); `extractor` string (`investqa_page_text@1`, the version of the deterministic extraction that produced `page_text`); `page_text` string (the page's own text, extracted from the archived bytes the hash names and never edited, summarized, translated, cleaned or re-parsed; the release check reads `page_text` with TST-142's text-token scan, the contact scan of decision 0029 item 5 and PRV-72's scan; a page whose text fails one has no row, and the build report names the page key, the check and the reason). The Arabic and English rows of one page carry the same `page_key`, taken from the English page's path; the pairing is the one the page itself declares (its alternate-language link) or, where it declares none, the reviewed page list of OI-181; a page with no declared or listed counterpart is shown in its own language with the missing-page state for the other. A page that states no language, or one that differs from its list entry, is refused per page as in item 5 of decision 0029. |
   ```

3. In DAT-143's requirement column, the sentence "never a page's paragraphs." is replaced by:

   ```
   never a page's paragraphs; a page's own text is held by `pub_investqa_page` as a verbatim quotation under [decision 0029](decisions/0029-the-agencys-pages-as-verbatim-quotations.md), one row per page and language, and never in this table.
   ```

   and the sentence "Screen text is rendered by application templates from these records, with a link to each page." is replaced by:

   ```
   Screen text is rendered by application templates from these records, with a link to each page; the page's own text is rendered verbatim as a quotation with its source, the date read and the link (decision 0029).
   ```

   and the sentence "A figure that a page states for a future period, or as a forecast, is not loaded." is replaced by:

   ```
   A figure that a page states for a future period, or as a forecast, is not loaded as a record field or a fact; the verbatim quotation of decision 0029 holds it only as the publisher's own words inside the quotation body.
   ```

4. In DAT-143's check column: "a paragraph column," becomes "a paragraph column on this table," and "a forward-looking figure," becomes "a forward-looking figure loaded into this table,".
5. In the same change, the table catalogue of section 7.2 gains, directly after the `pub_investqa_record` row:

   ```
   | `pub_investqa_page` | Public | agency page × language | `page_key`, `page_language` | `publicdata` | `investment_context`: the verbatim quotation of the agency's pages (decision 0029): sector context, the market entry pack (D1, S1), set-up steps, incentive packages and laws in the agency's own words |
   ```

6. In the change that accepts this record, rule 23 of AGENTS.md and CLAUDE.md becomes, byte-identical in both files:

   ```
   23. Render every numeral only through the Fact chip family. Build-time scans cover templates; do not substitute a run-time scan of model prose for structural prevention. One named exception, `verbatim-quotation` ([decision 0029](docs/decisions/0029-the-agencys-pages-as-verbatim-quotations.md)): a numeral that is a character of the stored `pub_investqa_page.page_text` may render, unparsed, as one opaque run inside the body element of the `source_quotation` component only; that text is never a fact, a claim, a question slot, a stage directive or a model input, and every other numeral, the quotation's caption included, stays in the Fact chip family. A quotation under this exception is not a forecast, an estimate or advice of this product.
   ```

   and the header Status row of each file gains "; amended by decision 0029 on <date of acceptance>".

7. In the same accepting change:
   - (a) DAT-155 of document 03: after its first sentence, insert

     ```
     The verbatim quotation `pub_investqa_page.page_text` of [decision 0029](decisions/0029-the-agencys-pages-as-verbatim-quotations.md) is not such a field: it is never returned as a fact or a label, and its characters render only inside the body of the `source_quotation` component under that record's `verbatim-quotation` exception.
     ```

   - (b) the numeral rule of document 10 section 5 gains, appended:

     ```
     The one exception is `verbatim-quotation` of decision 0029: a character of the stored `pub_investqa_page.page_text`, rendered as one opaque run inside the body element of the `source_quotation` component.
     ```

   - (c) check 1 of the provenance audit of document 10 section 13 reads:

     ```
     walks all visible text nodes and fails on any numeral not inside a Fact chip element, except inside the body element of a `source_quotation` component whose text equals, character for character, the stored `page_text` of the row it names (decision 0029);
     ```

   - (d) the sentence "Digits are Western in both languages." of document 10 becomes:

     ```
     Digits are Western in both languages, except inside a verbatim quotation of decision 0029, which keeps the publisher's own digits.
     ```

   - (e) BE-114 of document 08 gains, at the end of its requirement column, the sentence:

     ```
     `investment_context` returns an agency page's quotation as one `pub_investqa_page` row (key, language, title, URL, retrieval date, hash, extractor version, text), never as a fact, a label or a model input (decision 0029).
     ```

   - (f) FE-62 of document 10 reads:

     ```
     Every number in both languages uses Western digits, except a character of a verbatim quotation of decision 0029; a test scans the rendered Arabic page, outside the body element of every `source_quotation` component, for Arabic-Indic and Extended Arabic-Indic digits and finds none.
     ```

   - (g) the line "Digits are Western in both languages." of document 11, DES-30's first sentence, and the clause "digits are Western in both languages" of REV-24 of document 15 gain, appended before the full stop (before the semicolon that ends that clause):

     ```
     , except inside a verbatim quotation of decision 0029, which keeps the publisher's own digits
     ```

   - (h) TST-94 of document 12: the clause "in both languages no Arabic-Indic digit may appear in the page text" becomes:

     ```
     in both languages no Arabic-Indic digit may appear in the page text outside the body element of a `source_quotation` component (decision 0029)
     ```

8. In the same accepting change, PUB-88 of document 04: after "the record links to the page instead", insert

   ```
   ; the verbatim quotation of decision 0029 may show it as the publisher's own words, never as a figure, fact or forecast of this product
   ```

## Sources

- [Decision 0064](0064-the-narrowing-rows-decided.md) items 3 and 32; [decision 0017](0017-public-data-additions-and-public-splits.md) item 7; [decision 0026](0026-public-sources-used-in-full-locally.md) item 5; [decision 0034](0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md).
- DAT-143, DAT-155 and the `pub_investqa_record` and `pub_tender` rows of section 7.3 of [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md); PUB-88 of [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md); AI-27, AI-37 and AI-111 of [09_AI_ASSISTANT.md](../09_AI_ASSISTANT.md); FE-40, FE-62, FE-121 and FE-122 of [10_FRONTEND.md](../10_FRONTEND.md); BE-114 of [08_BACKEND.md](../08_BACKEND.md); DES-30 of [11_DESIGN_DIRECTION.md](../11_DESIGN_DIRECTION.md); REV-24 of [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md); PRV-72 and PRV-115 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md); TST-09, TST-94 and TST-142 of [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md).
- TASKS.md, task S2-T39; OPEN_ITEMS.md, items OI-178 and OI-181.
