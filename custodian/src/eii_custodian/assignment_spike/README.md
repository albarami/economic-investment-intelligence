# Synthetic traffic assignment spike

Task S1-T11 implements the fixture-only C25 assignment of MTH-88, MTH-89 and
MTH-90. It reads only the explicitly named flows, roads and parameter snapshot;
all fixtures are invented. This is spike code, not the release builder.

## Speed, time and loading

L-74 R1 fixes one whole speed in the method: divide free-flow speed by the
configured volume-delay factor, round half-up to whole kilometres per hour,
then apply the configured floor. Exact link minutes use that whole speed and
the graph's stored metre length. The released ratio is the whole speed divided
by free-flow speed, rounded half-up to three decimals. Volume bands still use
the exact assigned volume-to-capacity ratio. No row means free flow.

Both planes refuse fractional free-flow speeds, speeds above the named engine
maximum, a fractional floor, a floor below the named engine minimum, and any
class speed below the floor. The product reconstructs the whole speed and
refuses a noncanonical ratio or a speed below the snapshot's floor, naming the
rows file and link. It never changes a released speed to meet a floor.

Unit loading uses spherical great-circle distance, with lower node identifier
breaking a tie. The engine's sphere constant was not identified; the L-74 R8
fallback radius is 6,371,008.8 metres. Free-flow assignment paths use exact costs
and lexicographic node-sequence ties. Within-unit trips stay off the graph.
Free-flow paths are reused for all hours; traffic does not move to a quicker
road after congestion is assigned. Capacities and free-flow speeds remain
assumptions, not measured attributes of Qatar.

## Graph and product boundary

Single-link engine summaries report kilometres to metre resolution. The worked
fixture's node and unit coordinates were moved to retain its method-card lengths;
the hourly fixture retains its coordinates and uses measured graph lengths.
The two planes' road and parameter copies remain byte-identical. Headers bind
roads, flows and parameters by SHA-256. Provenance and evidence status stay
separate: hourly traffic is Simulated and observed; free-flow times are Public.

A screen obtains speed from `Traffic.link_speed`, link minutes from
`Traffic.link_minutes`, trip time and its breakdown from `Traffic.route`, and
areas from `Traffic.area`, all in `eii_product.areas_spike.traffic`.
L-83 R5 itemises exact link minutes and junction seconds. Residuals within one
printed millisecond per link are zero; larger positive residuals are rounded
half-up to milliseconds; a negative residual beyond that resolution is refused.
The total is the exact sum of its parts. Raw engine responses are exposed only
by `Traffic.route_for_measurement`. Drive-time outlines include turn costs at
junctions and are drawn from an engine grid; their entry-time deviations are
recorded in the task return.

## Verification state and commands

L-84 compares the custodian's shortest link time with the product route's exact
link-time sum. The engine's added junction cost is separate. Single-link times
agree within one printed millisecond; day-route residuals after itemised junction
seconds agree within one printed millisecond per link. Crossing and assignment
middle-node delays are pinned for engine requalification. The outline check uses
the L-85 absolute bound of forty seconds and retains the turn-shift check unchanged.
Recorded rows match fresh assignment bytes; the task return records the single
regeneration. The product's road and parameter copies remain byte-identical to
their custodian inputs.

Run `uv run --locked python -m pytest custodian/tests -v -p no:cacheprovider`.
The test-only calculation command is `python -m eii_custodian.assignment_spike
<flows> <roads> <parameters> <output>`. Wrong flow units return NO_DATA and exit
3; malformed inputs exit 1. The product imports none of this package.

The local mutation runner uses the pinned mutation dependency group and a
standard-library temporary copy of git-listed files. It runs from each package
folder with that package's source and tests; cross-plane tests under scripts/tests
are deliberately outside those local package runs. Observable survivors require
new tests; exact equivalent mutations are recorded in scripts/mutation_explained.toml.
The task return records commands, counts and limits. Independent review by another
maker remains with the lead. Round two supplies the road layer; decision record 0021 records the whole-speed rule.

A situation rounds the speed from its exact mean hourly minutes half-up to whole km/h (`situation_whole_speed`); a missing hourly row contributes its free-flow time before this function is called.
Run local mutation checks with `uv run --locked --group mutation python scripts/mutation.py custodian/src/eii_custodian/assignment_spike/{assign,delay,inputs,params,paths,run}.py`.
