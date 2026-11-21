# Lead-only restricted findings (S2-T35)

Only the lead's own shell runs the real-cache command from the repository root:

```sh
uv run --locked python -m pytest custodian/data_tests -vv -p no:cacheprovider
```

Neither the whole test command, a gate nor CI selects this folder. Ordinary
tests in `custodian/tests/test_restricted_expectation_guards.py` use invented
temporary caches only. There is no environment, CLI or configuration redirect
of `cache.CACHE`. The lead uses `data/public_cache/`; no agent reads that cache.
No fetching takes place here. Keep pytest's default traceback and short summary;
never enable locals. Safe failures contain a fixed case ID and reason only.

## National building inventory (S2-T20)

`test_national_buildings.py` is lead-shell-only. After the complete public build,
it rechecks the current pins and receipts, independently reconciles each part's
selected IDs to the canonical table and every table ID to a height row, and
checks exclusions and the per-part sorted-ID hashes. It repeats the building
and height producers with no network and compares their hashes (FE-98). This
replay rewrites only the producers' documented generated asset files, under
`data/assets/buildings/` and `data/assets/heights/`. It prints public aggregate
counts, optional-field coverage, boundary-review state and hashes, not IDs.
It was not run by the worker. STAC item addresses/schema, frame-box coverage,
invalid-footprint and in-box-outside-boundary review, and the pack's historical
Lusail-box count still require the lead's source reading. No box is guessed for
that historical comparison. A refusal is a failure, never a skip.

## Pinned method replays (P05)

`test_pinned_c1` reads `lic_active` and `pop_muni` through `cache.pinned`.
The population reader uses the frame's confirmed field schema. The replay
uses the reviewed municipality names and population indicators, the 2025
resident rows, and every licence-activity in the stock denominators, including
legacy codes. Missing or duplicate municipal resident counts fail. The test
checks both newly printed C1 denominators, both densities and both location
quotients. Its invented-cache tests are in
`custodian/tests/test_pinned_method_replays.py`.

`test_pinned_c8` reads the pinned `census_2020_workbook` and
`census_zone_sector` through `cache.pinned_body`, which reuses the frame's
verified receipt reader and the existing named-sheet OOXML reader. National
coverage comes from sheet `76`, the total row selected by label within the
"Both Sexes" block; it is not the separate establishment source `est_census`
or a sum over zones. The test recomputes each complete zone, checks the seven
sector counts sum to its total, returns `NO_DATA` for every zone with a null
sector count, and compares the national share, zone shares and range to plain
raw-file arithmetic within the unchanged half-percentage-point tolerance.
It prints no file values. Its invented-cache proof and wrong-value plants are
in `custodian/tests/test_pinned_c8.py`. The separate PUB-71 replay and its
lead-proof failure accounting are unchanged.

The fixture restores attribution for both sources from their registry rows,
without census counts or shares. A registry row has no file retrieval date:
`retrieval_date: "pinned receipt: retrieved_utc"` explicitly resolves that field
at replay time, and `SourceChain.retrieved` carries the pinned receipt's date.
`terms_read_on` remains the registry's terms date and is never substituted for
retrieval. No actual retrieval date is guessed or read from the real cache.
PO-S2-48 remains open until the lead supplies both method pins and runs:

```sh
uv run --locked python -m pytest custodian/data_tests/test_pinned_methods.py::test_pinned_c8 -vv -p no:cacheprovider
```

PO-S2-51 still needs the lead's real-cache run. PO-S2-52 remains open for the
signed activity spine and its input binding (OI-16 and OI-203, after the basket
confirmation OI-172). There is no skipped or prefix-based C2 class replay.
The new pinned C1 test was not run by P05; helper tests use invented temporary
snapshots only. No task or slice gate is closed by those helper tests.

## Inventory and preparation

`restricted_cases.CASES` is the metadata-only inventory, version `S2-T35-v1`.
Its anchors reconcile S2-T22's task log, OI-195, OI-276, PUB-71 and document 04
section 2.2's locally retained counts. Decision 0034 item 3's standing places
are excluded. The removed district alias is a name rather than a numeric
finding; the existing alias guard remains responsible for it. No source record,
source name, expected value or expected-record digest belongs in this folder.
Another maker must check completeness before the lead supplies expectations.

PUB-71 replays both sector and occupation snapshots with `read_cached`,
`layer_rows` and `check_employment`, then `coverage_share` and `rounded`.
It checks raw national inputs and national/zone results using the existing
precisions and exact equality of the stage record. National figures sum only
zones that carry counts, leaving zones with both counts null out of both sums,
as the source publishes them and the original public-data stage computed PUB-71.
Source-count cases replay
`layer_rows` and count validated rows. Census counts use the source's own
geography. No tabulated count is apportioned to a drawn area.

The committed GIS pointer identifies services, but not the removed numeric
finding kinds. The evidence file it cites is not supplied in this workspace.
H2's exact period, hour predicate, denominator, weighting and selected partition
binding are likewise not recoverable from the supplied committed records.
Those cases stay outstanding. `read_gis` already reads verified snapshot bytes,
checks the same receipt identities as `read_cached`, then calls `_parse_body`.
`boundary_finding_counts` and `h2_hour_counts` have invented-input tests; they do
not assert a recovered real recipe. H2 cannot become ready until its recipe
and partition-to-assembled-snapshot binding are confirmed and implemented.
`bnd_muni_2025`'s row count is pinned by its registry `row_count_min`/`row_count_max`, checked by `fetch/checks.py` at fetch; it is not an inventory case.

The lead prepares these **uncommitted** files by independent inspection of
the selected source snapshots, never from output of the replay code under test:

- `data/public_cache/method_pins.json`: existing source-key to SHA-256 map.
- `data/public_cache/local_expectations/PUB-71.json`: the existing object with
  exactly the five keys in `stage._LOCAL_FIELDS['PUB-71']`, each decimal text.
  Its shape is unchanged.
- `data/public_cache/local_expectations/restricted_cases.json`: an object with
  exactly `version` (`restricted.v1`) and `cases` (case ID to record).

Every ready case needs a record. Each record has exactly `method`, `version`,
`period`, `geography`, `units`, `expectation_origin`, `source_shas`,
`record_sha256`, `precision` and `tolerance`. All except the origin, hashes and
expected values are fixed by the committed inventory and `precision(case)`.
The origin must be nonempty and name an independent worksheet or reading.
`source_shas` holds exactly the case's sources and agrees with `method_pins.json`
and the selected receipts. `record_sha256` is SHA-256 of `canonical(expected)`:
UTF-8 JSON with sorted keys, no separator whitespace and `ensure_ascii=False`.
Keep every such digest local, including evidence of the lead's plant.

For PUB-71, `expected` is the object in its separate existing file. For other
ready cases, add exactly one further record key, `expected`, holding only
`rows` as decimal text. `precision` has the same field set, using integer zero
for raw counts and zone results, integer one for `national_1dp`. `tolerance`
has the same fields, all decimal text zero: nothing loosens stage equality.
Unknown IDs/fields, malformed or nonfinite decimal text, duplicate JSON keys,
wrong versions/pins/checksums, and symlink/path escapes are refused by name.
Missing files or case records fail as `<case_id>:missing_record`.

`CaseLineage` validates lead-test evidence only. Publisher, dataset title, URL
and retrieval date come from the receipt; method/version come from the case;
the digest equals the selected receipt and pin. Licence ID/basis agree literally
with the registry, including a genuinely empty ID. A release table is present
only if listed by the registry. PUB-71 also builds a strict `SourceChain` for
`pub_census_zone`. A GIS lineage with no table/licence is never converted into
a fabricated release fact. Release chain validation is unchanged.

## Outstanding set B and lead's wrong-value proof

Pin verbosity at `-vv` in the command above and the invented child runs. At
lower verbosity, pytest can truncate a long node's short-summary line to the
terminal width, dropping its reason (lead ruling L-1056 item 2). Never rely on
`COLUMNS` or a terminal. Keep `pytest.fail(..., pytrace=False)`; the accepted
summary form is exactly `FAILED <node> - Failed: <CASE>:<reason>`. Every other
`FAILED` or `ERROR` line, including a truncated line, fails with
`summary_unparsed` (L-1056 items 1 and 3).

Before running, derive B with `restricted_cases.outstanding()` from the
reviewer-checked inventory and record it in the ledger. The current full set is:

- `C12-MTH-46:awaiting_routine` (S6-T13).
- `H2:awaiting_expectation` (S2-T35 recipe/partition confirmation).
- `GIS-ZONES:awaiting_expectation` (S2-T35 finding confirmation).
- `GIS-MUNICIPALITIES:awaiting_expectation` (S2-T35 finding confirmation).
- `GIS-DISTRICTS:awaiting_expectation` (S2-T35 finding confirmation).

Each is a failing parametrized test, never a pass, skip or xfail. C12's acceptance
remains unticked until S6-T13 supplies the routine. The command intentionally
exits one while B is nonempty. An exit code alone proves no plant.

1. Supply all ready records independently. Run the exact command above and
   capture its exit and default short summary. Require exit one and reasons
   exactly B. Any extra reason, including `missing_record`, is a failed proof.
2. Save the original local companion and selected ready expectation bytes.
   Record their file SHA-256s and the selected record's canonical checksum
   locally. Change one expected field **in place**, recompute the record
   checksum, and rerun the same command. Require exactly B plus
   `<planted case>:expectation_mismatch` and exit one.
3. Restore original bytes in a `finally` block even if a check fails. Prove both
   file hashes and the case-record checksum restored. Run once more; require
   exactly B and exit one. No redirect, refreshed baseline or retry.

Count **every** `FAILED` and `ERROR` short-summary line. An unparsed line is an
unexpected reason and fails the proof. The final failed count must match the
number of parsed lines; no skipped, xfailed or error count is allowed.
`local_expectations.summary_reasons(text, exit_code)` validates this accounting
without launching a run; separately compare its returned set with B or the
planted union. Record every exit, count and reason set in the lead's ledger.
Use only IDs/reasons in committed evidence; local values and their digests stay
local. The builder's invented subprocess proof does not replace this lead run.

## Coverage limit

Comparators, parsers and counters here are outside the mutation runner's module
roots. Mutation coverage is **not measured**, not a pass; the task ledger and
proposed open item carry that limitation. No campaign or new mutation gate is
introduced (decision 0055). Existing regression assertions, cache helpers,
commit/alias guards, runner selections and privacy/security controls stay intact.
