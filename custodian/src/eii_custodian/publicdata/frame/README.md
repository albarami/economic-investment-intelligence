# Frame build status — S2-T02

`build_frame(cache, registry, review, output=None)` reads verified source pairs
without network access. Its result contains tables, receipts with method
`frame.v1`, inventories and named limitations. It is a partial frame build, not
a completed release. Fixtures contain invented values only.

The lead's structure-only note for ruling L-202, read on 2026-11-14, supplies the
raw schemas and join rules. `raw.py` reads the three named administrative
GeoJSON members inside the licensed `bnd_hdx` ZIP without extracting files.
It checks CRS84, properties, code structure and polygon types. Municipality,
zone and district geometry all come from that source under L-202 R1.

`layers.py` validates the closed attribute sets of the seven map layers. Their
geometry is never used: their cached exports state no coordinate system.
`joins.py` checks equal zone sets, derives the municipality codes through those
zones, and requires a consistent one-to-one municipality mapping. The two boundary sources
are joined by keys, never by names. District census rows first join the
map boundary layer by zone and district number; that layer joins licensed
districts by zone and English name. The district numberings are never compared.
Unmatched name pairs are reported and excluded until a reviewed alias exists.
`district_layer_aliases.csv` supplies only human-reviewed aliases.

When an output folder is supplied, the build writes the derived municipality
mapping to `municipality_names.csv` there for human review. It does so before
later frame checks, so a subsequent refusal does not hide the map that needs
review. The committed review mappings are not populated from fetched records.
The Greater Doha set remains the lead's assumption in its CSV; a name that does
not resolve through the reviewed municipality names refuses. This
selects the explicit set after the key-based join; it does not join the two
municipality sources by name.

The district population field `POP2020` maps to the closed residents/persons
pair in `pub_census_district`, on its joined district, with receipt lineage.
All map attributes are inventoried. L-212 M1–M5 and the lead's service-description
note, read on 2026-11-14, now fix the zone measures. `measures.py` emits employees
from the sector total only after checking equality with the nine named occupation
counts, excluding `Other`, in every zone. Both layers must be present together,
have the same zones and the same null coverage. Household totals sum `Qatari` and
`Non_Qatari` only when both exist. Nulls emit no rows; zero remains a figure.
Receipt lineage stays source-specific, including the occupation receipt used by
the employment check. Sector and occupation breakdowns, the population aged above
15 and the labour-gathering counts stay unloaded with their reason and DAT-128
status `not_applicable` in the build report. Household split fields are separately
listed as undeclared. The registry currently declares no nationality split; no
split-schema extension is invented if a future registry declares one.

L-222 N1–N5 confirms `pop_muni.municipality` as English and `lbldy` as
Arabic. Both fields resolve through the committed `municipality_names.csv`
(PUB-27), using the shared lookup in `crosswalk.py`. Whitespace runs, including
non-breaking spaces, collapse to a plain space and end whitespace is dropped;
no other normalisation is applied. Conflicting normalised spellings or keys
outside the frame refuse the crosswalk load. Both names on a row must resolve
to the same key. Unmapped spellings fail with source, field and distinct count;
only `output/build_report.json` receives the spellings, when output is supplied.
No spelling is printed or added to the committed crosswalk by the builder.
Unknown indicator tokens remain inventoried and unloaded. The
`est_census`, `zone_population` and `census_hh_type_2020` rows retain their confirmed
publisher and licence but remain skipped because their fields are unconfirmed.
`bnd_muni_2025` stays skipped. `bnd_geob` is not read by the frame build.

There is one assembler: `build_frame` inspects verified raw source pairs and
calls `build_live_frame`. The old staged-only assembler is removed under L-212
M7. Integration fixtures use the same ZIP and map-layer envelopes as the real
build. Primitive geometry, crosswalk, census and gazetteer tests remain.

Showcase and flagship source points resolve when `source_id` and `record_key`
are both filled and the places output names that point. An entry that is still
null stays pending S2-T06. Team-written Arabic remains pending native review
(PUB-32). The raw build reports those unresolved points rather than inventing
them. No geometry repair, tolerance, privacy parameter, new network fetcher or
command is introduced.

Library references recorded by the previous pass on 2026-11-14:
[h3-py API](https://uber.github.io/h3-py/api_verbose.html),
[h3-py changelog](https://uber.github.io/h3-py/_changelog.html),
[Shapely manual](https://shapely.readthedocs.io/en/2.2.0/manual.html), and
[Shapely constructive operations](https://shapely.readthedocs.io/en/2.2.0/constructive.html).
The minimal local stubs describe only calls this task uses. Third-party
libraries stay in the root engine dependency group, as L-202 requires.


Under ruling L-255, split a resolution-8 parent if any resolution-9 child has
its centre in a Greater Doha municipality, even when the parent's centre is
outside the frame. Store only the split parent's children whose own centres
are in the frame; never store that parent. Store an unsplit parent only when
its own centre is in the frame. Each stored cell takes its municipality, zone,
district and Greater Doha flag from its own centre. Siblings outside Greater
Doha therefore remain resolution 9; no Greater Doha cell is resolution 8.
Ambiguous centre membership still refuses. Stored ancestors and duplicate
resolution-9 ownership units both refuse.

Point ownership uses the point's resolution-9 index, or that index's
resolution-8 parent when stored. No owner means no cell; no neighbouring cell
is substituted. A fine cell uses its native hexagon. A coarse cell uses
`h3.cells_to_geo` over its resolution-9 children, tracing their shared outline
from indexes rather than a floating-point polygon union. The resolution-8 geometry is not a hexagon.
The h3 4.5.0 installed implementation and the official API reference above
were checked on 2026-11-14; fixture tests exercise the outline and ownership.

Municipalities and zones must tile the frame exactly. Districts must be valid,
non-overlapping and wholly inside exactly one zone with consistent keys.
Each zone must be covered exactly by districts or contain none and appear in
`zones_without_districts.csv` with `no_district_in_boundary_source`.
Partial coverage, unknown exceptions, unlisted gaps and listed zones with a
district all refuse. Null grid district keys occur only in those reviewed
zones, counted once with `zone_without_district`. Districts without a centre
stay in the district table and are counted; zones without a centre refuse.
Administrative gazetteer points remain unchanged when they have no owner:
only municipality, zone and district rows may have null cells, counted by
kind with `point_without_base_cell`. Other kinds still require a cell.

Measured limits from the lead's L-255 real-boundary probe of 2026-11-14
(not reproduced by this fixture-only pass): 460 resolution-9 units whose
centres are on land have no owner because the unsplit parent centre is outside
the frame; 473 owned units have centres outside the frame. The probe's rough
area equivalents are about 48.45 and 49.82 square kilometres, respectively;
these are not exact land/sea intersection areas. The centre rule can omit
land and extend stored shapes over sea. The source's district-free zone 99
has three offshore pieces and five coarse-cell centres. Two districts have
no stored centre, and five administrative district points have no owner.
The frame is not an exact geographic cover of land.

Every municipality's four source names (licensed English and Arabic, zone
layer English and Arabic) must resolve to its own frame code in the committed
names file. Greater Doha aliases use that same lookup; duplicate codes refuse.
The optional output includes `proposed_zone_crosswalk.csv` with every inspected
zone-number source, and `proposed_population_indicators.csv` with all indicator
names unmapped. Existing reviewed rows are preserved; supplemental proposed
rows retain previously unlisted source tokens even for an existing zone number.
Every number outside the frame is marked unmatched in the supplemental rows.
Only committed review filenames are read, never proposed files. The report
summarises unlisted zone numbers once per source; the proposal holds the detail.
