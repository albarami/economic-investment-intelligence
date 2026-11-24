# Decision 0063: The photorealistic spend meter and the operational Fact chip

| | |
|---|---|
| Status | Accepted, 2026-11-19: the owner's words of 2026-11-18 at 23:32 (the 3D cap may rise above USD 20) and at 23:35 (the 3D mode sized for full-quality showings), relayed by the owner's advisor, applied by the lead's rulings L-1015, L-1017 part B and L-1020; recorded by the lead |
| Date | 2026-11-19 |
| Owner | The owner |
| Decided by | The owner's words of 2026-11-18 at 23:32 and 23:35, relayed by the owner's advisor, under AGENTS.md rule 46, applied by lead ruling L-1015 (2026-11-18 23:34), lead ruling L-1017 part B (2026-11-18 23:50) and lead ruling L-1020 (2026-11-19 00:20) |
| Amends | The view budget of the photorealistic 3D mode in BRF-102 of document 01; the API row of the component table of section 2 (its Must never column), ARC-35 (its rule and its verification) and the paid-mode row of section 11 of document 02; the `tiles3d_google` row of section 2.2 and PUB-109 of document 04; FE-148 and section "S3-T16 Part A component boundary" of document 10; TST-255, the photorealistic 3D row of section 5.1 and the provider row of section 8 of document 12; the slice S3 paragraph of section 11 of document 14; the map-mode entry of the glossary; TASKS.md S2-T01 (its ticked first criterion, wording only), S3-T16 (its two criteria that named the view budget, and its scope); the accepted-records sentence and the Decision records table of docs/README.md |
| Purpose | Make the guard of the paid photorealistic 3D mode a visible spend meter with one named ceiling and no per-view budget, and give the Fact chip family one typed form for that live operational quantity. |
| Read first | [Decision 0023](0023-ten-additions-and-the-data-rule.md) item A7; PUB-109 of [document 04](../04_PUBLIC_DATA_PACK.md); OPS-74 and section "S3-T16 Part A settings under implementation" of [document 13](../13_DEPLOYMENT_AND_OPERATIONS.md); section "S3-T16 Part A implementation boundary" of [document 08](../08_BACKEND.md); section "9.2 The Fact chip" of [document 11](../11_DESIGN_DIRECTION.md); AGENTS.md rules 16, 17 and 23 |

## Context

Decision 0023 item A7 made the photorealistic 3D tiles the one paid service of the product and the owner capped their
spend at USD 20 in total. The pack then guarded it twice: a project-wide count of billable tile requests refused every
request at the cap, and a per-view budget refused a view's tiles beyond a fixed number.

On 2026-11-18 at 23:32 the owner answered, of the sentence of decision 0023 that caps the mode at USD 20 in total:
the budget may rise above USD 20 where that adds to and deepens the value of the system. Ruling L-1015 applied it: the
cap stays USD 20 and nothing above it is spent until the owner names another number in the owner's own words, and the
cap is one named setting read by the project-wide count, with no figure repeated in code, tests or documents. At 23:35
the owner added that the owner alone uses the 3D mode, shows it a limited number of times in total, and wants nothing
to limit its value and depth when it is shown. Ruling
L-1017 part B applied it, with the advisor's note of 23:37 (measure first; reuse within the cache headers), and made the
guard a spend meter rather than a limiter of a view. Fix pass 5 of S3-T16 part P built the meter on the server and
stopped at its display, because the Fact chip family (rule 23) held only release-fact, input and reference forms, and a
running request count is operational state, not a release fact with a source chain. Ruling L-1020 chose the first
option of that return: one new typed form of the family. Fix pass 6 built it. Both passes were approved by another
maker's review of the two commits.

This record states what was decided and which code and tests carry it. It claims no merge, no passed gate, no measured
showing and no native Arabic approval.

## Decision

1. **The spend meter.** The ceiling of the photorealistic 3D mode is USD 20 in total, held once as the named setting
   `SPEND_CEILING_USD` and read by the project-wide count; it stays until the owner names another number after a
   measured showing, and a new number enters a decision record only after the owner approves it (L-1015 (b) and (c);
   L-1017 B (e)). There is no per-view budget: no view is refused, cut, lowered in detail, area or length, or stopped
   part way by a per-view rule (L-1017 B (a) and (d)). The warning comes before the ceiling at `WARNING_FRACTION`, a
   lead default of 80 percent of the effective request limit until the micro-pass measures a showing, when it is
   replaced by "remaining below one measured showing" (L-1017 B (c)); the warning refuses and slows nothing. The ceiling
   is the only stop and it is absolute: the server refuses a request with `cap_reached` before sending once the
   durable count reaches the effective limit, and a lower configured limit (`EII_PHOTOREAL_LIMIT`) or a higher read
   price can only lower that limit (L-1017 B (b) and (d)). The count is kept in the project's request journal, which a
   pending line is synced to before each send and which no command, restart, release or store switch resets; an
   unreadable or interrupted journal refuses with `count_unavailable` and the meter is then null, never a made-up zero.
   The meter (billable requests, request limit, spend in USD as an exact decimal string, warning flag, ceiling, price
   per thousand, method version and the date of the default price reading) is computed only by the server's tested
   meter function `Budget.meter`, version `1`, with Python `Decimal`; the browser does no sum, product, comparison or
   rounding on it (rules 16 and 17), and reading the meter never writes the journal.
2. **The `operational` form of the Fact chip family.** The family gains exactly one typed form, `operational`, for
   live operational quantities; its first and only user is the photorealistic spend meter (L-1020 (a)).
   - It takes only the closed meter object from the server (or null with a closed reason), never free text, a fact
     identifier or a value computed in the browser. The availability parser accepts the closed fields only and refuses
     an unknown field, a malformed count or decimal, and an unknown method version.
   - Every numeral it shows goes through the family's existing formatters and bidi isolation: counts through the count
     path, the spend and the ceiling through an operational USD path that checks the server's plain decimal notation
     and returns the string byte for byte, the date through the family's calendar formatter.
   - Its explanation panel names the quantity as operational, never Public, Synthetic, Simulated or a release fact:
     the source is the project's request journal; the method is `Budget.meter` with its server version; the price is
     the named setting `EII_PHOTOREAL_PRICE_PER_THOUSAND` with its effective value, the pricing page it was read from
     and the date of the reading; the ceiling is `SPEND_CEILING_USD`. No publisher licence is claimed for a count
     (L-1020 (b)). As built, the panel gives the date of the default price reading recorded in the `tiles3d_google` row
     of document 04 and labels it the documented default reading, which attests to no operator override; the pricing
     page has no recorded address yet and the panel says "To record" until one is recorded, never an invented address.
   - No release-fact chip accepts an operational value and the operational form accepts no fact identifier or
     registry; both directions have planted violations (L-1020 (c)).
   - Its words are new closed keys in English and Arabic, every Arabic key marked pending native review; the warning
     sentence appears only when the server's warning flag is true; the meter refreshes on each meter response the
     page already receives, with no polling timer and no request added to read it (L-1020 (d)).
3. **The security bounds that stay.** The native routing of the 3D tiles keeps its two bounds as security bounds, not
   spend rules: a registered view expires 10,800 seconds after it starts (or after it is registered, if it never
   starts), and one view's tile set is refused when it would hold more than 10,000 aliases. The micro-pass, run on the
   free monthly requests with the key otherwise unused until then (L-1015), measures the tile requests of one
   full-quality showing of Doha and one of all Qatar, first and repeat over the same route, reads the tiles' cache
   headers, and measures each showing against both bounds. If a showing nears either bound, the lead raises it as a
   finding, never as a cut of the showing (L-1020 (e)). No cost range is quoted before that measurement (L-1017 B (e)).
4. **What carries it.** The code and tests named in "Where it is built" carry items 1 to 3; the passages listed in the
   Amends row are changed to state items 1 and 3 (see "Passages amended").

## Where it is built

Item 1, in `product/src/eii_product/photoreal_tiles/limit.py` (`SPEND_CEILING_USD`, `WARNING_FRACTION`, `SpendMeter`,
`billable_limit`, `Budget.count`, `Budget.meter`, `Budget.request`) and `product/src/eii_product/api/map_modes.py` (the
shared pricing of dispatch and meter and the photoreal `meter` of `GET /api/map-modes`), with these tests of
`product/tests/test_map_modes.py`:

- `test_named_spend_ceiling_controls_the_billable_limit` (a changed setting changes the guard; L-1015 (a));
- `test_view_above_six_hundred_and_restart_forgets_view` (a view continues past the former per-view allowance and a
  restart forgets the view, not the count);
- `test_limit_price_and_serialized_concurrency` and `test_meter_setting_can_only_lower_named_ceiling`;
- `test_meter_warning_below_at_and_above_fraction` and `test_warning_fraction_is_one_named_default`;
- `test_meter_keeps_small_decimal_money_in_plain_notation` and `test_meter_updates_on_requests_and_survives_restart`;
- `test_meter_at_cap_keeps_total_and_refuses_without_sending`;
- `test_meter_never_invents_a_total_for_unavailable_count`, `test_counter_damage_fails_closed` and
  `test_counter_io_failure_refuses_without_forgetting`;
- `test_new_application_and_release_roots_preserve_the_journal`.

Item 2, in `web/src/facts/FactChip.tsx` (the `operational` member of `FactChipProps` and `OperationalChip`),
`web/src/facts/formatters.ts` (the operational USD path of `formatFactValue`), `web/src/stage/map-modes.ts` (the closed
meter type and parser), `web/src/stage/Stage.tsx` (the meter mounted in the stage controls), the `operational.*` keys of
`web/src/i18n/en.json` and `web/src/i18n/ar.json` (the Arabic ones marked pending native review) and
`web/src/styles/answer.css`, with these tests:

- `test_meter_operational_provenance_is_server_bound` of `product/tests/test_map_modes.py`;
- in `web/tests/component/operational-meter.test.tsx`: "renders exact server money and journal explanation in %s",
  "uses only the server warning flag even with deliberately contradictory numbers", "withholds null with reason and no
  zero in %s" and "mounts in stage controls and refreshes on the existing mode-error response without extra fetches";
- in `web/tests/unit/map-modes.test.ts`: "accepts the server meter without browser money or warning calculations" and
  "requires the photoreal meter field and refuses it on other modes", with its table of malformed meters;
- "operational and release-fact props reject each other, including fact IDs" of
  `web/scripts/tests/operational-contract.node-test.mjs`, which compiles the planted violations of
  `web/tests/fixtures/operational-contract.tsx` (a value or compact chip given the meter, an operational chip given a
  fact identifier or an extra one, a release chip given an extra meter);
- the `probe-meter.tsx` invalid case of `web/eslint-rules/numerals-only-in-fact-chip.test.mjs`, under the unchanged
  rule `eii/numerals-only-in-fact-chip`;
- "operational meter placement, contrast and keyboard" of `web/tests/audit/answer.spec.ts`, in both languages and
  both themes.

Item 3, in `product/src/eii_product/photoreal_tiles/native.py` (`NativeViews.purge` for the expiry and the alias count
check of the tile set), unchanged by either fix pass; the expiry is exercised by
`test_aliases_are_query_free_bound_to_one_view_and_purged` of `product/tests/test_photoreal_native.py`. The measurement
of item 3 has not been run.

The prose of the same change is section "S3-T16 Part A implementation boundary" and BE-139 of document 08, OPS-74 and
section "S3-T16 Part A settings under implementation" of document 13, and the paragraph on the `operational` form in
section "9.2 The Fact chip" of document 11.

## Passages amended

Each passage below named a per-view budget. Each is changed by a minimal edit that states items 1 and 3 and cites this
record; the rest of each passage, its requirement ID and any tick are unchanged. "The bounds" below stands for "a
registered view expires 10,800 seconds after it starts and one view's tile set is refused above 10,000 aliases, as
security bounds, not spend rules".

- Document 01, BRF-102: "requests are refused once the count reaches the number that the cap allows; one view loads at
  most 600 tiles; and" becomes "requests are refused once the count reaches the number that the cap allows, the cap held
  as the named setting `SPEND_CEILING_USD` with a warning before it at `WARNING_FRACTION`; there is no per-view tile
  budget (decision 0063); and".
- Document 02, section "2. Components", API row, Must never column: "pass on a photorealistic 3D tile request once
  the project-wide count has reached its cap, or more than 600 tiles for one view" becomes "pass on a photorealistic
  3D tile request once the project-wide count has reached its cap" with a link to this record.
- Document 02, ARC-35: "one view loads at most 600 tiles." becomes "there is no per-view tile budget: the only stop is
  that ceiling, held as `SPEND_CEILING_USD` and warned before at `WARNING_FRACTION`, and" the bounds "(decision 0063)."
- Document 02, ARC-35, its verification: "a planted request once the count has reached its cap, and a planted view of
  more than 600 tiles, are each refused;" becomes "a planted request once the count has reached its cap is refused, and
  a planted view past the former per-view allowance is served below the cap (decision 0063);".
- Document 02, section "11. Quality attributes and architectural risks", the row on the paid photorealistic 3D mode:
  "refuses every request at the cap; at most 600 tiles for one view;" becomes "refuses every request at the cap
  (`SPEND_CEILING_USD`), with a warning before it and no per-view tile budget (decision 0063);".
- Document 04, section "2.2 Coverage, use and traps", the `tiles3d_google` row: "and one view loads at most 600 tiles"
  becomes "the ceiling held as `SPEND_CEILING_USD` with a warning before it at `WARNING_FRACTION`, and no view has a
  per-view tile budget (decision 0063)".
- Document 04, PUB-109: "and one view loads at most 600 tiles." becomes "and there is no per-view tile budget: the only
  stop is that ceiling, held as `SPEND_CEILING_USD` and warned before at `WARNING_FRACTION`, and" the bounds "(decision
  0063)."; and "planted tests prove the refusal of the 3D tiles at the project-wide count and at the view budget"
  becomes "planted tests prove the refusal of the 3D tiles at the project-wide count and the continued service of a
  view above the former per-view allowance (decision 0063)".
- Document 10, FE-148: "One view loads at most 600 tiles, and a test with a hand-made fixture fails if one view requests
  more." becomes "No view has a per-view tile budget: a test with a hand-made fixture serves a view past the former
  per-view allowance below the ceiling; the only stop is the project-wide ceiling `SPEND_CEILING_USD`, warned before at
  `WARNING_FRACTION`, and" the bounds "(decision 0063)."
- Document 10, section "S3-T16 Part A component boundary": "child JSON requests count against the same view and project
  budget" becomes "child JSON requests count against the project-wide count, with no per-view budget (decision 0063)";
  "The server journal, cap and view budget remain Part A responsibilities." becomes "The server journal and the
  project-wide ceiling remain Part A responsibilities; there is no per-view budget (decision 0063)."
- Document 12, TST-255: "One view loads at most 600 tiles, and a planted 601st tile request of one view must be
  refused." becomes "There is no per-view tile budget (decision 0063): a planted view that continues past the former
  per-view allowance is served while the project-wide count is below its limit; the only stop is that limit, from
  `SPEND_CEILING_USD`, warned before at `WARNING_FRACTION`, and" the bounds.
- Document 12, section "5.1 Tests added by decisions 0016 and 0017", the photorealistic 3D row: "requests refused at the
  project-wide count and beyond the view budget" becomes "requests refused at the project-wide count only, with no
  per-view budget (decision 0063)".
- Document 12, section "8. Not tested in version 1, and why", the provider row: "the project-wide count and the view
  budget on a stub" becomes "the project-wide count and the spend meter on a stub, with no per-view budget (decision
  0063)".
- Document 14, section "11. slice S3 — Living map and Public-only answer": "one view loads at most 600 tiles" becomes
  "no view has a per-view tile budget (decision 0063)".
- The glossary, "Map mode": "; one view loads at most 600 tiles," becomes ", with no per-view tile budget (decision
  0063),".
- TASKS.md, S2-T01, its ticked first criterion (the tick stands): "under the project-wide spend cap and view budget"
  becomes "under the project-wide spend cap (`SPEND_CEILING_USD`) with no per-view budget (words changed by decision
  0063)".
- TASKS.md, S3-T16, its criterion "[ ] one view loads at most 600 tiles, and a planted view that requests more fails"
  becomes "[ ] no view has a per-view tile budget (decision 0063): a planted view that continues past the former
  per-view allowance is served below the ceiling, the only stop is `SPEND_CEILING_USD`, warned before at
  `WARNING_FRACTION`, and" the bounds; its criterion's "the refusal at the limit and the view budget are tested without
  the provider" becomes "the refusal at the limit and the continued service of a view past the former per-view allowance
  (decision 0063) are tested without the provider"; its scope's "project-wide count and view budget" becomes
  "project-wide count and spend meter and no per-view budget (decision 0063)"; its Delivery line carries the status note
  of this record.
- docs/README.md: this record in the accepted-records sentence and its row in the Decision records table.

Section "S3-T16 Part A implementation boundary" and BE-139 of document 08, OPS-74 and section "S3-T16 Part A settings
under implementation" of document 13, and section "9.2 The Fact chip" of document 11 already state items 1 to 3 (see
"Where it is built") and are not changed here. Decision 0023, an accepted record, keeps its words where its item A7 and
its list of documents name the per-view tile limit or the view budget; they read with items 1 and 3 of this record.

## Consequences

- The owner sees a running total of billable requests and spend against the ceiling, and a warning before it, while the
  mode is on; a full-quality showing is never cut by a spend rule short of the ceiling.
- Raising the ceiling is a change of one named setting, made only after the owner names the number and a record holds
  it; the planted test of item 1 shows the guard follows the setting.
- The Fact chip family has one form whose provenance is operational state. Any later operational quantity needs its own
  ruling and record; this record admits only the spend meter.
- The pricing-page address and the native Arabic review of the new keys are owed, for the lead's open items; until
  then the panel says "To record" and the Arabic keys stay marked pending.

## What does not change

Rule 23 stays: every numeral on the screen goes through the Fact chip family, and the lint rule that forbids a bare
numeral is not relaxed. No release-fact chip (`value` or `compact`) accepts an operational value, and the release-fact
forms keep their contracts, their full source chain (rule 19) and DES-71, DES-74, DES-75 and DES-77, of which the
`operational` form is the one stated exception. The journal's transaction, the before-send refusal at the ceiling,
`cap_reached`, `count_unavailable`, the key handling of PUB-109 and OPS-74, the same-origin route, nothing of a tile
stored, and the rule that no test, gate, command or the guided story calls the provider or needs its key are unchanged.
No spend above `SPEND_CEILING_USD` happens before the owner names a new number. Every gate and review is unchanged.

## Sources

- The owner's words of 2026-11-18 at 23:32 and 23:35, relayed by the owner's advisor, with the advisor's note of 23:37,
  and lead rulings L-1015, L-1017 part B and L-1020 applying them (project records of the run, outside the pack).
- The returns of S3-T16 part P fix passes 5 and 6 and the approving review of both (project records of the run,
  outside the pack); commits 8f1194e and 76e7dba of the part's branch.
- The `tiles3d_google` row of section 2.1 and PUB-109 of document 04, for the price reading of 2026-11-13.
