# S6-T25 generated-series calculation admission

Maker: OpenAI. Model: GPT-6 Codex. Principal forecasting engineer; strict
self-review persona rejects stale computations and unproved pipeline parity.
Independent different-maker implementation review remains for the lead.

This record describes `c30-series-v3`, the calculation catalogue in
`core/src/eii_core/calc/forecast_list.py`. It asserts no mounted source, released
history, source-to-release swap parity, real-source provenance migration or
screen acceptance. All test histories and hashes are invented. No source data,
private calibration or cache was read. No Public fact is produced by this audit.

Authority: decision 0036 items 1, 2 and 7; decision 0023 item 12;
document 03 DAT-158, DAT-136 and sections 7.2, 7.3 and 8; document 06 PRV-34,
PRV-38, PRV-54 and its contributor-universe table; document 07 C30 and MTH-98.
The proposed `custodian/src/eii_custodian/conformance/release_registry.json`
does not exist on this base. Agreement tests use the tracked document 03
catalogue and column definitions; this is not release-registry validation.

Released-series admission reads `Definition.confirmed_sources` and requires
exact set equality with the typed `ReleaseAdmission.feed_names` evidence before
any fit, returning the closed `forecast_not_offered` refusal on a wrong, extra
or missing feed. These are the existing feed identities of rule 12, selected
for the series, rather than the full four-feed window universe on every route.
The field requires unique, nonempty text names; ordering does not change the
admitted set. Source-chain hashes remain bound to `source_hashes` separately.
All forecast companions retain this admission evidence in their lineage.
This checks in-memory feed identities only: mounted manifest verification,
including the mapping from those feeds to the selected table's source chains,
stays with OI-324. No new feed or manifest/window rule is introduced.

Every admitted generated series uses Synthetic inputs, subject `area`, Inferred
facts, the two Synthetic caveats and `forecast_backtest_range`. The unit set,
family and breakdown stay fixed through the admitted history; this layer reads
no records and performs no new protection. Area geography means existing
`release_units:` or permitted `area_shape:` sums; national means `national`.
Municipality routes exist only where the original pay/stayer definitions permit
them. The new occupation routes do not invent municipality units.

History for each entry is the trailing consecutive monthly run ending at the
last month of the admitted window. Every point, both ends of a stayer pair
included, belongs to that window. The manifest's existing `window_period` and
`window_key` must match the series handoff; the target is the next month, a
projection of released values, not a newly protected statistic. The configured
`window_months` is 23 in `rv-1.0.0-s1`. C30's existing minimum yields 16 points
for the retained monthly horizon; paired fixtures use 22 adjacent pairs inside
the same window. Actual sufficiency is checked per history, never inferred from
that configured capacity. Gaps truncate history; carried-forward points suppress
before fitting. No window size, privacy rule, attack size or tolerance changes.

### pay_level

Retained. Feeds: business_register.v1, employment.v1, residence.v1, wages.v1
(the union of the two supported table routes). Tables: worker_pay, resident_pay.
Monthly (`month`) history as above. Unit qar_per_month; levels area, municipality, national.
Mean wage uses the wage_bill numerator and earner_count denominator in the same
wp_all_money or rp_all_money family, measure net or basic, ALL breakdown.

### earner_count

Retained. Feeds: business_register.v1, employment.v1, residence.v1, wages.v1.
Tables: worker_pay, resident_pay. Monthly (`month`) history as above. Unit count; levels
area, national. Single earner_count of wp_all_count or rp_all_count, net or basic,
ALL breakdown. No cross-family reconciliation is introduced.

### wage_bill

Retained. Feeds: business_register.v1, employment.v1, residence.v1, wages.v1.
Tables: worker_pay, resident_pay. Monthly (`month`) history as above. Unit qar; levels area,
municipality, national. Single wage_bill in wp_all_money or rp_all_money,
net or basic, ALL breakdown.

### stayer_index

Retained. Feeds: business_register.v1, employment.v1, residence.v1, wages.v1.
Table: month_change, bound back to worker_pay or resident_pay. Adjacent-month
history as above. Unit index; levels municipality, national. Single
stayer_wage_index in the existing all_money or all_quartile family, net or basic,
cohort breakdown. No finer geography and no hiring/leaving forecast is admitted.

### employment_by_area

Retained. Feeds: business_register.v1, employment.v1, wages.v1. Table worker_pay.
Monthly (`month`) history as above. Unit count; levels area, national. Single earner_count
in wp_all_count, net or basic, ALL breakdown.

### employment_by_occupation_residence

Added. Feeds: business_register.v1, employment.v1, residence.v1, wages.v1.
Table occupation_pay. Monthly (`month`) history as above. Unit count; levels area, national.
Single earner_count in op_res_quartile, measure net or basic. The ordered
breakdown is basis=residence then occupation_group; the family marker is
`basis=residence;occupation_group=<group>;band=ALL`, the group's `ALL` band
total (PRV-38). Groups use the source contract's
major groups, unmapped and other. These are the released count primitives of
the occupation family, never an unprotected person count or a new finer split.

### employment_by_occupation_workplace

Added. Feeds: business_register.v1, employment.v1, wages.v1. Table occupation_pay.
Monthly (`month`) history as above. Unit count; levels area, national. Single earner_count
in op_work_quartile, measure net or basic. The ordered breakdown is
basis=workplace then occupation_group; the family marker is
`basis=workplace;occupation_group=<group>;band=ALL`, the group's `ALL` band
total (PRV-38). The same closed groups apply.
Residence and workplace families are never interchanged or combined.

### Evaluated entries not added

- joiner_count and leaver_count: retired by decision 0046 item 1, reaffirmed by
  decision 0064 item 20 and lead ruling L-1209 F1. Cohorts retained for C20 and
  privacy do not authorise hiring/leaving forecasts.
- home_area_share: a joint count at ha_work_count by terminal ha_home, not an
  inbound-worker total or a newly inferred home area. Which count/geography
  joins C30 remains a C30 catalogue-owner choice; no series is fabricated here.
- outlet_register: protected activity/size leaves under or_register_count.
  No distinct forecast measure is approved here. Ordinary monthly establishment
  counts retain the conditional Public pub_register_snapshot route; generated
  counts never backfill its missing Public history (decision 0023 item 12).
- register_company_list: last-month-only, company-keyed employee counts, no
  monthly history; named-company forecasts remain forbidden by rule 24.
- resident_pay housing and side counts (not_measured_count, irregular_count),
  worker_pay side counts (deployed_elsewhere_count, irregular_count): coverage
  measures with separate families. No new forecast identity/binding is fixed in
  this version. The C30 catalogue owner must decide their inclusion separately.
- occupation_pay wage_bill and derived mean pay: columns are supported, but
  this addition fixes only occupation employment counts. Additional measure
  identities/bindings remain with the C30 catalogue owner and OI-320; their
  generated provenance is not a reason to exclude them.
- presence_count, flow_hourly, presence_split, flow_split, traffic_hourly and
  access_score: Simulated inputs are eligible in principle under decision 0036,
  but these tables have day-type/hour keys and no dated ordered monthly history.
  No artificial history or series across protected windows is introduced.

Known unavailable Public entries preserve the exact source reasons of the
S2-T17 registry: ForecastOpen now has status NO_DATA and empty facts under
L-1209 F2. Only insufficient actual history uses series_too_short. Carried-forward
history remains SUPPRESSED/CARRIED_FORWARD. This resolves the calculation path
only; OI-325's executable API/emitter mapping still needs its owners.

### Backtest freshness and bounded substitution evidence

All seven generated keys use ForecastSeries and forecast_series, the same CPU
Decimal candidates, fixed smoothing grid, MASE and empirical interval/caption
procedure. Method and candidate versions and dependency pins are unchanged;
no random draw, new dependency or threshold is added. ForecastResult reruns
the whole backtest on the admitted trailing history and compares every candidate,
residual, selected model, scale, error, forecast, interval and caption count.
Matching labels and consistently rebuilt companions do not legitimise a stale
computation. Replacement invented histories are observed entering both rolling
backtests and the full-history final fit; this proves calculation substitution.

### Dependency owners and exact inspected commits

- S6-T14 calculation base: cbff06dd1a079b0ffb7dc913580c484f9c7aebe9.
- S4-T14 employment owner: local/S4-T14-fix1,
  1f3bf12b84e17f9c25b1309f0d20b8d325aed1eb. Its employment_swap module states
  generated-feed parity remains NOT DONE; release gender coverage is also owed.
- S4-T15 wages owner: local/S4-T15-fix2,
  785d09baae615c329df56f0e641281d183178b91. Its wage_swap module states
  generated-feed parity and deterministic CPU fallback remain NOT DONE.
- S4-T16 residence owner: local/S4-T16-a1,
  b21d900787ff05154e234d3a5c71fe119d9cf2d3. Its residence_swap module has
  no generator/protection entry point and disclaims generated-pipeline parity;
  origin propagation into the shared feed manifest is still owed.
- S4-T17 movement owner: local/S4-T17-b1,
  52ac6d842e2aacda123b3bd1f1d339d9249064d3. No monthly mobility history is
  claimed from that dependency. No dependency commit is imported by this task.
- S5-T04 release-producing owner (after S4-T05 and S5-T01 to S5-T03): the
  release build remains a placeholder on the pinned base; there is no completed
  release-producing implementation commit to cite. Its completed lineage and
  source-to-release substitution evidence are required before pipeline parity.
- OI-324 / S6-T14 source/API owners: mounted manifest verification, fixed
  ReleaseStore readers, authenticated dispatch, emitter and two-store parity.
  In-memory window validation proves none of these.
- Lead and go-live gate owner under ARC-141, decision 0036 item 2, MTH-48 and
  TST-267: wire source substitution and refuse generated placeholder fits until
  re-fitting and re-backtesting on authorised real sources. No implemented gate
  is claimed; the lead must pin its implementing task and evidence. S6-T25 owns
  method-side freshness only. Future real-source class migration is still open.

AC2's full pipeline swap and AC6's go-live criterion remain unticked. Full
completion and pipeline parity cannot be claimed while those dependencies are
open. OI-319 to OI-324 retain their horizon, identity, real-history, wire and
screen limits. The lead runs the whole suite and arranges different-maker review.
