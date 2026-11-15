# Places pipeline (S2-T06)

This package reads local Overture Parquet and builds `pub_place`. It does not
route. An area arrives only through `AreaProvider`: a reviewed point, a mode
(`walk` or `drive`) and a cut-off (5 or 10 minutes) return one polygon with its
method version, graph hash, inputs hash and engine version, or a typed error.
A result flagged `stand_in` is not passing evidence for a flagship decision.

`record_level_source` is the one function that selects the source entry whose
`property` is empty. The licence comes from the attribution table keyed on that
entry's `dataset` token. `sources[].license` is ignored.

Outside a showcase area a place is shown at confidence 0.7000 or above. Inside,
only the latest status `verified_open` is shown. With no area provider every
place is treated as outside and the report says `showcase_areas_pending`.

Every result carries the caveat "Open listings are incomplete". The census
figure is an input that carries its lineage from `est_census`. When that input
is absent the report says `census_comparison_pending` and the caveat holds no
figure. The Arabic line is pending native review.

Build places before the frame. A filled gazetteer spec without the places
output `places_s2_t06/place_points.json` stays a named frame error.

The four concrete files are registry rows under the S2-T06 block. Each file's
receipt is checked before the file is read. Tests use invented Parquet and a
stand-in transport. They do not fetch those files.
