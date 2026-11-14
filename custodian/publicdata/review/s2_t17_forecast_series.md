# S2-T17 forecast source confirmation

PLN-25 evidence prepared for the slice S2 gate; independent review pending.
Builder: senior data engineer for source registries and forecast inputs.
Reviewer: principal reviewer of public-data provenance and forecast inputs, another maker (pending).

This is source admission metadata, not a forecast or proof that a series at every
activity, district or sector has sufficient history. S6-T14 must check the mounted
release, actual series continuity and units and C30's backtest minimum. In particular,
C23's completion certificates remain too short. No fetched records were read here.

Evidence: the lead's source reading of 2026-11-14, questions Q1 to Q7, and rulings
L1 to L10, supplied to this task; document 04 PUB-103 and section 2.2, document 07
cards C14, C23 and C30, document 03 DAT-158 and DAT-167. The source keys below resolve
to publisher, dataset URL and licence in sources.yaml. Retrieval dates and full
body hashes remain in S2-T01 receipts; the supplied reading gives abbreviated
hashes only and is not a replacement for release lineage (DAT-94). This task emits
no Public fact and does not claim a verified full receipt chain. Decision 0026 W5
keeps non-open-licence records out of the repository; W12's withdrawn production
value is outside the closed source mapping. Terms do not control this source gate.

The district subject and the investment sector grain are lead assumptions pending
the owner's confirmation, not new publisher facts. The lead owns OI-98 and OI-102;
the open questions below are proposed ledger additions, not claims they were entered.

`licence_issues` — `held`; source keys `lic_issued`; table `pub_licence_issued`. `2013-04/2025-05`; `month`; past_count `146`. Licence issues by activity and municipality, only covered codes; earlier, broken months exist from 2009-09. Undated rows never enter; continuity at each activity and municipality remains for C30. Evidence: Lead source reading 2026-11-14 Q1; document 04 PUB-103 and section 2.2; document 07 C30.

`licence_cancellations` — `held`; source keys `lic_cancelled`; table `pub_licence_cancelled`. `2016-03/2025-05`; `month`; past_count `111`. Licence cancellations by activity and municipality; earlier, broken months exist from 2015-12. Exclude 1,221 undated rows; retain bulk-month flags. Continuity at each activity and municipality remains for C30. Evidence: Lead source reading 2026-11-14 Q2; document 04 PUB-68 and PUB-103; document 07 C30.

`property_prices` — `held`; source keys `prop_sales`; table `pub_property_sale`. `2020/2025`; `year`; past_count `6`. Six years with data; five complete years (2021 to 2025); 2020 holds July to December only. C30 decides which history counts at each district; no completeness rule added here. Annual medians per square metre with deal counts; never joined to quarterly per-square-foot prices. District is the publisher label with municipality, Public only, never apportioned or an area subject (lead assumption). Evidence: Lead source reading 2026-11-14 Q5 and ruling L5; document 04 PUB-103; document 07 C14 and C30.

`hotel_demand_and_room_rates` — `held`; source keys `hotel_segment`; table `pub_hotel_monthly`. `2014-01/2025-03`; `month`; past_count `135`. One entry because demand and average_daily_rate share every month of every segment; separate demand and adr indicators each retain their own published unit in pub_hotel_monthly (document 03 section 7.2). No measure is derived from the other; units are not inferred here. Evidence: Lead source reading 2026-11-14 Q3; document 04 PUB-103 and section 2.2.

`consumer_prices` — `open`; source keys `cpi_group`; table `pub_price_index`. OI-98: `consumer_prices` — `publisher_or_licence_unconfirmed`. Which confirmed source and history metadata close this reason? No cache file; publisher unconfirmed, a technical reason. Registry skip remains unchanged. Evidence: Lead source reading 2026-11-14 Q4; document 04 PUB-103.

`producer_prices` — `open`; source keys ; table `none`. OI-98: `producer_prices` — `no_source_table`. Which confirmed source and history metadata close this reason? price_ext is a candidate for S2-T19, not an adopted source. Evidence: Document 04 PUB-103; document 07 C30.

`imports_by_product` — `open`; source keys `cus_imp_2019`, `cus_imp_2025`; table `pub_customs_import`. OI-98: `imports_by_product` — `past_count_not_stated`. Which confirmed source and history metadata close this reason? The combined count is not stated; the later file alone holds 14 months. PUB-44 roll-up applies; no inferred combined month count. Evidence: Document 04 section 2.2, PUB-44 and PUB-103; lead ruling L8.

`announced_investment` — `held`; source keys `fdi_projects`; table `fdi_projects`. `2017/2025`; `year`; past_count `9`. Complete announcement years only; the running year and undated projects never enter. Sector uses the publisher's top grain (lead assumption). Metadata only; no project record or value committed. Evidence: Lead source reading 2026-11-14 Q6 and ruling L6; document 04 PUB-103; document 07 C30.

`construction_pipeline` — `held`; source keys `permits_muni/total-building-completion-certificates-issued-by-municipality-and-type-of-building-type-of`; table `pub_building_permits`. `2021/2023`; `year`; past_count `3`. Annual completion certificates by municipality only, never permit series. C23 and C30 state that three annual points are too short; source admission does not override the backtest. Evidence: Lead source reading 2026-11-14 Q7; document 07 C23 and C30; document 04 PUB-103.

`expected_households_and_workers` — `open`; source keys ; table `none`. OI-98: `expected_households_and_workers` — `no_conversion_parameter_source_table`. Which confirmed source and history metadata close this reason? No registered table for conversion parameters; census_hh_type_2020 has no release table. Evidence: Document 04 PUB-103.

`property_prices_quarterly` — `open`; source keys `prop_sales`, `prop_resi_units/weekly-residential-units-sales-bulletin`; table `pub_property_quarter`. OI-98: `property_prices_quarterly` — `awaiting_s2_t19_period_frequency_past_count`. Which confirmed source and history metadata close this reason? Card C41: median per square foot by district and use, with each quarter's deal count; separate from annual medians per square metre. S2-T19 fetches sources and sets period, frequency and count; Public district label with municipality only, never apportioned. Evidence: TASKS.md S2-T17 amendment; document 04 PUB-103 and PUB-107; document 03 DAT-167.
