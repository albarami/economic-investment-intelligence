# 03 — Data Contracts

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017 and 0019 on 2026-11-12, and by decisions 0021 and 0022 on 2026-11-13 |
| Date | 2026-11-13 |
| Owner | albarami |
| Purpose | Define every schema that crosses a boundary: the five source feeds, the release, the manifest, the fact object with its subjects and the area record, the graph and the application schema, each with tests that fail loudly. |
| Read first | [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md), [02_ARCHITECTURE.md](02_ARCHITECTURE.md), [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) |

## In brief

- Five source contracts (`business_register.v1`, `employment.v1`, `wages.v1`, `residence.v1`,
  `mobility.v1`) describe custodian-type feeds. Here every feed is synthetic or simulated, except
  that the establishments of `business_register.v1` are the real companies of the public business
  register, to which synthetic employment, wage and residence records are attached by registration
  number ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)); a real feed would have to pass the same conformance suite. Each protected feed holds every month of the one
  protected window. Every model of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md)
  item 15 reads the release tables built from these contracts, by their contract names only; nothing
  says that real records are used.
- Every field states what may leave the custodian plane and in what form. Person names, bank fields,
  addresses and record identifiers never leave it. Of a register company's attached records only its
  employee count leaves it, beside the company's registration number, as a row of the register-company
  list; its card fields are Public and come from the register. The named synthetic firms and their
  firm list are retired ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)).
- One wage-band scheme (twelve bands from a published Qatar Open Data Portal table) is used everywhere.
- The release is Parquet tables plus a manifest; the loader accepts only tables the manifest names;
  protected tables hold additive primitives only (the register-company list holds one employee count
  per company), and the one fixed-composition wage index of `month_change`.
- Protected rows carry monthly periods inside one protected window. `window_key`, one `window_key`
  per `world_seed` and the freeze rules are unchanged.
- Simulated presence is released as estimated counts with a range, by release unit, day type, hour,
  summer switch and segment. Hourly flows and road-link traffic are released beside it. All three
  are marked Simulated. No table holds presence by pay band: that figure is computed from published
  rows (DAT-160).
- An area is a drawn polygon, a radius from a point, or a walk or drive time from a point. Only
  figures from the protected record types snap to whole release units. The area record keeps the
  requested shape and, for protected figures, the snapped units with the snap report.
- Public tables add the 77 portal datasets, the FDI projects and the agency's pages of
  [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), and four Public tables
  of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) (DAT-157).
  Only a Public table whose registry entry declares it carries a sex or nationality-group dimension.
  Synthetic and protected contracts carry no sex or gender, and carry nationality only as the
  worker's nationality group and the register's establishment nationality (decision 0022, DAT-141).
- Every number on screen is a fact object (section 9). Its subject limits which facts a claim
  accepts. Provenance and evidence status stay separate. A field of a Public source whose published
  value is a date or a text that holds a digit is a fact too, in a closed unit (DAT-155). A forecast,
  a base rate, a site estimate and a scenario range are sets of facts from tested code, each with the
  typed companion facts that its rule names (DAT-158 to DAT-162).
- A headerless, undated or unscoped feed fails. Rows with placeholder identifiers are quarantined and
  counted, and too many of them fail the feed.

## 1. Conventions

### 1.1 Terms

- **Custodian plane**: the offline build (`custodian/`), the only place record-level (synthetic) data
  exists ([02_ARCHITECTURE.md](02_ARCHITECTURE.md)). **Vault**: its ephemeral store, deleted after
  each build.
- **Feed**: one delivery of one source contract for one reference period (a feed bundle, section 3),
  produced by an adapter; v1 has only the synthetic adapter. For a protected contract the reference
  period is the span of the window's months, and the feed holds every month of it (section 7.1).
  **Conformance suite**: the tests in this document for one contract; a feed that fails any of them
  never enters the vault.
- **Release**: the immutable, content-addressed output of one build (Parquet tables plus
  `manifest.json`). **Release unit**: a whole-cell unit, a municipality remainder, a terminal
  `ha_home` municipality unit, a municipality unit of the `money` and `quartile` pay partitions
  (`rp_all_money`, `rp_all_quartile`, `wp_all_money`, `wp_all_quartile`) or the national unit
  ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16).
- **Window**: the one protected span of consecutive complete months that a version 1 release
  exports. Its rows carry the months as their periods (DAT-136).
- **Area record**: the requested shape of an area and, for protected figures, its snapped release
  units with the snap report (section 9.2).
- **Register company**: a real company of the public business register or of the financial centre's
  public register. Its card fields are Public (`pub_register_company`); the synthetic employment,
  wage and residence records attached to it by its registration number are its attached records
  ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)).
- **Register-company list**: the Protected table `register_company_list`, which gives each register
  company's employee count from its attached records (section 7.3, DAT-140). It replaces the firm
  list of named synthetic firms, which decision 0022 retires.
- **Public split table**: a Public table with a `sex` or `nationality_group` dimension that the
  registry entries of its sources declare (DAT-141).
- **Base cell**: the fixed-grid cell at a location: H3 resolution 9 inside Greater Doha, 8 elsewhere
  (master design section 6). **Primitive**: an additive released count or wage bill (section 7.3).
- **ADDITIVE FAMILY**: one release table, one partition, one measure where that table has measures,
  and one breakdown. Its leaves are mutually exclusive. Every stored total is the exact sum of the
  leaves of its own family; no equality is required between families (PRV-29, PRV-71).

### 1.2 Logical types

| Type | Meaning | Parquet | DuckDB | PostgreSQL |
|---|---|---|---|---|
| `string` | UTF-8 text | BYTE_ARRAY (UTF8) | VARCHAR | text |
| `int` | 64-bit integer | INT64 | BIGINT | bigint |
| `decimal(p,s)` | exact decimal; money is QAR | DECIMAL(p,s) | DECIMAL(p,s) | numeric(p,s) |
| `bool` | true or false | BOOLEAN | BOOLEAN | boolean |
| `date` | calendar date | DATE | DATE | date |
| `month` | `YYYY-MM` | BYTE_ARRAY (UTF8) | VARCHAR | text |
| `timestamp` | UTC instant, microseconds | TIMESTAMP (UTC) | TIMESTAMPTZ | timestamptz |
| `cell` | H3 cell index as a 64-bit integer | INT64 | BIGINT | bigint |
| `geometry` | WKB, EPSG:4326, GeoParquet 1.1 encoding | BYTE_ARRAY (WKB) | GEOMETRY | geometry(Geometry,4326) |

- `cell` is an integer: the H3 index keeps its top bit reserved at zero (H3 documentation), and
  PostgreSQL holds no `h3` extension (master design section 3.3). H3 arithmetic runs only in DuckDB
  and Python.
- DuckDB 2.0, PostGIS 3.6 and GeoParquet are newer than most model training data: read their current
  documentation first. The public-data research (2026-11-11) notes DuckDB 2.x needs
  `SET geometry_always_xy=true`; confirm at the spike (slice S1).
- Null column: `N` never null; `Y` nullable, and the row names the status or reason that explains a
  null (DAT-07).

### 1.3 Crossing classes (the "what may cross" vocabulary)

Every source field carries exactly one class, and `LIST` may be added to it. `LIST` is the only
class that combines with another. The release builder and the loader enforce them.

| Class | What may leave the custodian plane |
|---|---|
| `NEVER` | Nothing. The field stays in the vault and is deleted with it. |
| `LINK` | Nothing. Used only by linkage to join feeds inside the vault. |
| `GEO` | Only as membership of a release unit (`unit_member`); never as a per-record location. |
| `DIM` | Only as a value of a closed, coarse code list used as a dimension of a released table. |
| `AGG` | Only as a contribution to treated additive primitives in a protected or simulated table. |
| `QC` | Only as aggregate counts in the conformance report and the coverage declaration. |
| `PROV` | Only as provenance: reference period, hashes, contract version in the manifest. |
| `LIST` | Only as a column of `register_company_list` (DAT-140), for a register company with attached records: its `registration_number`, the key to its Public card fields, and its employee count, which is derived inside the vault from the attached employment records (DAT-04). Never beside a wage, wage bill, pay band, occupation, nationality group, residence or opening or closing month, and never a vault identifier ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). |

## 2. The eight contract design requirements

These are general lessons about administrative data. They apply to every source contract.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-01 | One legal registration can cover several establishments. Feeds join on `establishment_id`. A join on `legal_entity_id` alone is allowed only when that legal entity has exactly one establishment in the register for the same reference period; otherwise the join fails. | Fixture: a legal entity with two establishments and wage records keyed by legal entity only. Linkage must raise `AMBIGUOUS_REGISTRATION` and attach no record. |
| DAT-02 | Identifiers are normalised (trim, upper-case, remove inner spaces and non-breaking spaces, convert Arabic-Indic digits to ASCII), then validated against their pattern (section 4); a register company's `registration_number` is normalised the same way and validated against the register file (DAT-12, [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). Placeholders are rejected: empty, `0`, `-`, an em dash, `N/A`, `NA`, `NULL`, `NONE`, `UNKNOWN`, `TBD`, and any body made of one repeated character. | Fixture rows with each placeholder and with noisy but valid identifiers, registration numbers of the invented stand-in register included. Placeholders land in the quarantine count; noisy valid identifiers normalise to the canonical form. |
| DAT-03 | Occupation and activity free text is mapped only through a reviewed map (`contracts/maps/occupation_map.csv`, `contracts/maps/activity_map.csv`; columns `raw_normalised`, `target_code`, `status` in `mapped`, `unmappable`, `pending`, `reviewed_on`). Unmapped values stay visible as `unmapped` and are never counted in any group. | A fixture with an unmapped title must appear under `unmapped` in `occupation_pay` and in no other group; the group totals plus `unmapped` equal the overall total. |
| DAT-04 | The same person can appear in several feeds and several times in one feed. Records are deduplicated by person within employer group and month. Workplace tables count one job per (person, employer group, month). Residence tables count one person per month, attached to the job with the highest net pay that month (ASSUMPTION: simplest rule that never counts a resident twice). | Fixture: one person with two records in one group and one in another group. `worker_pay` counts two jobs; `resident_pay` counts one person. |
| DAT-05 | A feed without an internal reference period is not accepted. File dates, creation times and file names are provenance only and never set a period. | A feed whose rows lack the contract's period field fails with `NO_REFERENCE_PERIOD`, whatever its file date. |
| DAT-06 | Coverage is always partial. Every feed ships a coverage declaration (section 3.2) that lists what it does not cover. | A feed bundle without `coverage.json`, or with an empty `exclusions` list and no `exclusions_none_reason`, fails. |
| DAT-07 | Unknown stays blank with a reason. Missing coverage is never turned into zero. Every nullable field has a companion status or a reason code. | Fixture with unresolved cells, missing occupations and an incomplete month: each appears as a null with its reason or in a named count (`unmapped`, `irregular_count`, coverage report); a test fails if any of them becomes 0 or enters a band. |
| DAT-08 | Every feed has headers and a schema. Parquet carries its schema. A CSV file is accepted only when its first row equals the contract's field names in contract order; a headerless file fails. | A CSV fixture whose first row is data fails with `HEADER_MISSING`; a CSV with fields out of order fails with `HEADER_MISMATCH`. |

## 3. Feed bundles

### 3.1 Bundle layout

A feed bundle is one directory, `<feeds>/<contract>/<reference_period>/`, holding
`feed_manifest.json`, `coverage.json` and one file per table (Parquet preferred; CSV per RFC 4180,
UTF-8, comma-separated, header row first). A reference period that spans months is written
`YYYY-MM/YYYY-MM` in the manifest and `YYYY-MM_YYYY-MM` in the directory name. Each of the four
protected contracts delivers one feed for the whole window, so `window_key` keeps exactly four
inputs (section 8). `feed_manifest.json` fields: `contract` (for example
`wages.v1`), `contract_revision`, `reference_period`, `adapter`, `produced_at` (provenance only,
DAT-05), `seed` (synthetic feeds only) and `tables` (list of `{name, file, format, row_count, sha256}`).

### 3.2 Coverage declaration

`coverage.json` fields: `contract`, `reference_period`, `in_scope` (one sentence),
`exclusions` (list of `{code, description, estimated_share}` with `estimated_share` null when not
known), `exclusions_none_reason` (null unless `exclusions` is empty), `known_gaps` (list of
sentences), `months` (list of `{month, status}` with status `complete` or `incomplete`).

### 3.3 Feed rules

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-09 | A feed bundle holds `feed_manifest.json`, `coverage.json` and exactly the tables its contract names; every file's SHA-256 and row count match the bundle manifest. | Extra file, missing file, hash mismatch and row-count mismatch fixtures each fail. |
| DAT-10 | Conformance runs before any record enters the vault. One failed test stops the build. A row-level failure quarantines the row; a feed whose quarantined rows exceed 1% of any table fails (ASSUMPTION: a proposed acceptance threshold). Reports print rule names and row counts only, never record values or identifiers. | A failing fixture stops `./eii build-world`; a 2% placeholder fixture fails the feed; a log scan finds no `SYN-` token and no field value in the report. |
| DAT-11 | A field whose crossing class is `NEVER`, `LINK` or `QC` never appears as a column, or as a value, in any release table. | The loader check DAT-83 runs over every release; the release builder test also scans every string column for the identifier pattern of section 4, with no exception since [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) retired `firm_list.firm_key`, and checks that a `registration_number` appears only in `register_company_list` and `pub_register_company` (DAT-83, DAT-140). |

## 4. Identifiers for synthetic entities

Pattern: `SYN-<kind>-<body>`. The body uses the Crockford base-32 alphabet
(`0123456789ABCDEFGHJKMNPQRSTVWXYZ`), contains at least two letters and no run of more than four
digits. These two constraints are an ASSUMPTION chosen so that no body can read as a real numeric
identifier.

| Kind | Entity | Body length | Example (illustrative) |
|---|---|---|---|
| `E` | Establishment | 6 | `SYN-E-7F3K2Q` |
| `L` | Legal entity (the registration) | 6 | `SYN-L-Q4W8NB` |
| `G` | Employer group | 6 | `SYN-G-H2MX7R` |
| `P` | Person | 8 | `SYN-P-K7Q2M9XD` |
| `F` | Salary file | 8 | `SYN-F-3ZT8KQ4W` |

No release holds a value of these forms. The firm list and its released `firm_key` are retired by
[decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md); a register company is keyed in the release by the register's own registration
number, which is not a synthetic identifier (DAT-15, DAT-140).

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-12 | Every synthetic identifier matches `^SYN-[ELGPF]-[0-9A-HJKMNP-TV-Z]{6,8}$` with the body length of its kind and the letter and digit-run constraints above. The register company's `registration_number` (section 6.1) is not a synthetic identifier: it is the register's own number, and it must equal a registration number of the business register's file read through `EII_REGISTER_FILE` or, for a company of the financial centre's public register, of that register's own file read through `EII_FC_REGISTER_FILE` ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) item 1). | Regex and constraint check over every identifier column of every feed except `registration_number`, which is checked against the two register files; the fixtures use an invented stand-in of each file, of the same shape: a company present only in the stand-in of the financial centre's file passes through `EII_FC_REGISTER_FILE`, and a `registration_number` absent from both stand-ins fails. |
| DAT-13 | Collision rule: identifiers are generated from a seeded, collision-free sequence (a keyed permutation of a counter), never by random draw. Any duplicate within a kind fails the build. | Uniqueness check per kind; two builds from one seed produce identical identifiers. |
| DAT-14 | Companies carry no synthetic name: a register company keeps the name the register publishes ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) items 1 and 5). The synthetic names that remain, the display names of the fictional organisations of the seats (`app.organisation.display_name`) and the depot and branch labels of the case sample files (section 12.2), come from a visibly synthetic lexicon. A name whose normalised form (case-folded, diacritics and tatweel removed, spaces collapsed), with or without its visible `SYN` token, equals any real name in `pub_register_company`, `pub_place`, `pub_place_fsq`, `gazetteer`, `pub_venue_visits` or `fdi_projects.company` fails the build ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 12, [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 21, decision 0022 item 5). Synthetic persons are located to a base cell, never to a named building. | Collision test against all six tables; a fixture name equal to a company of the invented stand-in register, a gazetteer entry, a venue, an investing company or a name of `pub_place_fsq`, with or without the token, fails. |
| DAT-15 | No synthetic identifier, in any contract, mimics a real registration, establishment or personal identifier: no all-digit synthetic identifier, and no run of exactly eight or eleven digits anywhere in the repository. The one real identifier a contract holds is the register company's `registration_number` (section 6.1). Its values exist only outside the repository, in the register file, the vault, the release and the serving stores, and never in a brief, a fixture, a log, a ledger row, an egress record or a model request ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) item 8). The tests use an invented stand-in register whose numbers obey this rule. | The CI identifier-pattern scan and DAT-12; the invented stand-in register passes the scan. |

## 5. The wage-band scheme

The scheme is the twelve-band structure of the Qatar Open Data Portal dataset "Average Monthly Wage
(Q.R.) for Workers in Private Sector in Qatar" (CC BY, 2020 to 2025, retrieved 2026-11-11). That table
counts occupations by average monthly wage; this project applies the same boundaries to person-month
pay. That reuse is an ASSUMPTION: it keeps every band comparable with a published table.

| Band | Monthly amount (whole QAR) | Band | Monthly amount (whole QAR) |
|---|---|---|---|
| B01 | 1,000 or less | B07 | 25,000 to 29,999 |
| B02 | 1,001 to 4,999 | B08 | 30,000 to 34,999 |
| B03 | 5,000 to 9,999 | B09 | 35,000 to 39,999 |
| B04 | 10,000 to 14,999 | B10 | 40,000 to 44,999 |
| B05 | 15,000 to 19,999 | B11 | 45,000 to 49,999 |
| B06 | 20,000 to 24,999 | B12 | 50,000 and more (open top band) |

The published labels read "1000 Riyals", "1001 - 4999", "5000 - 9999", then steps of 5,000 up to
"45000 - 49999", and "50000 and More".

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-16 | Bands B01 to B12 above are the only wage bands in the repository: release, tools, cards, assistant and public pay comparison. The published B01 is exactly QAR 1,000; this scheme extends it to "1,000 or less" so that net pay below the basic minimum still has a band (ASSUMPTION). | A test loads the band table from `contracts/` and fails if any other band boundary appears in code or release. |
| DAT-17 | An amount is rounded half-up to whole QAR before banding. Both measures (`net`, `basic`) use the same scheme and are never pooled. | Boundary fixtures: 4,999.49 is B02; 4,999.50 is B03; 50,000 is B12. |
| DAT-18 | Merging adjacent bands (fewer than five earners) yields a range `band_from`..`band_to` of existing bands; it never creates a new boundary. | Every `band_from` and `band_to` value in the release is one of B01..B12 or `ALL`. |

The statutory floor for synthetic basic pay is QAR 1,000 a month under Law No. 17 of 2020 (ILO news
release, retrieved 2026-11-11).

## 6. Source contracts

Each contract lives in `contracts/<name>/` as JSON Schema per table plus a semantics note. The tables
below are binding. "Public layout field" points to the public specification that a field mirrors.

### 6.1 `business_register.v1`

**Purpose.** Where activity is licensed: establishment identity, legal entity, employer group,
activity and registered location. Under [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) the establishments are the real
companies of the public business register and of the financial centre's public register. The world
build reads the register file through `EII_REGISTER_FILE`, and the financial centre's file through
`EII_FC_REGISTER_FILE`, in the lead's own shell: a company's name, activity and registered location
are the register's published fields, taken only from those files. Only the employment, wage and
residence records attached to a company (sections 6.2 to 6.4) are generated, with the employee
count, size class and deployed share of staff derived from them (decision 0022 item 2). No other
attribute of a real company is generated ([05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md)
SYN-16): a field of this feed that the register does not publish for a company, such as
`registration_status`, `address_type` or `licence_status`, is taken only from the register files
where a register shows it, and is otherwise absent for that company. How such an absent field is
held, the address type and the opening and closing months stay open (document 05 Q12 and Q14), and
no value is generated for them meanwhile; whether the vault keeps legal-entity and employer-group
keys beside the registration number is open (document 05 Q13). Each establishment carries the
company's registration number, which attaches the synthetic employment, wage and residence records
to it (decision 0022 item 2).
**Reference period.** `as_of_date`: the snapshot date, the last day of its month. A feed holds one
snapshot for every month of its reference period (section 7.1).
**Coverage declaration.** In scope: establishments licensed in the commercial register, and the
companies of the financial centre's public register (decision 0022 item 1). The feed declares as
exclusions entities registered in neither (government entities, entities licensed by a free-zone
authority). ASSUMPTION: the simplest honest scope for a
commercial register; a real custodian states its own.

Table `legal_entity` (grain: one row per legal entity per `as_of_date`).

| Field | Type | Null | Meaning and allowed values | Crosses as |
|---|---|---|---|---|
| `as_of_date` | date | N | snapshot date | PROV |
| `legal_entity_id` | string | N | `SYN-L-…` | LINK |
| `group_id` | string | Y | `SYN-G-…`; null means the entity is its own group | LINK |
| `registration_status` | string | N | `active`, `suspended`, `cancelled` | QC |

Table `establishment` (grain: one row per establishment per `as_of_date`).

| Field | Type | Null | Meaning and allowed values | Crosses as |
|---|---|---|---|---|
| `as_of_date` | date | N | snapshot date | PROV |
| `establishment_id` | string | N | `SYN-E-…` | LINK |
| `legal_entity_id` | string | N | parent legal entity | LINK |
| `registration_number` | string | N | the register company's registration number, read with the register file through `EII_REGISTER_FILE`, or with the financial centre's file through `EII_FC_REGISTER_FILE`; it attaches the synthetic employment, wage and residence records to the real company (decision 0022 item 2); not a synthetic identifier, and never in the repository (DAT-12, DAT-15) | LIST (as the key of `register_company_list`) |
| `trade_name` | string | N | the register company's name as the register publishes it (decision 0022 item 1); the release takes the name from `pub_register_company`, never from the vault | NEVER |
| `registered_cell` | cell | Y | base cell of the registered location that the register publishes; null when `address_status` is `unresolved` | GEO |
| `address_status` | string | N | `resolved`, `unresolved` | QC |
| `address_type` | string | N | `own_premises`, `office_tower`, `shared_business_centre`, `unknown` | QC |
| `licence_status` | string | N | `active`, `suspended`, `cancelled` | AGG |
| `licence_valid_from` | date | Y | null when not recorded | NEVER |
| `licence_valid_to` | date | Y | null when open-ended | NEVER |
| `establishment_nationality` | string | Y | the register's establishment nationality, a company attribute (decision 0022 item 6); null when the register shows none | DIM, only as a dimension that document 06 releases |

Table `establishment_activity` (grain: one row per establishment, activity and `as_of_date`).

| Field | Type | Null | Meaning and allowed values | Crosses as |
|---|---|---|---|---|
| `as_of_date` | date | N | snapshot date | PROV |
| `establishment_id` | string | N | establishment | LINK |
| `activity_code` | string | Y | commerce activity code as published (7-digit commerce code or 6-digit legacy); null when only text exists | DIM, after mapping to an `activity_class` node |
| `activity_text` | string | Y | activity as registered, free text | NEVER |
| `is_primary` | bool | N | exactly one primary row per establishment | AGG |

The May 2025 active licence-activity extract holds 249,622 activities across 4,755 codes (master
design section 9): 84.6% of the count (211,277; 2,035 codes) is under 7-digit codes whose first
four digits are an ISIC class, 4.5% (11,276; 1,363 codes) under other 7-digit codes, 10.8%
(26,844; 1,336 codes) under 6-digit legacy codes, and 0.1% (225) under 13 five-digit codes
(169) and 8 eight-digit codes (56). The four groups sum to the total. Of the legacy codes, 138
(3,163 activities) have a misleading class-like prefix. Every 7-digit commerce code mapping
requires a valid four-digit ISIC class, a meaning check and recorded human approval; a 6-digit
legacy code is never mapped by prefix.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-20 | Every `establishment.legal_entity_id` exists in `legal_entity` for the same `as_of_date`, and every non-null `group_id` names at least one legal entity. | Referential-integrity check. |
| DAT-21 | `activity_code` and `activity_text` are not both null. | Row-level check; failing rows are quarantined and counted. |
| DAT-22 | Activity codes reach the spine only through the reviewed `activity_map` (DAT-03); a 6-digit legacy code without a reviewed row maps to the `UNMAPPABLE` node. | A fixture with code 561000 must not land under any restaurant class. |
| DAT-23 | Exactly one `is_primary = true` row per establishment and `as_of_date`. | Count check. |
| DAT-24 | Quality: at least 98% of active establishments have `address_status = resolved`. The activity distribution is the recomputed four-group split above: 84.6% / 4.5% / 10.8% / 0.1%, including 138 legacy codes with misleading class-like prefixes. Every 7-digit commerce code mapping requires a valid four-digit ISIC class and recorded human approval. Six-digit legacy codes are never mapped by prefix, because 561000 is spare-parts trade, not restaurants (master design section 9). Thresholds here and in DAT-34, DAT-47, DAT-54 and DAT-64 are proposed acceptance thresholds (ASSUMPTION). | Bucket counts, all four groups, their displayed percentages and their sum match the master design; prefix-mapping fixtures, including 561000, fail; a mapping without human approval fails. |

### 6.2 `employment.v1`

**Purpose.** Who works where: person-to-establishment spells, occupation, employer sector and
whether the job is deployed away from the registered address. It sizes employers and gives
occupation groups.
**Reference period.** `reference_month`: the month the snapshot describes (state at month end). A
feed holds every month of its reference period (section 7.1).
**Coverage declaration.** In scope: employment relationships the custodian records. The feed declares
the employer sectors it holds. Persons whose sector is outside covered private-sector work are
"not measured" for pay (master design section 8).

Table `employment_spell` (grain: one row per person, establishment and spell, valid in the month).

| Field | Type | Null | Meaning and allowed values | Crosses as |
|---|---|---|---|---|
| `reference_month` | month | N | reference month | PROV |
| `person_id` | string | N | `SYN-P-…` | LINK |
| `establishment_id` | string | N | `SYN-E-…` | LINK |
| `spell_start` | date | N | start of the spell | LINK |
| `spell_end` | date | Y | null while the spell is open | LINK |
| `occupation_text` | string | Y | job title as recorded, free text | NEVER |
| `occupation_code` | string | Y | ISCO-08 unit group if recorded; null when only text exists | DIM, as ISCO-08 major group after mapping |
| `employer_sector` | string | N | `private`, `government_department`, `government_company`, `mixed`, `diplomatic`, `non_profit`, `domestic` | AGG (sets the coverage class) |
| `worksite_basis` | string | N | `registered_address`, `deployed_elsewhere`, `unknown` | AGG (`deployed_elsewhere_count`) |
| `nationality_group` | string | N | the worker's nationality group, coded as the real records code it (decision 0022 item 2); its closed list is fixed in `contracts/` in that format | DIM, only as a dimension that document 06 releases |

There is no sex, gender, age or name field, and none may be added (master design section 3.3,
DAT-141). The one nationality field is `nationality_group`, in the format of the real records
(decision 0022 item 2; rule 10 of AGENTS.md).
The sector list follows the public Labour Force Survey categories cited in the claims research.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-30 | `establishment_id` exists in the register snapshot of the same month. | Referential-integrity check. |
| DAT-31 | Occupation reaches the release only as an ISCO-08 major group through the reviewed `occupation_map`, or as `unmapped` (DAT-03). | A fixture title absent from the map appears only under `unmapped`. |
| DAT-32 | `spell_end` is null or not earlier than `spell_start`; overlapping spells of one person at one establishment are merged before linkage. | Fixture with reversed dates fails; overlapping fixture yields one spell. |
| DAT-33 | Deployed staff are never mapped to a worksite: `deployed_elsewhere` jobs count only in `deployed_elsewhere_count` at the registered unit. | Fixture contractor: zero earners placed at any cell other than its registered cell. |
| DAT-34 | Quality: at most 5% of active spells have both occupation fields null. | Share check. |

### 6.3 `wages.v1`

**Purpose.** What covered jobs pay, basic and net, by month.
**Model.** The layout mirrors the public "Wage Protection System File Format Specifications" of the
Salary Information File (a header of employer fields and one record per worker per file; CSV per
RFC 4180), retrieved 2026-11-11 from a Qatari bank's published copy. The ILO's November 2025 regional
report describes the same file content. This contract keeps the pay fields and drops every bank field,
every payer field, worker names, notes and the reserved fields.
**Reference period.** `salary_month` (the public layout's "Salary Year and Month").
**Coverage declaration.** In scope: payrolls of employers under the wage protection system. The
exclusions the ILO lists are declared with these codes: `government_entities`, `oil_and_derivatives`,
`armed_forces_police`, `financial_centre_employers`, `casual_workers`, `domestic_workers`,
`employer_family_members`, `agriculture`. Each month is marked `complete` or `incomplete`.

Table `salary_file` (grain: one row per employer establishment per file).

| Field | Type | Null | Meaning and allowed values | Public layout field | Crosses as |
|---|---|---|---|---|---|
| `file_id` | string | N | `SYN-F-…` | (file name) | LINK |
| `employer_establishment_id` | string | N | `SYN-E-…` | Employer establishment identifier | LINK |
| `salary_month` | month | N | reference month | Salary Year and Month | PROV |
| `file_created_at` | timestamp | N | provenance only | File Creation Date and Time | PROV |
| `total_salaries` | decimal(18,2) | N | stated total, QAR | Total Salaries | QC |
| `record_count` | int | N | stated number of records | Number of Records | QC |
| `sif_version` | string | N | missing source value normalised to `0` by the adapter, as the public layout states; the normalisation is counted in conformance output | SIF Version | QC |

Table `salary_record` (grain: one row per person per file).

| Field | Type | Null | Meaning and allowed values | Public layout field | Crosses as |
|---|---|---|---|---|---|
| `file_id` | string | N | parent file | (file) | LINK |
| `record_sequence` | int | N | unique within the file | Record Sequence | QC |
| `person_id` | string | N | `SYN-P-…`, replaces the personal or visa number | Employee identity or visa number | LINK |
| `payment_frequency` | string | N | `M` monthly, `B` bi-weekly | Salary Frequency | QC |
| `working_days` | int | N | 0 to 99; 0 means leave all month | Number of Working days | AGG (eligibility) |
| `net_salary` | decimal(18,2) | N | amount paid for the month, QAR | Net Salary | AGG |
| `basic_salary` | decimal(18,2) | N | contractual monthly basic, QAR, greater than 0 | Basic Salary | AGG |
| `extra_hours` | decimal(5,2) | N | overtime hours, up to 999.99 | Extra hours | NEVER |
| `extra_income` | decimal(18,2) | N | additions, QAR | Extra income | NEVER |
| `deductions` | decimal(18,2) | N | deductions, QAR | Deductions | NEVER |
| `payment_type` | string | N | `normal`, `settlement`, `partial`, `delayed`, `final_settlement`; a missing source value is normalised to `normal` by the adapter and counted in conformance output | Payment Type | QC |
| `housing_allowance` | decimal(18,2) | Y | not validated at source | Housing Allowance | NEVER |
| `food_allowance` | decimal(18,2) | Y | not validated at source | Food Allowance | NEVER |
| `transport_allowance` | decimal(18,2) | Y | not validated at source | Transportation Allowance | NEVER |
| `overtime_allowance` | decimal(18,2) | Y | not validated at source | Over Time Allowance | NEVER |
| `deduction_reason_code` | string | Y | `01`, `02`, `03`, `04`, `99`; required when `deductions` is not 0 | Deduction Reason Code | NEVER |

Excluded on purpose: worker name, worker bank, worker account, payer establishment, payer personal
identifier, payer bank, payer account, notes, the two reserved fields. The public layout's
"DECIMAL(X,Y)" counts X digits before the point, so its "Decimal (3,2)" equals SQL decimal(5,2);
types in this document use SQL meaning.

**Eligible person-month (the wage primitive).** A person-month within one employer group enters
earner counts, bands and wage bill only when: every record has the adapter-normalised `normal`
payment type; the working days sum to at least `min_full_month_days` (a `rules_version` parameter, proposed 20,
ASSUMPTION); and the net sum is greater than zero. Measure `net` is the sum of `net_salary` over the
month's records; measure `basic` is the `basic_salary` of the latest record that month (it is a
monthly rate). Ineligible person-months are counted in `irregular_count`, never as zero pay
(ASSUMPTION: avoids arrears and partial months distorting monthly pay).

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-40 | No bank, account, payer, name, notes or reserved field exists in any `wages.v1` table. | Schema check against an explicit deny-list. |
| DAT-41 | `record_count` equals the number of `salary_record` rows of the file. | Count check per file. |
| DAT-42 | One record per person per file (as the public layout requires). | Uniqueness of (`file_id`, `person_id`). |
| DAT-43 | `basic_salary > 0`; `deduction_reason_code` present whenever `deductions <> 0`. Before these row checks, the adapter normalises missing `sif_version` to `0` and missing `payment_type` to `normal`, writes both as non-null and records each normalisation count in conformance output. | Row checks; failures quarantined and counted; fixtures with missing source values prove non-null normalised output and an explicit normalisation count. |
| DAT-44 | Bi-weekly records are combined into the month before any statistic; the band applies to the month total. | Fixture: two bi-weekly records of QAR 2,600 band as B03, not B02. |
| DAT-45 | A month marked `incomplete` in the coverage declaration is excluded from every release window. | Fixture with an incomplete latest month: no release period includes it. |
| DAT-46 | Every `employer_establishment_id` exists in the register for the same month (DAT-01 governs joins). | Referential-integrity check. |
| DAT-47 | Quality: `total_salaries` is within QAR 1 of the sum of `net_salary`; under 1% of full-month records have `basic_salary` below QAR 1,000, each counted and reported. | Per-file and share checks. |

### 6.4 `residence.v1`

**Purpose.** Where covered earners live, reduced to a base cell and a housing class before the feed
is written. The address itself is never in the contract.
**Reference period.** `as_of_date`: snapshot at the last day of its month. A feed holds one snapshot
for every month of its reference period (section 7.1).
**Coverage declaration.** In scope: persons with a registered address. Declared gaps: addresses not
updated after a move (staleness), and labour-accommodation addresses arranged by employers.

Table `residence` (grain: one row per person per `as_of_date`).

| Field | Type | Null | Meaning and allowed values | Crosses as |
|---|---|---|---|---|
| `as_of_date` | date | N | snapshot date | PROV |
| `person_id` | string | N | `SYN-P-…` | LINK |
| `residence_cell` | cell | Y | base cell; null when `cell_status` is `unresolved` | GEO |
| `cell_status` | string | N | `resolved`, `unresolved` | QC |
| `housing_class` | string | N | `family_housing`, `labour_accommodation`, `institution`, `unknown` | DIM |
| `address_updated_on` | date | Y | last address update; null when not recorded | QC |

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-50 | No field holds an address, street, building, unit or coordinate; location exists only as `residence_cell`. | Schema deny-list check. |
| DAT-51 | `residence_cell` is a valid base cell: resolution 9 inside Greater Doha, 8 elsewhere, and present in `grid_cell`. | Every non-null value joins `grid_cell`. |
| DAT-52 | One row per person per `as_of_date`. | Uniqueness check. |
| DAT-53 | Residents with `unresolved` cells are counted in the coverage report and never placed in a cell. | Fixture: unresolved residents absent from every unit. |
| DAT-54 | Quality: at least 97% of rows `resolved`; `unknown` housing class under 2%. | Share checks. |

### 6.5 `mobility.v1`

**Purpose.** How many people are present, by place and time, as aggregates only. The tables are
shaped like telecom footfall products: panel device counts with an expansion factor, by fixed cell
and hour. The feed's time block is one clock hour. There are no trajectories, no device identifiers
and no per-place counts. The mobility simulator writes this feed (master design section 8); no
operator is contacted.
**Reference period.** `observation_start` and `observation_end` (dates) on every row.
**Coverage declaration.** In scope: devices of one simulated operator panel. Declared gaps: devices
are not people; expansion carries panel bias; visitors without a local subscription are modelled, not
observed.

Table `presence_hourly` (grain: base cell × day type × summer switch × hour × segment).

| Field | Type | Null | Meaning and allowed values | Crosses as |
|---|---|---|---|---|
| `observation_start`, `observation_end` | date | N | window the feed summarises | PROV |
| `cell` | cell | N | base cell | GEO |
| `day_type` | string | N | `weekday`, `friday`, `saturday`, `national_day`, `ramadan_day`, `match_day` | DIM |
| `summer` | bool | N | true for the summer season of document 05; true only with `weekday`, `friday` or `saturday` | DIM |
| `hour` | int | N | 0 to 23, local time | DIM |
| `segment` | string | N | `resident`, `worker`, `visitor` | DIM |
| `panel_devices` | int | N | distinct panel devices; at least 20 | QC |
| `expansion_factor` | decimal(9,4) | N | panel-to-population factor | QC |
| `expanded_presence` | decimal(14,2) | N | expanded average presence | AGG (to `presence_count`) |

`weekday` is Sunday to Thursday. `national_day`, `ramadan_day` and `match_day` are the three
simulated event day types of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)
(National Day, a day in Ramadan and a major match at a stadium), each with its own hour-by-hour
profile ([05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md)). Ramadan is
this one day type; it is no longer a season.

Table `od_hourly` (grain: origin × destination × day type × summer switch × hour). Same period, day
type, summer, hour, `panel_devices` and `expansion_factor` fields, plus `origin_cell` and
`destination_cell` (cell, N, H3 resolution 7, ASSUMPTION: coarse enough for flows) and
`expanded_trips` (decimal(14,2), N, AGG to `flow_hourly`).

The feed has no speed table. Road traffic is computed in the release build from released hourly
flows (`traffic_hourly`, DAT-139), never from an untreated feed row. The optional live traffic
provider of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md)
item 17 is not a feed and adds no table (DAT-163).

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-60 | No row has `panel_devices` below 20 (parameter set A minimum; set B applies 30 in the privacy engine). | Minimum check over both count tables. |
| DAT-61 | No table has a device, person, trip or sequence identifier, and no table is finer than one hour. | Schema deny-list and grain check. |
| DAT-62 | `presence_hourly` and `od_hourly` cells are valid H3 cells of the stated resolution inside the Qatar frame. | Join to `grid_cell` or its resolution-7 parents. |
| DAT-63 | `expanded_presence` and `expanded_trips` cross only as the treated, rounded estimates of `presence_count`, with their low and high bounds, and of `flow_hourly` (DAT-138, DAT-139, PRV-59); this replaces the unitless scores of the earlier pack ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 7). `panel_devices` and `expansion_factor` never cross. | No release column holds an untreated feed value under any name; `panel_devices` and `expansion_factor` occur in no release table; every released estimate and bound is a treated value. |
| DAT-64 | Quality: `expansion_factor` is at least 1; `summer` is true only with `weekday`, `friday` or `saturday`. | Range and combination checks. |

## 7. The release contract

### 7.1 Rules

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-70 | A `protected` release holds exactly the Parquet tables listed in section 7.2, one file each, at `data/releases/<release_id>/tables/<table>.parquet`. A `public_only` release holds only the listed Frame, Public, Graph, Lineage and applicable Control tables; it contains no Protected or Simulated table. The Public table `access_score_grid` is held by both kinds once the registry entry of its grid names it, and by neither before (DAT-154). The four Public tables of decision 0019 are held by both kinds once built (DAT-157). `release_manifest` is excluded from both kinds because the loader materialises it. | Directory listing equals the manifest table list for each release kind; a Protected or Simulated table in `public_only` and a `release_manifest.parquet` fixture fail; an `access_score_grid` held by one kind and not the other from the same registry, or held while the registry entry of `worldpop_qat_2020` does not name it, fails. |
| DAT-71 | Protected tables hold additive primitives only: the count and wage-bill columns named in 7.3, beside their key columns and, in `month_change`, its `status` and its one fixed-composition index, `stayer_wage_index` (PRV-55). No other index and no mean, median, quantile, share, minimum or maximum column exists in them. `register_company_list` is the one Protected table keyed by company rather than by release unit: it holds only the columns 7.3 names for it, one `employee_count` per register company, and no wage, wage bill or other count (DAT-140, [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). | Column allowlist per protected table; a wage, wage-bill, pay-band or other count column planted in `register_company_list`, and a stayer wage bill column planted in `month_change`, fail. |
| DAT-72 | Every row of a protected table other than `register_company_list`, which is keyed by registration number (DAT-140), of `presence_count`, of `flow_hourly` and of `access_score` references a `release_unit` whose `status` is `published`; withheld units carry no rows. | Referential and status check. |
| DAT-73 | A whole-cell release unit is one base grid cell or a union of whole base cells inside one root; each root is the intersection of one resolution-7 parent with one municipality. The only cross-root unions are a remainder made from failed roots of one municipality, the terminal `ha_home` unit made from every `op_res_quartile` whole-cell unit and remainder of one municipality, and the municipality unit of `rp_all_money`, `rp_all_quartile`, `wp_all_money` or `wp_all_quartile` made from every whole-cell unit and remainder of that partition in one municipality, which lies above that partition's units and holds exact sums of its published units' treated leaves, apart from the two unreleased stayer wage bills behind its stayer index (PRV-13, PRV-16, PRV-55). Each contributor universe has one parent-linked partition family: a coarser partition is made only by merging units of the finer one, and independent merges never cross. Closure and exact sums are required only within one additive family; cross-family routes are checked by the consistency audit of PRV-71 and are not required to be equal. Complement tests run across tables, dimensions and the months of the window. Cross-month fixtures and the mover case are part of version 1 for the months of the one window ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 10); a second protected window is not. In every `./eii build-release`, closure is proved, for every month of the window, by exhaustive structural checks for candidate A, candidate B and again for the selected export. After each proof, at least 10,000 seeded fuzz pairs run for that candidate or selected export. | `unit_member` proves exact coverage within each partition by the units that cover the frame and containment or disjointness across every partition and breakdown dimension of one contributor universe; in each of the four pay partitions every municipality has exactly one municipality unit whose members are exactly the union of that partition's units in its municipality, and a planted municipality unit that is not that union, or a planted unit of that partition that lies in no municipality unit, fails; exhaustive checks enumerate every treated leaf, supported derivation, within-family route and finite `make_area` input required by PRV-111, check sums only within each family, and send every cross-family route pair to PRV-71 without asserting equality. The custodian build report records at least 10,000 pairs for candidate A, at least 10,000 for candidate B and a repeated run of at least 10,000 for the selected export; the exported closure report carries only the selected-export proof and repeated run. A mutation after candidate validation fails the selected-export gate. No version 1 fixture contains a second protected window; the cross-month fixtures include a mover between two units across one pair of adjacent months. |
| DAT-74 | Public tables never share a row, unit or column with a protected table; Public figures stay on their official geographies. A Public figure reaches a drawn area only as an apportioned, Inferred fact computed at run time (DAT-147), never as a stored row; a row of a Public split table never reaches one, except that whole cells of `pub_pop_agesex_grid` may be summed over an area, which is not an apportionment (DAT-141). | No public table has `unit_id`; no protected table has `zone_code`; apportioning fixtures run under DAT-147. |
| DAT-75 | Every table has a declared primary key with no null key parts; total rows use the literal `ALL` for bands and for a `breakdown_key` without a breakdown, and `all` for `housing_class` and for the total of any other category dimension, never null. | Key uniqueness and not-null check on both engines. |
| DAT-76 | Situation keys are exactly `weekday_lunch`, `weekday_evening`, `friday_evening`, `ramadan_iftar`. They select hours of the hourly Simulated tables through `situation_windows`; `ramadan_iftar` uses the day type `ramadan_day` and only `summer = false`. In every Simulated table, rows with `summer = true` use only the day types `weekday`, `friday` and `saturday` (ASSUMPTION: the three event day types are released with `summer = false` only). | Enumeration check on the rule value and on the simulated tables; a `summer = true` row with an event day type fails. |

**Situation windows (ASSUMPTION, stored in `rules_version` so they change without code).** The
four dial situations select hours of the hourly Simulated tables. The shared rule
`situation_windows` has unit `canonical_json` and this exact value:
`{"friday_evening":{"day_type":"friday","hours":[19,20,21],"summer_values":[false,true]},"ramadan_iftar":{"day_type":"ramadan_day","hours":[17,18,19],"summer_values":[false]},"weekday_evening":{"day_type":"weekday","hours":[19,20,21],"summer_values":[false,true]},"weekday_lunch":{"day_type":"weekday","hours":[12,13],"summer_values":[false,true]}}`.
Hours are inclusive. The rule value names each situation's day type, hours and allowed `summer`
values without another configuration. The hour windows are those of the earlier pack; the value no
longer maps a season, because Ramadan is now the day type `ramadan_day` and the summer switch is a
column of the Simulated tables. `weekday` means Sunday to Thursday, the working week the simulator
assumes ([05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md)).

**Periods.** Protected tables carry one month, `YYYY-MM`, as `period`: a month of the one protected
window that a version 1 release exports. The window's span, `YYYY-MM/YYYY-MM` from its first to its
last month, is the protected `period`: the manifest records it as `window_period`, and it is the
`period` of `window_key` ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)
item 10, DAT-136).
`month_change` names two adjacent months, `YYYY-MM/YYYY-MM`. Each monthly row holds the primitives
of its own month, which stay additive across units of their own additive family; a figure over
several months is computed by `eii_core.calc` from the monthly rows of one family (ASSUMPTION). A
version 1 release holds no second protected window. Simulated tables carry no period column: they
describe typical days of the `mobility.v1` observation window, and a Simulated fact's `period` is
that window, `YYYY-MM-DD/YYYY-MM-DD`. Public tables keep the source period: `YYYY`, `YYYY-MM`,
`YYYY-Qn`, `YYYY-YYYY` for a school year, `YYYY/YYYY` for a change between two years, or, in
`fdi_projects`, the announcement date at the precision the page gives.

### 7.2 Table catalogue

Writers are modules of `custodian/`; readers are modules of `product/` (`store` loads every table).

| Table | Class | Grain | Key | Written by | Read by (tools) |
|---|---|---|---|---|---|
| `grid_cell` | Frame | base cell | `cell` | `publicdata` | `make_area`, `area_evidence`, `compare_areas` |
| `release_unit` | Frame | unit | `unit_id` | `privacy` | `make_area`, `area_evidence`, `compare_areas` |
| `unit_member` | Frame | unit × cell | `unit_id`, `cell` | `privacy` | `make_area` |
| `zone` | Frame (Public geometry) | zone | `zone_code` | `publicdata` | `area_evidence`, `sector_facts`, `stage` |
| `district` | Frame (Public geometry) | district | `district_key` | `publicdata` | `resolve`, `area_evidence`, `stage` |
| `municipality` | Frame (Public geometry) | municipality | `municipality_code` | `publicdata` | `area_evidence`, `sector_facts` |
| `gazetteer` | Frame (Public) | named place | `place_key` | `publicdata` | `resolve` |
| `road_link` | Frame (Public geometry) | road link | `link_id` | `publicdata` | `make_area`; traffic layer |
| `resident_pay` | Protected | unit × period × measure × housing class × band range | `unit_id`, `period`, `measure`, `housing_class`, `band_from`, `band_to` | `privacy` | `area_evidence`, `compare_areas` |
| `worker_pay` | Protected | unit × period × measure × band range | `unit_id`, `period`, `measure`, `band_from` | `privacy` | `area_evidence`, `compare_areas` |
| `home_area_share` | Protected | work unit × home unit × period | `work_unit_id`, `home_unit_id`, `period` | `privacy` | `area_evidence` |
| `outlet_register` | Protected | unit × period × activity class × size band | `unit_id`, `period`, `activity_node_id`, `size_band` | `privacy` | `area_evidence` |
| `occupation_pay` | Protected | unit × period × measure × basis × group × band range | `unit_id`, `period`, `measure`, `basis`, `occupation_group`, `band_from` | `privacy` | `pay_benchmark` |
| `register_company_list` | Protected | register company × last month | `registration_number`, `period` | `privacy` | company card; prospect, partner and supplier lists (D3, D4, S3) |
| `month_change` | Protected | unit × adjacent months × table × measure | `unit_id`, `period`, `table_name`, `measure` | `privacy` | D5, D6 |
| `presence_count` | Simulated | unit × day type × hour × summer × segment | `unit_id`, `day_type`, `hour`, `summer`, `segment` | `privacy` (from the `mobility` feed) | `area_evidence`, `compare_areas`; presence and crowd-density layers; D1, D2, D3, D6 |
| `flow_hourly` | Simulated | origin unit × destination unit × day type × hour × summer | `origin_unit_id`, `destination_unit_id`, `day_type`, `hour`, `summer` | `privacy` (from the `mobility` feed) | flow layer; input of `traffic_hourly` |
| `traffic_hourly` | Simulated | road link × day type × hour × summer | `link_id`, `day_type`, `hour`, `summer` | `mobility` (from released `flow_hourly`) | `make_area` (drive by hour); traffic layer; D2, D7 |
| `access_score` | Simulated | unit × supply layer × mode × cut-off × day type × hour × summer × traffic | `unit_id`, `activity_key`, `mode`, `cutoff`, `day_type`, `hour`, `summer`, `traffic` | `mobility` (after the privacy engine, from released `presence_count` and the `travel_time_matrix` artefact, DAT-151) | `reachable_access`; D2 |
| `pub_licence_active` | Public | municipality × activity code × snapshot | `municipality_code`, `activity_code`, `period` | `publicdata` | `sector_facts`, `area_evidence` |
| `pub_licence_cancelled` | Public | municipality × activity code × month | `municipality_code`, `activity_code`, `period` | `publicdata` | `sector_facts` |
| `pub_licence_issued` | Public | municipality × activity code × period | `municipality_code`, `activity_code`, `period` | `publicdata` | D6, openings over time (PUB-94) |
| `pub_zone_utility` | Public | zone × year × utility | `zone_code`, `period`, `utility` | `publicdata` | `sector_facts`, `area_evidence` |
| `pub_transit_monthly` | Public | month × mode | `period`, `mode` | `publicdata` | `area_evidence`, `sector_facts` |
| `pub_sector_accounts` | Public | activity × year × indicator | `activity_code`, `period`, `indicator` | `publicdata` | `sector_facts` |
| `pub_wage_table` | Public (split) | table × period × breakdown | `table_code`, `period`, `breakdown_key`, `indicator` | `publicdata` | `pay_benchmark`, `sector_facts` |
| `pub_customs_import` | Public | tariff line × origin × month | `tariff_code`, `origin_iso3`, `period` | `publicdata` | `supplier_lens` |
| `pub_property_sale` | Public | district × year × property type | `district_key`, `period`, `property_type` | `publicdata` | `area_evidence` |
| `pub_census_zone` | Public | zone × census year × indicator | `zone_code`, `period`, `indicator` | `publicdata` | `area_evidence` |
| `pub_population_municipality` | Public | municipality × period × indicator | `municipality_code`, `period`, `indicator` | `publicdata` | `sector_facts`, `area_evidence` |
| `pub_census_national` | Public | period × indicator | `period`, `indicator` | `publicdata` | `sector_facts`, `area_evidence` |
| `pub_census_district` | Public | district × period × indicator | `district_key`, `period`, `indicator` | `publicdata` | `area_evidence` |
| `pub_place` | Public | place | `place_id` | `publicdata` | `scan_places`, `resolve` |
| `pub_place_verification` | Public | place × check date | `place_id`, `check_date` | `publicdata` | `scan_places`, `resolve` |
| `pub_register_company` | Public | register company | `registration_number` | `publicdata` (from the register file read through `EII_REGISTER_FILE` and the financial centre's file read through `EII_FC_REGISTER_FILE`; no fetcher for the register's site is in the repository, decision 0022 item 1) | company card; the map's establishment points; firm counts and density; prospect, partner and supplier lists (D3, D4, S3); name-collision test (DAT-14) |
| `pub_hotel_monthly` | Public | month × star class × indicator | `period`, `star_class`, `indicator` | `publicdata` | `sector_facts` |
| `pub_price_index` | Public | month × group | `period`, `group_code` | `publicdata` | `sector_facts` |
| `pub_property_resi` | Public | district × month × unit type | `district_key`, `period`, `unit_type` | `publicdata` | D2, D6, reverse location view |
| `pub_venue_visits` | Public | venue × period × indicator | `venue_key`, `period`, `indicator` | `publicdata` | named public places (`place_public`) |
| `pub_building_permits` | Public | municipality × period × document × permit type × building type | `municipality_code`, `period`, `document_type`, `permit_type`, `building_type` | `publicdata` | D6, reverse location view |
| `pub_establishment_size` | Public | bulletin × activity × size class × year × indicator | `table_code`, `activity_key`, `size_class`, `period`, `indicator` | `publicdata` | D1, D3, S1, cases C1 and C2 |
| `pub_manufacturing` | Public | table × year × breakdown × indicator | `table_code`, `period`, `breakdown_key`, `indicator` | `publicdata` | D4, D7, S3, case C1 |
| `pub_trade_wr` | Public | trade type × year × indicator | `trade_type`, `period`, `indicator` | `publicdata` | D1, S1 |
| `pub_population_age` | Public | municipality × year × age group × indicator | `municipality_code`, `period`, `age_group`, `indicator` | `publicdata` | D3 |
| `pub_hotels_municipality` | Public | municipality × year × facility type | `municipality_code`, `period`, `facility_type` | `publicdata` | D1 |
| `pub_trade_logistics` | Public | table × year × breakdown × indicator | `table_code`, `period`, `breakdown_key`, `indicator` | `publicdata` | D7 |
| `pub_census_2015_municipality` | Public | municipality × indicator | `municipality_code`, `period`, `indicator` | `publicdata` | fidelity report by municipality (firm counts and density come from the register, decision 0022) |
| `pub_labour_sex_municipality` | Public (split) | municipality × year × sex × indicator | `municipality_code`, `period`, `sex`, `indicator` | `publicdata` | D5 |
| `pub_population_age_sex` | Public (split) | municipality × year × age group × sex × indicator | `municipality_code`, `period`, `age_group`, `sex`, `indicator` | `publicdata` | D3 |
| `pub_active_sex_age` | Public (split) | year × sex × age group × activity × indicator | `period`, `sex`, `age_group`, `activity_key`, `indicator` | `publicdata` | D5 |
| `pub_active_nationality_occupation` | Public (split) | year × nationality group × sex × occupation × activity × indicator | `period`, `nationality_group`, `sex`, `occupation_key`, `activity_key`, `indicator` | `publicdata` | D5 |
| `pub_compensation_nationality` | Public (split) | bulletin × year × activity × nationality group × indicator | `table_code`, `period`, `activity_key`, `nationality_group`, `indicator` | `publicdata` | D5, D1 |
| `pub_students` | Public (split) | municipality × school year × level × type × sex × nationality group × indicator | `municipality_code`, `period`, `education_level`, `education_type`, `sex`, `nationality_group`, `indicator` | `publicdata` | D3, D5 |
| `pub_visitor_markets` | Public (split) | table × period × nationality group × breakdown × indicator | `table_code`, `period`, `nationality_group`, `breakdown_key`, `indicator` | `publicdata` | D1, D3 |
| `fdi_projects` | Public | announced project | `project_key` | `publicdata` | map layer; D1, D4, D6, D7, S1, S2 |
| `pub_investqa_record` | Public | agency page record | `record_type`, `record_key` | `publicdata` | sector context, the market entry pack (D1, S1), set-up steps, break-even calculator (optional inputs) |
| `zone_type` | Public | zone | `zone_code` | `publicdata` (the build-time area types of C17, DAT-152) | `similar_areas`; D2 |
| `access_score_grid` | Public | population-grid cell × supply layer × mode × cut-off × traffic | `grid_key`, `activity_key`, `mode`, `cutoff`, `traffic` | `publicdata` (the build-time scores of the population-grid layer of C12 at free flow, from Public inputs only, DAT-154) | `reachable_access`; D2 |
| `pub_venue_busyness` | Public | named venue × day of week × hour | `place_id`, `day_of_week`, `hour` | `publicdata` (from the source `busy_gmaps`, inside `./eii build-public` only, DAT-157) | named public places (`place_public`); card C37; the pooled hourly anchor of the simulation |
| `pub_night_lights` | Public | frame cell × month | `cell`, `period` | `publicdata` (from the source `ntl_blackmarble`, aggregated to the frame) | night-time radiance map layer; card C36 |
| `pub_place_fsq` | Public | place | `fsq_place_id` | `publicdata` (from the source `places_fsq`, fetched from the public copy on Source Cooperative and read without an account, DAT-157) | `scan_places`, `resolve`; competitors and typical neighbours |
| `pub_pop_agesex_grid` | Public (split) | grid cell × age band × sex × year | `grid_key`, `age_band`, `sex`, `period` | `publicdata` (from the source `worldpop_qat_agesex`) | card C38 |
| `graph_node` | Graph | node | `node_id` | `publicdata`, `release` (lineage nodes) | `resolve`, `supplier_lens`, `scan_places`, `sector_facts` |
| `graph_edge` | Graph | edge | `edge_id` | `publicdata`, `release` (lineage edges) | same as `graph_node` |
| `fact_lineage` | Lineage | lineage id × source | `lineage_id`, `source_id` | `release` | evidence drawer API (all tools set `lineage_ref`) |
| `source_registry` | Lineage | source | `source_id` | `publicdata`, `release` | evidence drawer API, Trust centre |
| `rules_version` | Control | rule × parameter set | `rules_version_id`, `parameter_set`, `rule_code` | `privacy` | all tools, Trust centre |
| `suppression_reason` | Control | reason code | `code` | `privacy` | all tools ("Why can't I see this?") |
| `survival_report` | Control | parameter set × partition | `parameter_set`, `partition_id` | `privacy` | Proof room |

[Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) replaces `presence_index`,
`flow_od` and `speed_factor` with `presence_count`, `flow_hourly` and `traffic_hourly`. No release
holds the old three, and the loader refuses them (DAT-83). For the rows added by decisions 0016,
0017 and 0019, the last column names the journeys (D1 to D7), services (S1 to S3), cases, method
cards and map layers that read the table; [08_BACKEND.md](08_BACKEND.md) names the tools. Beside
the readers named in the column, the method cards of decision 0019 read existing tables: card C30
reads the Public series tables that hold a series of its closed list (`pub_licence_issued`,
`pub_licence_cancelled`, `pub_property_sale`, `pub_property_resi`, `pub_hotel_monthly`,
`pub_price_index`, `pub_customs_import`, `fdi_projects` and `pub_building_permits`, each only where
it holds the series); card C31 reads `pub_licence_active`, `pub_licence_issued` and
`pub_licence_cancelled`; cards C33 to C35 read `pub_establishment_size`, `pub_place`, `pub_place_fsq`
and `presence_count` (card C32 reads `presence_count` and the pay tables, DAT-160). The optional 3D
view (decision 0019 item 14, family `view_3d`) adds no table: it extrudes whole release units, with
the `release_unit` geometry and the released values of the flat view, by one protected area statistic
or by the crowd density of DAT-138, never on a cell, a building footprint or a drawn shape; it is off
by default and every extruded value is also a Fact chip in the flat view. "Public (split)" marks a Public
split table (DAT-141); its manifest class is `public`. The travel times behind `access_score` are not
a table: they are the manifest artefact `artefacts/travel_time_matrix.parquet` (section 8, DAT-153).
`access_score_grid` holds the scores of the population-grid layer of C12 at free flow, in both
release kinds; the times behind it are not stored (DAT-154).

`release_manifest` is deliberately absent from this Parquet catalogue and from `manifest.tables`.
The loader materialises it in each store from the verified `manifest.json`, as specified in section
8. It has no Parquet file and is never an input to its own release hash.

### 7.3 Columns

Types follow section 1.2; a column without a stated type is `string`. Every Public table also has
`source_id` (N), which joins `source_registry`. "Cnt" means a treated, rounded `int` primitive.

| Table | Columns |
|---|---|
| `grid_cell` | `cell` cell; `resolution` int (8 or 9); `parent_r7` cell; `in_greater_doha` bool; `zone_code` string; `district_key` string; `municipality_code` string; `geometry` geometry |
| `release_unit` | `unit_id` string; `partition_id` string; `unit_kind` string (`cell`, `merged`, `remainder`, `municipality`, `national`), where `municipality` is the terminal `ha_home` unit or a unit of the municipality level that `rp_all_money`, `rp_all_quartile`, `wp_all_money` and `wp_all_quartile` hold above their units, one per municipality in each of those four partitions ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16); `resolution` int (Y, null for `remainder`, `municipality` and `national`); `municipality_code` string (Y, null for `national`); `rule_tier` string (`count`, `money`, `quartile`); `status` string (`published`, `withheld`); `suppression_reason_code` string (Y, null when published); `geometry` geometry |
| `unit_member` | `unit_id` string; `cell` cell |
| `zone` | `zone_code` string; `name_en` string; `name_ar` string; `municipality_code` string; `geometry` geometry; `source_id` |
| `district` | `district_key` string; `name_en` string; `name_ar` string; `municipality_code` string; `geometry` geometry; `source_id` |
| `municipality` | `municipality_code` string; `name_en` string; `name_ar` string; `geometry` geometry; `source_id` |
| `gazetteer` | `place_key` string; `kind` string (`municipality`, `zone`, `district`, `landmark`, `building`, `station`, `place`, `gateway`), where `gateway` marks a port, the airport, a free zone or a land crossing that journey D7 measures travel times to; `name_en` string; `name_ar` string; `aliases` string (semicolon-separated, Y); `lon`, `lat` decimal(9,6); `cell` cell; `showcase_verified` bool; `source_id` |
| `road_link` | `link_id` string (`rl:` followed by a seven-digit sequence that the release build assigns in the order of the routing graph's edges; never an OpenStreetMap identifier); `road_class` (`motorway`, `trunk`, `primary`, `secondary`, `tertiary`, `residential`); `length_m` integer (whole metres: the length that the routing graph of the release holds for the link's edge; a length that is not whole is refused, [decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md) item 4); `geometry` geometry (line); `source_id` |
| `resident_pay` | `unit_id`; `period`; `measure` (`net`, `basic`); `housing_class` (`family_housing`, `labour_accommodation`, `institution`, `unknown`, `other`, `all`); `band_from`, `band_to` (B01..B12 or `ALL`); `earner_count` Cnt; `wage_bill` decimal(16,0) (Y: only on `ALL` rows of `money` or `quartile` tier units); `not_measured_count` Cnt (Y: only on `ALL` rows whose unit belongs to `rp_housing_count`); `irregular_count` Cnt (Y: only on those same rows); on a `municipality` unit of `rp_all_money` or `rp_all_quartile`, every primitive is the exact sum of the treated leaves of its published units, on the band boundaries all of them kept (PRV-16) |
| `worker_pay` | `unit_id`; `period`; `measure`; `band_from`, `band_to`; `earner_count` Cnt; `wage_bill` (as above); `deployed_elsewhere_count` Cnt (Y: only on `ALL` rows whose unit belongs to `wp_site_count`); `irregular_count` Cnt (Y: only on those same rows); on a `municipality` unit of `wp_all_money` or `wp_all_quartile`, as for `resident_pay` |
| `home_area_share` | `work_unit_id`; `home_unit_id` (the terminal municipality unit of `ha_home`, formed as the union of every `op_res_quartile` whole-cell unit and remainder of the governing residence family in that municipality); `period`; `earner_count` Cnt |
| `outlet_register` | `unit_id`; `period`; `activity_node_id` (an `activity_class` node); `size_band` (`no_payroll`, `s01_09`, `s10_49`, `s50_plus`; ASSUMPTION); `outlet_count` Cnt |
| `occupation_pay` | `unit_id`; `period`; `measure`; `basis` (`residence`, `workplace`); `occupation_group` (ISCO-08 major group `0`..`9`, `unmapped`, `other`); `band_from`, `band_to`; `earner_count` Cnt; `wage_bill` (as above) |
| `register_company_list` | `registration_number` string (the register company's registration number, the key of `pub_register_company`; never a `SYN-` value, and held only in the release and the serving stores, DAT-140); `period` (the last month of the window only); `employee_count` int (Y: null when withheld; the company's number of employees in that month from its attached records, DAT-140); `suppression_reason_code` (Y: `CARRIED_FORWARD` when PRV-125 withholds the count, null when the count is published) |
| `pub_register_company` | `registration_number` string (the register's own key, as in `register_company_list`; never in the repository, a brief, a fixture, a log, a ledger row, an egress record or a model payload, [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) item 8); the fields of the register's public card as the register publishes them, person names excluded (decision 0022 item 1); `registered_cell` cell (Y: the base cell of the registered location; null when it does not resolve); `establishment_nationality` (Y: the register's establishment nationality, a company attribute, decision 0022 item 6); `source_id` (the public business register or the financial centre's public register). The full column list is set with the register's registry row in [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) |
| `month_change` | `unit_id` (for `home_area_share`, the work unit); `period` (two adjacent months, `YYYY-MM/YYYY-MM`); `table_name` (`resident_pay`, `worker_pay`, `occupation_pay`, `home_area_share`, `outlet_register`); `measure` (`net`, `basic`; `none` for `home_area_share` and `outlet_register`); `status` (`published`, `carried_forward`: the month mark of PRV-123); `stayers`, `joiners`, `leavers` Cnt (Y: only on published `resident_pay` and `worker_pay` rows, never for an empty cohort, which carries its row forward, DAT-137; on a `municipality` or `national` unit, the exact sums of the treated cohort leaves of its published units that cover the frame, which are `cell`, `merged` and `remainder` units and never a municipality unit, [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16); `stayer_wage_index` decimal(7,1) (Y: the fixed-composition index of PRV-55, 100 times the stayers' wage bill in the later month over their wage bill in the earlier month, computed in the release build by `eii_core.calc` from the two treated stayer wage bills and rounded half-up to half a point; only on published rows of `money` or `quartile` tier units of those two tables at municipality level or coarser (`unit_kind` `municipality`, the municipality level of `rp_all_money`, `rp_all_quartile`, `wp_all_money` and `wp_all_quartile`, so available per municipality; or `national`) whose stayers exceed `min_earners_trend` and pass every atom test, and whose non-empty joiner and leaver cohorts each have at least `min_earners_money` earners; never by sector, because wage trends by sector come from the Public series `wage_act` of `pub_wage_table` (DAT-137); otherwise null, on every `cell`, `merged` and `remainder` unit included, and a tool returns a null index on a published row as `SUPPRESSED` with `DETAIL_NEEDS_LARGER_GROUP`; the two stayer wage bills are never released); `openings`, `closures` Cnt (Y: only on published `outlet_register` rows, never for an empty cohort, which carries its row forward, DAT-137); every component is null when `carried_forward` |
| `presence_count` | `unit_id`; `day_type` (`weekday`, `friday`, `saturday`, `national_day`, `ramadan_day`, `match_day`); `hour` int (0 to 23, local time); `summer` bool; `segment` (`resident`, `worker`, `visitor`); `status` (`published`, `withheld`); `estimate`, `low`, `high` Cnt (Y: null when `withheld`), estimated people present in the hour, never a count of devices; `suppression_reason_code` (Y: `BELOW_PANEL_MINIMUM` when `withheld`, null otherwise) |
| `flow_hourly` | `origin_unit_id`; `destination_unit_id`; `day_type`; `hour`; `summer`; `estimate` Cnt, estimated vehicle trips in the hour (PRV-59, MTH-88); published leaves only (DAT-139) |
| `traffic_hourly` | `link_id`; `day_type`; `hour`; `summer`; `speed_ratio` decimal(5,3) (the link's whole speed at that hour over the free-flow speed of its road class, rounded half-up to three decimals, above 0 and at most 1.000, MTH-89; the product reads the whole speed back as round_half_up(speed_ratio × free-flow speed), [decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md)); `volume_band` (an ordered key `vb1`, `vb2` and so on, from the closed list that [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) fixes with the volume-delay rule) |
| `access_score` | `unit_id` (a published `px_base` unit: the demand location); `activity_key` (the supply layer of C12: an activity spine key whose Public places of the mapped category are the supply points, or the key of a reviewed list of gazetteer points); `mode` (`walk`, `drive`); `cutoff` int (minutes: one of the cut-offs that C12 fixes for the mode at slice S2); `day_type`, `hour` int, `summer` bool (the `presence_count` key of the residents present who form the demand, DAT-76); `traffic` (`free_flow`; or `hourly`, for `drive` only, timed by `traffic_hourly` at the same `day_type`, `hour` and `summer`); `provenance` (`simulated`: the least-real class of the row's inputs, DAT-91); `status` (`published`, `withheld`); `score` decimal(12,4) (Y: null when `withheld`; supply points per 10,000 people present within reach, C12 step 2); `suppression_reason_code` (Y: `BELOW_PANEL_MINIMUM` when `withheld`, null otherwise) |
| `pub_licence_active` | `municipality_code`; `activity_code` string; `activity_name_ar` string; `period` (snapshot month); `active_count` int |
| `pub_licence_cancelled` | `municipality_code`; `activity_code`; `period` (`YYYY-MM`, or `UNDATED` where the source has no date); `cancelled_count` int; `bulk_month` bool (flagged administrative bulk month) |
| `pub_licence_issued` | `municipality_code`; `activity_code`; `period` (the source's own period); `issued_count` int; only the codes the issued series covers, each fact with the note that the series is incomplete (PUB-69, PUB-94) |
| `pub_zone_utility` | `zone_code`; `period` (`YYYY`); `utility` (`electricity`, `water`); `value` decimal(18,2); `unit` (`kWh`, `m3`); `partial_year` bool |
| `pub_transit_monthly` | `period`; `mode` (`bus`, `metro`, `tram`); `riders` int; `anomaly_flag` bool |
| `pub_sector_accounts` | `activity_code` (ISIC Rev.4); `period`; `indicator` string; `value` decimal(18,2); `unit` string |
| `pub_wage_table` | `table_code` (names the public table, so conflicting tables are never mixed; master OI-03); `period`; `breakdown_key` string (canonical `dimension=value` pairs or `ALL`); `indicator`; `value` decimal(18,2); `unit` |
| `pub_customs_import` | `tariff_code` string (as published, 12 digits for 2025 onwards); `description_en`, `description_ar` string; `origin_iso3` string; `period`; `value_qar` decimal(18,2); `weight_kg` decimal(18,2) (Y); `quantity` decimal(18,2) (Y); `quantity_unit` string (Y) |
| `pub_property_sale` | `district_key`; `municipality_code`; `period` (`YYYY`); `property_type` (from the Arabic source field); `deal_count` int; `median_price_per_m2` decimal(12,2) (Y, null when `deal_count` is 0) |
| `pub_census_zone` | `zone_code`; `period` (`2020`); `indicator`; `value` decimal(18,4); `unit` |
| `pub_population_municipality` | `municipality_code`; `period`; `indicator`; `value` decimal(18,4); `unit`; `source_id` |
| `pub_census_national` | `period`; `indicator`; `value` decimal(18,4); `unit`; `source_id` |
| `pub_census_district` | `district_key`; `period`; `indicator`; `value` decimal(18,4); `unit`; `source_id` |
| `pub_place` | `place_id` string (source identifier); `name` string; `name_ar` string (Y); `category` string (public place category); `lon`, `lat` decimal(9,6); `cell` cell; `source_release` string; `source_provider` string; `licence` string; `confidence` decimal(5,4); `merged_ids` string (Y, semicolon-separated reviewed source identifiers) |
| `pub_place_verification` | `place_id` string; `check_date` date; `reviewer_role` string; `verification_link` string; `status` (`verified_open`, `closed_or_moved`, `not_found`, `duplicate`); `source_id` |
| `pub_hotel_monthly` | `period`; `star_class` string; `indicator` (`occupancy`, `adr`, `revpar`, `supply`, `demand`); `value` decimal(14,2); `unit` |
| `pub_price_index` | `period`; `group_code` string; `index_value` decimal(10,2); `base_period` string |
| `pub_property_resi` | `district_key`; `municipality_code`; `period` (`YYYY-MM`: the weekly bulletins aggregated by month); `unit_type` (published key); `deal_count` int; `median_price` decimal(14,2) (Y, null when `deal_count` is 0); `price_basis` (`per_m2` when `median_price` is per square metre of floor area, where the bulletin rows carry one; `per_unit` when it is per unit sold; one basis for all the sales of a row, and the fact unit is `qar_per_m2` or `qar` accordingly, as C14 names it); transaction and parcel identifiers are dropped before the release (PUB-14) |
| `pub_venue_visits` | `venue_key` (the key of the committed, reviewed venue crosswalk, PUB-89); `venue_kind` (`museum_or_exhibition`, `health_centre`); `name_en` string; `name_ar` string (Y: null when no licensed Arabic name exists); `region` string (Y: the health region as published; null for museums and exhibitions); `place_id` (Y: the `pub_place` record that the crosswalk links; null otherwise, and the venue then has no map point); `period` (`YYYY-MM` for museums and exhibitions, `YYYY` for health centres); `indicator` (`visitors`, `patient_visits`); `value` int; `unit` (`visits`) |
| `pub_building_permits` | `municipality_code`; `period` (`YYYY` or `YYYY-MM`, as published); `document_type` (`building_permit`, `completion_certificate`); `permit_type` (published key, or `all`); `building_type` (published key, or `all`); `document_count` int |
| `pub_establishment_size` | `table_code` (names the survey bulletin, so the size classes of different bulletins are never mixed: one code for each bulletin of `est_size_act`, and one for the hotels and restaurants size table `sec_hr_size`, whose rows give restaurants (ISIC 561) and the other hotel and restaurant activities by size class, as C24 needs); `activity_key` (published activity, with its ISIC Rev.4 code where the bulletin gives one); `size_class` (as that bulletin publishes it); `period` (`YYYY`); `indicator` (`establishments`, `employees`, `compensation`, `revenue`, `costs`; ASSUMPTION: `revenue` and `costs` are the per-establishment revenue and cost columns of `sec_hr_size` that cards C33 and C35 take as their benchmark, confirmed at slice S2, PUB-07); `value` decimal(18,2); `unit` |
| `pub_manufacturing` | `table_code` (one per source dataset, because field names differ between industries); `period` (`YYYY`); `breakdown_key` (canonical `dimension=value` pairs, for example licence type or product, or `ALL`); `indicator` (lower snake case, through a committed field map); `value` decimal(18,4); `unit` (as published; investment in `qar_million` is cumulative licensed investment, and licence-type rows are not plants) |
| `pub_trade_wr` | `trade_type` (published key); `period` (`YYYY`); `indicator` (purchases, sales or stocks, lower snake case through a committed field map); `value` decimal(18,2); `unit`; context only, never a forecast |
| `pub_population_age` | `municipality_code`; `period` (`YYYY`); `age_group` (published key); `indicator` (`residents`); `value` decimal(18,4); `unit` (`persons`) |
| `pub_hotels_municipality` | `municipality_code`; `period` (`YYYY`); `facility_type` (published key, for example hotels and hotel apartments); `facility_count` int (facilities, not rooms or guests) |
| `pub_trade_logistics` | `table_code`; `period` (`YYYY`); `breakdown_key` (canonical `dimension=value` pairs: certificate type and importing country, or vessel type and country of previous port or of registration, each country as an ISO 3166-1 alpha-3 code through a committed crosswalk; or `ALL`); `indicator` (for example `certificates`, `gross_tonnage`, `net_tonnage`); `value` decimal(18,2); `unit` |
| `pub_census_2015_municipality` | `municipality_code`; `period` (`2015`); `indicator` (`establishments`, `employees`); `value` decimal(18,4); `unit` (`establishments`, `persons`); every use states the year |
| `pub_labour_sex_municipality` | `municipality_code`; `period` (`YYYY`); `sex` (`female`, `male`); `indicator` (`population`, `labour_force`, `employed`, `unemployed`); `value` decimal(18,4); `unit` (`persons`); survey estimates |
| `pub_population_age_sex` | `municipality_code`; `period` (`YYYY`); `age_group`; `sex` (`female`, `male`); `indicator` (`residents`); `value` decimal(18,4); `unit` (`persons`) |
| `pub_active_sex_age` | `period` (`YYYY`); `sex` (`female`, `male`); `age_group`; `activity_key`; `indicator` (`economically_active`); `value` decimal(18,4); `unit` (`persons`); national |
| `pub_active_nationality_occupation` | `period` (`YYYY`); `nationality_group` (`qatari`, `non_qatari`); `sex` (`female`, `male`, `all`); `occupation_key` (published key); `activity_key`; `indicator` (`economically_active`); `value` decimal(18,4); `unit` (`persons`); national |
| `pub_compensation_nationality` | `table_code` (one per survey bulletin); `period` (`YYYY`); `activity_key`; `nationality_group` (`qatari`, `non_qatari`, or `all` where the bulletin publishes a total); `indicator` (`employees`, `compensation`); `value` decimal(18,2); `unit` (compensation is annual); national |
| `pub_students` | `municipality_code`; `period` (school year, `YYYY-YYYY`); `education_level` (published key); `education_type` (published key); `sex` (`female`, `male`); `nationality_group` (`qatari`, `non_qatari`); `indicator` (`students`); `value` int; `unit` (`persons`) |
| `pub_visitor_markets` | `table_code`; `period` (`YYYY` or `YYYY-MM`; a table that holds months as columns is unpivoted to one row per month); `nationality_group` (the published nationality or origin-region group of the visitors, or `all`); `breakdown_key` (other published dimensions, for example hotel rating or mode of entry, or `ALL`); `indicator` (for example `guests`, `arrivals`); `value` decimal(18,2); `unit` |
| `fdi_projects` | `project_key` string (`fdi_` followed by the first 16 lowercase hexadecimal characters of the SHA-256 of the canonical JSON of the project's published fields); `company` string (the investing company, as published); `source_country` string (Y: as published; null when the page leaves it empty); `source_country_iso3` string (Y: through a committed crosswalk; null when unmapped); `sector`, `sub_sector`, `business_function` (the page's function field) and `project_type` string (each Y: as published; null when the page leaves it empty); `capex_value` decimal(18,2) (Y: null when the page gives none); `capex_unit` string (Y: as the page states it; null with `capex_value`); `jobs` int (Y: null when the page gives none); `announced` string (Y: `YYYY`, `YYYY-MM` or `YYYY-MM-DD`, at the precision the page gives; null when it gives none; returned as a fact of unit `calendar_year`, `calendar_month` or `calendar_date` by that precision, DAT-155); `location_text` string (Y: as published); `municipality_code` (Y: through the municipality name map of PUB-27 when the location names a municipality); `place_key` (Y: the gazetteer entry a committed, reviewed crosswalk links; null otherwise); and every further field that slice S2 finds (DAT-142) |
| `pub_investqa_record` | `record_type` (`sector`, `opportunity`, `incentive`, `incentive_parameter`, `setup_step`, `law`); `record_key` string (lower snake case from the page's path; for an `incentive_parameter`, the package key and the parameter kind joined by a colon); `parent_key` (Y: the sector of an opportunity or the package of a parameter; null otherwise); `sequence` int (Y: the order of a set-up step on its page; null otherwise); `title_en` string; `title_ar` string (Y: null when the page has no Arabic version); `reference` string (Y: a law's number and year as the page states it; null otherwise); `link_url` string (Y: the link a law page gives; null otherwise); `activity_keys` string (Y: semicolon-separated activity spine keys of a sector or opportunity, through a committed, reviewed crosswalk; null otherwise); `parameter_key` (Y: on `incentive_parameter` rows only, one of the four parameter kinds of the break-even card of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md), or `other` for a parameter that the calculator does not use); `value` decimal(18,4) (Y: on `incentive_parameter` rows only; null when the page states no number); `unit` (Y: `ratio` for a share from 0 to 1, `qar_per_month` for a monthly amount, or as the page states it for `other`); `duration_months` int (Y: the duration the page states; null when it states none); `as_stated` string (Y: the page's own wording of a parameter, kept for the reviewer's check; screens render template text); `period` (Y: the period the page states for a figure; null when it states none, and the fact then takes the retrieval date); `page_url` string |
| `zone_type` | `zone_code` (a zone of `zone`); `area_type` int (Y: 1, 2 or 3, numbered as C17 numbers its types; null unless `type_status` is `typed`); `type_status` (`typed`; `feature_missing` for a zone that lacks a feature and that C17 lists and leaves out; `types_unstable` on every row when the two stability figures do not reach the thresholds of C17); `features_version` string (the version of the reviewed C17 feature list the types were built from); `period` (the reference period of those features, as that list states it); `mean_silhouette`, `mean_adjusted_rand` decimal(5,4) (the release's two stability figures of C17, equal on every row); `source_id` (the `source_registry` row of the reviewed feature list) |
| `access_score_grid` | `grid_key` string (`wp_` followed by the cell's row and column in the grid file `worldpop_qat_2020`, each written as five digits and joined by `_`: one of the grid's own 100 m cells, never a frame cell or a release unit); `lon`, `lat` decimal(9,6) (the cell's centre); `activity_key` (the supply layer of C12, as in `access_score`); `mode` (`walk`, `drive`); `cutoff` int (minutes: one of the cut-offs that C12 fixes for the mode at slice S2); `traffic` (`free_flow` only: an hourly time is Simulated); `provenance` (`public` on every row: every input is Public, DAT-91); `demand_weight` decimal(12,4) (`P_i` of C12: the people that the grid file gives the cell for 2020; a weight only, never shown as a population figure; the population by age and sex that is shown is the separate table `pub_pop_agesex_grid`); `status` (`published` on every row, because no row of this Public table is withheld); `score` decimal(12,4) (supply points per 10,000 people within reach, C12 step 2; 0 for a cell from which no supply point of the layer lies within the cut-off, as `access_score` stores for a unit); `suppression_reason_code` (Y: null on every row, because no row is withheld); `period` (`2020`, the year of the grid; the supply points and the routing graph keep their own retrieval dates in `source_registry`); `source_id` (the `source_registry` row of the grid, as on every Public table); `source_ids` string (semicolon-separated and sorted: the `source_registry` rows of every input of the row, that is the grid, its supply layer and the routing graph) |
| `pub_venue_busyness` | `place_id` string (the `pub_place` record of a venue on the build-time list of the source `busy_gmaps`); `day_of_week` (`sunday`, `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`); `hour` int (0 to 23, local time); `busyness_index` int (0 to 100: the relative busyness of that hour as the source publishes it, never a count of people); `retrieved_on` date (the retrieval date, which a fact from the table takes as its `period` and shows beside the label "Google Maps popular times"); `source_id` |
| `pub_night_lights` | `cell` cell (a base cell of `grid_cell`: the public-data build aggregates the monthly product to the frame from whole pixels, none split, and the table is never keyed by release unit); `period` (`YYYY-MM`); `radiance` decimal(14,4) (night-time radiance in nW per cm² per sr, fact unit `radiance_nw_cm2_sr`); `source_id` |
| `pub_place_fsq` | `fsq_place_id` string (the source's own identifier); `name` string; `name_ar` string (Y: only where the source gives one); `category` string (the source's own category, as published; the reviewed mapping to the `place_category` nodes of section 10 is a committed, reviewed configuration, not a column); `lon`, `lat` decimal(9,6); `cell` cell; `source_release` string (the release date of the copy used, such as `2025-01-10`, the newest of the three releases read on 2026-11-12); `licence` string; source-given fields only, so that no attribute is invented for a real named place |
| `pub_pop_agesex_grid` | `grid_key` string (the cell's row and column in the grid files of `worldpop_qat_agesex`, written as for `access_score_grid` with the prefix `wa_`, so that the keys of the two grids never collide: one of the grid's own 100 m cells, never a frame cell or a release unit); `lon`, `lat` decimal(9,6) (the cell's centre, which decides whether the cell lies inside an area, DAT-141); `age_band` string (the grid's own band key); `sex` (`female`, `male`); `people` decimal(18,4) (people in the cell, as the grid gives them); `period` (`YYYY`, the year of the grid); `source_id` |
| `graph_node`, `graph_edge` | section 10 |
| `fact_lineage` | `lineage_id` string (`lin_` plus the table name, with a suffix when one table has several transforms); `table_name` string; `partition_id` string (Y: required for a protected-table home family, null otherwise); `measure` string (Y: `net` or `basic` where the protected table has that dimension, null otherwise); `breakdown` string (Y: required for a protected-table home family and one of `none`, `band`, `housing_class`, `occupation_group_by_band`, `home_municipality`, `side_count_type`, `activity_class_by_size_band`, `cohort` (a `month_change` component), `company_row` (a `register_company_list` row, decision 0022); null otherwise); `family_role` (`single`, `numerator`, `denominator`; Y for a protected-table home family, null otherwise); `source_id` string; `input_class` (`public`, `synthetic`, `simulated`); `transform` string (`module.function@version`); `rules_version_id` string (Y, null for Public tables) |
| `source_registry` | `source_id` string; `kind` (`public_dataset`, `public_document`, `reviewed_config`, `synthetic_feed`, `simulation_output`); `title`; `publisher`; `url` (Y for synthetic and simulated); `licence` string; `licence_basis` string (Y: the basis of use that the registry entry records, [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 3.1, for example `owner_decision` for the investment sources and for the source `busy_gmaps`, [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 19; null for synthetic and simulated sources); `retrieved_on` date; `sha256` string; `commit_allowed` bool; `attribution` string; `public_splits` string (Y: semicolon-separated subset of `sex` and `nationality` that the registry entry declares in `public_splits`, DAT-141; null when it declares none) |
| `release_manifest` (loader-materialised store table only) | One row per entry of verified `manifest.tables`: `release_id`; `table_name`; `provenance_class` (`frame`, `protected`, `simulated`, `public`, `graph`, `lineage`, `control`); `file`; `sha256`; `row_count` int; `schema_sha256`; plus the scalar fields of section 8 repeated on every row. It has no row for itself. |
| `rules_version` | `rules_version_id`; `parameter_set` (`A`, `B`, `shared`); `rule_code`; `value` string; `unit` string; `description_en` string |
| `suppression_reason` | `code` (upper snake case, for example `BELOW_MIN_EARNERS`, `EMPLOYER_DOMINANCE`, `TOP_TWO_DOMINANCE`, `PERSON_CONCENTRATION`, `REMAINDER_FAILED`); `label_en`; `label_ar` (pending native review); `explanation_en`; `explanation_ar` |
| `survival_report` | `parameter_set`; `table_name`; `partition_id`; `units_total`, `units_published`, `units_pooled`, `units_withheld` int; `earners_published_share` decimal(5,2) (rounded to whole percent) |

The following closed lists and placement rules are part of the release schema, not application
conventions.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-127 | Protected category rows accept exactly these values: `resident_pay.housing_class` is `family_housing`, `labour_accommodation`, `institution`, `unknown`, `other` or `all`; `occupation_pay.occupation_group` is `0` to `9`, `unmapped` or `other`. `other` is a treated leaf and exists only where pooling occurred. For a primitive in a family with a breakdown, its `all` or band `ALL` row is the derived exact sum of the treated leaves of that family and is not treated again. For a primitive in a family with no breakdown, the applicable `all` or band `ALL` row is itself the one treated leaf. Side counts exist only on band `ALL` rows whose `resident_pay` unit belongs to `rp_housing_count` or whose `worker_pay` unit belongs to `wp_site_count`. | Closed-enum fixtures reject every other value; a second treatment of a derived `all` or `ALL` row fails; a no-breakdown `all` or `ALL` leaf passes and its absence fails; an `other` row without pooled source categories fails; side-count rows on any other partition or band fail. |
| DAT-128 | The audit-count indicator and unit pairs in `pub_census_zone`, `pub_population_municipality`, `pub_census_national` and `pub_census_district` are exactly `residents`/`persons`, `households`/`households`, `establishments`/`establishments` and `employees`/`persons`. Indicator names are lower snake case. Any other indicator is not a count and must have status `not_applicable` in `artefacts/attacker_view_public_totals.json` until a release-contract revision adds it to this list. The rows of the Public tables that [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) and [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) add (`pub_pop_agesex_grid` holds people counts) are reviewed for applicability as [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) section 10.4 requires: one found inapplicable is `not_applicable` with its closed reason (PRV-115), and one found applicable fails the privacy build until a release-contract revision lists its count indicator so that it can be enabled (OI-24). Every applicable count row must be representable and enabled under PRV-115; an applicable municipality, district, zone or national row that is absent, unconfigured or cannot be mapped safely fails the privacy build. `pub_census_zone` and `pub_census_district` carry the rows of the census map layers that decision 0017 admits to the local release (item 10; OI-04 closed for version 1); nothing fetched from them is committed (DAT-85). | One fixture for each allowed pair passes; a wrong unit, mixed-case indicator, enabled unlisted indicator, absent applicable row, unconfigured applicable row or unsafe mapping fails; a fixture with census-layer rows proves both tables load in both stores with every applicable count row enabled; a row of an added Public table marked `enabled` before a revision lists its indicator fails, and so does one that the review finds applicable. |
| DAT-129 | `rules_version.parameter_set` is exactly `A`, `B` or `shared`. The A and B rule-code allowlist is `min_earners_count`, `min_groups_count`, `min_earners_money`, `min_earners_quartile`, `max_group_share`, `max_top2_share`, `max_person_share`, `min_band_cell`, `round_count`, `round_money`, `min_earners_trend`, `min_panel_devices`, `round_movement`, `audit_headcount_width`, `audit_wage_relative_width` and `money_delta`. `round_movement`, the rounding base of every released presence and flow value, is fixed at the slice S1 gate, with B's base no smaller than A's (PRV-59). The shared rule-code allowlist is `export_parameter_set`, `window_months`, `min_full_month_days`, `situation_windows`, `feasibility_tolerance`, `integrality_tolerance`, `optimality_tolerance` and `outward_bound`. `min_full_month_days` has value `20` and unit `days`; `window_months` has unit `months` and the value fixed at the slice S1 gate (decision 0016 assumes the 24 months of SYN-12); `situation_windows` has the exact unit and value defined in section 7.1. `presence_scale` and `flow_scale` left the list with the presence index (DAT-63). Every listed code occurs exactly once for each applicable parameter set; no other code is accepted. | Exact-set comparison by parameter set; complete shared-rule fixture passes; missing, duplicate, misplaced, unknown, altered-window and wrong-unit fixtures fail. |
| DAT-130 | `suppression_reason.code` is exactly one of `SNAPPED_TO_WHOLE_UNITS`, `PART_OF_AREA_POOLED`, `BANDS_MERGED`, `DEPLOYED_ELSEWHERE_NOT_MAPPED`, `CARRIED_FORWARD`, `POOLED_IN_REMAINDER`, `REMAINDER_FAILED`, `FAILED_THIS_PERIOD`, `DETAIL_NEEDS_LARGER_GROUP`, `SPLIT_NOT_PUBLISHABLE`, `BANDS_NOT_SHARED`, `BELOW_PANEL_MINIMUM`, `NOT_MEASURED`, `OUTSIDE_FRAME`, `NO_FIRM_OR_PERSON_FACTS`, `DIMENSION_NOT_OFFERED`, `AREA_TYPE_NOT_OFFERED`, `NO_TIME_SERIES`, `EGRESS_BLOCKED`, `BELOW_MIN_EARNERS`, `BELOW_MIN_EMPLOYER_GROUPS`, `EMPLOYER_DOMINANCE`, `TOP_TWO_DOMINANCE`, `PERSON_CONCENTRATION` or `BAND_TOO_SMALL`. The release contains one row for each code and no other row. | Exact-set comparison; unknown, missing and duplicate code fixtures fail. Scene fixtures prove `NO_FIRM_OR_PERSON_FACTS`, `AREA_TYPE_NOT_OFFERED` and `BELOW_PANEL_MINIMUM` are representable; a `month_change` fixture proves `CARRIED_FORWARD` is (PRV-123). |

The tables added by decisions 0016, 0017 and 0019 follow these rules.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-136 | Every Protected-table row carries one month of the window, `YYYY-MM`, as its `period`, except `month_change`, whose `period` names two adjacent months of the window. The window is `window_months` consecutive months that the `wages.v1` coverage declaration marks complete (DAT-45). Its span is the manifest's `window_period` and the protected `period` of `window_key` (section 8); the monthly periods of the rows are not `window_key` inputs. Partitions are frozen for the whole window and one treatment holds for every month ([decision 0007](decisions/0007-disclosure-control-by-pooling-and-stable-treatment.md)); each month passes every control that a single period passes (PRV-24). A Simulated fact takes the `mobility.v1` observation window as its `period`. No second protected window is built. | Period-format checks per table; a protected row outside the span fails; a `window_period` that differs from the first and last monthly `period` of the protected tables fails; the `window_key` of a monthly release equals the section 8 computation from `window_period` and the four feeds; a second window fails; the differencing attacks across months of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) recover nothing with the controls on. |
| DAT-137 | `month_change` holds one row for each published unit of each protected table (for `home_area_share`, each work unit), each pair of adjacent months and each measure. Cohort counts exist only on the rows of `resident_pay` and `worker_pay` (stayers, joiners and leavers) and of `outlet_register` (openings and closures); the rows of `occupation_pay` and `home_area_share` are status-only month marks that hold no component and form no additive family, while their changed cohorts are tested under PRV-56 all the same ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) section 6.1). Its `status` is `published` only when every changed cohort of that unit, table and pair (joiners, leavers and movers at origin and destination, stayers, openings and closures) passes the cohort tests of PRV-56 and the row is not carried forward with another unit under the rule below; its components are then treated, rounded leaves, so a change is released only where it passes. Otherwise `status` is `carried_forward`; so is, for the same pair of months, the row of every unit of every later partition of the same contributor universe that contains a carried-forward unit, and of the municipality unit and the national unit of the pay partition of the carried-forward unit ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16, PRV-55), with all its dependent totals (for a municipality unit of PRV-16 or a national unit, the exact sums of the atoms shown for its units, PRV-55), as PRV-56 requires (for a carried-forward `ha_home` unit, the `home_area_share` row of every work unit with a leaf in it). On a carried-forward row every component is null, and the later month's treated atoms of that unit and tier repeat the earlier month's (PRV-56); the row is the month mark of PRV-123, shown with `CARRIED_FORWARD`. A carried-forward change is never shown as zero or as no change. An empty cohort of a component (stayers, joiners or leavers; openings or closures) is a count of zero, which is below every count threshold: it fails exactly like a non-empty cohort below its threshold, and the row and its containing units are carried forward as above. A published row therefore never holds an empty cohort: an empty cohort is never shown as zero, and never as a withheld component on a published row. A changed cohort that no component releases on its own (movers, contributors whose employer group, band or category changed, and every changed cohort behind a status-only row of `occupation_pay` or `home_area_share`) is tested when it is not empty, as PRV-113 item 11 does ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) section 6.1, ASSUMPTION 35). The fixed-composition wage trend of PRV-55 is released as `stayer_wage_index`, only on a `money` or `quartile` tier unit at municipality level or coarser (`unit_kind` `municipality` or `national`): a municipality unit of `rp_all_money`, `rp_all_quartile`, `wp_all_money` or `wp_all_quartile`, so the index is available per municipality, or a national unit of one of those partitions ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-16). Such a unit holds no cohort leaf: its `stayers`, `joiners` and `leavers` are the exact sums of its published units' treated cohort leaves, and its row is `carried_forward` whenever the row of any of those units is for that pair of months, its pay figures then staying the exact sums of the atoms that the release shows for its units (PRV-55). On every finer unit (`cell`, `merged` or `remainder`) the index is null. No index exists by sector: wage trends by sector come from the public portal's wage series by economic activity, `wage_act` in `pub_wage_table` ([04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 2.1), never from a protected split, and national by sector is the finest sector view in version 1. No stayer wage bill is released. | Cohort fixtures: a component on an `occupation_pay` or `home_area_share` row fails; a failing joiner cohort gives `carried_forward`, null components and identical treated atoms in both months; an empty joiner, leaver, stayer, opening or closure cohort gives `carried_forward` for its row and the containing units, exactly as a failing one does; a published row that holds an empty cohort, as a zero or as a null component, fails; an empty mover cohort alone gives no `carried_forward` row; a failing cohort in a count-tier unit gives `carried_forward` rows for every containing unit of the later partitions of its universe; a passing fixture gives published components; a `stayer_wage_index` on a `cell`, `merged` or `remainder` unit, on a `count` tier unit or a carried-forward row, where the stayers do not exceed `min_earners_trend`, or where a non-empty joiner or leaver cohort has fewer than `min_earners_money` earners fails, and so does a stayer wage bill column; a published `stayer_wage_index` on a municipality unit of `rp_all_money` whose conditions hold passes; a municipality unit's row published while the row of a unit inside it is carried forward fails, and so does a municipality unit's cohort count that differs from the sum of its published units' cohort leaves; a zero or "no change" rendered for a carried-forward pair fails. |
| DAT-138 | `presence_count` holds one row for every published unit of its partition and every allowed combination of `day_type`, `hour`, `summer` and `segment` (DAT-76). A `published` row has `estimate`, `low` and `high` with `low` ≤ `estimate` ≤ `high`, treated under document 06: panel minimum, complementary suppression and rounding ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 7). A `withheld` row has all three null and the reason `BELOW_PANEL_MINIMUM`, whether its feed rows were missing, below the panel minimum or withheld by complementary suppression; the release does not say which. The three segments of one (`unit_id`, `day_type`, `hour`, `summer`) group are published or withheld together. A presence fact is a Simulated count of estimated people; its range is shown by two further facts from the same row, `low` and `high`. Its label reads as estimated people around the location and never names a building, business or place. The table has no pay-band dimension; people present by pay band are the computed figure of DAT-160. Crowd density (unit `people_per_km2`) is computed by `eii_core.calc` from released estimates and unit or shape areas. | Dense-key check; a published row with `low` above `estimate` or `estimate` above `high` fails; a group with mixed segment status fails; a withheld row with a value fails; a label fixture that names a gazetteer place fails. |
| DAT-139 | `flow_hourly` holds published leaves only: an estimate of vehicle trips in one hour from an origin unit to a destination unit, under the panel minimum, complementary suppression by complete origin group and rounding of document 06 (PRV-58, PRV-59). An absent pair has no published flow and is never shown as zero. `traffic_hourly` is computed in the custodian plane by one tested function that assigns released `flow_hourly` estimates to `road_link` under the one volume-delay rule of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 8). It reads no protected table and no untreated feed row. A row exists only where the assigned volume is above zero, with `speed_ratio` above 0 and at most 1.000, and the speed it gives back is a whole number of km/h of at least the speed floor of C25; any other link and hour keeps its free-flow time ([decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md)). With the default provider (`EII_TRAFFIC_PROVIDER` `simulated`), every flow and traffic fact, and every fact computed for an outline built with `traffic_hourly`, has provenance Simulated through the least-real rule (DAT-91, SYN-54). The optional live provider adds no row to `traffic_hourly` or any other table: its tiles are picture layers from which no numeral is read, and a traffic-aware area is session geometry (DAT-163, ARC-135). | The lineage of `traffic_hourly` names only `flow_hourly`, `road_link` and the method; a fixture that reads a protected table or a feed row fails; a ratio above 1.000 or at 0 fails; a ratio that gives back a speed below the floor, or that is not the rounded ratio of a whole speed, fails; the regression fixture of MTH-89 fixes the assignment; an absent pair rendered as zero fails; a release table, row or artefact built from a provider response fails. |
| DAT-140 | `register_company_list` follows PRV-125 and holds only the columns of 7.3: one row for each register company of `pub_register_company` that has attached records, for the last month of the window only, with its `registration_number`, its `employee_count`, the company's number of employees in that month counted from the attached employment records under DAT-04 ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) items 4 and 5), and its `suppression_reason_code`. Where PRV-125 withholds a company's count because its unit's last-month atoms are carried forward, the row stays, with a null `employee_count` and the reason `CARRIED_FORWARD`; a published count has a null reason. It replaces the firm list of named synthetic firms, which decision 0022 retires. Nothing else of the attached records crosses for one company: no column holds a wage, wage bill, pay band, occupation, nationality group, residence, employer group, legal entity, owner, staff, opening or closing month or vault identifier, and no graph node or edge refers to a register company (DAT-101). The `registration_number` is the register's own Public key, never a vault identifier and never a `SYN-` value. It stays in the register file, the vault, the release, the serving stores and the API responses, pages and exports that show a company's card or a list ([02_ARCHITECTURE.md](02_ARCHITECTURE.md) ARC-03); no repository file, brief, fixture, log, ledger row, egress record or model payload carries it, and the identifier and egress scans refuse it there (decision 0022 item 8; PRV-72, PRV-103). A company's card and a list show its published fields and this employee count only, or, where the count is withheld, the withholding with its reason and never a zero, and a list is ordered only by tested code over criteria the user can see and change, never by a wage or another unreleased value ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-125). The employee counts are attacker knowledge in the attacker-view audit, and the attack suite runs the planted cases of decision 0022 item 7. A fact about one register company's employee count is Synthetic and fills only a `register_company` slot (DAT-145). | Column allowlist; a row of another month, a wage, wage-bill, pay-band, occupation, nationality or residence column planted in the table, and a row whose `registration_number` is absent from `pub_register_company`, fail; a published `employee_count` that differs from the attached records' count under DAT-04 fails; a carried-forward row with a null `employee_count` and `CARRIED_FORWARD` passes, and the same row with a planted numeric count, a null count without a reason and a reason beside a published count each fail; a withheld count rendered as a zero fails; a `SYN-` value in any column fails (DAT-83); a registration number of the invented stand-in register planted in an API log, a ledger row, an egress record or a model payload is a hit of the scans of PRV-72 and PRV-103; a planted wage of one company on a card or in a list fails, and a planted released aggregate that isolates one company fails (decision 0022 item 7); an employee-count fact in any slot other than `register_company` fails. |
| DAT-141 | A column `sex` or `nationality_group`, or a `breakdown_key` dimension of either name, exists only in a Public table each of whose sources declares that dimension in `source_registry.public_splits`, copied from its registry entry (PUB-90), apart from the two nationality fields of decision 0022 named below: `sex` permits a `sex` dimension and `nationality` a `nationality_group` dimension. In version 1 these Public split tables are `pub_wage_table`, `pub_labour_sex_municipality`, `pub_population_age_sex`, `pub_active_sex_age`, `pub_active_nationality_occupation`, `pub_compensation_nationality`, `pub_students`, `pub_visitor_markets` and `pub_pop_agesex_grid`; each keeps the source's own geography and categories ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 5). No source contract, Protected, Simulated, Frame or Control table or case sample file has a column whose underscore-separated name parts include `sex`, `gender`, `nationality`, `citizenship`, `ethnicity`, `religion`, `language` or `age`, and none of their closed lists holds a sex, gender or nationality value: the synthetic records carry none and none is derived for them (SYN-13). The two exceptions of [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) item 6 are `employment_spell.nationality_group`, the worker's nationality group in the format of the real records, and `establishment.establishment_nationality`, the register's establishment nationality; a Protected table may carry either as a dimension only where document 06 releases it, under its rules, and with the column named in 7.3. A fact read from a split row has `input_classes` exactly `public` and geography kind `public` or `national` (`area_shape` only in the case below). It is never joined to a synthetic record, used to segment synthetic records or simulated presence, apportioned to an area or combined with a protected figure. One case is allowed ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 22): the sum of whole cells of `pub_pop_agesex_grid` over an area the user chose, where a cell counts when its centre lies inside the area's `requested_shape` and no cell is split. That sum is not an apportionment. Its fact is Public, with `input_classes` exactly `public`, geography kind `area_shape`, no `apportioned_from`, evidence status `observed` as for an exact-shape count of Public points (DAT-147; ASSUMPTION 40), the caveat key `grid_cells_summed`, and its source and year; it is for display only, so it is never a criterion of a rank or fit fact (DAT-134), never a feature (DAT-152), never combined with a protected or Simulated figure and never placed with one in a claim or component. The generator reads the grid only collapsed across age and sex, as weights, and no synthetic record carries age or sex (SYN-13). | Schema scan of every contract and release table, with a planted column, `breakdown_key` dimension and closed-list value for each denied part; a sex or gender column anywhere outside a Public split table fails, and so does a nationality column other than the two of decision 0022 or in a table that document 06 does not release it in; an undeclared split in a Public table fails; a split fact with another input class or with a `release_units` or `user_scenario` geography fails, and so does one with an `area_shape` geography unless it is the whole-cell sum of `pub_pop_agesex_grid` with no `apportioned_from`. Planted violations of the exception each fail: a cell split by the shape's edge, a cell counted whose centre lies outside, a sum with `apportioned_from`, a sum without `grid_cells_summed`, a sum from any other split table, a sum used as a criterion of a rank fact, and a sum in the same claim as a protected or Simulated figure. |
| DAT-142 | `fdi_projects` loads every project field that the dashboard page holds ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 6): the columns of 7.3 and every further field that slice S2 finds, added as a nullable column by a contract revision (DAT-120); until then an unexpected field fails the fetch (PUB-07). Each fact from it is Public and shows its source and retrieval date through `source_registry`. Every capex or jobs fact carries the caveat key `fdi_estimates`, whose text restates the source's note that the figures are estimates of publicly announced projects and that the dashboard does not capture every project. A project fact fills only an `fdi_project` slot or a Public slot of another subject, and is never joined to a register company's attached records, protected or simulated data (decision 0022). No named query filters projects by company name or returns them for a typed company name: they are listed by sector, sub-sector, function, project type, source country, announcement period or geography. Two projects with identical published fields fail the build. Only the fetcher, the parser, the contract and their tests are committed; the tests use a small synthetic page of the same shape with visibly fictional company names, and fetched data stays in `data/` (DAT-85). | Contract fixtures on the synthetic page; an unexpected field, a capex or jobs fact without the caveat, a join to `register_company_list` or another protected table, a company-name filter and a duplicate project each fail; a repository scan finds no fetched page. |
| DAT-143 | `pub_investqa_record` holds structured records of the agency's sector, opportunity, incentive, set-up and law pages, read through the source `investqa_pages` ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 7, PUB-88): keys, titles, order, references, links and typed incentive parameters, never a page's paragraphs. Screen text is rendered by application templates from these records, with a link to each page. A figure that a page states for a future period, or as a forecast, is not loaded. Only the four parameter kinds of the break-even card enter a calculation; any other parameter is listed with its page link as not used by the calculator. A parameter enters a calculation only when the user selects its package; the result carries `user_input`, the caveat `your_inputs` and a lineage naming the parameter's page (DAT-92), and no stored Public figure changes. Only the fetcher, the parser, the contract and their tests are committed, with a synthetic test page of the same shape. | Contract fixtures on the synthetic page; a paragraph column, a forward-looking figure, a parameter kind outside the closed list used in a calculation and an unselected package that changes a result each fail. |
| DAT-151 | `access_score` holds the build-time reachable-access scores of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) C12 (MTH-02): one row for every published `px_base` unit as a demand location and every supply layer, mode, cut-off, presence key and traffic setting that C12 fixes for stored scores. It is computed in the custodian plane after the privacy engine and the traffic assignment, by the one tested C12 function, from released values only: as demand, the residents present of `presence_count` (segment `resident`, at the row's `day_type`, `hour` and `summer`), summed in step 1 over every demand location of the layer in the frame; the Public supply points of the layer, each located to its `px_base` unit; and the times of `travel_time_matrix` (DAT-153) at free flow, or at the row's key when `traffic` is `hourly`. A stored score never has a protected demand layer, because it would divide a Public count by a protected count ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-41), and never puts a Public statistic on a release unit (MTH-56). It reads no withheld presence group, no feed row and nothing outside the release, so it is post-processing of released values. A row is `withheld` with `BELOW_PANEL_MINIMUM` when its own presence group is withheld or when any supply point within its reach draws on a withheld presence group (PRV-58, PRV-122); a withheld group is never counted as zero, and an area summary that draws on a withheld row returns `BELOW_PANEL_MINIMUM`. Every row has provenance Simulated through the least-real rule (DAT-91). A fact read from it has subject `area`; a supply point appears only as its Public category, and no figure is attached to a named place (DAT-145). | The lineage of `access_score` names only `presence_count`, `pub_place` or the reviewed gazetteer list, `travel_time_matrix` and the C12 method; a fixture that reads a Protected table, a feed row or a withheld group fails; a withheld presence group inside a supply point's reach gives `withheld` rows with `BELOW_PANEL_MINIMUM` for every demand location that reaches it, and a score computed with that group as zero fails; the C12 fixture of MTH-66 reproduces; a fixture release whose protected rows, and whose feed values behind a withheld presence or flow group, change gives a byte-identical `access_score` (PRV-124); a `provenance` other than `simulated` and a `walk` row with `traffic` `hourly` fail. |
| DAT-152 | `zone_type` holds the three area types of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) C17, built once per release by its k-means run on the reviewed list of Public features: one row for every zone of `zone`. Every feature is Public and defined the same way for a zone and a drawn shape; no Synthetic, Simulated or Protected figure and no Public split by sex or nationality is a feature (DAT-141), so the table is Public and no such figure is attached to a named zone. `mean_silhouette` and `mean_adjusted_rand` are the release's two stability figures of C17 and are equal on every row. `area_type` is filled only where `type_status` is `typed`; the null of every other row is explained by its `type_status` (DAT-07). A user's area takes its type at request time from the type centres that `eii_core.calc` recomputes from this table and the same features (C17). | Exact-key check against `zone`; a feature read from a Synthetic, Simulated or Protected table, or from a Public split table, fails; rows with different stability figures fail; a null `area_type` on a `typed` row, or a filled one on another row, fails; the three-group fixture of MTH-73 is recovered exactly. |
| DAT-153 | The manifest artefact `artefacts/travel_time_matrix.parquet` holds the travel times that [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) C12 uses (MTH-02): for each mode, the network time from the centre of one `px_base` unit's base cell to the centre of another's, for every ordered pair whose time is at most the largest cut-off of C12 for that mode. An absent pair is beyond that cut-off or has no route, and C12 gives it no weight. Its columns are `from_unit_id` and `to_unit_id` (`px_base` units); `mode` (`walk`, `drive`); `traffic` (`free_flow`; or `hourly`, for `drive` only); `day_type`, `hour` and `summer` (null when `traffic` is `free_flow`; otherwise one `traffic_hourly` key of DAT-76); and `minutes` decimal(7,2). The release build writes it in the custodian plane after the traffic assignment, on the routing graph of the release, with the free-flow speeds of C25 for `free_flow` rows and the whole link speeds that `traffic_hourly` gives back for `hourly` rows; its times are the itemised route totals of [decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md) item 6 over those speeds (the exact sum of the link times and the line of turns at junctions), so they equal the totals that a route shows. A free-flow time is Public and an hourly time Simulated (DAT-91). It reads no protected row, suppressed flow group or feed row (PRV-124). Only a `protected` release lists it in `manifest.artefacts`; like every artefact it is read as a file and never loaded into a store (ARC-43). | The lineage of every fact computed with it names the routing graph's source and, for `hourly` rows, `traffic_hourly`; a fixture that reads a protected table or a feed row fails; a fixture release whose protected rows, and whose feed values behind a suppressed flow group, change gives a byte-identical artefact (PRV-124); a `walk` row with `traffic` `hourly`, and an `hourly` row without its key, fail; two builds from the same inputs give the same artefact digest. |
| DAT-154 | `access_score_grid` holds the build-time reachable-access scores of the population-grid layer of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) C12, at free flow only (MTH-02): one row for every cell of the grid `worldpop_qat_2020` whose population value is above zero and whose centre lies in the frame, and every supply layer, mode and cut-off that C12 fixes for stored scores. It is computed in the release build by the one tested C12 function of `eii_core.calc` from Public inputs only: as demand, each cell's grid value `P_i`, summed in step 1 over every cell of the layer in the frame; the Public supply points of the layer; and the free-flow network time from the graph node of the mode nearest the cell's centre to the graph node of the mode nearest each supply point (ties: lower node id, as C25 loads units), on the routing graph of the release. These times are not stored, and `travel_time_matrix` is not read; an hourly time is Simulated, so the table has no hourly row. Every row has provenance `public` through the least-real rule (DAT-91), and a `public_only` and a `protected` release built from the same Public inputs hold the same rows (DAT-70). The table has no `unit_id`: its cells are the grid's own cells, and no row is joined to, apportioned to or summed over release units or frame cells (DAT-74, MTH-56); no Synthetic, Simulated or Protected figure enters it, so it never combines a protected value with a Public figure ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-41). `demand_weight` is a weight only and is never shown as a population figure ([04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 2.2). A cell from which no supply point of the layer is within the cut-off has its true score 0, which step 2 of C12 gives, as `access_score` stores it for a unit. An area whose cells all score 0 has the area score 0, as for the Simulated layer, and an area score computed from this table is `NO_DATA` only when the sum of the area's weights is 0, that is when no populated cell lies in the area (C12). No row is withheld, so every row is `published` and `suppression_reason_code` is null on every row. The table is built only when the registry entry of `worldpop_qat_2020` names it among its `release_tables`, which document 04 does for C12 once slice S2 confirms the grid's file and licence; until then neither release kind holds it, and the grid layer returns `NO_DATA` (MTH-66). A fact read from it has subject `area`; a supply point appears only as its Public category, and no figure is attached to a named place (DAT-145). Its rows enter the public-total inventory of PRV-115 like every Public row. | The lineage of `access_score_grid` names only `worldpop_qat_2020`, `pub_place` or the reviewed gazetteer list, the routing graph's source and the C12 method; a fixture that reads a Protected, Synthetic or Simulated table, `travel_time_matrix`, a feed row or the vault fails; a `public_only` and a `protected` release built from the same Public inputs give a byte-identical table, and so does a fixture release whose protected and Simulated rows change; the C12 fixture of MTH-66, with its two demand locations as grid cells, reproduces 2.5 and 5.83 per 10,000 and the area score of 5.0; a third cell of 1,000 people that reaches neither supply point is stored `published` with the score 0, makes the area score over the three cells 4.0 and has the area score 0 on its own, and an area with no populated cell returns `NO_DATA`; a `provenance` other than `public`, a `traffic` other than `free_flow`, a `unit_id` column, a sum over release units, a row with a status other than `published` or with a null score, a cell with no supply point within reach stored with anything but the score 0, a non-null `suppression_reason_code` and a release whose holding of the table disagrees with the registry entry of `worldpop_qat_2020` each fail. |
| DAT-157 | The four Public tables of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) (7.3) are written by `publicdata` inside `./eii build-public` only, never at run time, from the sources `busy_gmaps`, `ntl_blackmarble`, `places_fsq` and `worldpop_qat_agesex`; once built they are held by both release kinds (DAT-70), and every row enters the public-total inventory of PRV-115 and is reviewed under DAT-128. A token or key is read from the environment and is never written to a file, a `url` of the registry or manifest, or a log (rule 14, DAT-106). A fact from `pub_venue_busyness` is a Public fact of a `place_public` subject, unit `relative_index`, with the label "Google Maps popular times", its retrieval date and the caveat key `relative_busyness_not_people`; it is a relative index and never a count of people, and no component holds it beside an estimated-people figure. The registry entry of `busy_gmaps` has `commit_allowed` false and `licence_basis` `owner_decision` (PUB-12): its values stay in the uncommitted public cache, no repository file or test fixture holds a fetched value, its fetcher is tested on a hand-made page of the documented shape with fictional venues, and it is left out of the nightly live fetch. A fact from `pub_night_lights` is night-time radiance, unit `radiance_nw_cm2_sr`, with the caveat keys `night_lights_not_activity` and, for an area figure, `calculated`; the table is keyed by frame cell and built from whole pixels with no split, it has no `unit_id`, no row is put on a release unit, and a figure for a drawn area is the mean of the frame-cell values whose centres lie inside it, each cell counted once (card C36): Public in provenance, Observed in status, never a sum, never apportioned, with no `apportioned_from` and no `grid_cells_summed` (DAT-74). `pub_place_fsq` holds source-given fields only. It is fetched inside `./eii build-public` from the public copy on Source Cooperative (host `data.source.coop`, which joins the allow-list of PUB-03), as geospatially partitioned GeoParquet read without an account; only the files that cover Qatar are fetched, and no secret variable is added for this source (decision 0019 item 21). The registry entry of `places_fsq` records the release used, and `source_release` holds the release date of the copy used (the newest of the three releases read on 2026-11-12 is dated 2025-01-10); the places are shown with that date. The owner decided on 2026-11-12 that this copy, dated 2025-01-10, is used for version 1 as it is: no account is opened and no newer release is fetched for now. Where a place of the copy disagrees with OpenStreetMap or Overture, which are current, the newer source wins (PUB-102). Competitors and typical neighbours read `pub_place` and `pub_place_fsq` together, the two never merged (PUB-102). `pub_pop_agesex_grid` is a Public split table whose registry entry declares `sex` (DAT-141); a fact from it is the whole-cell sum over an area, with its source and year. The weather profiles are generator inputs in the public cache and the calibration manifest, not a release table, and the traffic provider's tiles and areas are in no table. The traffic provider has no row in `source_registry`, because nothing of it is fetched into the cache; [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) lists it for its terms and attribution. | Registry and schema fixtures: a `busyness_index` outside 0 to 100, as a `count` fact, or in a component beside an estimated-people figure; a fetched `busy_gmaps` value in a committed file or test fixture (repository scan); a `busy_gmaps` entry with `commit_allowed` true or without `owner_decision`; a live fetch of `busy_gmaps` or of a keyed source in the nightly run; a key or token in any `url`, registry row or log; a `unit_id` column or a release-unit row in `pub_night_lights`; a night-lights fact carrying no `night_lights_not_activity`; a `pub_place_fsq` row with an attribute that the source does not give, with no release date in `source_release`, or a release holding the table with no fetched source; a `source_registry` row for the traffic provider; and a `pub_pop_agesex_grid` whose registry entry lacks `sex` in `public_splits` each fail. |

`unit_id` is `<partition_id>:<kind>:<n>` (kind `c`, `m`, `r`, `u` or `n`, with `u` for a
`municipality` unit: the terminal `ha_home` unit or a unit of the municipality level of the four
pay partitions; `n` a six-digit sequence ordered
by the smallest member cell), for example `rp_all_money:m:000042`. Partitions and tiers: document 06.
Derived statistics (mean, median band, quartile bands, shares, crowd density, apportioned figures and
changes between months) are computed by `core` from primitives with thresholds from `rules_version`
([07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md)).
A ratio statistic is one of the mean wage or the coverage, irregular or deployed-elsewhere shares.
Its numerator and denominator come from columns of the same stored rows: one table, one partition,
one unit set and one measure where the table has measures. Those columns may belong to two additive
families, and `fact_lineage` names both with `family_role` values `numerator` and `denominator`.
This closed list and the one closed presence/pay case of DAT-160 are the only exceptions to one home family per figure (PRV-30).

## 8. The manifest and the loader

Every release directory holds `manifest.json`. Its scalar `release_kind` is `public_only` or
`protected`. Scalars common to both kinds are `release_id`, `release_contract_version`
(`release.v1`), `build_id`, `built_at` (provenance only), `code_version` (the full git commit hash),
`rules_version_id` and `engine_versions` (DuckDB, PostGIS target, Python). A `protected` manifest
also has `parameter_set` (the one exported set, `A` or `B`), `world_seed`, `spare_seeds`,
`scenario_sha256` (the committed scenario hash), `window_period` (the span `YYYY-MM/YYYY-MM` of the
window's months, DAT-136), `window_key`, `protected_sha256` and `contracts`
(list of `{name, revision, feed_sha256, reference_period}`). A `public_only` manifest omits
`window_period`, `window_key`, `protected_sha256`, `parameter_set`, `world_seed`, `scenario_sha256`
and `contracts`.
Its lists:
`tables` (`{name, file, provenance_class, sha256, row_count, schema_sha256, grain}`), `sources`
(`{source_id, url, licence, retrieved_on, sha256}`) and `artefacts` (`{path, sha256}`). The complete
`artefacts` inventory and every artefact digest participate in the release identity.

Each protected build evaluates A and B inside the custodian plane and writes exactly one
`protected` release for the configured `export_parameter_set`. The unselected protected table set
never leaves the custodian plane; only aggregate survival and attack results cross. A `public_only`
release contains no Protected or Simulated table, is never frozen and is never entered in the
export register. `EII_RELEASE_DIR` names a release of either kind.

`window_key` is the lowercase hexadecimal SHA-256 of canonical UTF-8 JSON holding the protected
`period` and, for the four protected contracts `business_register.v1`, `employment.v1`,
`residence.v1` and `wages.v1` in that name order, the pair `{name, sha256}`, where `sha256` is the
`feed_sha256` already recorded for that feed in `manifest.contracts` (PRV-120). The protected
`period` is the manifest's `window_period`, the span of the window's months (DAT-136); the monthly
periods of the rows are not inputs, and neither are `mobility.v1`, Public and Simulated tables,
rules, reports and scene fixtures.
Object keys are sorted by Unicode code point, non-ASCII characters are emitted directly as UTF-8,
there is no insignificant white space and there is no floating-point value. The hash input has this
exact shape:
`{"period":"<YYYY-MM/YYYY-MM>","protected_inputs":[{"name":"business_register.v1","sha256":"<lowercase hex>"},{"name":"employment.v1","sha256":"<lowercase hex>"},{"name":"residence.v1","sha256":"<lowercase hex>"},{"name":"wages.v1","sha256":"<lowercase hex>"}]}`.
No post-linkage projection or second input hash is used. A changed feed under the same `world_seed`
therefore creates a second `window_key`, which the register uniqueness rule refuses. No invariance
to scenario text is claimed.

`protected_sha256` is the lowercase hexadecimal SHA-256 of canonical UTF-8 JSON containing the
selected protected tables' `{name, sha256}` objects sorted by `name`, with sorted keys, no
insignificant white space and no floating-point value. Both scalar fields remain in the DAT-80 hash
input. Therefore `window_key` enters the release identity, although a Public, Simulated, report,
scene-fixture or rule change does not change `window_key` by itself.

For a `protected` release, the privacy artefact inventory is closed for version 1. A `public_only`
release does not require these privacy artefacts:

| Path | Role |
|---|---|
| `artefacts/attacker_view_audit.json` | Versioned canonical audit configuration required by PRV-112: model schema version, candidate parameter set, `window_key`, `protected_sha256`, `rules_version_id`, `parameter_set`, target classes, signed local-knowledge, insider and colluder fixture references, solver tolerances and `time_budget_seconds`, with the measured command, machine class, elapsed seconds and run hash from which the budget was set. |
| `artefacts/attacker_view_public_totals.json` | Canonical, versioned, signed inventory required by PRV-115. Its entry identifiers equal exactly one source entry for every `source_registry` row, one row entry for every row of every Public manifest table, and one sum entry for every complete category split that a Public table's registry entry declares and whose total over the same other key values is not itself a row; each entry records `enabled` or `not_applicable` under PRV-115. |
| `artefacts/reports/closure_report.json` | Selected-export exhaustive structural-check results and repeated fuzz count and seed required by PRV-49 and PRV-111, naming the release by `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set`. Candidate A and B reports remain inside the custodian plane. |
| `artefacts/reports/attacker_view_audit_report.json` | Attacker-view audit report required by PRV-69 and PRV-112 to PRV-116: per parameter set, the person and employer-group target-class counts, solve count, outward-rounded interval widths, elapsed time and pass or fail. |
| `artefacts/reports/attack_report.json` | Signed Ed25519 attack-report envelope required by PRV-79; it carries aggregate results for A and B and no unselected protected row. |
| `artefacts/reports/survival_detail_report.json` | Signed Ed25519 survival-detail-report envelope required by PRV-81; it carries the A and B aggregate detail. |
| `artefacts/scene/two_shapes.json` | Signed scene-fixture envelope for the two prepared requests of scene step 2 under PRV-106. |
| `artefacts/scene/complement.json` | Signed scene-fixture envelope for the two prepared requests and pre-validated unit sets of scene step 3 under PRV-106 and PRV-119. Their symmetric difference is exactly one published `merged` unit containing at least two base cells, and no figure exists for any member base cell alone (PRV-105). |
| `artefacts/scene/injection.json` | Signed scene-fixture envelope for the catalogue and injection regression of scene step 4 under PRV-119. |

The non-privacy build report `artefacts/reports/fidelity_report.json` is also listed in
`manifest.artefacts`; it is the machine-readable fidelity report of SYN-34 used by the Proof room.
A `protected` release also lists the non-privacy artefact `artefacts/travel_time_matrix.parquet`,
the travel times of C12 by mode, at free flow and by hour (DAT-153); like every artefact, its digest
takes part in the release identity (DAT-80). A `public_only` release has no such artefact.

The attacker-view audit has one acceptance model (PRV-113). It fixes every published protected leaf
to its untreated monthly aggregate, admits only attacker knowledge verified against sealed truth,
and applies the published-means-passed, survival and public-total constraints of PRV-113. Targets
that the model cannot distinguish form one target class (PRV-112, PRV-116). Layout implications that
PRV-113 excludes are covered by the typed attacks of PRV-76. The report records evidence under that
stated attacker; it is not a proof of non-disclosure. No manifest artefact contains an untreated
aggregate, a knowledge-fixture value, a target value or another person-level or employer-level true
value.

Release-internal artefact and report identity is governed by DAT-80. `load_receipt.json` is written
by the loader and is not listed in `manifest.artefacts`; it carries the matching `release_id` for
both release kinds. A run-time privacy receipt of an answer is not a release artefact and may show
`release_id`.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-80 | `release_id` is the full 64-character lowercase hexadecimal SHA-256 of the canonical `manifest.json` (keys sorted, UTF-8, no insignificant white space, no floating-point values) with only `release_id`, `build_id` and `built_at` removed. The complete `tables` and `artefacts` inventories and every table and artefact digest remain in the hash input; for a `protected` release, `window_key` and `protected_sha256` remain too. `window_key` is the SHA-256 of canonical JSON holding the protected `period` and, for the four protected contracts (`business_register.v1`, `employment.v1`, `residence.v1`, `wages.v1`, in that name order), the pair `{name, sha256}` where `sha256` is the `feed_sha256` the manifest already records for that feed. It does not change when a Public or Simulated table, a scene fixture, a report or a treatment rule changes. A change that alters a feed under the same `world_seed` gives that seed a second `window_key`, which the uniqueness rule refuses; no invariance to scenario text is claimed. No artefact or report listed in `manifest.artefacts` contains `release_id`, `build_id` or `built_at`; for a protected release each names the release by `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set`. The manifest binds those four values to `release_id`, and start-up checks every signed report against the mounted manifest. `load_receipt.json` is not a manifest artefact and carries `state` and the manifest's `release_id` for both release kinds. Nondeterministic artefact bytes create a different release or must be made deterministic. | Recompute and compare for both release kinds; two builds from the same inputs yield the same id; for a protected release, changing a protected feed's `feed_sha256` or the protected period changes `window_key` and the release id, while changing only a Public or Simulated table, scene fixture, report or treatment rule leaves `window_key` unchanged but changes the release id when its manifest content changes; no scenario-text invariance is asserted; a changed table or artefact digest changes the release id; planted `release_id`, `build_id` and `built_at` fields in every manifest artefact or report fail; a receipt whose `release_id` differs from the manifest fails. |
| DAT-81 | The loader requires exact manifest agreement under `tables/` and `artefacts/`. At the release root it allows only `manifest.json`, `release.duckdb` and `load_receipt.json`; every other path is rejected. Manifest paths are normalised relative paths under their expected subdirectory. Absolute paths, `..`, symlinks, non-regular files and resolved paths outside the release root or expected subdirectory are rejected before loading. | Extra, missing, absolute, traversal, symlink and non-regular-file fixtures are refused; repeat loading tolerates only the two named loader outputs at the root. |
| DAT-82 | The loader verifies each table and artefact's SHA-256, each table's row count and each table's schema hash before loading and refuses the whole release on any mismatch. `schema_sha256` is SHA-256 over canonical JSON containing the ordered column name, logical type, nullability and, for geometry columns, geometry type and SRID. | Tampered-file and reordered-or-retyped-schema fixtures are refused; independent writers compute the same schema hash. |
| DAT-83 | The loader refuses any table whose name is not in section 7.2, any protected-table column outside the DAT-71 allowlist, any closed-list value or placement that fails DAT-127 to DAT-130, any within-family total that differs from the exact sum of its own additive-family leaves, any column named `person_id`, `establishment_id`, `legal_entity_id`, `group_id` or `file_id`, and any string value in any column matching one of the five identifier prefixes `SYN-E-`, `SYN-L-`, `SYN-G-`, `SYN-P-` or `SYN-F-`: since [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) retired the firm list and its `firm_key`, no release holds a value of these forms. A `registration_number` column exists only in `register_company_list` and `pub_register_company`, and every `registration_number` of `register_company_list` is one of `pub_register_company` (DAT-140). The loader does not compare two different additive families for equality; PRV-71 performs the custodian-plane cross-family bound check before export. | One fixture per refusal reason, including every closed list, a wrong within-family sum and each of the five identifier forms; a `SYN-E-` value in any column, a `firm_list` table and a `firm_key` column each fail; a `registration_number` column in any other table, and a `register_company_list` row whose number is absent from `pub_register_company`, fail; the fixtures use the invented stand-in register; a cross-family difference loads without an equality or reconciliation check. |
| DAT-84 | The loader writes the same tables to PostgreSQL (schema `r_` plus the first 16 hexadecimal characters of the full `release_id`) and to the DuckDB standby file, and materialises `release_manifest` in both from verified `manifest.json`. Both stores are staged and verified before `load_receipt.json`, which is not listed in `manifest.artefacts`, is written with `state: complete` and `release_id` equal to the mounted manifest's id. A protected-release receipt also carries matching `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set`; a `public_only` receipt omits those protected-window fields. Preflight and the API refuse a release without the receipt, without `state: complete`, with a mismatched `release_id`, or, for a protected release, with any mismatched protected-window field. The parity suite compares the stores after the rounding rule stated in [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md). | Parity suite green on both engines, including `release_unit.geometry`, `district` and `grid_cell.district_key`; an absent, incomplete or wrong-release receipt refuses service; protected and `public_only` receipt fixtures enforce their conditional fields. |
| DAT-85 | Every source in `manifest.sources` has a licence and a retrieval date; a source whose `commit_allowed` is false (for example the census map layers, the FDI dashboard and the agency's pages, used in this internal project under [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), and the relative-busyness source `busy_gmaps` under [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 19) is fetched at build time and never committed. A response of the live traffic provider is not a source of the release: it is fetched at run time, nothing of it is stored, and no `manifest.sources` row exists for it (DAT-163). | Manifest check; repository scan finds no such file; a `manifest.sources` row for a provider response fails. |
| DAT-131 | For a `protected` release, the manifest lists every privacy artefact at the exact path in the inventory above and no second file with the same role. A `public_only` release does not require a privacy artefact. Every signed JSON artefact is one canonical envelope containing its payload, `signature_algorithm` equal to `Ed25519`, `public_key_id` and `signature`; its manifest SHA-256 covers the complete envelope. The fixture identifier for each scene artefact is `scene:` followed by that lowercase manifest SHA-256. Every artefact and report follows the release-identity rule of DAT-80. The artefact scan also fails on any untreated aggregate, knowledge-fixture value, target value or other person-level or employer-level true value. | Protected-release exact-path and one-role checks; missing, renamed, duplicate-role, unsigned, tampered, wrong-release-name, forbidden-identity-field and true-value fixtures fail. A `public_only` fixture without privacy artefacts passes. The attacker-view report fixture proves that target-class counts, solve counts, outward-rounded interval widths, elapsed time and pass or fail are representable without a true value. |
| DAT-132 | For a `protected` release, `manifest.parameter_set` equals the shared `export_parameter_set` and exactly that set's protected tables occur in `manifest.tables`. The default `export_parameter_set` is `A` and is fixed, with `window_months`, at the slice S1 gate before the first world build; OI-35 permits an owner or data owner to overrule it only before that gate. `survival_report`, `artefacts/reports/survival_detail_report.json` and `artefacts/reports/attack_report.json` retain aggregate A and B results. No unselected protected table or row occurs anywhere in the release. A `public_only` release has no `parameter_set`, protected table, Simulated table or protected-window field and is never frozen or registered. | Protected candidate build with both table sets fails; a protected candidate with the wrong selected set fails; a missing or post-gate selection fails; aggregate report fixtures for both sets pass; a `public_only` fixture with any forbidden table or field, freeze descriptor or register line fails. |
| DAT-133 | `./eii freeze` accepts a `protected` release only, is run twice and takes no new flag; a `public_only` release is never frozen or entered in the export register. On its first run on the build machine, it requires the current test pass and a recorded human release review with fields `reviewer_role`, `review_date`, `survival_report_read`, `attack_report_read`, `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set`; the two report-read fields are true and the four release fields equal the verified manifest. It writes the data bundle and checksum list, copies the review record into the bundle as `review.json`, writes `freeze.json` with `release_id`, `window_key`, `protected_sha256`, `world_seed`, `frozen_commit`, `review_record` equal to `review.json` and `state: pending`, and appends exactly one JSON line to `infra/export_register.jsonl` with these fields in order: `window_key`, `protected_sha256`, `world_seed`, `rules_version_id`, `parameter_set`, `release_id`, `code_version`; every value equals the verified manifest. The line reaches the base branch through a normal pull request. On its second run, from a base-branch commit containing that line, the same command builds the application archive from that commit, verifies an offline installation, writes the archive checksum beside the bundle and changes only `freeze.json.state` to `complete`. A protected release is frozen when its bundle has `freeze.json`. For a frozen release only, the installer and `./eii up` require `state: complete` and the matching `window_key` and `protected_sha256` line in the register shipped inside the installed application; either failure exits 7. A release under `data/releases/` on the build machine has no `freeze.json` and is not checked. Continuous integration checks the register alone: existing lines are immutable, one `protected_sha256` is allowed per `window_key`, and one `window_key` per `world_seed`. A freeze is refused when the release is `public_only`, the same `window_key` is registered with different protected tables or the same `world_seed` with a different `window_key`. After a freeze, any change of rules version, exported set, treatment code or world generator requires a new `world_seed` and a new build before another freeze (PRV-120). A frozen bundle refused at install or start because its line is missing from the installed application's register or its freeze is incomplete is remedied by finishing this two-run freeze, not by changing the seed. No signed export-register receipt or substitute file is created. | A `public_only` freeze or register-entry attempt fails; missing-role, missing-date, unread-report, missing-`world_seed` and manifest-mismatch fixtures fail; the first run writes the bundle, checksum list, pending descriptor, `review.json` and one register line; the second no-flag run appends no line, runs only from the containing base-branch commit, verifies offline installation, writes the archive checksum and marks the descriptor complete. A second protected hash for one window key, a second window key for one world seed, a changed line or a removed line fails in a clean continuous-integration checkout using the register alone. Installation and start of a frozen bundle exit 7 when its line is absent from the installed application's register or `freeze.json` is not complete; an unfrozen build release is not checked. A planted signed export-register receipt does not satisfy any check. |

## 9. The fact object

Every number on screen is rendered from one fact. The schema below is binding and lives at
`contracts/fact.v1.schema.json`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:eii:contract:fact:v1",
  "title": "EII fact", "type": "object", "additionalProperties": false,
  "required": ["fact_id", "value", "unit", "period", "geography", "provenance", "input_classes",
               "evidence_status", "reliability", "coverage_keys", "caveat_keys", "label_en",
               "label_ar", "lineage_ref", "release_id"],
  "properties": {
    "fact_id": {"type": "string", "pattern": "^f_[0-9a-f]{32}$"},
    "value": {"type": ["number", "string", "null"]},
    "unit": {"enum": ["count", "qar_per_month", "qar", "qar_thousand", "qar_million", "qar_per_kg",
                      "qar_per_m2", "usd_million", "kwh", "riders", "ratio", "percent", "index", "relative_index",
                      "wage_band", "size_band", "volume_band", "metres", "minutes",
                      "covers_per_day", "people_per_km2", "tonnage", "rank", "direction",
                      "calendar_date", "calendar_month", "calendar_year", "published_text",
                      "radiance_nw_cm2_sr"]},
    "period": {"type": "string", "minLength": 4},
    "geography": {
      "type": "object", "additionalProperties": false, "required": ["kind"],
      "properties": {
        "kind": {"enum": ["release_units", "public", "national", "user_scenario", "area_shape"]},
        "unit_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "public_code": {"type": "string", "pattern": "^(zone|municipality|district|place):.+$"},
        "area_id": {"type": "string", "minLength": 1},
        "apportioned_from": {"type": "string",
                             "pattern": "^(release_units|(zone|municipality|district):.+)$"}},
      "allOf": [
        {"if": {"properties": {"kind": {"const": "release_units"}}, "required": ["kind"]},
         "then": {"required": ["unit_ids"],
                  "not": {"anyOf": [{"required": ["public_code"]}, {"required": ["area_id"]},
                                    {"required": ["apportioned_from"]}]}}},
        {"if": {"properties": {"kind": {"const": "public"}}, "required": ["kind"]},
         "then": {"required": ["public_code"],
                  "not": {"anyOf": [{"required": ["unit_ids"]}, {"required": ["area_id"]},
                                    {"required": ["apportioned_from"]}]}}},
        {"if": {"properties": {"kind": {"enum": ["national", "user_scenario"]}}, "required": ["kind"]},
         "then": {"not": {"anyOf": [{"required": ["unit_ids"]}, {"required": ["public_code"]},
                                    {"required": ["area_id"]}, {"required": ["apportioned_from"]}]}}},
        {"if": {"properties": {"kind": {"const": "area_shape"}}, "required": ["kind"]},
         "then": {"required": ["area_id"],
                  "not": {"anyOf": [{"required": ["unit_ids"]}, {"required": ["public_code"]}]}}}]},
    "provenance": {"enum": ["public", "synthetic", "simulated", "suppressed"]},
    "input_classes": {"type": "array", "minItems": 1, "uniqueItems": true,
                      "items": {"enum": ["public", "synthetic", "simulated", "user_input"]}},
    "evidence_status": {"enum": ["observed", "inferred", "still_to_test"]},
    "reliability": {"enum": ["standard", "low_count", "not_applicable"]},
    "coverage_keys": {"type": "array", "items": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}},
    "caveat_keys": {"type": "array", "items": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"}},
    "label_en": {"type": "string", "minLength": 1},
    "label_ar": {"type": "string", "minLength": 1},
    "lineage_ref": {"type": "string", "pattern": "^lin_[a-z0-9_]+$"},
    "release_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
  "allOf": [
    {"if": {"properties": {"provenance": {"const": "suppressed"}}, "required": ["provenance"]},
     "then": {"properties": {"value": {"type": "null"}}},
     "else": {"properties": {"value": {"type": ["number", "string"]}}}},
    {"if": {"properties": {"unit": {"const": "count"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": ["integer", "null"]}}}},
    {"if": {"properties": {"unit": {"enum": ["qar_per_month", "qar", "qar_thousand", "qar_million",
                                                "qar_per_kg", "qar_per_m2", "usd_million", "kwh",
                                                "riders", "ratio", "percent", "index", "relative_index", "metres",
                                                "minutes", "covers_per_day", "people_per_km2",
                                                "tonnage", "radiance_nw_cm2_sr"]}},
            "required": ["unit"]},
     "then": {"properties": {"value": {"type": ["number", "null"]}}}},
    {"if": {"properties": {"unit": {"const": "rank"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": ["integer", "null"], "minimum": 1}}}},
    {"if": {"properties": {"unit": {"const": "direction"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"enum": ["higher", "lower", "equal", null]}}}},
    {"if": {"properties": {"unit": {"const": "wage_band"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": ["string", "null"],
                                        "pattern": "^B(0[1-9]|1[0-2])(\\.\\.B(0[1-9]|1[0-2]))?$"}}}},
    {"if": {"properties": {"unit": {"const": "size_band"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": ["string", "null"],
                                        "pattern": "^(no_payroll|s[0-9]{2}_([0-9]{2}|plus))$"}}}},
    {"if": {"properties": {"unit": {"const": "volume_band"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": ["string", "null"], "pattern": "^vb[0-9]+$"}}}},
    {"if": {"properties": {"unit": {"const": "calendar_date"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": "string",
                                        "pattern": "^[1-9][0-9]{3}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"}}}},
    {"if": {"properties": {"unit": {"const": "calendar_month"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": "string", "pattern": "^[1-9][0-9]{3}-(0[1-9]|1[0-2])$"}}}},
    {"if": {"properties": {"unit": {"const": "calendar_year"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": "string", "pattern": "^[1-9][0-9]{3}$"}}}},
    {"if": {"properties": {"unit": {"const": "published_text"}}, "required": ["unit"]},
     "then": {"properties": {"value": {
       "type": "string", "minLength": 1, "maxLength": 200,
       "allOf": [{"pattern": "[0-9]"}, {"pattern": "^\\S(.*\\S)?$"},
                 {"not": {"pattern": "[\\u0000-\\u001F\\u007F-\\u009F\\u0660-\\u0669\\u06F0-\\u06F9\\u200B-\\u200F\\u2028-\\u202E\\u2060-\\u2069\\uFEFF]"}},
                 {"not": {"pattern": "(^|[^0-9])([0-9]{8}|[0-9]{11})([^0-9]|$)"}}]}}}},
    {"if": {"properties": {"unit": {"enum": ["calendar_date", "calendar_month", "calendar_year",
                                                "published_text"]}},
            "required": ["unit"]},
     "then": {"properties": {"provenance": {"const": "public"}, "input_classes": {"const": ["public"]},
                             "evidence_status": {"const": "observed"},
                             "reliability": {"const": "not_applicable"}}}},
    {"if": {"properties": {"input_classes": {"contains": {"const": "user_input"}}},
            "required": ["input_classes"]},
     "then": {"properties": {"evidence_status": {"const": "inferred"}}}},
    {"if": {"properties": {"caveat_keys": {"contains": {"enum": ["forecast_backtest_range",
                                                                 "estimate_on_simulated_inputs",
                                                                 "scenario_not_forecast",
                                                                 "present_by_pay_band_assumed"]}}},
            "required": ["caveat_keys"]},
     "then": {"properties": {"evidence_status": {"const": "inferred"}}}},
    {"if": {"properties": {"geography": {"required": ["apportioned_from"]}},
            "required": ["geography"]},
     "then": {"properties": {"evidence_status": {"const": "inferred"}}}}]
}
```

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-90 | Every tool result validates against the schema; a fact that fails is dropped and its slot shows the `NO_DATA` template, which may carry a reason key (`series_too_short`, `forecast_below_zero` and `no_denominator` join it with decision 0019, DAT-158, DAT-159; a reason key is not a suppression code of DAT-130). Non-suppressed numeric units require non-null numeric values, `count` requires an integer, `wage_band` accepts only B01–B12 or a `B01..B02`-style range, `size_band` only a size band of 7.3 or a joined range of adjacent bands, the three date units and `published_text` only the closed string forms of DAT-155, only a Suppressed fact has a null value, each geography kind has mutually exclusive fields, a geography with `apportioned_from` requires `inferred` (DAT-147), and every `lineage_ref` must pass DAT-94 before the API emits the fact. | Schema and lineage validation in every tool test; null numeric, fractional count, numeric wage-band, unknown size-band, non-suppressed null, mixed-geography, apportioned-but-observed and unresolved-lineage fixtures fail. |
| DAT-91 | Least-real rule, computed in `core`: unless the fact is `suppressed`, `provenance` equals the least-real class in `input_classes` (Public more real than Synthetic, more real than Simulated); `user_input` does not take part in the ordering. | Property test over all class combinations. |
| DAT-92 | A fact computed from the user's own inputs carries `user_input` and `evidence_status = inferred`, the caveat key `your_inputs`, and a `lineage_ref` that resolves the deterministic method and every release fact used with those inputs. It is never written to the release or the store. | Break-even fixture: the fact has complete method and release-input lineage, appears in the API response and in no table. |
| DAT-93 | `fact_id` matches `^f_[0-9a-f]{32}$` and is the first 32 hexadecimal characters of the SHA-256 of the canonical JSON of (`release_id`, `metric_key`, `geography`, `period`, `qualifiers`). Tool names, canonical arguments and fact slots are not inputs. | Two calls producing the same semantic fact return identical ids; changing any semantic component changes the id; a different tool-call shape alone does not. |
| DAT-94 | `lineage_ref` names a `lineage_id` in `fact_lineage` and resolves the complete Source chain: fact → release table → deterministic method and version → source with publisher, dataset or page, licence, retrieval date and file SHA-256. For a fact derived from a protected table, the same lineage normally names exactly one home additive family through `table_name`, `partition_id`, `measure` where that table has measures, `breakdown` and `family_role: single`; every source row of that `lineage_id` repeats the same family tuple. One exception is a ratio statistic in the closed list: mean wage, coverage share, irregular share or deployed-elsewhere share. Its numerator and denominator come from columns of the same stored rows — one table, one partition, one unit set and one measure where applicable — even when the columns belong to two additive families; its lineage contains both tuples with `family_role: numerator` and `family_role: denominator`. The other exception is the one closed presence/pay case: the figure of DAT-160, whose lineage names `presence_count` and one protected band family per segment — `wp_all_quartile` for workers present, `rp_all_quartile` for residents present — with their lineage roles; every other combination of a protected value with a presence, flow or traffic value fails. No extra field is added to the fact object. A count and adjacent non-ratio shares must resolve to the same family, and no output may present two families as two numeric estimates of one population (PRV-30). A fact with an absent, unresolved or incomplete chain or required protected family tuple is not a fact: the release build fails if it constructs one, and the fact API does not emit it. No number of the optional live traffic provider is a fact: a tile is a picture layer and no numeral is read from it, a traffic-aware area is session geometry with a provenance note (DAT-163), and the minutes of a drive-time area are the user's own request. | A fact whose value is read from a provider tile or response fails. Every fact in the golden set resolves the complete chain; every non-ratio protected fact resolves one `single` home-family tuple; each ratio-statistic fixture resolves numerator and denominator tuples from the same stored rows. Planted missing or inconsistent table, partition, applicable measure, breakdown, family role, method version, publisher, dataset or page, licence, retrieval date and file-hash links each fail both build and API validation. A ratio whose rows or unit set differ, a ratio outside the closed list with two families, a card whose count and adjacent non-ratio shares have different home-family tuples, and a layout that places two routes to one population side by side all fail validation. |
| DAT-95 | The schema allows exactly the three pinned evidence statuses. "Not measured" is a display state rendered from the coverage key `not_measured`, never an evidence status (ASSUMPTION: keeps the pinned field list intact). | Enumeration check. |
| DAT-134 | Difference, ratio, rank and direction are comparison fact kinds. Difference keeps the compared measure's unit; ratio uses `ratio`; rank uses the positive-integer unit `rank`; direction uses `direction` with value `higher`, `lower` or `equal` (ASSUMPTION: the master design names the kind but not its wire values). Comparison facts are produced only by deterministic, tested functions in `eii_core.calc`, validate against the same fact schema and complete Source-chain rule as every other fact, and enter claim slots by fact id. A model, template or browser never computes or selects their values. A rank or fit fact is emitted only with the criterion values, the weights and the rank-stability facts of MTH-45 beside it ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 5). A forecast, a base rate or a site estimate may be a criterion ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 13) only with its value, its weight and its interval, range or count facts beside the rank, each removable by the user; a forecast or base rate ranks only candidates on its series' own geography, or enters as an apportioned count where card C18 allows one (DAT-147), and the site estimate, and any criterion with a Simulated or Synthetic input, is off in public-only mode. No Public split by sex or nationality and no whole-cell sum of `pub_pop_agesex_grid` is a criterion. | One regression for each comparison kind and each direction value; fixtures produced by a model, template or browser fail the calculation-origin check; a rank fixture without its criteria, weights or stability facts fails; a rank whose criterion is a forecast, base rate or estimate shown without its interval, range or count facts, a split-table or grid-sum criterion, and a site estimate in a public-only rank fail. |
| DAT-135 | Every answer receipt carries `accounting_gate` with label `Checked before display`, overall `result` (`pass` or `fail`) and exactly five checks in this order: `Sources`, `Assumptions`, `Nothing invented`, `Scope`, `Limits stated`. Each check is `{name, result}`, with `result` equal to `pass` or `fail`. A failed check selects the template writer's default answer and is retained in the receipt. | Exact-schema and order test; one planted failure per check proves the failed result, default answer and retained receipt. |
| DAT-144 | A projection ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 11) is computed only by `eii_core.calc` over a published or released series. Its fact has `evidence_status` `inferred`, the caveat key `projection_not_forecast`, a `period` after the last period of the series, and a lineage naming the projection method and version and the series it extends. The projection is never applied to a revenue, demand or success measure, and it is never called a forecast; a forecast (DAT-158), a base rate (DAT-159) and an estimate (DAT-161) are separate fact kinds with their own rules ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md)). | Fixtures: a projection marked `observed`, without the caveat, without method lineage, or of a revenue, demand or success measure fails; a projection that carries `forecast_backtest_range`, and a forecast that carries `projection_not_forecast`, fails. |
| DAT-155 | A field of a Public source that a tool returns for display, whose published value is a date or a text that holds a digit, is a fact in one of four closed units, so that every digit on screen stays in a Fact chip ([08_BACKEND.md](08_BACKEND.md) BE-114). A retrieval date and the label of a time control are not such fields ([10_FRONTEND.md](10_FRONTEND.md) FE-122). `calendar_date` holds `YYYY-MM-DD`, `calendar_month` holds `YYYY-MM` and `calendar_year` holds `YYYY`, each as a string at exactly the precision the source gives: a value is never padded to a finer precision (a month never becomes its first day) or cut to a coarser one, and `eii_core` rejects a day that its month lacks, the 29th of February outside a leap year included. `published_text` holds a Public field exactly as published when its value holds a digit, such as a project code: 1 to 200 characters (ASSUMPTION: long enough for a published field; a longer value is not a chip); at least one digit, every digit a Western digit (U+0030 to U+0039); no leading or trailing white space; no character of Unicode category Cc, Cf, Zl or Zp, so that it shows on one line in the chip's own isolate; and no run of exactly eight or eleven digits (DAT-15). A field without a digit is a label, never a `published_text` fact. A fact of these four units is read from a Public source: its provenance is `public`, its input classes are `public` alone, its evidence status is `observed`, its reliability is `not_applicable`, and its value equals the stored field character for character. The schema checks the forms, the provenance, the status and the parts of the character rules that a portable pattern can state; `eii_core` checks every rule in full, the calendar day and the Unicode categories included; a fact that fails either check is dropped under DAT-90 and is never shown as a label instead. The Fact chip shows a date unit at the precision the fact carries, with no grouping, and `published_text` verbatim ([10_FRONTEND.md](10_FRONTEND.md) section 5). | Schema-conformance fixtures: `2025-03-14` and `2024-02-29` as `calendar_date`, `2025-03` as `calendar_month`, `2025` as `calendar_year` and the illustrative code `EXAMPLE-07` as `published_text`, each Public, observed and `not_applicable`, pass. Each of these fails: `2025-02-29`, `2025-04-31`, `2025-3-14`, `14/03/2025` and `2025-03` as `calendar_date`; `2025-13`, `2025-3` and `2025-03-14` as `calendar_month`; `25`, `0999` and the JSON number 2025 as `calendar_year`; as `published_text`, a value with no digit, an empty value, a leading or trailing space, a line break, a bidirectional control character, an Arabic-Indic digit, a value of 201 characters, and a run of exactly eight and one of exactly eleven digits, both built at run time ([12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md) TST-09); and a fact of any of the four units whose provenance is `synthetic`, whose input classes hold more than `public`, whose evidence status is `inferred` or whose value is null. A tool fixture that returns the stored `announced` value `2025-03` of `fdi_projects` as `calendar_date` `2025-03-01`, or any value that differs from its stored field, fails. |
| DAT-158 | A forecast of a published series ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 2 to 6, card C30 of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md)) is computed at request time by `eii_core.calc` from release tables, as a projection is (DAT-144), and is never written to the release; it is computed over a series of the closed, versioned list of C30, read through one series contract (series key, source table, geography, ordered periods, values, unit). The list holds Public series whose source table is held by the release, and the released monthly series of the window: pay level, earner count and wage bill, the stayer index at municipality level, and establishments and employment by area (item 6). A series of the owner's list for which [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) holds no source table is listed there as open and is not on the list of C30, so it gets no forecast. The model is chosen by the rolling-origin backtest of C30 and by nothing else (MTH-98); a series too short for the backtest minimum gets no fact and the `NO_DATA` template with the reason key `series_too_short`, never a model without a backtest. A point forecast below zero for a series that cannot be negative gets no fact and the `NO_DATA` template with the reason key `forecast_below_zero` (card C30). A forecast is one set of facts from one computation, each fact with the same qualifiers, with the metric keys below: the forecast value, the two interval ends, the measured backtest error, the number of backtest points and the two counts of the interval caption. The class of a forecast is the class of its series (DAT-91): Public for a Public series and Synthetic for a released monthly series. Each fact is Inferred in status (the caveat key `forecast_backtest_range` forces it in the schema), has the subject and geography of its series and, as its `period`, the period it forecasts; its `fact_id` qualifiers hold the model key and the horizon (DAT-93). A forecast of a released monthly series is a fixed function of rows that are already released: it is a labelled projection from the released months, not a protected statistic of a later month (PRV-54). It is called a forecast, its subject is the `area` of its series, its origin is the last released month, and beside `forecast_backtest_range` it carries the existing caveat keys of a Synthetic series, `synthetic_not_evidence_about_qatar` and `synthetic_change`. A series with a carried-forward month in its window is not forecast and returns the suppression `CARRIED_FORWARD` (DAT-130), as card C21 rules for projections. A forecast of a Public series stays on its series' own geography; it reaches a drawn area only as an apportioned Inferred fact where card C18 allows one (DAT-147), and the forecast of a Public split series stays on the source's own geography and categories (DAT-141). Its lineage names the method and its version and the series (its release table), as for a projection (DAT-144), and resolves to the source (DAT-94; for a released series, to the protected table and home family that DAT-94 requires); the interval ends, the backtest error and the number of backtest points are facts of the same computation, shown with it. The interval is empirical, built from the backtest's own errors at each horizon, and is never called a probability or a confidence level. Rows `UNDATED` of `pub_licence_cancelled` never enter a series; a `bulk_month` and the incomplete issued series are handled by the stated rule of the card, every licence forecast carries the incompleteness note (PUB-69, PUB-94), and no net series of issues minus cancellations is formed. A forecast of a released series is off in public-only mode as a ranking criterion (DAT-134). A forecast of announced investment by sector keeps the caveat key `fdi_estimates` on its capex or jobs facts (DAT-142), and no forecast output of a source whose `commit_allowed` is false is committed (DAT-85). | Fixtures: a forecast of a series off the list, of a series without a held table, or of a Simulated series fails; a forecast of a released monthly series that is marked Public, lacks `synthetic_not_evidence_about_qatar` or `synthetic_change`, has a subject other than `area`, has an origin other than the last released month, or is a protected statistic of a later month fails; a released series with a carried-forward month in its window returns `SUPPRESSED` with `CARRIED_FORWARD` and no forecast; a series below the minimum returns `NO_DATA` with `series_too_short` (shown as "not enough history") and no fact; a forecast with no interval end, backtest error, backtest points or caption count, with `forecast_inside` above `forecast_tested`, marked `observed`, without `forecast_backtest_range`, with `projection_not_forecast`, or without method or series lineage fails; a model chosen by anything but the backtest, a series built from `UNDATED` rows, a bulk month outside the rule of the card and a net series each fail; a forecast of a split series on an `area_shape` geography without `apportioned_from` fails; the same series and release give the same ids. |
| DAT-159 | An entry, closure or survival base rate (item 7, card C31) is computed by `eii_core.calc` from the Public licence tables only (`pub_licence_active`, `pub_licence_issued`, `pub_licence_cancelled`), by activity and on the source's own geography, never for a drawn area. It is a set of facts: the share (`base_rate_share`) beside its numerator, its denominator, its period and, where the numerator does not exceed the denominator, the two ends of its Wilson interval (`base_rate_numerator`, `base_rate_denominator`, `base_rate_low`, `base_rate_high`, and the facts' `period`). The entry and closure base rates are flows over the published active stock of the same activity and geography (`pub_licence_active`), labelled approximate by card C31, each with its two counts and its period. The survival base rate returns `NO_DATA` with the reason key `no_denominator`, because the Public licence tables do not link a cancellation to its issue, until a Public source does (an OPEN line); no survival figure is promised or shown. Wherever else the Public tables do not carry the denominator, the answer is likewise `NO_DATA` with `no_denominator`. Rows `UNDATED` never enter it, a `bulk_month` is handled by the stated rule of the card, and every rate built on the issued series carries the incompleteness note and covers only the codes that series covers (PUB-69, PUB-94). Nothing is computed from the Synthetic births and closures (`openings` and `closures` of `month_change`), and no figure of issues minus cancellations is formed. The facts are Public in provenance and carry the caveat key `base_rate_not_your_chance`: the rate is a share of past licences of that activity and area, never the chance that the user's own venture survives. Its evidence status is Observed: a base rate is a Public fact with evidence status Observed, the status of the churn rate of card C2 (fixed arithmetic over published counts, caveat `calculated`), and it carries the caveat key `base_rate_not_your_chance`. | Fixtures: a rate from a Synthetic table or from `month_change`, for a drawn area, with no numerator, denominator or period, or without `base_rate_not_your_chance`, or with an evidence status other than Observed, fails; a survival base rate that returns a number, and a rate whose denominator no Public table carries that returns a number instead of `NO_DATA` with `no_denominator`, fail; `UNDATED` rows or an unflagged bulk month counted in a rate, a rate on the issued series without its incompleteness note, and a net figure each fail. |
| DAT-160 | The people present by pay band through the day (items 11 and 12, card C32, PRV-126) are computed by `eii_core.calc` in the product plane for a whole release unit, a day type and an hour, as a fixed function of published rows only: the published `presence_count` groups of the unit's cells, and the published pay-band shares of the same unit (one protected band family per segment: `wp_all_quartile` for workers present, `rp_all_quartile` for residents present). No table and no band dimension is added to the release, and `presence_count` keeps its key (DAT-138); mobility still meets wage statistics only area to area. The figure is returned only when every row it draws on is published; a withheld, suppressed, carried-forward or remainder row is never filled in, and the figure passes through the suppression reason of the row that is missing (`BELOW_PANEL_MINIMUM` for a presence group). Visitors have no pay band: their count is the presence fact of the visitor segment, without a band. People who have no wage record are not separated, which the caveat key `present_by_pay_band_assumed` states. The fact has the metric key `present_by_pay_band`, unit `count`, geography kind `release_units` on the snapped unit list (PRV-18) and is never apportioned to a drawn outline; its provenance is Simulated through DAT-91, its status Inferred, its subject `area`, and it carries the caveat key `present_by_pay_band_assumed`. Its label reads as estimated people and never as spending, spending power, income present or purchasing power. Its lineage names the method and both published inputs as PRV-126 fixes it, `presence_count` and the band family of each segment with their lineage roles; that figure is the one closed presence/pay case of DAT-94 (PRV-30). | Fixtures: a figure that draws on a withheld, suppressed, carried-forward or remainder row, with that row filled in as zero or from another unit, fails; a visitor row given a band fails; a figure on an `area_shape` geography, a band column or table in the release, a figure read from a feed row or an untreated primitive, and a label that names spending fail; the attack suite treats the figure as a function of observable release fields (PRV-126). |
| DAT-161 | A site demand and revenue estimate (item 8, card C33) is computed by `eii_core.calc` for an area or pin that the user chose, and its subject is `area`: it is never an estimate for a named real building or business, and no figure for a named competitor is computed for display, shown, stored or logged. It is three facts, `estimate_low`, `estimate_middle` and `estimate_high` (fixed percentiles of the draws of a seeded Monte Carlo over the stated ranges of the model's uncertain parameters, so cases of the model), and the facts of its main drivers: the `estimate_driver_swing` facts of a one-at-a-time swing computed in code, with the rank facts that order them and the stability facts that DAT-134 requires beside a rank. Its inputs are the facts of DAT-160, the competitors of `pub_place` and `pub_place_fsq` as counts and distances, and category spend ranges calibrated to the `sec_hr_size` rows of `pub_establishment_size`; the spend per person by band is a stated, visible and editable range of the model and is never called spending power. The seed, the draw count and the model parameters are `qualifiers` of each `fact_id` (DAT-93), so the same inputs give the same id and different inputs a different one. Provenance is the least-real class of the inputs (DAT-91), so Simulated while it reads DAT-160; the status is Inferred, a pin or typed range is a user input (DAT-92), and each of the three facts carries the caveat key `estimate_on_simulated_inputs` while any input is Simulated or Synthetic. An input that DAT-160 or DAT-147 returns as `BELOW_PANEL_MINIMUM` makes the estimate `NO_DATA` with that reason, never zero. The estimate fills `area` slots only, is off in public-only mode, and is unavailable while OI-03 keeps the survey figures off screen. | Fixtures: an estimate for a `place_public`, `fdi_project` or `register_company` subject, a figure for a named competitor, and an estimate stored in a table, log or ledger fail; an estimate without any of its three cases, with a driver not computed by the swing, or with Simulated inputs and no `estimate_on_simulated_inputs` fails; a spend range that is not a visible, editable input fails; two runs with the same seed give the same ids and a changed seed a different id; an estimate in public-only mode, and one while OI-03 is open, fail. |
| DAT-162 | The catchment-share scenario (item 9, card C34) and the revenue range of the user's outlet (item 10, card C35) are the user's scenarios, computed by `eii_core.calc` from typed user inputs of the closed list of scenario inputs, which decision 0019 item 10 extends, and from released facts. C34 gives `catchment_share_outlet`, the share of the user's outlet, and `catchment_share_competitors`, the share of the competitors split by competitor category and by distance band (unit `percent`), from distance and an attractiveness that the user sets for the outlet against the competitors as a group or by competitor category. `catchment_share_competitors` is one fact for each cell of the split, and the `qualifiers` of its `fact_id` (DAT-93) hold the competitor category and the distance band, never a place key (for example Italian restaurants within 500 m; other restaurants). The categories come from the reviewed category mapping of the places layer, with `other`; the distance bands are a closed list of the card (ASSUMPTION: within 500 m, 500 m to 1 km, 1 km to 2 km, beyond). A cell that holds a single competitor is merged into the next wider cell (the same category in the next distance band, then `other`) before any fact is made, so no fact stands for one competitor. Where `other` still holds a single competitor after the merges, no cell fact is made and the one `catchment_share_competitors` fact is the share of all competitors together, without those qualifiers; with one competitor in all, no `catchment_share_competitors` fact is made (card C34). No share, revenue or other figure is computed for one named competitor, which keeps only its Public facts and its distance. C35 gives `scenario_low`, `scenario_middle` and `scenario_high` (unit `qar`) and the break-even point, which is the break-even fact of card C4 and not a new metric key, from the Public survey benchmark of `pub_establishment_size`, the simulated people present at area grain and the user's capture rate and average bill. Every assumption is a visible, editable typed input. Each fact carries `user_input`, the caveats `your_inputs` and `scenario_not_forecast`, and the status Inferred, is never written to the release or the store (DAT-92) and is never called a forecast. A fact that draws on a Simulated or Synthetic input has that provenance (DAT-91) and fills an `area` slot, never a `scenario` slot (DAT-145). Like the break-even calculator, both stay off screen while OI-03 is open. | Fixtures: a share or revenue attributed to one named competitor, a competitor share keyed by a place or whose cell holds a single competitor and was not merged into the next wider cell, a category or distance band outside the closed lists, a competitor share given only as one figure for all competitors together although every cell of its split holds two or more competitors, a competitor share for a list of one competitor, a scenario fact without `scenario_not_forecast`, `your_inputs` or `user_input`, marked `observed`, or carrying `forecast_backtest_range` fails; a fact with an assumption that the user cannot see and change fails; a scenario fact stored in a table, and a Simulated-input scenario fact in a `scenario` slot, fail; a scenario while OI-03 is open fails. |

The metric keys of the facts above are a closed list, and every fact of them validates against the
fact schema like any other (DAT-90). An unknown metric key or an unknown qualifier fails, as for
every closed list, and a forecast emitted without one of its companion facts fails; one planted
fixture proves each refusal. The caveat keys are the fixed sentences of
[11_DESIGN_DIRECTION.md](11_DESIGN_DIRECTION.md) and slots of the catalogues of
[09_AI_ASSISTANT.md](09_AI_ASSISTANT.md); the Arabic sentence of each is pending native review.

| Metric key | Unit | Value | Fact of |
|---|---|---|---|
| `forecast_value` | the unit of the series | number | DAT-158: the forecast for the period of the fact |
| `forecast_low`, `forecast_high` | the unit of the series | number, `forecast_low` at most `forecast_high` | DAT-158: the interval ends at that horizon |
| `forecast_backtest_error` | `ratio` | number, 0 or more | DAT-158: the backtest error of the chosen model, by the one measure of C30 |
| `forecast_backtest_points` | `count` | integer, 1 or more | DAT-158: the number of backtest points |
| `forecast_inside`, `forecast_tested` | `count` | integers, `forecast_inside` at most `forecast_tested` | DAT-158: the two counts of the interval caption, how many past values fell inside the range that the other past errors gave, of how many tested |
| `base_rate_share` | `percent` | number | DAT-159 |
| `base_rate_numerator`, `base_rate_denominator` | `count` | integers, the denominator above 0 | DAT-159 |
| `base_rate_low`, `base_rate_high` | `percent` | numbers, `base_rate_low` at most `base_rate_high` | DAT-159: the ends of the Wilson interval of card C31, present only where the numerator does not exceed the denominator |
| `present_by_pay_band` | `count` | integer | DAT-160: one fact for each segment (`worker`, `resident`), pay band and bound (`estimate`, `low`, `high`), the three in the `qualifiers` |
| `estimate_low`, `estimate_middle`, `estimate_high` | `qar` | number, in that order not decreasing | DAT-161 |
| `estimate_driver_swing` | `qar` | number, 0 or more | DAT-161: the swing of one uncertain parameter of card C33, with the parameter key and its rank in the `qualifiers` |
| `catchment_share_outlet` | `percent` | number | DAT-162 (C34): the share of the user's outlet |
| `catchment_share_competitors` | `percent` | number | DAT-162 (C34): one fact for each cell of the split by competitor category and distance band, the category and band in the `qualifiers`, never a place |
| `scenario_low`, `scenario_middle`, `scenario_high` | `qar` | number, in that order not decreasing | DAT-162 (C35) |
| `venue_busyness_index` | `relative_index` | integer, 0 to 100 | DAT-157 (card C37): the published index of one venue, day of week and hour |
| `night_lights_radiance` | `radiance_nw_cm2_sr` | number, 0 or more | DAT-157 (card C36): the value of a frame cell and month, or the mean of card C36 for an area |
| `population_grid_people` | `count` | integer | DAT-157 (card C38): the sum of whole cells for an area and year, with the age band and the sex in the `qualifiers` |

| Caveat key | Carried by |
|---|---|
| `forecast_backtest_range` | every fact of a forecast (DAT-158) |
| `estimate_on_simulated_inputs` | the three cases of a site estimate while an input is Simulated or Synthetic (DAT-161) |
| `scenario_not_forecast` | every fact of a scenario (DAT-162) |
| `base_rate_not_your_chance` | every fact of a base rate (DAT-159) |
| `present_by_pay_band_assumed` | the figure of people present by pay band (DAT-160) |
| `relative_busyness_not_people` | every fact from `pub_venue_busyness` (DAT-157) |
| `night_lights_not_activity` | every fact from `pub_night_lights` (DAT-157) |
| `live_traffic_provider` | every fact computed over a traffic-aware area from the provider (DAT-163) |
| `grid_cells_summed` | the whole-cell sum of `pub_pop_agesex_grid` (DAT-141) |

**Example 1, Public (illustrative values).** Zone 69 electricity use, 2025 against 2021: 3.34 times
(master design section 9, Qatar Open Data Portal, CC BY). Identifiers are examples.

```json
{"fact_id": "f_ab3c9e1d7f2a4b6cab3c9e1d7f2a4b6c", "value": 3.34, "unit": "ratio", "period": "2021/2025",
 "geography": {"kind": "public", "public_code": "zone:69"},
 "provenance": "public", "input_classes": ["public"], "evidence_status": "observed",
 "reliability": "not_applicable", "coverage_keys": [],
 "caveat_keys": ["activity_proxy_not_population"],
 "label_en": "Electricity use, 2025 against 2021",
 "label_ar": "<Arabic label, pending native review>",
 "lineage_ref": "lin_pub_zone_utility", "release_id": "5f2c9ab04e7d1c3a5f2c9ab04e7d1c3a5f2c9ab04e7d1c3a5f2c9ab04e7d1c3a"}
```

**Example 2, Synthetic composite (illustrative values).** Median net pay band of covered earners
living within a five-minute walk. It combines band counts from `resident_pay` (Synthetic) over three
units with the band boundaries of section 5 (Public), so its chip shows Synthetic and its drawer lists
both classes. "Observed" here means read from the release; it does not mean real.

```json
{"fact_id": "f_9c4e2a7b1d0f6e3a9c4e2a7b1d0f6e3a", "value": "B03", "unit": "wage_band", "period": "2025-11",
 "geography": {"kind": "release_units",
               "unit_ids": ["rp_all_money:m:000042", "rp_all_money:c:000107", "rp_all_money:c:000108"]},
 "provenance": "synthetic", "input_classes": ["synthetic", "public"], "evidence_status": "observed",
 "reliability": "standard", "coverage_keys": ["covered_private_sector_only", "not_measured_shown"],
 "caveat_keys": ["synthetic_not_evidence_about_qatar"],
 "label_en": "Median net pay band, covered earners living within reach",
 "label_ar": "<Arabic label, pending native review>",
 "lineage_ref": "lin_resident_pay", "release_id": "5f2c9ab04e7d1c3a5f2c9ab04e7d1c3a5f2c9ab04e7d1c3a5f2c9ab04e7d1c3a"}
```

### 9.1 Subjects

Every claim and component slot of the assistant catalogues has a subject
([09_AI_ASSISTANT.md](09_AI_ASSISTANT.md)). The subject decides which facts may fill its slots. The
validator reads it from the resolved subject and the fact's fields, never from wording
([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 20,
[decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 9).

| Subject | Names | Identified by | Accepts |
|---|---|---|---|
| `area` | a drawn, radius or travel-time area, or the release units of an evidence block | `area_id` | Public, Synthetic, Simulated and Suppressed facts, observed or inferred. Inferred includes a Public or Simulated figure apportioned to the area (DAT-147). |
| `place_public` | a real named public place: a gazetteer entry, a `pub_place` or `pub_place_fsq` record, or a venue of `pub_venue_visits` or `pub_venue_busyness` | `place_key`, `place_id`, `fsq_place_id` or `venue_key` | Public facts only; for a named competitor of the catchment-share scenario (DAT-162) also its distance from the user's outlet, whose inputs are Public and the user's own point. No share, score or estimate is attached to it. |
| `register_company` | one real company of the public business register or of the financial centre's public register, a row of `pub_register_company` ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)) | `registration_number`, which the application resolves and never sends to the model or writes to an egress record, a ledger row or a log | Public facts of `pub_register_company` (the fields the register publishes, person names excluded); the Synthetic fact `employee_count` of its row in `register_company_list`; and, in a list, the rank and fit facts that tested code computes over the card fields, the employee count, Public inputs such as free-flow drive time and the user's typed criteria and weights, with the stability facts of DAT-134. Never a Simulated fact, an estimate, share or score, or a wage, wage bill or other labour or residence fact of the company: those appear only in released aggregates of `area` subjects, and in the oversight seat and the company's own seat only as their designs provide (rule 8 of AGENTS.md). |
| `fdi_project` | one published investment announcement of `fdi_projects` | `project_key` | Public facts only, read from `fdi_projects` and its source; never a fact computed with a synthetic, protected or simulated input |

The other subjects of the claim catalogue accept Public facts only, including, for `scenario`, the
user-input facts of DAT-92 whose provenance is Public; a scenario fact that draws on a Simulated or
Synthetic input fills an `area` slot instead (DAT-162). A Suppressed fact may fill a slot whose
subject accepts the class the fact would otherwise have. No Synthetic or Simulated fact, and no
estimate, share, score, rank or fit, fills a slot whose subject is a real named place, building,
business or project ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md)
item 1). The one exception is the `register_company` subject, which accepts its employee count and,
in a list, its rank and fit facts, as its row states ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) items 4 and 5). The
subject `synthetic_firm` of the named synthetic firms is retired by decision 0022, and the validator
rejects it (DAT-145).

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-145 | Subjects and the facts they accept are exactly those of section 9.1. The validator rejects a Synthetic or Simulated fact in any slot whose subject is not `area` or `register_company`; in a `register_company` slot, a Simulated fact, a Synthetic fact other than its `employee_count` and its list rank and fit facts, an estimate, share or score fact, and a wage, wage bill or other labour or residence fact of the company ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) items 4 and 7); a fact about one register company's employee count outside a `register_company` slot; an estimate, share or score fact (DAT-161, DAT-162) in a slot whose subject is a `place_public`, `fdi_project` or other real named place, building, business or project; a `register_company` subject whose key is not a `registration_number` of the mounted `pub_register_company` (a `SYN-` key, an `fk_` key or a number absent from the table); the retired subject `synthetic_firm`; and an `fdi_project` slot whose fact lineage names a table other than `fdi_projects`. A rejected response gets one repair, then the template fallback. | One fixture for each rejected combination, a `synthetic_firm` subject, a `SYN-E-` or `fk_` subject key, a key absent from the mounted table, a wage fact of one company in a `register_company` slot and an estimate in a competitor's `place_public` slot included; each accepted combination passes, a `register_company` subject of the mounted stand-in register with its Public card facts, its employee count and a list rank included; changing only the label text changes no decision. |

### 9.2 The area record

An area is a polygon the user draws, a radius from a point, or a walk or drive time from a point; a
drive time can be taken at an hour of day
([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 6). With the optional
live traffic provider, a traffic-aware drive-time area is a second route into the session, through the
adapter, and is registered as a session polygon (DAT-163). `make_area`
returns one area record for each request. Its JSON Schema is `contracts/area.v1.schema.json`.

| Field | Content |
|---|---|
| `area_id` | the identifier that `make_area` returns ([08_BACKEND.md](08_BACKEND.md)); the same request on the same release gives the same id |
| `release_id` | the mounted release |
| `shape` | `polygon`, `radius`, `walk` or `drive` |
| `request` | exactly the fields of its shape, with values from the closed lists of [08_BACKEND.md](08_BACKEND.md): `shape_id` (the SHA-256 of the canonical polygon that the user drew and the session registered, EPSG:4326); or `point` (latitude and longitude, or a gazetteer key) with `radius_m` for `radius` or `minutes` for `walk` and `drive`; for a `drive` at an hour of day, `day_type`, `hour` and `summer`; for a `drive` at a dial situation, `situation` and `summer` |
| `anchor_cell` | the base cell of the point; for a drawn polygon, the base cell of its representative point ([08_BACKEND.md](08_BACKEND.md), `eii_core.shapes`). A drawn polygon snaps as drawn, with no anchor (PRV-17, PRV-18). |
| `requested_shape` | GeoJSON geometry of the shape the request produced: the polygon, the circle or the travel-time outline |
| `traffic` | `free_flow`; the `traffic_hourly` key (`day_type`, `hour`, `summer`) of a drive at an hour of day; or, for a drive at a dial situation, `situation` (one of the four situation keys of DAT-76) and `summer` (a value that `situation_windows` allows for that situation), for which the outline takes on each road link the speed of the link's length over the arithmetic mean of the link's times over the hours that `situation_windows` gives the situation, on its day type and that summer setting, rounded half-up to a whole km/h, a link without a `traffic_hourly` row at an hour taking its free-flow time for that hour ([decision 0021](decisions/0021-one-speed-for-a-link-and-an-hour.md) item 8) ([07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) C25) |
| `protected` | absent in public-only mode; otherwise one entry for each evidence block: `block`, `partition_id`, `tier`, sorted `unit_ids`, `unit_set_sha256` and the snap report of PRV-22, with the note code `SNAPPED_TO_WHOLE_UNITS` (the snap sentence) |
| `apportioning` | present when a figure is apportioned to the area: the method key and version of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md), and the identifier and weight of each release unit or official geography that the shape intersects |
| `provider_note` | present only on an area that entered through the provider adapter (DAT-163): an object with no additional properties and exactly five required fields — `provider` (the literal `tomtom`), `request` (an object with no additional properties and exactly three required fields: `latitude`, a number from -90 to 90; `longitude`, a number from -180 to 180; and `minutes`, one of 5, 10 and 15, the drive cut-offs of [08_BACKEND.md](08_BACKEND.md); it holds no key, no token and no other field), `retrieved_at` (a UTC timestamp), `response_sha256` (64 lowercase hexadecimal characters) and `attribution` (the literal `© TomTom`); absent on every other record |

Only figures from the protected record types (business register, employment, residence, wages)
snap to whole release units. They read the `unit_ids` of a `protected` entry and carry its snap
report. Public point layers and the Simulated road links of `traffic_hourly` are selected by the
exact `requested_shape`, and so are the whole cells of `pub_pop_agesex_grid` whose centres lie inside
it (DAT-141). Public statistics and the Simulated presence and flow counts reach the area
only by apportioning (DAT-147); the whole-cell sum of that grid is not an apportionment. A drawn
shape, an area from the provider adapter and their records live only in the session store of the
session and seat that drew or requested them; no `app` table holds either (DAT-149).

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-146 | A request carries exactly the fields of its `shape`. A drawn polygon is valid, has one outer ring and no hole, lies inside the frame and keeps within the vertex and size limits of [08_BACKEND.md](08_BACKEND.md); no request is the complement or the difference of other areas. The record is a deterministic function of the request and the mounted release: the same request gives a byte-identical canonical record and the same `area_id` (PRV-19). A protected table is read only through the `unit_ids` of a `protected` entry, never through a shape, cell or coordinate (BE-54). An outline built with `traffic_hourly`, at an hour or at a dial situation, gives every fact computed for the area the provenance Simulated through the least-real rule (DAT-91, SYN-54); a traffic-aware area from the optional provider is not such an outline but a registered polygon (DAT-163). In public-only mode the record has no `protected` entry (BE-105). | Schema fixtures for each shape; a polygon with a hole, a multipolygon, a self-intersecting ring and a point outside the frame each fail; a complement request fails; a `traffic` field with an unknown situation key, or with a `summer` value that `situation_windows` does not allow for its situation (`ramadan_iftar` with `summer = true`), fails; repeated requests give byte-identical records; a protected read without a `protected` entry fails; a fact for a traffic-dependent outline whose provenance is not Simulated fails. |
| DAT-147 | A Public statistic stays on its official geography. When `eii_core.calc` apportions one to an area, the fact has geography kind `area_shape` with `apportioned_from` naming the official geography, `evidence_status` `inferred`, the caveat key `apportioned_estimate`, and a lineage naming the apportioning method and version ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 6). Released `presence_count` and `flow_hourly` estimates reach a drawn area the same way, with `apportioned_from` `release_units`, as post-processing of published leaves only; a value that draws on a withheld presence group returns `BELOW_PANEL_MINIMUM` (PRV-58, PRV-122). No fact from a Protected table has geography `area_shape`, and no row of a Public split table is apportioned (DAT-141); the sum of whole cells of `pub_pop_agesex_grid` over an area is not an apportionment, has no `apportioned_from`, and follows DAT-141, and so is the mean of the `pub_night_lights` frame-cell values whose centres lie inside an area, each cell counted once, Public and Observed with the caveat keys `calculated` and `night_lights_not_activity` and no `apportioned_from` (card C36, DAT-157). | Fixtures: an apportioned fact marked `observed`, without `apportioned_from`, without the caveat or without method lineage fails; an apportioned value over a withheld group that is not `BELOW_PANEL_MINIMUM` fails; a protected-table fact with `area_shape` fails; an apportioned split row fails, including one of `pub_pop_agesex_grid` that is weighted by area instead of summed by whole cells; a `pub_night_lights` area figure that sums the cells, is apportioned or carries `apportioned_from` fails, and the mean over the frame-cell values 4 and 10 renders 7, with `NO_DATA` where no value exists (card C36); an exact-shape count of Public points passes as `observed`. |
| DAT-163 | With `EII_TRAFFIC_PROVIDER` set to `tomtom`, the key present and the presenter's offline control not set (ARC-135), a traffic-aware drive-time area may enter the session through the provider adapter, a second route beside the user's drawing ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 17). The adapter registers the returned outline as a session polygon, bound to the session and seat like a drawn shape: its record has shape `polygon` and `request.shape_id`, meets the validity rules of DAT-146 for a drawn polygon, and carries the `provider_note` of 9.2: the closed object with `provider` `tomtom`, the typed `request` (the resolved point and the minutes, no key), `retrieved_at`, `response_sha256` and the attribution `© TomTom`. The area is geometry and not a fact; the minutes are the user's own request, and no numeral of a tile or response is a fact (DAT-94). Nothing of a response is written to disk, to the release, to the ledger, to an `app` table or to a log (DAT-149); the note lives in the session store with the record, and a ledger row carries only the `shape_id`. A figure computed over the area follows the rules of a drawn shape (DAT-147), carries the least-real class of its released inputs (DAT-91) and the caveat key `live_traffic_provider`; a figure over a stored session area is repeatable for that area. With the default provider the record is as DAT-146 states, and a test, a gate, a command or the guided story never needs the provider: tests build the response from hand-made fixtures in the documented format, and no response is committed. | Fixtures: an adapter area without `provider_note`, one whose note is missing a field, carries an extra field or a malformed `retrieved_at` or `response_sha256`, one whose `request` is not an object, lacks `latitude`, `longitude` or `minutes`, carries a further field, holds a latitude or longitude outside its range or minutes other than 5, 10 and 15, one that does not pass DAT-146 as a polygon, one whose note holds a key or token, and a figure over it without `live_traffic_provider` fail; a response, or a hash of one, found in a release, ledger row, `app` table or log, and a numeral read from a tile or response as a fact, fail; with the switch `simulated`, the key absent or the offline control set, an adapter request fails with no outbound call; a repeated request for a stored session area gives the same figures; a test that calls the live service, or a committed response, fails. |

## 10. The economic graph

Graph tables are plain node and edge tables. Traversals are bounded: at most four steps per query
and fifteen nodes per drawn path (master design section 4).

`graph_node`: `node_id` string (`<node_type>:<code>`); `node_type`; `code` string; `label_en`,
`label_ar` string; `provenance` (`public`, `lineage`); `source_id` string (Y, null for `release` and
`table` nodes).

| `node_type` | Code | Source |
|---|---|---|
| `activity` | commerce activity code (7-digit commerce code; mapping requires a valid four-digit ISIC class and recorded human approval; or 6-digit legacy) | public licence datasets |
| `activity_class` | ISIC Rev.4 class, plus the single node `UNMAPPABLE` | UN classification tables |
| `place_category` | public places taxonomy category | open places release; the reviewed category mapping of `pub_place_fsq` |
| `input` | reviewed basket input key (for example `pasta`) | reviewed basket configuration |
| `tariff_line` | tariff code at eight digits or finer (the heading 1902 also holds instant noodles; master design section 9) | public customs imports |
| `origin` | ISO 3166-1 alpha-3 country code | public customs imports |
| `source` | `source_id` | `source_registry` |
| `table` | release table name | manifest |
| `release` | `release_id` | manifest |

`graph_edge`: `edge_id` string; `edge_type`; `from_node_id`, `to_node_id`; `provenance` (`public`,
`lineage`); `basis` (`official`, `computed`, `editorial_reviewed`, `lineage`); `period` (Y);
`attr_value` decimal(18,4) (Y); `attr_unit` string (Y); `attr_value_2` decimal(18,4) (Y);
`attr_unit_2` string (Y); `source_id`.

| `edge_type` | From → to | Basis | Attributes |
|---|---|---|---|
| `classified_as` | `activity` → `activity_class` | `editorial_reviewed` (DAT-22) | none |
| `listed_as` | `activity_class` → `place_category` | `editorial_reviewed` | none |
| `needs_input` | `activity_class` → `input` | `editorial_reviewed` (basket) | none |
| `defined_by` | `input` → `tariff_line` | `editorial_reviewed` | none |
| `imported_from` | `tariff_line` → `origin` | `official` | value (QAR) and weight (kg), per `period` |
| `found_near` | `place_category` → `place_category` | `computed` (co-location quotient over public places of `pub_place` and `pub_place_fsq`, method in [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md)) | quotient and permutation p-value |
| `sourced_from` | any Public node or `table` → `source` | `lineage` | none |
| `contains` | `release` → `table` | `lineage` | none |

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-100 | An edge joins two Public nodes, or it is a lineage edge whose provenance is `lineage` and whose one end is a `source`, `table` or `release` node. | Edge check over the whole graph. |
| DAT-101 | No node or edge refers to a firm, establishment, legal entity, group or person, real or synthetic, a register company included ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)): no firm-level edges. | Build fails if any code matches `SYN-` or a registration number of `pub_register_company`, or any node type outside the table above exists. |
| DAT-102 | Every `activity` node has exactly one `classified_as` edge; legacy codes without a reviewed mapping point to `UNMAPPABLE` and stay visible. | Degree check. |
| DAT-103 | Every non-lineage edge has a `source_id` with a licence in `source_registry`. | Join check. |

## 11. Lineage and source registry

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-105 | Every release table has at least one `fact_lineage` row; every `lineage_id` lists each source and each input class that fed the table. That includes the Public calibration inputs of the Simulated tables, the pooled hourly shape of relative busyness and the weather profiles of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 18 and 23: their file hashes are rows of `source_registry`, and the provenance of the table stays Simulated (DAT-91). | Join `release_manifest` to `fact_lineage`; a Simulated table calibrated to either input whose lineage omits its source fails. |
| DAT-106 | Every source in `source_registry` has publisher, dataset or page title, licence, retrieval date and file SHA-256. A Public source also has its URL, which holds no key or token (rule 14). A Synthetic or Simulated source uses the feed producer as publisher, the contract and feed as title, the repository licence, the build date as retrieval date and the feed file hash; its seed remains provenance in the manifest rather than replacing any Source-chain field. | Not-null check for every source-chain field; Public URL check, where a URL that holds a key or token fails; Synthetic and Simulated feed-hash-to-registry check. |
| DAT-107 | The input class of a `fact_lineage` row follows the source kind: `public_dataset`, `public_document` and `reviewed_config` give `public`; `synthetic_feed` gives `synthetic`; `simulation_output` gives `simulated`. | Mapping check. |

## 12. The application schema (PostgreSQL only, schema `app`)

This is the one canonical DDL for the application schema. The forward-only migrations under
`infra/postgres/` must implement it verbatim in substance; [08_BACKEND.md](08_BACKEND.md) and all
other documents refer here rather than restating columns or policies. The fixed read-function names
are an ASSUMPTION: the master design pins their behaviour but not their names.
[Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) adds what the journeys
need: each playbook serves one journey, keyed `d1` to `d7`, or one case only; a brief can belong to
one of the four cases, keyed `c1` to `c4`; and the closed tool and playbook lists, which grow with
the journeys, live in two reference tables (DAT-148). No `app` table holds a drawn shape, an area
record or a case sample file (DAT-149). [08_BACKEND.md](08_BACKEND.md) lists the endpoints that
call these functions.

The application generates every application identifier as UUID version 7. The DDL deliberately has
no identifier defaults, so disconnected SQLite replay retains the identifiers assigned by the
application. `payload_bytes` holds the exact UTF-8 payload of a call that passed the egress scan;
`payload_json` is only an optional parsed projection of it. A call that the egress scan blocks keeps
none of its proposed payload: `payload_bytes` and `payload_json` are null, `fact_ids_sent` is empty,
and `payload_sha256`, the hash of the proposed payload, is all that identifies it (DAT-156). There
are no hash-chain fields: replay safety comes from stable UUIDv7 primary keys and idempotent inserts.

```sql
CREATE SCHEMA app;

CREATE TABLE app.organisation (
  organisation_id uuid PRIMARY KEY,
  display_name text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('company', 'ministry')),
  is_fictional boolean NOT NULL CHECK (is_fictional),
  created_at timestamptz NOT NULL
);

CREATE TABLE app.seat (
  seat_key text PRIMARY KEY CHECK (seat_key IN ('oversight', 'company_a', 'company_b')),
  organisation_id uuid NOT NULL REFERENCES app.organisation(organisation_id),
  role text NOT NULL CHECK (role IN ('company', 'oversight')),
  label_en text NOT NULL,
  label_ar text NOT NULL,
  UNIQUE (seat_key, organisation_id)
);

-- Closed lists (DAT-148): the migration that creates these two tables inserts exactly the tool
-- and playbook registries of 08_BACKEND.md; a registry change is a new migration.
CREATE TABLE app.tool_key (
  tool text PRIMARY KEY CHECK (tool ~ '^[a-z][a-z0-9_]*$')
);

CREATE TABLE app.playbook_key (
  playbook text PRIMARY KEY CHECK (playbook ~ '^[a-z][a-z0-9_]*$'),
  journey text CHECK (journey IS NULL OR journey IN
    ('d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7'))
);

CREATE TABLE app.brief (
  brief_id uuid PRIMARY KEY,
  answer_id uuid NOT NULL,
  organisation_id uuid NOT NULL,
  seat_key text NOT NULL,
  release_id text NOT NULL CHECK (release_id ~ '^[0-9a-f]{64}$'),
  language text NOT NULL CHECK (language IN ('en', 'ar')),
  playbook text NOT NULL REFERENCES app.playbook_key(playbook),
  case_key text CHECK (case_key IS NULL OR case_key IN ('c1', 'c2', 'c3', 'c4')),
  question_text text NOT NULL,
  brief_json jsonb NOT NULL CHECK (jsonb_typeof(brief_json) = 'object'),
  catalogue_version text NOT NULL,
  memo_key text NOT NULL,
  created_at timestamptz NOT NULL,
  FOREIGN KEY (seat_key, organisation_id)
    REFERENCES app.seat(seat_key, organisation_id)
);

CREATE TABLE app.ledger_entry (
  entry_id uuid PRIMARY KEY,
  occurred_at timestamptz NOT NULL,
  seat_key text NOT NULL,
  organisation_id uuid NOT NULL,
  brief_id uuid REFERENCES app.brief(brief_id),
  answer_id uuid,
  kind text NOT NULL CHECK (kind IN
    ('ask', 'tool_call', 'brief_saved', 'brief_not_visible', 'store_switch')),
  playbook text REFERENCES app.playbook_key(playbook),
  tool text REFERENCES app.tool_key(tool),
  arguments jsonb NOT NULL,
  question_text text,
  area_cell bigint,
  activity_key text,
  release_id text NOT NULL CHECK (release_id ~ '^[0-9a-f]{64}$'),
  engine text NOT NULL CHECK (engine IN ('postgres', 'embedded')),
  status text,
  fact_ids jsonb NOT NULL,
  writer text CHECK (writer IS NULL OR writer IN ('model', 'template', 'replay')),
  injection_flag boolean NOT NULL,
  origin text NOT NULL CHECK (origin IN ('live', 'seeded')),
  FOREIGN KEY (seat_key, organisation_id)
    REFERENCES app.seat(seat_key, organisation_id)
);

CREATE TABLE app.egress_record (
  egress_id uuid PRIMARY KEY,
  ledger_entry_id uuid NOT NULL REFERENCES app.ledger_entry(entry_id),
  answer_id uuid NOT NULL,
  request_ordinal integer NOT NULL CHECK (request_ordinal >= 1),
  seat_key text NOT NULL,
  organisation_id uuid NOT NULL,
  route text NOT NULL CHECK (route IN ('router', 'writer', 'repair', 'prewarm')),
  occurred_at timestamptz NOT NULL,
  sent_at timestamptz,
  model text NOT NULL,
  release_id text NOT NULL CHECK (release_id ~ '^[0-9a-f]{64}$'),
  prompt_version text NOT NULL,
  payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
  payload_bytes bytea,
  payload_json jsonb,
  fact_ids_sent jsonb NOT NULL,
  usage jsonb,
  stop_reason text,
  scan_result text NOT NULL CHECK (scan_result IN ('passed', 'blocked')),
  cost_estimate_usd numeric(18,8),
  UNIQUE (answer_id, request_ordinal),
  FOREIGN KEY (seat_key, organisation_id)
    REFERENCES app.seat(seat_key, organisation_id),
  -- DAT-156: a call blocked by the egress scan keeps only the hash of its proposed payload.
  CHECK ((scan_result = 'blocked') = (payload_bytes IS NULL)),
  CHECK (scan_result = 'passed'
         OR (payload_json IS NULL AND fact_ids_sent = '[]'::jsonb AND sent_at IS NULL
             AND usage IS NULL AND stop_reason IS NULL AND cost_estimate_usd IS NULL))
);

ALTER TABLE app.organisation ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.organisation FORCE ROW LEVEL SECURITY;
ALTER TABLE app.seat ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.seat FORCE ROW LEVEL SECURITY;
ALTER TABLE app.brief ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.brief FORCE ROW LEVEL SECURITY;
ALTER TABLE app.ledger_entry ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.ledger_entry FORCE ROW LEVEL SECURITY;
ALTER TABLE app.egress_record ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.egress_record FORCE ROW LEVEL SECURITY;
ALTER TABLE app.tool_key ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.tool_key FORCE ROW LEVEL SECURITY;
ALTER TABLE app.playbook_key ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.playbook_key FORCE ROW LEVEL SECURITY;

CREATE POLICY owner_all ON app.organisation FOR ALL TO eii_owner
  USING (true) WITH CHECK (true);
CREATE POLICY owner_all ON app.seat FOR ALL TO eii_owner
  USING (true) WITH CHECK (true);
CREATE POLICY owner_all ON app.brief FOR ALL TO eii_owner
  USING (true) WITH CHECK (true);
CREATE POLICY owner_all ON app.ledger_entry FOR ALL TO eii_owner
  USING (true) WITH CHECK (true);
CREATE POLICY owner_all ON app.egress_record FOR ALL TO eii_owner
  USING (true) WITH CHECK (true);
CREATE POLICY owner_all ON app.tool_key FOR ALL TO eii_owner
  USING (true) WITH CHECK (true);
CREATE POLICY owner_all ON app.playbook_key FOR ALL TO eii_owner
  USING (true) WITH CHECK (true);

CREATE POLICY seat_self ON app.seat FOR ALL TO eii_app
  USING (seat_key = current_setting('eii.seat', true)
         AND organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid)
  WITH CHECK (seat_key = current_setting('eii.seat', true)
              AND organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid);
CREATE POLICY org_self ON app.organisation FOR ALL TO eii_app
  USING (organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid)
  WITH CHECK (organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid);
CREATE POLICY brief_company ON app.brief FOR ALL TO eii_app
  USING (seat_key = current_setting('eii.seat', true)
         AND current_setting('eii.seat', true) IN ('company_a', 'company_b')
         AND organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid)
  WITH CHECK (seat_key = current_setting('eii.seat', true)
              AND current_setting('eii.seat', true) IN ('company_a', 'company_b')
              AND organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid);
CREATE POLICY ledger_own ON app.ledger_entry FOR ALL TO eii_app
  USING (seat_key = current_setting('eii.seat', true)
         AND organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid)
  WITH CHECK (seat_key = current_setting('eii.seat', true)
              AND organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid);
CREATE POLICY egress_own ON app.egress_record FOR ALL TO eii_app
  USING (seat_key = current_setting('eii.seat', true)
         AND organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid)
  WITH CHECK (seat_key = current_setting('eii.seat', true)
              AND organisation_id = NULLIF(current_setting('eii.organisation', true), '')::uuid);

CREATE FUNCTION app.read_seat_context()
RETURNS TABLE (seat_key text, organisation_id uuid, role text,
               label_en text, label_ar text, organisation_label text,
               is_fictional boolean)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $$
  SELECT s.seat_key, s.organisation_id, s.role, s.label_en, s.label_ar,
         o.display_name, o.is_fictional
  FROM app.seat AS s
  JOIN app.organisation AS o USING (organisation_id)
  WHERE s.seat_key = current_setting('eii.seat', true);
$$;

CREATE FUNCTION app.read_company_briefs(p_brief_id uuid DEFAULT NULL)
RETURNS TABLE (brief_id uuid, answer_id uuid, organisation_id uuid, seat_key text,
               release_id text, language text, playbook text, journey text,
               case_key text, question_text text, brief_json jsonb,
               catalogue_version text, memo_key text, created_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $$
  SELECT b.brief_id, b.answer_id, b.organisation_id, b.seat_key, b.release_id,
         b.language, b.playbook, p.journey, b.case_key, b.question_text,
         b.brief_json, b.catalogue_version, b.memo_key, b.created_at
  FROM app.brief AS b
  JOIN app.playbook_key AS p ON p.playbook = b.playbook
  JOIN app.seat AS s
    ON s.seat_key = b.seat_key AND s.organisation_id = b.organisation_id
   AND s.role = 'company'
  WHERE s.seat_key = current_setting('eii.seat', true)
    AND (p_brief_id IS NULL OR b.brief_id = p_brief_id);
$$;

CREATE FUNCTION app.read_company_ledger()
RETURNS TABLE (entry_id uuid, occurred_at timestamptz, seat_key text,
               organisation_id uuid, brief_id uuid, answer_id uuid, kind text,
               playbook text, tool text, arguments jsonb, question_text text,
               area_cell bigint, activity_key text, release_id text, engine text,
               status text, fact_ids jsonb, writer text, injection_flag boolean,
               origin text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $$
  SELECT l.entry_id, l.occurred_at, l.seat_key, l.organisation_id, l.brief_id,
         l.answer_id, l.kind, l.playbook, l.tool, l.arguments, l.question_text,
         l.area_cell, l.activity_key, l.release_id, l.engine, l.status,
         l.fact_ids, l.writer, l.injection_flag, l.origin
  FROM app.ledger_entry AS l
  JOIN app.seat AS s
    ON s.seat_key = l.seat_key AND s.organisation_id = l.organisation_id
   AND s.role = 'company'
  WHERE s.seat_key = current_setting('eii.seat', true);
$$;

CREATE FUNCTION app.read_company_egress()
RETURNS TABLE (egress_id uuid, ledger_entry_id uuid, answer_id uuid,
               request_ordinal integer, seat_key text, organisation_id uuid,
               route text, occurred_at timestamptz, sent_at timestamptz,
               model text, release_id text, prompt_version text,
               payload_sha256 text, payload_bytes bytea, payload_json jsonb,
               fact_ids_sent jsonb, usage jsonb, stop_reason text,
               scan_result text, cost_estimate_usd numeric)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $$
  SELECT e.egress_id, e.ledger_entry_id, e.answer_id, e.request_ordinal,
         e.seat_key, e.organisation_id, e.route, e.occurred_at, e.sent_at,
         e.model, e.release_id, e.prompt_version, e.payload_sha256,
         e.payload_bytes, e.payload_json, e.fact_ids_sent, e.usage,
         e.stop_reason, e.scan_result, e.cost_estimate_usd
  FROM app.egress_record AS e
  JOIN app.seat AS s
    ON s.seat_key = e.seat_key AND s.organisation_id = e.organisation_id
   AND s.role = 'company'
  WHERE s.seat_key = current_setting('eii.seat', true);
$$;

CREATE FUNCTION app.read_oversight_ledger()
RETURNS TABLE (entry_id uuid, occurred_at timestamptz, answer_id uuid, kind text,
               playbook text, tool text, area_cell bigint, activity_key text,
               release_id text, engine text, status text, fact_ids jsonb,
               writer text, injection_flag boolean, origin text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $$
  SELECT l.entry_id, l.occurred_at, l.answer_id, l.kind, l.playbook, l.tool,
         l.area_cell, l.activity_key, l.release_id, l.engine, l.status,
         l.fact_ids, l.writer, l.injection_flag, l.origin
  FROM app.ledger_entry AS l
  WHERE current_setting('eii.seat', true) = 'oversight'
    AND EXISTS (SELECT 1 FROM app.seat AS s
                WHERE s.seat_key = 'oversight' AND s.role = 'oversight');
$$;

CREATE FUNCTION app.read_oversight_egress()
RETURNS TABLE (egress_id uuid, occurred_at timestamptz, answer_id uuid,
               request_ordinal integer, route text, sent_at timestamptz,
               model text, release_id text, prompt_version text,
               payload_sha256 text, fact_ids_sent jsonb, usage jsonb,
               stop_reason text, scan_result text, cost_estimate_usd numeric)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $$
  SELECT e.egress_id, e.occurred_at, e.answer_id, e.request_ordinal, e.route,
         e.sent_at, e.model, e.release_id, e.prompt_version, e.payload_sha256,
         e.fact_ids_sent, e.usage, e.stop_reason, e.scan_result,
         e.cost_estimate_usd
  FROM app.egress_record AS e
  WHERE current_setting('eii.seat', true) = 'oversight'
    AND EXISTS (SELECT 1 FROM app.seat AS s
                WHERE s.seat_key = 'oversight' AND s.role = 'oversight');
$$;

CREATE FUNCTION app.read_oversight_demand(
  p_by text,
  p_distinct_organisation_minimum integer DEFAULT 2
)
RETURNS TABLE (group_key text, entry_count bigint, organisation_count bigint)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $$
  WITH scoped AS (
    SELECT l.area_cell, l.activity_key, p.journey, l.organisation_id
    FROM app.ledger_entry AS l
    LEFT JOIN app.playbook_key AS p ON p.playbook = l.playbook
    WHERE current_setting('eii.seat', true) = 'oversight'
      AND EXISTS (SELECT 1 FROM app.seat AS s
                  WHERE s.seat_key = 'oversight' AND s.role = 'oversight')
  ), grouped AS (
    SELECT CASE p_by
             WHEN 'area' THEN area_cell::text
             WHEN 'activity' THEN activity_key
             WHEN 'decision' THEN journey
           END AS group_key,
           organisation_id
    FROM scoped
    WHERE p_by IN ('area', 'activity', 'decision')
  )
  SELECT group_key, count(*), count(DISTINCT organisation_id)
  FROM grouped
  WHERE group_key IS NOT NULL
  GROUP BY group_key
  HAVING count(DISTINCT organisation_id) >= p_distinct_organisation_minimum;
$$;

REVOKE ALL ON SCHEMA app FROM PUBLIC;
GRANT USAGE ON SCHEMA app TO eii_app;
REVOKE ALL ON ALL TABLES IN SCHEMA app FROM eii_app;
GRANT INSERT ON app.brief, app.ledger_entry, app.egress_record TO eii_app;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO eii_app;
```

The application role therefore has no `SELECT` privilege on any base table of `app`. It reads only
through these fixed functions. Company and oversight functions have separate return types. Every
function runs as `eii_owner`, sets an empty `search_path`, enables row security and checks the
transaction-local seat explicitly. The oversight types omit organisation identity, organisation
labels, seat keys, question text, brief text, raw tool arguments and outbound payload content. The
demand function groups `decision` by the journey of the playbook, `d1` to `d7`.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-110 | Tables and fixed read functions are owned by `eii_owner`, a role the application does not use. Every `app` table has row-level security enabled and forced. `eii_app` has no `SELECT` on an `app` base table and reads only through the canonical functions with locked empty `search_path` and explicit seat checks. | Catalogue and privilege queries prove ownership, `relforcerowsecurity`, no base-table `SELECT` and function settings; direct base reads fail. |
| DAT-111 | After one-time picker selection, the API verifies the signed `eii_seat` session cookie and calls `read_seat_context` to derive the organisation. It sets `eii.seat` and `eii.organisation` only as transaction-local settings from that result, never from an address or request field. Policies compare those settings directly with `seat_key` and `organisation_id`, without a base-table subquery. All application ids are UUID version 7 generated by the application. A request without a valid seat sees no rows. | Cookie-to-setting and pool-reuse tests; queries with missing or empty settings return no rows; cross-organisation settings fail; identifier fixtures prove UUID version 7 and replay-stable ids. |
| DAT-112 | A company seat reads and writes only rows of its own organisation through the company return types and insert policies. Company B cannot read Company A's brief. | Database-level tests as Company B, oversight, unset seat and empty seat return no Company A brief; cross-seat inserts fail. |
| DAT-113 | `ledger_entry` and `egress_record` are append-only: no role used by the application has UPDATE or DELETE. Stable UUIDv7 primary keys and `ON CONFLICT DO NOTHING` make local replay idempotent; no hash chain is defined. | Privilege check; replay, repeated replay and interruption-after-commit fixtures produce no duplicates or loss. |
| DAT-114 | Oversight reads ledger, egress and demand rows only through the fixed oversight return types, which carry no organisation identity, question text, brief text, raw tool arguments or outbound payload content, and reads no brief rows. The fixed demand function performs the aggregate and applies the configured `distinct_organisation_minimum`, default 2; this is demonstration configuration, not a disclosure threshold. Live rows are tagged "this session"; seeded rows are marked Synthetic (master OI-08). | Return-type inspection and planted-field tests, including resolve text inside a tool argument; one organisation is suppressed and two are displayed under the default; non-oversight calls return no rows; direct base reads fail. |
| DAT-115 | The application role has `SELECT` only on the configured `r_<first 16 hexadecimal characters of release_id>` release schema, not on application base tables; a release write attempt fails. | Privilege and write-refusal tests. |
| DAT-148 | `app.tool_key` holds exactly the closed tool registry of [08_BACKEND.md](08_BACKEND.md) and `app.playbook_key` exactly the closed playbook registry of [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md), each playbook with the one journey, `d1` to `d7`, that it serves, or a null journey for a playbook that serves a case only ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 16). The forward-only migration that creates them inserts their rows; a registry change is a new migration (DAT-125). `eii_app` has no privilege on either table; the foreign keys of `brief` and `ledger_entry` enforce both closed lists. | A migration test compares both tables with the registries; an insert naming an unknown tool or playbook fails; a registry entry missing from a table fails; a direct read as `eii_app` fails. |
| DAT-149 | No `app` table holds a drawn shape, an area record (section 9.2) or a case sample file (section 12.2); an area from the provider adapter and its `provider_note` are held as a drawn shape and its record are (DAT-163). The serving process keeps a drawn shape and a sample file only in the session store of the session and seat that drew the shape or loaded the file by its closed key (DAT-150, [08_BACKEND.md](08_BACKEND.md) BE-109). A ledger row about an area carries the record's `anchor_cell` as `area_cell` and the `shape_id` or `area_id` in its arguments, never a coordinate of the shape. | Catalogue check: no `app` column holds a geometry, a GeoJSON shape or sample-file rows; a ledger fixture with shape coordinates in `arguments` fails; `area_cell` equals the record's `anchor_cell`. |
| DAT-156 | An `egress_record` row keeps an outbound payload only when the egress scan passed it ([09_AI_ASSISTANT.md](09_AI_ASSISTANT.md) AI-77, AI-82). A call that the scan blocks has `scan_result` `blocked`, `payload_sha256` equal to the SHA-256 of the proposed payload's UTF-8 bytes, null `payload_bytes`, `payload_json`, `sent_at`, `usage`, `stop_reason` and `cost_estimate_usd`, and an empty `fact_ids_sent`, so nothing that the scan found, such as a register company's registration number or another field of a register row ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) item 8), a canary marker or a secret-shaped token, is stored ([02_ARCHITECTURE.md](02_ARCHITECTURE.md) ARC-73). A call that passed the scan has `scan_result` `passed` and its exact bytes in `payload_bytes`. The two table checks of the DDL enforce both cases, and the local SQLite ledger applies the same rule to the same columns ([08_BACKEND.md](08_BACKEND.md) BE-77, BE-80). | A blocked fixture whose proposed payload holds a planted row of the invented stand-in register (its registration number and name) writes one row with `scan_result` `blocked`, the proposed payload's hash, the nulls above and an empty `fact_ids_sent`; a scan of every column of that row, in PostgreSQL and in the local ledger, finds neither the number nor the name. Inserting a blocked row with a non-null `payload_bytes`, `payload_json`, `sent_at`, `usage`, `stop_reason` or cost, or with a non-empty `fact_ids_sent`, a passed row with a null `payload_bytes`, or a `scan_result` other than `passed` or `blocked` fails in both ledgers. |

### 12.1 Offline typed-decision records (not an application table)

Version 1 has no `app.decision_record` table. Each offline gateway call writes one JSON record under
`evals/typed_decisions/runs/` with this closed field set. `option_order` records both fixed,
hash-derived orders for a `choice`; `human_disposition` is null until a person dispositions the row.
Records are build and evaluation evidence only and are never read by serving code.

| Field | Content |
|---|---|
| `decision_class` | `spine_match`, `router_miss_finder`, `brief_second_reader`, `question_route` or `string_parity` |
| `kind` | `yes_no`, `choice` or `ordinal` |
| `provider_configured`, `provider_used`, `reported_model_id` | configured route, actual provider and self-reported model identifier |
| `rubric_id`, `rubric_sha256` | rubric identity and hash |
| `input_class`, `input_sha256`, `language` | `public`, `synthetic`, `project_text` or `team_question` only; canonical input hash and language |
| `route`, `option_order` | offline route and the option order or orders used |
| `returned_label`, `returned_scores`, `top_score` | provider result exactly as returned and its ranking signal |
| `threshold_in_force`, `threshold_outcome` | threshold configuration and `DECIDED`, `BELOW_THRESHOLD`, `UNAVAILABLE`, `DISABLED`, `ERROR` or `BLOCKED_BY_DATA_POLICY` |
| `memo_key` | hash of decision class, rubric hash, normalised inputs, model id and adapter version |
| `latency_ms`, `fallback_applied`, `permitted_effect` | measured call duration, fallback and the only permitted downstream effect |
| `recorded_at` | UTC timestamp |
| `human_disposition` | later human disposition, or null |

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-126 | Offline decision records use the closed schema above and live only under `evals/typed_decisions/runs/`. The separate `gateway/` package is imported only by `evals/` and `scripts/` tooling. No `app.decision_record` or other run-time decision table exists in version 1. | Schema and import-boundary tests; a serving-code read or an application-table fixture named `decision_record` fails. |

### 12.2 Case sample files (not an application table)

Cases C3 and C4 each load a synthetic file that stands for the company's own records
([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 4). Version 1 has no
application table for them.

| File | Fields |
|---|---|
| `delivery_records.v1` (case C3, a distributor's deliveries; one row per delivery) | `delivery_date` date (inside the reference period); `hour` int (the dispatch hour, 0 to 23); `depot` string (a fictional depot label that passes the name test of [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md) SYN-20); `depot_cell` cell; `customer_cell` cell; `customer_activity` string (an ISIC class of the activity spine); `units` int |
| `branch_sales.v1` (case C4, a retail chain's branch sales; one row per branch, month, day type and opening hour) | `branch` string (a fictional branch label that passes the name test of SYN-20); `branch_cell` cell; `month` month; `day_type` (`weekday`, `friday`, `saturday`); `hour` int (an opening hour, 0 to 23); `sales_qar` decimal(14,2), QAR (net sales in that hour, summed over the days of that type in the month); `tickets` int |

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-150 | A case sample file is a committed fixture marked Synthetic, made by a seeded generator from the frame and Public tables only, never from the vault or a protected table. The product loads a sample file only for cases `c3` and `c4`, only by a closed key that names one of that case's committed files, and only when the committed file's SHA-256 equals its committed value; no file is ever received from the browser, which has no file input, drop path or hashing of its own ([10_FRONTEND.md](10_FRONTEND.md) FE-120). It is held only in the session and seat that loaded it (DAT-149). Neither its records nor any fact computed from it is written to the release, a store, an `app` table, a log, the memo or an egress record, or sent to the model; the ledger records only the call, the case key and the status, and a brief that uses such facts is not saved ([08_BACKEND.md](08_BACKEND.md) BE-118). A fact computed from it carries `user_input` and `synthetic`, `evidence_status` `inferred` and the caveats `your_inputs` and `sample_file`; its lineage names the method and the committed file's `source_registry` row (kind `synthetic_feed`, the file's SHA-256); it fills only `area` slots (DAT-145). | After a session, no table row, log line, memo or egress record holds a record of the file or a fact from it; a second seat reads no fact from the first seat's file; a request that carries a file, a path, a URL or an unknown key is refused with nothing kept, and a committed file whose bytes no longer match its committed SHA-256 is not loaded; saving a brief that uses such a fact fails; lineage resolves to the file's hash; a sample-file fact in a `scenario` or `place_public` slot fails. |

## 13. Versioning and compatibility

The amendments of decisions 0016, 0017 and 0019 are made before any contract file exists under
`contracts/`. They keep the `.v1` contract names and `release.v1`; DAT-120 to DAT-123 apply from
the first committed contract.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-120 | Contract names carry the major version (`wages.v1`). A revision number within a major version may only add a nullable field or a new table that no existing consumer reads. | Schema diff tool classifies each change; CI fails on an unclassified change. |
| DAT-121 | Any removed, renamed or retyped field, tightened nullability, new value in a closed list, changed meaning or changed reference-period rule is a new major version (`v2`), with its own conformance suite. | Schema diff fixtures for each case are classified as major. |
| DAT-122 | A change to the wage-band scheme, the crossing classes or the fact schema is a new major version of the release contract (`release.v2`). | Diff check on `contracts/`. |
| DAT-123 | The loader accepts only releases whose `release_contract_version` major equals the one the product was built for. | Fixture with `release.v2` is refused. |
| DAT-124 | A release is immutable. Any change of input, rule, code or seed produces a new `release_id`; briefs and ledger rows keep the `release_id` they used, so old answers stay reproducible. | Rebuild with one changed rule yields a new id; the old directory is untouched. |
| DAT-125 | Application schema changes are forward-only numbered migrations in `infra/` (ASSUMPTION: simplest safe practice). | Migration runner test on an empty and a seeded database. |

## Open questions and assumptions

ASSUMPTIONS: (1) identifier bodies need two letters and no digit run over four (section 4);
(2) the published occupation band table is reused for person-month pay, with B01 extended to
"1,000 or less" (DAT-16); (3) residence tables attach a person to the month's highest-paid job
(DAT-04); (4) register scope excludes government and free-zone entities, and includes the
financial centre's public register as a second register under decision 0022 (6.1);
(5) all quality thresholds and the 1% quarantine limit are proposals (DAT-10, DAT-24); (6) eligible
person-month rule and `basic` from the latest record (6.3); (7) OD flows at H3 resolution 7 (6.5);
(8) situation hour windows and the Sunday-to-Thursday week (7.1); (9) monthly rows hold the
primitives of their own month, and a figure over several months is computed from the rows of one
family (7.1); (10) outlet size bands (7.3); (11) scalar values in
linked-input hash JSON use the canonical representations fixed in section 8; (12) fixed application read-function names
(section 12); (13) "Not measured" is a coverage key (DAT-95); (14) forward-only application
migrations (DAT-125); (15) comparison-direction wire values are `higher`, `lower` and `equal`
(DAT-134); (16) the attacker-view audit report path is
`artefacts/reports/attacker_view_audit_report.json`; (17) Ramadan is the one day type
`ramadan_day`, and the three event day types are released with `summer = false` only (6.5,
DAT-76); (18) `presence_count` is dense over its allowed key combinations, so that a withheld row
never shows why it was withheld (DAT-138); (19) traffic rows exist only for links of the six road
classes with an assigned volume above zero and carry the summer switch of the flows they are
assigned from (DAT-139); (20) the forms of `link_id` and `project_key` (7.3); the release's own
`SYN-E-` sequence for `firm_key` is withdrawn by decision 0022 with the firm list (DAT-140); (21) the weekly residential
bulletin is released as monthly aggregates with deal counts (`pub_property_resi`); (22)
`pub_visitor_markets` keeps the visitors' nationality and origin-region groups as published,
while decision 0017 names the Qatari and non-Qatari categories for the labour, compensation and
student tables (DAT-141); (23) the case sample files have the fields of
section 12.2 and are made from the frame and Public tables only (DAT-150); (24) the gazetteer kind
`gateway` marks the destinations that journey D7 measures travel times to (7.3); (25) the closed
tool and playbook lists are reference tables in the database, and the journey and case keys are
`d1` to `d7` and `c1` to `c4` (DAT-148); (26) a drawn area is one simple polygon, so that no
request can describe "everything except" an area (DAT-146); (27) withdrawn by decision 0022: the
withheld firm-list row it described is retired with the firm list (DAT-140); (28) withdrawn by
decision 0022: the joined firm-list size bands are retired with the firm list, and a register
company's card shows its employee count (7.3); (29) the build-time access scores of release units (`access_score`) take
the residents present of `presence_count` as their only demand layer, so that no stored score
combines a protected value with a Public figure or puts a Public statistic on a release unit
(DAT-151); (30) the travel-time
matrix holds only the pairs within the largest cut-off of C12 and is an artefact read as a file, so
that neither store carries it (DAT-153); (31) the hotels and restaurants size table enters
`pub_establishment_size` under its own `table_code`, so that C24 reads restaurants from that table
(7.3); (32) a residential median carries one price basis for all its sales (`pub_property_resi`);
(33) the scores of the population-grid layer of C12 are stored at free flow only in the Public
table `access_score_grid`, at the grid's own 100 m cells and in both release kinds, so that the
public-only answer has an access layer that reads no Protected or Simulated table and no Public
figure is put on a release unit (DAT-154); (34) `access_score` and `access_score_grid` are keyed by
cut-off, so that the closed `cutoff` argument of `reachable_access` selects stored rows
([08_BACKEND.md](08_BACKEND.md); DAT-151, DAT-154); (35) a `published_text` fact holds at most 200
characters, enough for a published field shown in a chip (DAT-155); (36) the metric keys, units and
value orders of the facts of forecasts, base rates, people present by pay band, estimates,
scenarios and the Public figures of DAT-157, and the schema condition that makes four caveat
keys force the status Inferred (section 9, DAT-157 to DAT-162); (37) a base rate has the status that the churn rate of card C2 has,
`observed` (DAT-159); (38) `pub_night_lights` is keyed by frame cell, from whole pixels with no split,
and not by release unit, because no Public table has a `unit_id` (DAT-74, DAT-157), and the grid key of `pub_pop_agesex_grid`
takes the prefix `wa_` (7.3); (39) the indicators `revenue` and `costs` of `pub_establishment_size`
are the survey's per-establishment revenue and cost columns (7.3); (40) the whole-cell sum of
`pub_pop_agesex_grid` over an area has the status `observed`, as an exact-shape count of Public
points does (DAT-141, DAT-147).

- No longer open for version 1 (owner's answer of 2026-11-12, decision 0016 item 9): version 1
  holds no protected split by activity, and national by sector is its finest sector view. Pay by
  sector comes from `pub_compensation_nationality`, `pub_establishment_size` and `pub_wage_table`
  on their national geography, and wage trends by sector come only from the public portal's wage
  series by economic activity, the Public national branch of method card C19 over the activity
  table `wage_act` of `pub_wage_table`, which needs no protected split
  ([07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) MTH-97). Pay figures and the stayer index are
  shown per municipality through the municipality level of the `money` and `quartile` pay
  partitions (DAT-137; [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md)
  PRV-16).
- OPEN: document 05 fixes how the feed's expanded trips become the vehicle trips that
  `flow_hourly` releases (MTH-88).
- OPEN: the apportioning weight for drawn shapes (area, or a licensed public population grid) is
  fixed in document 07 and confirmed at slice S2 (decision 0016). It is a weight and a total, never a
  split; the whole-cell sum of the age and sex grid `pub_pop_agesex_grid` is a separate display
  figure and is not that weight (DAT-141).
- OPEN: document 07 does not yet fix the number and boundaries of the `volume_band` keys; they are
  fixed there at slice S1, beside the volume-delay parameters of MTH-89. The way the ratios of each
  `link_id` reach the routing graph is fixed with SYN-53 at slice S1.
- OPEN: the structure of the dashboard page and of the agency's pages, every further FDI field and
  the capex unit are confirmed at slice S2 against a synthetic test page of the same shape
  (decision 0017). The unit `usd_million` is listed for a source that states millions of US
  dollars; the confirmation decides whether the dashboard does.
- OPEN: units of the added Public tables that the fact unit list lacks, for example product
  quantities in `pub_manufacturing`, join it when slice S2 confirms each source's columns
  (PUB-07).
- OPEN: the public source of tenders is confirmed at slice S2; without one, no tender table exists
  (decision 0016).
- OPEN: whether count indicators of the added Public tables join the attacker-view public totals
  (DAT-128, PRV-115) is decided with the public-totals selection of OI-24 at slice S5.
- OPEN: document 07 (C12) fixes which supply layers, modes, cut-offs and presence keys
  `access_score` stores, which supply layers, modes and cut-offs `access_score_grid` stores, and the
  largest cut-off of each mode, which bounds `travel_time_matrix`, at slice S2 (DAT-151, DAT-153,
  DAT-154).
- OPEN: slice S2 confirms the columns and units of the four Public tables of decision 0019 (DAT-157),
  among them the unit of `radiance_nw_cm2_sr`.
- ASSUMPTION: the files of the places copy of decision 0019 item 21 that cover Qatar are found
  through the dataset's own metadata file; the task that builds the fetcher confirms it.
- OPEN: the Public source of each series of the owner's list (decision 0019 item 2) for which
  [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) holds no source table; document 04 lists it as
  open, and it is not on the list of card C30 until a table is held (decision 0019, open questions).
- OPEN: the Public source of the survival base rate, which the Public licence tables cannot give
  (DAT-159); until then it returns `NO_DATA` with `no_denominator`.
- OPEN: the closed subject list has no official district, so the subject of a forecast of a series on
  district geography (property prices by district) is fixed at slice S2.
- OPEN (decision 0022): how the attachment by registration number treats a registration that covers
  several establishments in the register (DAT-01), and the legal-entity and employer-group structure
  generated for register companies (6.1).
- OPEN (decision 0022): the columns of `pub_register_company` and of the invented stand-in register,
  and the closed lists of `nationality_group` and `establishment_nationality` in the format of the
  real records, are fixed with the register's registry row in document 04 and with the calibration
  table, without committing a real value (6.1, 6.2, 7.3).
- OPEN (decision 0022): whether `employee_count` is rounded or otherwise treated under document 06
  before it crosses (DAT-140).
- OPEN (decision 0022): which released tables carry the nationality group or the establishment
  nationality as a dimension is set with document 06 (DAT-141).
- OPEN (decision 0022): whether the monthly openings and closures of `outlet_register` in
  `month_change` stay now that the establishments are register companies read from one register file
  (DAT-137), and whether `outlet_register` counts by size band still need their own suppression where
  the register's own counts are Public (7.2).
- OPEN (decision 0022): whether the attached wage records cover the companies of the financial
  centre's public register, whose employers the wage protection system excludes (6.3).

Open items from the master design that touch this document: OI-03 (two public wage tables and two
restaurant totals: `pub_wage_table.table_code` keeps tables apart until reconciled), OI-04 (closed
for version 1 by decision 0017 item 10: the census map layers enter the local release with
`commit_allowed = false`), OI-06 (source labels: contracts use neutral record-type names), OI-07
(closed by decision 0016 item 12; the firm list it allowed is retired by decision 0022, and the
register-company list replaces it, DAT-140), OI-08 (ledger labels and oversight view,
DAT-114), OI-11 (moved to `docs/17_DEPLOYMENT_HARDENING.md` by decision 0016 item 21; version 1
evaluates sets A and B and exports set A, and DAT-60 uses set A). OI-24 selects the public totals
of the attacker-view audit at slice S5. OI-35 fixes the exported set before treatment; the default
is A (DAT-132, PRV-120).

Open question: confirm the eligibility rule and the monthly primitives against documents 06 and 07;
if they differ, the lead decides and this document is revised.

## Sources

Retrieved 2026-11-11 unless a date is given.

- [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md),
  [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) and
  [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), accepted
  2026-11-12.
- The sources of decision 0019, read 2026-11-12 (publisher, licence or terms, as its Sources list
  them; the full entries are in [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md)):
  - Live traffic provider (`traffic_tomtom_flow`, `traffic_tomtom_range`): TomTom, Traffic API
    documentation, https://docs.tomtom.com/traffic-api/ ; the provider's developer terms could not
    be read, and nothing of a response is stored.
  - Relative busyness (`busy_gmaps`): Google, "About popular times, wait times and visit duration
    data", https://support.google.com/business/answer/6263531 ; no licence for reuse is stated, and the
    use is the owner's decision (`licence_basis` `owner_decision`).
  - Night-time lights (`ntl_blackmarble`): NASA, VNP46A3 product page,
    https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A3/ (DOI
    10.5067/VIIRS/VNP46A3.002), under NASA's data and information policy.
  - Places (`places_fsq`): Foursquare, access page of the open source places dataset,
    https://docs.foursquare.com/data-products/docs/access-fsq-os-places , Apache 2.0; fetched from the
    public copy on Source Cooperative, https://data.source.coop/fused/fsq-os-places/ (its README states
    the Apache License, Version 2.0; newest release dated 2025-01-10), read 2026-11-12.
  - Population by age and sex (`worldpop_qat_agesex`): WorldPop, https://hub.worldpop.org/geodata/listing?id=138 ,
    CC BY 4.0 (DOI 10.5258/SOTON/WP00841).
  - Hourly weather history (`weather_openmeteo`): Open-Meteo, https://open-meteo.com/en/docs/historical-weather-api ,
    non-commercial use, data CC BY 4.0.
- Qatar Open Data Portal, catalogue export and Explore API v2.1, CC BY 4.0 (portal licence page),
  retrieved 2026-11-12: https://www.data.gov.qa/api/explore/v2.1/ (the 77 added datasets are listed
  in [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) section 2).
- FDI Projects dashboard of the national investment promotion agency (data from fDi Markets), read
  2026-11-12: https://fdiprojects.invest.qa/
- The national investment promotion agency's sector, opportunity, incentive, set-up and law pages,
  read at every fetch under decision 0017: https://www.invest.qa/

- Qatar Open Data Portal, "Average Monthly Wage (Q.R.) for Workers in Private Sector in Qatar", CC BY
  (band labels read from its records API): https://www.data.gov.qa/explore/dataset/average-monthly-wage-q-r-for-workers-in-private-sector-in-qatar-2021-2025/
- "Wage Protection System File Format Specifications", copy published by Commercial Bank of Qatar:
  https://www.cbq.com.qa/-/media/project/cbq/cbqwebsite/documents/wps-file-format.pdf
- International Labour Organization, "Wage Protection Systems in the Gulf Cooperation Council
  Countries", November 2025: https://www.ilo.org/sites/default/files/2025-11/ILO_Beirut_Wage-Protection_Report_R10.pdf
- International Labour Organization, minimum wage news release (Law No. 17 of 2020):
  https://www.ilo.org/resource/news/qatar-adopts-non-discriminatory-minimum-wage
- Qatar Open Data Portal, active commercial certificates by municipality and activity, CC BY:
  https://www.data.gov.qa/explore/dataset/moci-active-certificates-by-municipality-and-business-activity/
- Labour Force Survey 2024 sector categories, republished by the Gulf Labour Markets, Migration and
  Population programme: https://gulfmigration.grc.net/qatar-economically-active-population-aged-15-years-and-above-by-nationality-qatari-non-qatari-and-activity-sector-2024/
- H3 documentation, cell index bit layout: https://h3geo.org/docs/library/index/cell
- UN Statistics Division, economic classifications: https://unstats.un.org/unsd/classifications/Econ/
- JSON Schema draft 2020-12 meta-schema: https://json-schema.org/draft/2020-12/schema
- Flowminder, "Understanding CDR aggregates": https://covid19.flowminder.org/cdr-aggregates/understanding-cdr-aggregates-fundamentals
- Project research files of 2026-11-11 (public economic data, architecture options, graph value,
  claims and legal landscape, decision-copilot panel design); measurements are attributed in the text.
