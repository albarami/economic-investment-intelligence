# C30 forecast calculation handoff

S6-T14 step one adapts part A onto the current base. Formula authority:
[document 07 C30](../../../../docs/07_ECONOMIC_METHODS.md#c30-forecasts-of-published-series).
The series definitions are `c30-series-v2`, candidates `c30-candidates-v1`, method
`c30_rolling_origin@v1`. Version two preserves the open reasons of S2-T17, accepts
conditional Public snapshot histories of establishments and uses the published
hotel indicator `adr` at national grain. The production horizon remains one;
the wider horizon list is undecided (OI-319), not narrowed by this handoff.

`forecast_series` accepts one immutable in-memory `ForecastSeries`, reads no
store and writes nothing. Every admitted series requires `ReleaseAdmission`:
release identity, table and schema digests, the document 03 table grain and the
original source/hash pairs. Its checks validate supplied bindings only. No
reader on this base verifies mounted bytes or constructs that evidence; invented
fixtures are not proof of a mounted release. Missing/foreign evidence fails
before fitting. Static open entries cannot be promoted by supplying evidence.
`forecast_source_refusal(key)` returns that status before a reader or series
is constructed, so a source-less entry needs no invented chain or history.
Open entries return `ForecastOpen` with the unchanged registry reason, no numeric facts
and the proposed tool status `OUT_OF_SCOPE`. This is distinct from
`ForecastNotOffered` for off-list/prohibited or invalid series bindings, and from
`NoData(series_too_short)` for admitted history below C30's minimum.

`ForecastPoint` holds an exact Decimal value, period, indicator, release, unit,
deal count, bulk/carry/publication/completeness flags. Counts are nonnegative
integers. One series uses one release, geography, source categories, frequency
and unit. Only its latest consecutive run is fitted; any carried-forward month
in the supplied window suppresses before suffix selection. Unpublished input
fails before fitting. Released series carry a window key, actual generator
name/version and the fixed protected home-family route. Cross-window assembly
and protected later-month reads are not implemented or authorised here.

All candidates fit prefixes only, use one seasonal scale and are selected on
unrounded error with catalogue-order ties. Extrema and leave-one-out counts use
the winner's residuals at the same horizon. The exact negative point refuses
before rounding; interval ends clamp independently, with both marks mandatory.
These are the C30 baseline assumptions, not an empirical model comparison study.

The result retains exact computation, input history, source pipelines,
subject/geography/categories, origin/target, method and candidate versions,
protected families, caveats and immutable model/horizon qualifiers. Each of its
seven `ForecastFact` companions also carries a `ForecastLineage` with that
computation's series/indicator, method/version, model/horizon, release evidence
and generator/window/families. Original `SourceChain.method` and `version` are
never overwritten with C30's version. Property history keeps its deal counts.
A Public split by sex or nationality never becomes a ranking criterion.

## Units and remaining contract decisions

The typed numeric unit list retains `qar_per_m2` and the existing wire unit
`usd_million` (document 03 DAT-90 and the `fdi_projects` column contract).
Hotel and announced-capex units travel with the input; no currency conversion
or measure-to-measure derivation is performed. Project counts use `count`.

The part-A display places are retained as assumptions, not publisher precision:
counts, wage bill and mean wage at zero places; stayer index at one; property,
hotel and capex at two (a count unit always at zero); error at two. Rounding is
half-up, once, with `exact_unrounded` retained. Thus a count forecast's displayed
value is an integer even when its exact fitted value is fractional. OI-320
records the unresolved canonical identity, count display policy and zero-scale
unscaled-MAE versus ratio-only wire error. No wire schema is weakened or false
ratio emitted. Calculation facts are not canonical DAT-93 wire facts.

Conditional `establishments_by_area` takes a Public count for every genuinely
kept historical `pub_register_snapshot` month (`history_route=snapshot`). It is
a stock, never a dates-derived opening/closure flow. No current stock is
backfilled. This is an internal conditional binding, separately inventoried
from S2-T17's exact registry list, not a new registry-held claim. OI-321 keeps
real history availability, source-owner stock/flow confirmation, employment
routing and other adapter assumptions open. Missing snapshot evidence fails;
no fabricated row or generated flow supplies it.

## Integration boundaries

The base exposes a tile spike only. It has no forecast `ReleaseStore.fetch`
query, authenticated `app.read_seat_context()` integration, manifest verifier
or canonical forecast fact emitter. No conditional API module or SQL is
invented, and product imports no custodian cache reader (OI-324). No two-store
forecast parity or live-source acceptance is claimed.

Both C30 English sentences are pinned. Card/chart declarations require all
seven companions and both clamp booleans; the loader rejects omitted, extra,
duplicate or wrongly typed slots. The layout checks the metric, unit,
Inferred status, period, geography kind, provenance and lineage reference
available in `ReturnedFact`. That type lacks release/series/model/horizon,
values and clamp metadata; its checks cannot replace canonical emission or
full accounting. Zero-scale series-unit error cannot bind to a ratio-only
wire slot (OI-320).

No forecast claim is published: metadata/history chip bindings, native Arabic,
the shared Fact family, card, stepped band and rendered success/refusal/clamp
states await step two and the missing emitter. The original sources, actual
generator metadata and method limitations remain; audience origin words and
textures are not restored. C21 remains a projection. OI-322 and OI-323 track
those remaining presentation obligations. OI-318 and OI-325 track source-owner
confirmation and final open-entry status mapping. This handoff does not close
OI-03, OI-98 or OI-102 or tick any screen criterion in TASKS.md.
