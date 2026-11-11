# 03 — Data Contracts

| | |
|---|---|
| Status | Draft v0.2, corrected after independent review on 2026-11-11 (see PROGRESS.md) |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Define every schema that crosses a boundary: the five source feeds, the release, the manifest, the fact object, the graph and the application schema, each with tests that fail loudly. |
| Read first | [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md), [02_ARCHITECTURE.md](02_ARCHITECTURE.md) |

## In brief

- Five source contracts (`business_register.v1`, `employment.v1`, `wages.v1`, `residence.v1`,
  `mobility.v1`) describe custodian-type feeds. Here every feed is synthetic or simulated; a real feed
  would have to pass the same conformance suite.
- Every field states what may leave the custodian plane and in what form. Names, bank fields,
  addresses and record identifiers never leave it.
- One wage-band scheme (twelve bands from a published Qatar Open Data Portal table) is used everywhere.
- The release is Parquet tables plus a manifest; the loader accepts only tables the manifest names;
  protected tables hold additive primitives only.
- Every number on screen is a fact object (section 9); provenance and evidence status stay separate.
- A headerless, undated or unscoped feed fails. Rows with placeholder identifiers are quarantined and
  counted, and too many of them fail the feed.

## 1. Conventions

### 1.1 Terms

- **Custodian plane**: the offline build (`custodian/`), the only place record-level (synthetic) data
  exists ([02_ARCHITECTURE.md](02_ARCHITECTURE.md)). **Vault**: its ephemeral store, deleted after
  each build.
- **Feed**: one delivery of one source contract for one reference period (a feed bundle, section 3),
  produced by an adapter; v1 has only the synthetic adapter. **Conformance suite**: the tests in this
  document for one contract; a feed that fails any of them never enters the vault.
- **Release**: the immutable, content-addressed output of one build (Parquet tables plus
  `manifest.json`). **Release unit**: a whole-cell unit, a municipality remainder, a terminal
  `ha_home` municipality unit or the national unit
  ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md)).
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

Every source field carries exactly one class. The release builder and the loader enforce them.

| Class | What may leave the custodian plane |
|---|---|
| `NEVER` | Nothing. The field stays in the vault and is deleted with it. |
| `LINK` | Nothing. Used only by linkage to join feeds inside the vault. |
| `GEO` | Only as membership of a release unit (`unit_member`); never as a per-record location. |
| `DIM` | Only as a value of a closed, coarse code list used as a dimension of a released table. |
| `AGG` | Only as a contribution to treated additive primitives in a protected or simulated table. |
| `QC` | Only as aggregate counts in the conformance report and the coverage declaration. |
| `PROV` | Only as provenance: reference period, hashes, contract version in the manifest. |

## 2. The eight contract design requirements

These are general lessons about administrative data. They apply to every source contract.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-01 | One legal registration can cover several establishments. Feeds join on `establishment_id`. A join on `legal_entity_id` alone is allowed only when that legal entity has exactly one establishment in the register for the same reference period; otherwise the join fails. | Fixture: a legal entity with two establishments and wage records keyed by legal entity only. Linkage must raise `AMBIGUOUS_REGISTRATION` and attach no record. |
| DAT-02 | Identifiers are normalised (trim, upper-case, remove inner spaces and non-breaking spaces, convert Arabic-Indic digits to ASCII), then validated against their pattern (section 4). Placeholders are rejected: empty, `0`, `-`, an em dash, `N/A`, `NA`, `NULL`, `NONE`, `UNKNOWN`, `TBD`, and any body made of one repeated character. | Fixture rows with each placeholder and with noisy but valid identifiers. Placeholders land in the quarantine count; noisy valid identifiers normalise to the canonical form. |
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
UTF-8, comma-separated, header row first). `feed_manifest.json` fields: `contract` (for example
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
| DAT-11 | A field whose crossing class is `NEVER`, `LINK` or `QC` never appears as a column, or as a value, in any release table. | The loader check DAT-83 runs over every release; the release builder test also scans every string column for the identifier pattern of section 4. |

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

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-12 | Every synthetic identifier matches `^SYN-[ELGPF]-[0-9A-HJKMNP-TV-Z]{6,8}$` with the body length of its kind and the letter and digit-run constraints above. | Regex and constraint check over every identifier column of every feed. |
| DAT-13 | Collision rule: identifiers are generated from a seeded, collision-free sequence (a keyed permutation of a counter), never by random draw. Any duplicate within a kind fails the build. | Uniqueness check per kind; two builds from one seed produce identical identifiers. |
| DAT-14 | Synthetic trade names come from a visibly synthetic lexicon. A name whose normalised form (case-folded, diacritics and tatweel removed, spaces collapsed) equals any name in `pub_place` or `gazetteer` fails the build. Synthetic entities are located to a base cell, never to a named building. | Collision test against both tables; a fixture name equal to a gazetteer entry fails. |
| DAT-15 | No identifier, in any contract, mimics a real registration, establishment or personal identifier: no all-digit identifiers and no run of exactly eight or eleven digits anywhere in the repository. | The CI identifier-pattern scan and DAT-12. |

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
activity and registered location.
**Reference period.** `as_of_date`: the snapshot date (last day of the reference month).
**Coverage declaration.** In scope: establishments licensed in the commercial register. The synthetic
feed declares as exclusions entities registered outside it (government entities, entities licensed by a
separate financial-centre or free-zone authority). ASSUMPTION: the simplest honest scope for a
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
| `trade_name` | string | N | synthetic lexicon name (DAT-14) | NEVER |
| `registered_cell` | cell | Y | base cell of the registered address; null when `address_status` is `unresolved` | GEO |
| `address_status` | string | N | `resolved`, `unresolved` | QC |
| `address_type` | string | N | `own_premises`, `office_tower`, `shared_business_centre`, `unknown` | QC |
| `licence_status` | string | N | `active`, `suspended`, `cancelled` | AGG |
| `licence_valid_from` | date | Y | null when not recorded | NEVER |
| `licence_valid_to` | date | Y | null when open-ended | NEVER |

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
**Reference period.** `reference_month`: the month the snapshot describes (state at month end).
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

There is no nationality, sex, age or name field, and none may be added (master design section 3.3).
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
**Reference period.** `as_of_date`: snapshot at the last day of the reference month.
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

Table `presence_hourly` (grain: base cell × day type × season × hour × segment).

| Field | Type | Null | Meaning and allowed values | Crosses as |
|---|---|---|---|---|
| `observation_start`, `observation_end` | date | N | window the feed summarises | PROV |
| `cell` | cell | N | base cell | GEO |
| `day_type` | string | N | `weekday`, `friday`, `saturday` | DIM |
| `season` | string | N | `regular`, `summer`, `ramadan` | DIM |
| `hour` | int | N | 0 to 23, local time | DIM (through a situation) |
| `segment` | string | N | `resident`, `worker`, `visitor` | DIM |
| `panel_devices` | int | N | distinct panel devices; at least 20 | QC |
| `expansion_factor` | decimal(9,4) | N | panel-to-population factor | QC |
| `expanded_presence` | decimal(14,2) | N | expanded average presence | AGG (to `presence_score`) |

Table `od_hourly` (grain: origin × destination × day type × season × hour). Same period, day type,
season, hour, `panel_devices` and `expansion_factor` fields, plus `origin_cell` and
`destination_cell` (cell, N, H3 resolution 7, ASSUMPTION: coarse enough for flows) and
`expanded_trips` (decimal(14,2), N, AGG to `flow_score`).

Table `road_speed_hourly` (grain: road class × day type × season × hour). Fields: period fields,
`road_class` (string, N; OpenStreetMap `highway` values `motorway`, `trunk`, `primary`, `secondary`,
`tertiary`, `residential`), `day_type`, `season`, `hour`, `speed_ratio` (decimal(5,3), N, observed
speed divided by free-flow speed; AGG to `speed_factor`).

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-60 | No row has `panel_devices` below 20 (parameter set A minimum; set B applies 30 in the privacy engine). | Minimum check over both count tables. |
| DAT-61 | No table has a device, person, trip or sequence identifier, and no table is finer than one hour. | Schema deny-list and grain check. |
| DAT-62 | `presence_hourly` and `od_hourly` cells are valid H3 cells of the stated resolution inside the Qatar frame. | Join to `grid_cell` or its resolution-7 parents. |
| DAT-63 | `expanded_presence` and `expanded_trips` never cross as counts; they become unitless scores (section 7.3). | No release column holds them under any name. |
| DAT-64 | Quality: `expansion_factor` is at least 1; `speed_ratio` lies between 0.05 and 1.5. | Range checks. |

## 7. The release contract

### 7.1 Rules

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-70 | A `protected` release holds exactly the Parquet tables listed in section 7.2, one file each, at `data/releases/<release_id>/tables/<table>.parquet`. A `public_only` release holds only the listed Frame, Public, Graph, Lineage and applicable Control tables; it contains no Protected or Simulated table. `release_manifest` is excluded from both kinds because the loader materialises it. | Directory listing equals the manifest table list for each release kind; a Protected or Simulated table in `public_only` and a `release_manifest.parquet` fixture fail. |
| DAT-71 | Protected tables hold additive primitives only: the count and wage-bill columns named in 7.3. No mean, median, quantile, share, minimum or maximum column exists in them. | Column allowlist per protected table. |
| DAT-72 | Every row of a protected table, of `presence_index` and of `flow_od` references a `release_unit` whose `status` is `published`; withheld units carry no rows. | Referential and status check. |
| DAT-73 | A whole-cell release unit is one base grid cell or a union of whole base cells inside one root; each root is the intersection of one resolution-7 parent with one municipality. The only cross-root unions are a remainder made from failed roots of one municipality and the terminal `ha_home` unit made from every `op_res_quartile` whole-cell unit and remainder of one municipality (PRV-13). Each contributor universe has one parent-linked partition family: a coarser partition is made only by merging units of the finer one, and independent merges never cross. Closure and exact sums are required only within one additive family; cross-family routes are checked by the consistency audit of PRV-71 and are not required to be equal. Complement tests run across tables and dimensions. Cross-period fixtures and the mover case are deferred to backlog item L4. In every `./eii build-release`, closure is proved by exhaustive structural checks for candidate A, candidate B and again for the selected export. After each proof, at least 10,000 seeded fuzz pairs run for that candidate or selected export. | `unit_member` proves exact coverage within each partition and containment or disjointness across every partition and breakdown dimension of one contributor universe; exhaustive checks enumerate every treated leaf, supported derivation, within-family route and finite `make_area` input required by PRV-111, check sums only within each family, and send every cross-family route pair to PRV-71 without asserting equality. The custodian build report records at least 10,000 pairs for candidate A, at least 10,000 for candidate B and a repeated run of at least 10,000 for the selected export; the exported closure report carries only the selected-export proof and repeated run. A mutation after candidate validation fails the selected-export gate. No version 1 fixture contains a second protected window or mover case. |
| DAT-74 | Public tables never share a row, unit or column with a protected table; Public figures stay on their official geographies. | No public table has `unit_id`; no protected table has `zone_code`. |
| DAT-75 | Every table has a declared primary key with no null key parts; total rows use the literal `ALL` for bands and `all` for `housing_class`, never null. | Key uniqueness and not-null check on both engines. |
| DAT-76 | Situation keys are exactly `weekday_lunch`, `weekday_evening`, `friday_evening`, `ramadan_iftar`; rows with `summer = true` never use `ramadan_iftar`. | Enumeration check on simulated tables. |

**Situation windows (ASSUMPTION, stored in `rules_version` so they change without code).** The
shared rule `situation_windows` has unit `canonical_json` and this exact value:
`{"friday_evening":{"day_type":"friday","hours":[19,20,21],"season_by_summer":{"false":"regular","true":"summer"}},"ramadan_iftar":{"day_type":"weekday","hours":[17,18,19],"season":"ramadan","summer_values":[false]},"weekday_evening":{"day_type":"weekday","hours":[19,20,21],"season_by_summer":{"false":"regular","true":"summer"}},"weekday_lunch":{"day_type":"weekday","hours":[12,13],"season_by_summer":{"false":"regular","true":"summer"}}}`.
Hours are inclusive. The rule value resolves the season for every allowed `summer` value without
another configuration; `weekday` means Sunday to Thursday, the working week the simulator assumes
([05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md)).

**Periods.** Protected tables: `YYYY-MM/YYYY-MM`, the first and last month of the one protected
three-month window exported by version 1. Window primitives are monthly averages (person-months
divided by the months in the window), which stay additive across units of their own additive family
(ASSUMPTION). The format is
retained for backlog item L4, but a version 1 release contains no series or second protected
window. Public tables keep the source period: `YYYY`, `YYYY-MM`, `YYYY-Qn`, or `YYYY/YYYY` for a
change between two years.

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
| `resident_pay` | Protected | unit × period × measure × housing class × band range | `unit_id`, `period`, `measure`, `housing_class`, `band_from`, `band_to` | `privacy` | `area_evidence`, `compare_areas` |
| `worker_pay` | Protected | unit × period × measure × band range | `unit_id`, `period`, `measure`, `band_from` | `privacy` | `area_evidence`, `compare_areas` |
| `home_area_share` | Protected | work unit × home unit × period | `work_unit_id`, `home_unit_id`, `period` | `privacy` | `area_evidence` |
| `outlet_register` | Protected | unit × period × activity class × size band | `unit_id`, `period`, `activity_node_id`, `size_band` | `privacy` | `area_evidence` |
| `occupation_pay` | Protected | unit × period × measure × basis × group × band range | `unit_id`, `period`, `measure`, `basis`, `occupation_group`, `band_from` | `privacy` | `pay_benchmark` |
| `presence_index` | Simulated | unit × situation × summer × segment | `unit_id`, `situation`, `summer`, `segment` | `privacy` (from the `mobility` feed) | `area_evidence`, `stage` |
| `flow_od` | Simulated | origin unit × destination unit × situation × summer | `origin_unit_id`, `destination_unit_id`, `situation`, `summer` | `privacy` (from the `mobility` feed) | `stage` |
| `speed_factor` | Simulated | road class × situation × summer | `road_class`, `situation`, `summer` | `mobility` | `make_area` |
| `pub_licence_active` | Public | municipality × activity code × snapshot | `municipality_code`, `activity_code`, `period` | `publicdata` | `sector_facts`, `area_evidence` |
| `pub_licence_cancelled` | Public | municipality × activity code × month | `municipality_code`, `activity_code`, `period` | `publicdata` | `sector_facts` |
| `pub_zone_utility` | Public | zone × year × utility | `zone_code`, `period`, `utility` | `publicdata` | `sector_facts`, `area_evidence` |
| `pub_transit_monthly` | Public | month × mode | `period`, `mode` | `publicdata` | `area_evidence`, `sector_facts` |
| `pub_sector_accounts` | Public | activity × year × indicator | `activity_code`, `period`, `indicator` | `publicdata` | `sector_facts` |
| `pub_wage_table` | Public | table × period × breakdown | `table_code`, `period`, `breakdown_key`, `indicator` | `publicdata` | `pay_benchmark`, `sector_facts` |
| `pub_customs_import` | Public | tariff line × origin × month | `tariff_code`, `origin_iso3`, `period` | `publicdata` | `supplier_lens` |
| `pub_property_sale` | Public | district × year × property type | `district_key`, `period`, `property_type` | `publicdata` | `area_evidence` |
| `pub_census_zone` | Public | zone × census year × indicator | `zone_code`, `period`, `indicator` | `publicdata` | `area_evidence` |
| `pub_population_municipality` | Public | municipality × period × indicator | `municipality_code`, `period`, `indicator` | `publicdata` | `sector_facts`, `area_evidence` |
| `pub_census_national` | Public | period × indicator | `period`, `indicator` | `publicdata` | `sector_facts`, `area_evidence` |
| `pub_census_district` | Public | district × period × indicator | `district_key`, `period`, `indicator` | `publicdata` | `area_evidence` |
| `pub_place` | Public | place | `place_id` | `publicdata` | `scan_places`, `resolve` |
| `pub_place_verification` | Public | place × check date | `place_id`, `check_date` | `publicdata` | `scan_places`, `resolve` |
| `pub_hotel_monthly` | Public | month × star class × indicator | `period`, `star_class`, `indicator` | `publicdata` | `sector_facts` |
| `pub_price_index` | Public | month × group | `period`, `group_code` | `publicdata` | `sector_facts` |
| `graph_node` | Graph | node | `node_id` | `publicdata`, `release` (lineage nodes) | `resolve`, `supplier_lens`, `scan_places`, `sector_facts` |
| `graph_edge` | Graph | edge | `edge_id` | `publicdata`, `release` (lineage edges) | same as `graph_node` |
| `fact_lineage` | Lineage | lineage id × source | `lineage_id`, `source_id` | `release` | evidence drawer API (all tools set `lineage_ref`) |
| `source_registry` | Lineage | source | `source_id` | `publicdata`, `release` | evidence drawer API, Trust centre |
| `rules_version` | Control | rule × parameter set | `rules_version_id`, `parameter_set`, `rule_code` | `privacy` | all tools, Trust centre |
| `suppression_reason` | Control | reason code | `code` | `privacy` | all tools ("Why can't I see this?") |
| `survival_report` | Control | parameter set × partition | `parameter_set`, `partition_id` | `privacy` | Proof room |

`release_manifest` is deliberately absent from this Parquet catalogue and from `manifest.tables`.
The loader materialises it in each store from the verified `manifest.json`, as specified in section
8. It has no Parquet file and is never an input to its own release hash.

### 7.3 Columns

Types follow section 1.2; a column without a stated type is `string`. Every Public table also has
`source_id` (N), which joins `source_registry`. "Cnt" means a treated, rounded `int` primitive.

| Table | Columns |
|---|---|
| `grid_cell` | `cell` cell; `resolution` int (8 or 9); `parent_r7` cell; `in_greater_doha` bool; `zone_code` string; `district_key` string; `municipality_code` string; `geometry` geometry |
| `release_unit` | `unit_id` string; `partition_id` string; `unit_kind` string (`cell`, `merged`, `remainder`, `municipality`, `national`), where `municipality` is the terminal `ha_home` unit; `resolution` int (Y, null for `remainder`, the terminal `ha_home` municipality unit and `national`); `municipality_code` string (Y, null for `national`); `rule_tier` string (`count`, `money`, `quartile`); `status` string (`published`, `withheld`); `suppression_reason_code` string (Y, null when published); `geometry` geometry |
| `unit_member` | `unit_id` string; `cell` cell |
| `zone` | `zone_code` string; `name_en` string; `name_ar` string; `municipality_code` string; `geometry` geometry; `source_id` |
| `district` | `district_key` string; `name_en` string; `name_ar` string; `municipality_code` string; `geometry` geometry; `source_id` |
| `municipality` | `municipality_code` string; `name_en` string; `name_ar` string; `geometry` geometry; `source_id` |
| `gazetteer` | `place_key` string; `kind` string (`municipality`, `zone`, `district`, `landmark`, `building`, `station`, `place`); `name_en` string; `name_ar` string; `aliases` string (semicolon-separated, Y); `lon`, `lat` decimal(9,6); `cell` cell; `showcase_verified` bool; `source_id` |
| `resident_pay` | `unit_id`; `period`; `measure` (`net`, `basic`); `housing_class` (`family_housing`, `labour_accommodation`, `institution`, `unknown`, `other`, `all`); `band_from`, `band_to` (B01..B12 or `ALL`); `earner_count` Cnt; `wage_bill` decimal(16,0) (Y: only on `ALL` rows of `money` or `quartile` tier units); `not_measured_count` Cnt (Y: only on `ALL` rows whose unit belongs to `rp_housing_count`); `irregular_count` Cnt (Y: only on those same rows) |
| `worker_pay` | `unit_id`; `period`; `measure`; `band_from`, `band_to`; `earner_count` Cnt; `wage_bill` (as above); `deployed_elsewhere_count` Cnt (Y: only on `ALL` rows whose unit belongs to `wp_site_count`); `irregular_count` Cnt (Y: only on those same rows) |
| `home_area_share` | `work_unit_id`; `home_unit_id` (the terminal municipality unit of `ha_home`, formed as the union of every `op_res_quartile` whole-cell unit and remainder of the governing residence family in that municipality); `period`; `earner_count` Cnt |
| `outlet_register` | `unit_id`; `period`; `activity_node_id` (an `activity_class` node); `size_band` (`no_payroll`, `s01_09`, `s10_49`, `s50_plus`; ASSUMPTION); `outlet_count` Cnt |
| `occupation_pay` | `unit_id`; `period`; `measure`; `basis` (`residence`, `workplace`); `occupation_group` (ISCO-08 major group `0`..`9`, `unmapped`, `other`); `band_from`, `band_to`; `earner_count` Cnt; `wage_bill` (as above) |
| `presence_index` | `unit_id`; `situation`; `summer` bool; `segment` (`resident`, `worker`, `visitor`); `presence_score` decimal(14,4), unitless and additive across units, never a count of people or devices |
| `flow_od` | `origin_unit_id`; `destination_unit_id`; `situation`; `summer`; `flow_score` decimal(14,4), unitless |
| `speed_factor` | `road_class`; `situation`; `summer`; `factor` decimal(5,3) (ratio to free-flow speed) |
| `pub_licence_active` | `municipality_code`; `activity_code` string; `activity_name_ar` string; `period` (snapshot month); `active_count` int |
| `pub_licence_cancelled` | `municipality_code`; `activity_code`; `period` (`YYYY-MM`, or `UNDATED` where the source has no date); `cancelled_count` int; `bulk_month` bool (flagged administrative bulk month) |
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
| `graph_node`, `graph_edge` | section 10 |
| `fact_lineage` | `lineage_id` string (`lin_` plus the table name, with a suffix when one table has several transforms); `table_name` string; `partition_id` string (Y: required for a protected-table home family, null otherwise); `measure` string (Y: `net` or `basic` where the protected table has that dimension, null otherwise); `breakdown` string (Y: required for a protected-table home family and one of `none`, `band`, `housing_class`, `occupation_group_by_band`, `home_municipality`, `side_count_type`, `activity_class_by_size_band`; null otherwise); `family_role` (`single`, `numerator`, `denominator`; Y for a protected-table home family, null otherwise); `source_id` string; `input_class` (`public`, `synthetic`, `simulated`); `transform` string (`module.function@version`); `rules_version_id` string (Y, null for Public tables) |
| `source_registry` | `source_id` string; `kind` (`public_dataset`, `public_document`, `reviewed_config`, `synthetic_feed`, `simulation_output`); `title`; `publisher`; `url` (Y for synthetic and simulated); `licence` string; `retrieved_on` date; `sha256` string; `commit_allowed` bool; `attribution` string |
| `release_manifest` (loader-materialised store table only) | One row per entry of verified `manifest.tables`: `release_id`; `table_name`; `provenance_class` (`frame`, `protected`, `simulated`, `public`, `graph`, `lineage`, `control`); `file`; `sha256`; `row_count` int; `schema_sha256`; plus the scalar fields of section 8 repeated on every row. It has no row for itself. |
| `rules_version` | `rules_version_id`; `parameter_set` (`A`, `B`, `shared`); `rule_code`; `value` string; `unit` string; `description_en` string |
| `suppression_reason` | `code` (upper snake case, for example `BELOW_MIN_EARNERS`, `EMPLOYER_DOMINANCE`, `TOP_TWO_DOMINANCE`, `PERSON_CONCENTRATION`, `REMAINDER_FAILED`); `label_en`; `label_ar` (pending native review); `explanation_en`; `explanation_ar` |
| `survival_report` | `parameter_set`; `table_name`; `partition_id`; `units_total`, `units_published`, `units_pooled`, `units_withheld` int; `earners_published_share` decimal(5,2) (rounded to whole percent) |

The following closed lists and placement rules are part of the release schema, not application
conventions.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-127 | Protected category rows accept exactly these values: `resident_pay.housing_class` is `family_housing`, `labour_accommodation`, `institution`, `unknown`, `other` or `all`; `occupation_pay.occupation_group` is `0` to `9`, `unmapped` or `other`. `other` is a treated leaf and exists only where pooling occurred. For a primitive in a family with a breakdown, its `all` or band `ALL` row is the derived exact sum of the treated leaves of that family and is not treated again. For a primitive in a family with no breakdown, the applicable `all` or band `ALL` row is itself the one treated leaf. Side counts exist only on band `ALL` rows whose `resident_pay` unit belongs to `rp_housing_count` or whose `worker_pay` unit belongs to `wp_site_count`. | Closed-enum fixtures reject every other value; a second treatment of a derived `all` or `ALL` row fails; a no-breakdown `all` or `ALL` leaf passes and its absence fails; an `other` row without pooled source categories fails; side-count rows on any other partition or band fail. |
| DAT-128 | The audit-count indicator and unit pairs in `pub_census_zone`, `pub_population_municipality`, `pub_census_national` and `pub_census_district` are exactly `residents`/`persons`, `households`/`households`, `establishments`/`establishments` and `employees`/`persons`. Indicator names are lower snake case. Any other indicator is not a count and must have status `not_applicable` in `artefacts/attacker_view_public_totals.json` until a release-contract revision adds it to this list. Every applicable count row must be representable and enabled under PRV-115; an applicable municipality, district, zone or national row that is absent, unconfigured or cannot be mapped safely fails the privacy build. While OI-04 remains open, `pub_census_zone` and `pub_census_district` are present in every release with their declared schemas and zero rows. | One fixture for each allowed pair passes; a wrong unit, mixed-case indicator, enabled unlisted indicator, absent applicable row, unconfigured applicable row or unsafe mapping fails; the OI-04 fixture proves both tables exist, have zero rows and load in both stores. |
| DAT-129 | `rules_version.parameter_set` is exactly `A`, `B` or `shared`. The A and B rule-code allowlist is `min_earners_count`, `min_groups_count`, `min_earners_money`, `min_earners_quartile`, `max_group_share`, `max_top2_share`, `max_person_share`, `min_band_cell`, `round_count`, `round_money`, `min_earners_trend`, `min_panel_devices`, `audit_headcount_width`, `audit_wage_relative_width` and `money_delta`. The shared rule-code allowlist is `export_parameter_set`, `window_months`, `min_full_month_days`, `situation_windows`, `presence_scale`, `flow_scale`, `feasibility_tolerance`, `integrality_tolerance`, `optimality_tolerance` and `outward_bound`. `min_full_month_days` has value `20` and unit `days`; `situation_windows` has the exact unit and value defined in section 7.1. Every listed code occurs exactly once for each applicable parameter set; no other code is accepted. | Exact-set comparison by parameter set; complete shared-rule fixture passes; missing, duplicate, misplaced, unknown, altered-window and wrong-unit fixtures fail. |
| DAT-130 | `suppression_reason.code` is exactly one of `SNAPPED_TO_WHOLE_UNITS`, `PART_OF_AREA_POOLED`, `BANDS_MERGED`, `DEPLOYED_ELSEWHERE_NOT_MAPPED`, `POOLED_IN_REMAINDER`, `REMAINDER_FAILED`, `FAILED_THIS_PERIOD`, `DETAIL_NEEDS_LARGER_GROUP`, `SPLIT_NOT_PUBLISHABLE`, `BANDS_NOT_SHARED`, `BELOW_PANEL_MINIMUM`, `NOT_MEASURED`, `OUTSIDE_FRAME`, `NO_FIRM_OR_PERSON_FACTS`, `DIMENSION_NOT_OFFERED`, `AREAS_FROM_PINS_ONLY`, `NO_TIME_SERIES`, `EGRESS_BLOCKED`, `BELOW_MIN_EARNERS`, `BELOW_MIN_EMPLOYER_GROUPS`, `EMPLOYER_DOMINANCE`, `TOP_TWO_DOMINANCE`, `PERSON_CONCENTRATION` or `BAND_TOO_SMALL`. The release contains one row for each code and no other row. | Exact-set comparison; unknown, missing and duplicate code fixtures fail. Scene fixtures prove `NO_FIRM_OR_PERSON_FACTS`, `AREAS_FROM_PINS_ONLY` and `BELOW_PANEL_MINIMUM` are representable. |

`unit_id` is `<partition_id>:<kind>:<n>` (kind `c`, `m`, `r`, `u` or `n`, with `u` for the terminal
`ha_home` municipality unit; `n` a six-digit sequence ordered
by the smallest member cell), for example `rp_all_money:m:000042`. Partitions and tiers: document 06.
Derived statistics (mean, median band, quartile bands, shares, the presence index) are computed by
`core` from primitives with thresholds from `rules_version` ([07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md)).
A ratio statistic is one of the mean wage or the coverage, irregular or deployed-elsewhere shares.
Its numerator and denominator come from columns of the same stored rows: one table, one partition,
one unit set and one measure where the table has measures. Those columns may belong to two additive
families, and `fact_lineage` names both with `family_role` values `numerator` and `denominator`.
This closed list is the only exception to one home family per figure (PRV-30).

## 8. The manifest and the loader

Every release directory holds `manifest.json`. Its scalar `release_kind` is `public_only` or
`protected`. Scalars common to both kinds are `release_id`, `release_contract_version`
(`release.v1`), `build_id`, `built_at` (provenance only), `code_version` (the full git commit hash),
`rules_version_id` and `engine_versions` (DuckDB, PostGIS target, Python). A `protected` manifest
also has `parameter_set` (the one exported set, `A` or `B`), `world_seed`, `spare_seeds`,
`scenario_sha256` (the committed scenario hash), `window_key`, `protected_sha256` and `contracts`
(list of `{name, revision, feed_sha256, reference_period}`). A `public_only` manifest omits
`window_key`, `protected_sha256`, `parameter_set`, `world_seed`, `scenario_sha256` and `contracts`.
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
`feed_sha256` already recorded for that feed in `manifest.contracts` (PRV-120). `mobility.v1`,
Public and Simulated tables, rules, reports and scene fixtures are not inputs.
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
| `artefacts/attacker_view_public_totals.json` | Canonical, versioned, signed inventory required by PRV-115. Its entry identifiers equal exactly one source entry for every `source_registry` row plus one row entry for every row of every Public manifest table, and each entry records `enabled` or `not_applicable` under PRV-115. |
| `artefacts/reports/closure_report.json` | Selected-export exhaustive structural-check results and repeated fuzz count and seed required by PRV-49 and PRV-111, naming the release by `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set`. Candidate A and B reports remain inside the custodian plane. |
| `artefacts/reports/attacker_view_audit_report.json` | Attacker-view audit report required by PRV-69 and PRV-112 to PRV-116: per parameter set, the person and employer-group target-class counts, solve count, outward-rounded interval widths, elapsed time and pass or fail. |
| `artefacts/reports/attack_report.json` | Signed Ed25519 attack-report envelope required by PRV-79; it carries aggregate results for A and B and no unselected protected row. |
| `artefacts/reports/survival_detail_report.json` | Signed Ed25519 survival-detail-report envelope required by PRV-81; it carries the A and B aggregate detail. |
| `artefacts/scene/two_shapes.json` | Signed scene-fixture envelope for the two prepared requests of scene step 2 under PRV-106. |
| `artefacts/scene/complement.json` | Signed scene-fixture envelope for the two prepared requests and pre-validated unit sets of scene step 3 under PRV-106 and PRV-119. Their symmetric difference is exactly one published `merged` unit containing at least two base cells, and no figure exists for any member base cell alone (PRV-105). |
| `artefacts/scene/injection.json` | Signed scene-fixture envelope for the catalogue and injection regression of scene step 4 under PRV-119. |

The non-privacy build report `artefacts/reports/fidelity_report.json` is also listed in
`manifest.artefacts`; it is the machine-readable fidelity report of SYN-34 used by the Proof room.

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
| DAT-83 | The loader refuses any table whose name is not in section 7.2, any protected-table column outside the DAT-71 allowlist, any closed-list value or placement that fails DAT-127 to DAT-130, any within-family total that differs from the exact sum of its own additive-family leaves, any column named `person_id`, `establishment_id`, `legal_entity_id`, `group_id` or `file_id`, and any string value matching one of the five identifier prefixes `SYN-E-`, `SYN-L-`, `SYN-G-`, `SYN-P-` or `SYN-F-`. The loader does not compare two different additive families for equality; PRV-71 performs the custodian-plane cross-family bound check before export. | One fixture per refusal reason, including every closed list, a wrong within-family sum and each of the five identifier forms; a cross-family difference loads without an equality or reconciliation check. |
| DAT-84 | The loader writes the same tables to PostgreSQL (schema `r_` plus the first 16 hexadecimal characters of the full `release_id`) and to the DuckDB standby file, and materialises `release_manifest` in both from verified `manifest.json`. Both stores are staged and verified before `load_receipt.json`, which is not listed in `manifest.artefacts`, is written with `state: complete` and `release_id` equal to the mounted manifest's id. A protected-release receipt also carries matching `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set`; a `public_only` receipt omits those protected-window fields. Preflight and the API refuse a release without the receipt, without `state: complete`, with a mismatched `release_id`, or, for a protected release, with any mismatched protected-window field. The parity suite compares the stores after the rounding rule stated in [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md). | Parity suite green on both engines, including `release_unit.geometry`, `district` and `grid_cell.district_key`; an absent, incomplete or wrong-release receipt refuses service; protected and `public_only` receipt fixtures enforce their conditional fields. |
| DAT-85 | Every source in `manifest.sources` has a licence and a retrieval date; a source whose `commit_allowed` is false (for example the census map layers, master OI-04) is fetched at build time and never committed. | Manifest check; repository scan finds no such file. |
| DAT-131 | For a `protected` release, the manifest lists every privacy artefact at the exact path in the inventory above and no second file with the same role. A `public_only` release does not require a privacy artefact. Every signed JSON artefact is one canonical envelope containing its payload, `signature_algorithm` equal to `Ed25519`, `public_key_id` and `signature`; its manifest SHA-256 covers the complete envelope. The fixture identifier for each scene artefact is `scene:` followed by that lowercase manifest SHA-256. Every artefact and report follows the release-identity rule of DAT-80. The artefact scan also fails on any untreated aggregate, knowledge-fixture value, target value or other person-level or employer-level true value. | Protected-release exact-path and one-role checks; missing, renamed, duplicate-role, unsigned, tampered, wrong-release-name, forbidden-identity-field and true-value fixtures fail. A `public_only` fixture without privacy artefacts passes. The attacker-view report fixture proves that target-class counts, solve counts, outward-rounded interval widths, elapsed time and pass or fail are representable without a true value. |
| DAT-132 | For a `protected` release, `manifest.parameter_set` equals the shared `export_parameter_set` and exactly that set's protected tables occur in `manifest.tables`. The default `export_parameter_set` is `A` and is fixed with `presence_scale` and `flow_scale` at the slice S1 gate before the first world build; OI-35 permits an owner or data owner to overrule it only before that gate. `survival_report`, `artefacts/reports/survival_detail_report.json` and `artefacts/reports/attack_report.json` retain aggregate A and B results. No unselected protected table or row occurs anywhere in the release. A `public_only` release has no `parameter_set`, protected table, Simulated table or protected-window field and is never frozen or registered. | Protected candidate build with both table sets fails; a protected candidate with the wrong selected set fails; a missing or post-gate selection fails; aggregate report fixtures for both sets pass; a `public_only` fixture with any forbidden table or field, freeze descriptor or register line fails. |
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
    "unit": {"enum": ["count", "qar_per_month", "qar", "qar_thousand", "qar_per_kg", "qar_per_m2",
                      "kwh", "riders", "ratio", "percent", "index", "wage_band", "metres",
                      "minutes", "covers_per_day", "rank", "direction"]},
    "period": {"type": "string", "minLength": 4},
    "geography": {
      "type": "object", "additionalProperties": false, "required": ["kind"],
      "properties": {
        "kind": {"enum": ["release_units", "public", "national", "user_scenario"]},
        "unit_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "public_code": {"type": "string", "pattern": "^(zone|municipality|district|place):.+$"}},
      "allOf": [
        {"if": {"properties": {"kind": {"const": "release_units"}}, "required": ["kind"]},
         "then": {"required": ["unit_ids"], "not": {"required": ["public_code"]}}},
        {"if": {"properties": {"kind": {"const": "public"}}, "required": ["kind"]},
         "then": {"required": ["public_code"], "not": {"required": ["unit_ids"]}}},
        {"if": {"properties": {"kind": {"enum": ["national", "user_scenario"]}}, "required": ["kind"]},
         "then": {"not": {"anyOf": [{"required": ["unit_ids"]}, {"required": ["public_code"]}]}}}]},
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
    {"if": {"properties": {"unit": {"enum": ["qar_per_month", "qar", "qar_thousand", "qar_per_kg",
                                                "qar_per_m2", "kwh", "riders", "ratio", "percent",
                                                "index", "metres", "minutes", "covers_per_day"]}},
            "required": ["unit"]},
     "then": {"properties": {"value": {"type": ["number", "null"]}}}},
    {"if": {"properties": {"unit": {"const": "rank"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": ["integer", "null"], "minimum": 1}}}},
    {"if": {"properties": {"unit": {"const": "direction"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"enum": ["higher", "lower", "equal", null]}}}},
    {"if": {"properties": {"unit": {"const": "wage_band"}}, "required": ["unit"]},
     "then": {"properties": {"value": {"type": ["string", "null"],
                                        "pattern": "^B(0[1-9]|1[0-2])(\\.\\.B(0[1-9]|1[0-2]))?$"}}}},
    {"if": {"properties": {"input_classes": {"contains": {"const": "user_input"}}},
            "required": ["input_classes"]},
     "then": {"properties": {"evidence_status": {"const": "inferred"}}}}]
}
```

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-90 | Every tool result validates against the schema; a fact that fails is dropped and its slot shows the `NO_DATA` template. Non-suppressed numeric units require non-null numeric values, `count` requires an integer, `wage_band` accepts only B01–B12 or a `B01..B02`-style range, only a Suppressed fact has a null value, each geography kind has mutually exclusive fields, and every `lineage_ref` must pass DAT-94 before the API emits the fact. | Schema and lineage validation in every tool test; null numeric, fractional count, numeric wage-band, non-suppressed null, mixed-geography and unresolved-lineage fixtures fail. |
| DAT-91 | Least-real rule, computed in `core`: unless the fact is `suppressed`, `provenance` equals the least-real class in `input_classes` (Public more real than Synthetic, more real than Simulated); `user_input` does not take part in the ordering. | Property test over all class combinations. |
| DAT-92 | A fact computed from the user's own inputs carries `user_input` and `evidence_status = inferred`, the caveat key `your_inputs`, and a `lineage_ref` that resolves the deterministic method and every release fact used with those inputs. It is never written to the release or the store. | Break-even fixture: the fact has complete method and release-input lineage, appears in the API response and in no table. |
| DAT-93 | `fact_id` matches `^f_[0-9a-f]{32}$` and is the first 32 hexadecimal characters of the SHA-256 of the canonical JSON of (`release_id`, `metric_key`, `geography`, `period`, `qualifiers`). Tool names, canonical arguments and fact slots are not inputs. | Two calls producing the same semantic fact return identical ids; changing any semantic component changes the id; a different tool-call shape alone does not. |
| DAT-94 | `lineage_ref` names a `lineage_id` in `fact_lineage` and resolves the complete Source chain: fact → release table → deterministic method and version → source with publisher, dataset or page, licence, retrieval date and file SHA-256. For a fact derived from a protected table, the same lineage normally names exactly one home additive family through `table_name`, `partition_id`, `measure` where that table has measures, `breakdown` and `family_role: single`; every source row of that `lineage_id` repeats the same family tuple. The only exception is a ratio statistic in the closed list: mean wage, coverage share, irregular share or deployed-elsewhere share. Its numerator and denominator come from columns of the same stored rows — one table, one partition, one unit set and one measure where applicable — even when the columns belong to two additive families; its lineage contains both tuples with `family_role: numerator` and `family_role: denominator`. No extra field is added to the fact object. A count and adjacent non-ratio shares must resolve to the same family, and no output may present two families as two numeric estimates of one population (PRV-30). A fact with an absent, unresolved or incomplete chain or required protected family tuple is not a fact: the release build fails if it constructs one, and the fact API does not emit it. | Every fact in the golden set resolves the complete chain; every non-ratio protected fact resolves one `single` home-family tuple; each ratio-statistic fixture resolves numerator and denominator tuples from the same stored rows. Planted missing or inconsistent table, partition, applicable measure, breakdown, family role, method version, publisher, dataset or page, licence, retrieval date and file-hash links each fail both build and API validation. A ratio whose rows or unit set differ, a ratio outside the closed list with two families, a card whose count and adjacent non-ratio shares have different home-family tuples, and a layout that places two routes to one population side by side all fail validation. |
| DAT-95 | The schema allows exactly the three pinned evidence statuses. "Not measured" is a display state rendered from the coverage key `not_measured`, never an evidence status (ASSUMPTION: keeps the pinned field list intact). | Enumeration check. |
| DAT-134 | Difference, ratio, rank and direction are comparison fact kinds. Difference keeps the compared measure's unit; ratio uses `ratio`; rank uses the positive-integer unit `rank`; direction uses `direction` with value `higher`, `lower` or `equal` (ASSUMPTION: the master design names the kind but not its wire values). Comparison facts are produced only by deterministic, tested functions in `eii_core.calc`, validate against the same fact schema and complete Source-chain rule as every other fact, and enter claim slots by fact id. A model, template or browser never computes or selects their values. | One regression for each comparison kind and each direction value; fixtures produced by a model, template or browser fail the calculation-origin check. |
| DAT-135 | Every answer receipt carries `accounting_gate` with label `Checked before display`, overall `result` (`pass` or `fail`) and exactly five checks in this order: `Sources`, `Assumptions`, `Nothing invented`, `Scope`, `Limits stated`. Each check is `{name, result}`, with `result` equal to `pass` or `fail`. A failed check selects the template writer's default answer and is retained in the receipt. | Exact-schema and order test; one planted failure per check proves the failed result, default answer and retained receipt. |

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
{"fact_id": "f_9c4e2a7b1d0f6e3a9c4e2a7b1d0f6e3a", "value": "B03", "unit": "wage_band", "period": "2026-04/2026-06",
 "geography": {"kind": "release_units",
               "unit_ids": ["rp_all_money:m:000042", "rp_all_money:c:000107", "rp_all_money:c:000108"]},
 "provenance": "synthetic", "input_classes": ["synthetic", "public"], "evidence_status": "observed",
 "reliability": "standard", "coverage_keys": ["covered_private_sector_only", "not_measured_shown"],
 "caveat_keys": ["synthetic_not_evidence_about_qatar"],
 "label_en": "Median net pay band, covered earners living within reach",
 "label_ar": "<Arabic label, pending native review>",
 "lineage_ref": "lin_resident_pay", "release_id": "5f2c9ab04e7d1c3a5f2c9ab04e7d1c3a5f2c9ab04e7d1c3a5f2c9ab04e7d1c3a"}
```

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
| `place_category` | public places taxonomy category | open places release |
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
| `found_near` | `place_category` → `place_category` | `computed` (co-location quotient over public places, method in [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md)) | quotient and permutation p-value |
| `sourced_from` | any Public node or `table` → `source` | `lineage` | none |
| `contains` | `release` → `table` | `lineage` | none |

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-100 | An edge joins two Public nodes, or it is a lineage edge whose provenance is `lineage` and whose one end is a `source`, `table` or `release` node. | Edge check over the whole graph. |
| DAT-101 | No node or edge refers to a firm, establishment, legal entity, group or person, real or synthetic: no firm-level edges. | Build fails if any code matches `SYN-` or any node type outside the table above exists. |
| DAT-102 | Every `activity` node has exactly one `classified_as` edge; legacy codes without a reviewed mapping point to `UNMAPPABLE` and stay visible. | Degree check. |
| DAT-103 | Every non-lineage edge has a `source_id` with a licence in `source_registry`. | Join check. |

## 11. Lineage and source registry

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-105 | Every release table has at least one `fact_lineage` row; every `lineage_id` lists each source and each input class that fed the table. | Join `release_manifest` to `fact_lineage`. |
| DAT-106 | Every source in `source_registry` has publisher, dataset or page title, licence, retrieval date and file SHA-256. A Public source also has its URL. A Synthetic or Simulated source uses the feed producer as publisher, the contract and feed as title, the repository licence, the build date as retrieval date and the feed file hash; its seed remains provenance in the manifest rather than replacing any Source-chain field. | Not-null check for every source-chain field; Public URL check; Synthetic and Simulated feed-hash-to-registry check. |
| DAT-107 | The input class of a `fact_lineage` row follows the source kind: `public_dataset`, `public_document` and `reviewed_config` give `public`; `synthetic_feed` gives `synthetic`; `simulation_output` gives `simulated`. | Mapping check. |

## 12. The application schema (PostgreSQL only, schema `app`)

This is the one canonical DDL for the application schema. The forward-only migrations under
`infra/postgres/` must implement it verbatim in substance; [08_BACKEND.md](08_BACKEND.md) and all
other documents refer here rather than restating columns or policies. The fixed read-function names
are an ASSUMPTION: the master design pins their behaviour but not their names.

The application generates every application identifier as UUID version 7. The DDL deliberately has
no identifier defaults, so disconnected SQLite replay retains the identifiers assigned by the
application. `payload_bytes` holds the exact proposed or sent UTF-8 payload; `payload_json` is only
an optional parsed projection. There are no hash-chain fields: replay safety comes from stable
UUIDv7 primary keys and idempotent inserts.

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

CREATE TABLE app.brief (
  brief_id uuid PRIMARY KEY,
  answer_id uuid NOT NULL,
  organisation_id uuid NOT NULL,
  seat_key text NOT NULL,
  release_id text NOT NULL CHECK (release_id ~ '^[0-9a-f]{64}$'),
  language text NOT NULL CHECK (language IN ('en', 'ar')),
  playbook text NOT NULL CHECK (playbook IN ('site_check', 'staffing_and_pay', 'costs_and_suppliers')),
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
  playbook text CHECK (playbook IS NULL OR playbook IN
    ('site_check', 'staffing_and_pay', 'costs_and_suppliers')),
  tool text CHECK (tool IS NULL OR tool IN
    ('resolve', 'make_area', 'area_evidence', 'scan_places', 'compare_areas',
     'pay_benchmark', 'sector_facts', 'supplier_lens', 'stage')),
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
  payload_bytes bytea NOT NULL,
  payload_json jsonb,
  fact_ids_sent jsonb NOT NULL,
  usage jsonb,
  stop_reason text,
  scan_result text NOT NULL,
  cost_estimate_usd numeric(18,8),
  UNIQUE (answer_id, request_ordinal),
  FOREIGN KEY (seat_key, organisation_id)
    REFERENCES app.seat(seat_key, organisation_id)
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
               release_id text, language text, playbook text, question_text text,
               brief_json jsonb, catalogue_version text, memo_key text,
               created_at timestamptz)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
SET row_security = on
AS $$
  SELECT b.brief_id, b.answer_id, b.organisation_id, b.seat_key, b.release_id,
         b.language, b.playbook, b.question_text, b.brief_json,
         b.catalogue_version, b.memo_key, b.created_at
  FROM app.brief AS b
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
    SELECT l.area_cell, l.activity_key, l.playbook, l.organisation_id
    FROM app.ledger_entry AS l
    WHERE current_setting('eii.seat', true) = 'oversight'
      AND EXISTS (SELECT 1 FROM app.seat AS s
                  WHERE s.seat_key = 'oversight' AND s.role = 'oversight')
  ), grouped AS (
    SELECT CASE p_by
             WHEN 'area' THEN area_cell::text
             WHEN 'activity' THEN activity_key
             WHEN 'decision' THEN playbook
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
labels, seat keys, question text, brief text, raw tool arguments and outbound payload content.

| ID | Requirement | Conformance test |
|---|---|---|
| DAT-110 | Tables and fixed read functions are owned by `eii_owner`, a role the application does not use. Every `app` table has row-level security enabled and forced. `eii_app` has no `SELECT` on an `app` base table and reads only through the canonical functions with locked empty `search_path` and explicit seat checks. | Catalogue and privilege queries prove ownership, `relforcerowsecurity`, no base-table `SELECT` and function settings; direct base reads fail. |
| DAT-111 | After one-time picker selection, the API verifies the signed `eii_seat` session cookie and calls `read_seat_context` to derive the organisation. It sets `eii.seat` and `eii.organisation` only as transaction-local settings from that result, never from an address or request field. Policies compare those settings directly with `seat_key` and `organisation_id`, without a base-table subquery. All application ids are UUID version 7 generated by the application. A request without a valid seat sees no rows. | Cookie-to-setting and pool-reuse tests; queries with missing or empty settings return no rows; cross-organisation settings fail; identifier fixtures prove UUID version 7 and replay-stable ids. |
| DAT-112 | A company seat reads and writes only rows of its own organisation through the company return types and insert policies. Company B cannot read Company A's brief. | Database-level tests as Company B, oversight, unset seat and empty seat return no Company A brief; cross-seat inserts fail. |
| DAT-113 | `ledger_entry` and `egress_record` are append-only: no role used by the application has UPDATE or DELETE. Stable UUIDv7 primary keys and `ON CONFLICT DO NOTHING` make local replay idempotent; no hash chain is defined. | Privilege check; replay, repeated replay and interruption-after-commit fixtures produce no duplicates or loss. |
| DAT-114 | Oversight reads ledger, egress and demand rows only through the fixed oversight return types, which carry no organisation identity, question text, brief text, raw tool arguments or outbound payload content, and reads no brief rows. The fixed demand function performs the aggregate and applies the configured `distinct_organisation_minimum`, default 2; this is demonstration configuration, not a disclosure threshold. Live rows are tagged "this session"; seeded rows are marked Synthetic (master OI-08). | Return-type inspection and planted-field tests, including resolve text inside a tool argument; one organisation is suppressed and two are displayed under the default; non-oversight calls return no rows; direct base reads fail. |
| DAT-115 | The application role has `SELECT` only on the configured `r_<first 16 hexadecimal characters of release_id>` release schema, not on application base tables; a release write attempt fails. | Privilege and write-refusal tests. |

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

## 13. Versioning and compatibility

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
(DAT-04); (4) register scope excludes government and separately licensed zone entities (6.1);
(5) all quality thresholds and the 1% quarantine limit are proposals (DAT-10, DAT-24); (6) eligible
person-month rule and `basic` from the latest record (6.3); (7) OD flows at H3 resolution 7 (6.5);
(8) situation hour windows and the Sunday-to-Thursday week (7.1); (9) window primitives are monthly
averages within their additive family (7.1); (10) outlet size bands (7.3); (11) scalar values in
linked-input hash JSON use the canonical representations fixed in section 8; (12) fixed application read-function names
(section 12); (13) "Not measured" is a coverage key (DAT-95); (14) forward-only application
migrations (DAT-125); (15) comparison-direction wire values are `higher`, `lower` and `equal`
(DAT-134); (16) the attacker-view audit report path is
`artefacts/reports/attacker_view_audit_report.json`.

Open items from the master design that touch this document: OI-03 (two public wage tables and two
restaurant totals: `pub_wage_table.table_code` keeps tables apart until reconciled), OI-04 (census map
layers: `commit_allowed = false`), OI-06 (source labels: contracts use neutral record-type names),
OI-08 (ledger labels and oversight view, DAT-114), OI-11 (thresholds are proposals; DAT-60 uses set A).
OI-35 fixes the exported set before treatment; the default is A (DAT-132, PRV-120).

Open question: confirm the eligibility rule and window averaging against documents 06 and 07; if they
differ, the lead decides and this document is revised.

## Sources

All retrieved 2026-11-11.

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
