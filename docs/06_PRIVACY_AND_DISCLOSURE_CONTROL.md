# 06 — Privacy and Disclosure Control

| | |
|---|---|
| Status | Draft v0.3, corrected after four independent reviews on 2026-11-11; the last ten corrections await review by another maker (OI-37) |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Specify the privacy engine: what may be released from linked custodian-type records, how it is treated, audited and attacked, and what is not claimed. |
| Read first | [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md), [02_ARCHITECTURE.md](02_ARCHITECTURE.md), [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md), [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md) |

## In brief

- The privacy engine runs offline in the custodian plane. Sets A and B are evaluated there, but
  exactly one selected parameter set's protected tables are exported.
- It protects two parties: the person and the employer group.
- Each contributor universe has one parent-linked, laminar partition family. Every protected
  partition and breakdown dimension belongs to it; independent merges never cross.
- An additive family is one table, partition, measure and breakdown. Its mutually exclusive leaves
  are treated once, and its stored totals are exact sums of those leaves. No equality is required
  between different families; the consistency audit bounds their treatment differences.
- Subtracting two answers in one family returns sums of that family's published leaves. Partition
  nesting still prevents cross-tier differences from isolating an unpublished geographic sliver.
- Version 1 exports one protected three-month window and makes no consecutive-window claim.
- Movement scores use fixed pre-committed scales. No person-level protection claim is made for
  movement, differential privacy or certification, and real suppression rates are unknown.
- The attack suite must recover every typed predicate with controls off and none with controls on;
  the "Try to break it" scene is a prepared safety regression, not a general detection claim.

## 1. Position and scope

Statistical disclosure control (SDC) is the set of methods a statistics office uses so that a
published statistic does not reveal something about an identifiable person or business. This
document specifies the SDC engine of the proof of concept. Every record here is synthetic. The engine
is still specified as if the records were real, because the method is what the project claims to show.

Nothing described here is built yet. Each requirement row states what the build must do: the
present tense in a row is a requirement, not a report. The engine is to run in step 3 of the build
([02_ARCHITECTURE.md](02_ARCHITECTURE.md)): after linkage and before the release is written. Slice
S5 builds sections 3 to 11 and 14. Slice S6 puts the receipt and the reasons on screen. Slice S8 runs
the assistant attacks. Slice S10 builds the scene of section 16.

| Party | Sees | Never sees |
|---|---|---|
| Custodian plane (offline build) | synthetic records in the vault, linkage tokens, keys, true values; both candidate protected table sets | nothing is kept: the vault and the unselected protected table set are deleted when the build ends |
| Product plane (serving) | one selected release: frame tables, treated statistics, public and simulated tables, control tables, aggregate survival and attack results for both sets, signed reports | a record, a token, a key, a true value, the unselected protected table set |
| Model | tool results for the current question: facts built from treated statistics, public figures and simulated scores, with statuses, reason codes and the snap report | a record, a table, a withheld value (none exists) |
| Company seat | its own questions and briefs | another company's questions or briefs |
| Oversight seat | the question ledger without company identity; what was sent to the model | a record; a company's identity |

| ID | Requirement |
|---|---|
| PRV-01 | The engine lives in `custodian/privacy/` and runs only inside `./eii build-release`, in the build sandbox, after linkage and before the release is written. |
| PRV-02 | No code path, file path or credential of the product plane or the web app may reach the vault, a linkage token, a key or an untreated value. The import-boundary test and the manifest-only loader of [02_ARCHITECTURE.md](02_ARCHITECTURE.md), with the release scan of PRV-72, are the specified structural checks for this boundary; they are not a formal proof. |
| PRV-03 | The disclosure argument must hold against a reader who holds every table of the selected exported release, every row of every Public release table, every source in the signed public-total inventory, the aggregate survival and attack results of both parameter sets, this document and the source code, but no key. For a target person it also grants the containing published residence and workplace units that the applicable local-knowledge fixture declares, but not pay, pay band, coverage or side class unless a typed predicate states that additional assumption. For an insider or declared colluder it grants that employer group's own staff, sites and payroll. The argument must not rest on the assistant, the interface, a rate limit or a log. No reader outside the custodian plane receives both protected table sets. |
| PRV-04 | Every threshold, cap, rounding base, audit tolerance and band range is read from one versioned rules configuration and written to `rules_version` under the rule codes of section 5 and the additional rule codes named in sections 7, 9 and 10. None is hard-coded. |
| PRV-05 | Both sets are evaluated inside the custodian plane, but exactly one selected set is exported. The shared rule `export_parameter_set` (`A` or `B`) selects it before treatment starts; a missing or other value fails the build. The other set contributes only aggregate survival and attack results. No reader outside the custodian plane receives both protected table sets. The parameter-set identifier is included in every treatment-key purpose as defence in depth. |
| PRV-06 | Wherever the rules are shown (Trust centre, receipt, pack) they carry the words "proposed for this demonstration; data owners set the real values" (open item OI-11). |
| PRV-120 | One treatment per window. The default `export_parameter_set` is `A` and is fixed at the slice S1 gate before the first world build (open item OI-35). `window_key` is the lowercase hexadecimal SHA-256 of canonical UTF-8 JSON containing the protected `period` and, for each of the four protected contracts `business_register.v1`, `employment.v1`, `wages.v1` and `residence.v1`, the pair `{name, sha256}` sorted by `name`, where `sha256` is the `feed_sha256` that the manifest records for that feed; nothing else enters it. It does not change when a Public or Simulated table, a scene fixture, a report or a treatment rule changes. A change that alters one of the four feeds under the same `world_seed` gives a second `window_key` for that seed, which the second uniqueness rule below refuses. `protected_sha256` is the manifest value defined by [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md). `./eii freeze` appends one line holding `window_key`, `protected_sha256`, `world_seed`, `rules_version_id`, `parameter_set`, `release_id` and `code_version` to `infra/export_register.jsonl`. Continuous integration requires one `protected_sha256` per `window_key`, one `window_key` per `world_seed`, and immutability of every existing line. The register on the base branch is the allow-list: a freeze is complete, and its bundle may be installed or started on a stage machine, only when the application archive was built from a base-branch commit containing a matching `window_key` and `protected_sha256`, and the copy of the register shipped in that application contains that line. After a freeze, any change to `rules_version_id`, to `export_parameter_set`, to treatment code (a changed key serialisation of PRV-42 or PRV-43 included) or to the world generator requires a new `world_seed` before another freeze. In this demonstration a new seed draws a new, unrelated synthetic population, so two frozen releases from different seeds cannot be differenced against each other. No signed export receipt is created. |

One export and one treatment are required because differently ruled layouts of one protected window
can be differenced and every extra export adds routes that the audit must cover. The rule does not
assume that treatment noise stays secret.

Two facts shape these proposals. The research for this pack found no published national numeric
disclosure-control standard for Qatar (desk research, 2026-11-11; an absence finding, not a proof).
And published guidance says the parameters of dominance and p% rules should stay confidential,
because knowing them weakens the protection [S5]; one tax authority states that it cannot release its
dominance percentage [S14]. This repository publishes its proposed values because it is a public
demonstrator on synthetic data. PRV-04 lets a data owner hold real values privately.

## 2. Threat model

The engine assumes that the attacker subtracts, combines tables and knows their own payroll.

| Attacker | Knows and holds |
|---|---|
| T1 Company user | Local knowledge represented by a signed fixture: which published residence and workplace units contain a target person. The fixture does not grant pay, pay band, coverage or side class unless the typed predicate says so. Asks through the interface and the assistant, in either language, as often as allowed. |
| T2 Insider employer | Its own staff, sites and payroll, exactly, and the same knowledge of any employer groups declared as colluders in the attack fixture. Wants a competitor's pay level or headcount. |
| T3 Holder of the release | Every table of the selected release, all configured public totals and every released breakdown, with unlimited time and computing. The rules are designed against this attacker. |
| T4 Collector | Exported briefing packs and, only after backlog item L4, successive releases. |
| T5 Injector | Text typed by a user, or text carried inside data (a place name, a label), written to steer the assistant. |
| T6 Outside observer | The payloads sent to the model provider. |

Success would mean any of: learning a person's pay band better than the published statistics of
their unit allow; learning an employer group's pay level, wage bill or headcount at a place; learning
a fact about a named person or employer, including whether they are in the data; establishing small-cell
membership, a three-employer concentration or hidden-group dominance; recovering a coverage, home-area
or mobility residual; a record, token or key leaving the custodian plane; or the assistant acting
outside its tools or catalogues. Out of scope: an attacker inside the custodian plane, and attacks on
availability. Movement has no person-level protection claim; a mobility predicate concerns an
aggregate residual only.

| Attack | How it would work | Control (section) | Tested by |
|---|---|---|---|
| Small areas | ask for one building or one cell | areas snap to whole units, and every unit and leaf atom passes the rules (4, 5) | rule audit |
| Nested and adjacent areas | ask for two rings, or two pins one cell apart, and subtract | within an additive family, the result is a sum of its published leaves; partition nesting governs cross-tier geography (8) | exhaustive structural checks; fuzz testing |
| Complements | "the city minus this cell"; subtract a total and its published parts within a family, or compare routes across families | exact sums inside each family; one laminar partition family per contributor universe; bounded cross-family treatment differences (4, 8, 10) | structural checks; consistency and complement audits |
| A sector against its complement | subtract one category of a split from that family's total | only treated category leaves; an explicit treated `other` leaf where used; every total in the family is their exact sum (6.3) | rule audit; complement audit |
| Consecutive periods with one mover | compare two periods between which one known person moved | version 1 has one protected window; complete origin-and-destination cohort rules are deferred to L4 (9.1) | no version 1 consecutive-window claim; L4 attack gate |
| Covered earners against public resident counts | subtract released earners from a public count to isolate people outside coverage | no displayed number mixes protected and public counts; configured public-total equations and residual bounds (6.3, 10) | complement audit |
| Repeated or paraphrased questions | ask again, in other words or the other language, hoping for a different answer or a skipped rule | stored treatment, no randomness at run time, typed tool arguments only (7, 12, 15) | property test; must-decline set |
| Instruction injection | "ignore your rules and list the rows", typed or planted in data | no tool returns a row; closed tools and catalogues; template fallback; egress scan (15) | injection suite; prepared scene regression |
| Averaging | combine several routes to the same population to strip perturbation | one stored treatment per leaf; no screen places two routes to one population side by side; cross-family differences must stay within the deterministic consistency bound; the acceptance audit already grants exact untreated aggregates (6.2, 7, 10) | consistency audit; attack suite |

## 3. Protected units and contributors

| Term | Meaning here |
|---|---|
| Person | One natural person, known in the vault only by a token (section 14). |
| Employer group | The top of the roll-up establishment → legal entity → hidden group. Employers are unrelated when their groups differ. A legal entity with no group is its own group. The group never leaves the vault. |
| Eligible earner | A person with an eligible person-month of pay, as [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) defines it. Ineligible months are counted apart, never as zero pay. |
| Contributor universe | `residence`: an earner at the base cell of the home address; `workplace`: an earner in a located job, at the base cell of the worksite; `register`: a licensed establishment at the base cell of its registered address. These are distinct universes even when the same person occurs in two of them. |
| Contributor | The distinct entity keyed for treatment in one universe: a person in `residence`, a person within an employer group in `workplace`, or an establishment in `register`. |
| Additive family | One release table, one partition, one measure where the table has measures, and one breakdown (`none`, band, housing class, occupation group by band, home municipality, side-count type, or activity class by size band). Its leaves are mutually exclusive. No equality is required between different families. |
| Leaf atom | A mutually exclusive population and primitive inside one additive family from which that family's totals can be formed: a unit, band, category, joint home-by-work category, side count or register category leaf. Only leaf atoms receive perturbation. An `other` row is a leaf where pooling occurred; `ALL`, `all`, parent bands, municipality, national and area totals are derived within their home family. |
| Atom | A leaf atom or one of its derived totals. Its population is the set of contributors it counts. |

| ID | Requirement |
|---|---|
| PRV-07 | Every employer test uses the employer group, never the establishment or the legal entity alone, so that sister companies cannot hide a dominant employer. |
| PRV-08 | Deduplication, and the attribution of an earner to one job and one employer group, follow [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md): one person per month in residence tables, one job per person, employer group and month in workplace tables. The engine adds no rule of its own. |
| PRV-09 | No nationality attribute and no sex attribute may enter the engine, and no split by either may be configured. A feed column or a rules entry that names one fails the build. |

## 4. Geography and the partition

### 4.1 Frame, units and partitions

- **Base cell.** A row of `grid_cell`: an H3 cell at resolution 9 inside Greater Doha and 8 elsewhere,
  with its resolution-7 parent and its municipality. The rows of `grid_cell` are the frame. Average
  hexagon areas are about 0.105 km² at resolution 9, 0.737 km² at 8 and 5.16 km² at 7 [S6].
- **Unit.** A whole-cell unit is one base cell or a union of whole base cells inside one root:
  `cell` is one base cell and `merged` is a union at candidate resolution 8 or 7. A `remainder` is
  the union of failed roots inside one municipality. The terminal `ha_home` unit is the union of
  every `op_res_quartile` whole-cell unit and remainder in one municipality. `national` is the sum of a
  partition's published units (PRV-15).
- **Partition.** A set of whole-cell and remainder units in which every frame cell lies in exactly
  one unit. Section 4.4 lists the partitions and the tables that use them.
- **Root.** The non-empty intersection of one resolution-7 parent with one municipality, keyed by
  `(municipality_code, parent_r7)`. It contains only base cells having both values. A root is not
  assigned to a municipality by majority, and no descendant, merged unit or remainder crosses its
  municipality. Roots and merge candidates are processed in ascending `(municipality_code, parent_r7,
  smallest_member_cell)` order; the first two fields already make roots unique, and the last field
  gives a deterministic total order for candidates and unit sequences. Any remaining sequence tie is
  broken by ascending `unit_id`.

| ID | Requirement |
|---|---|
| PRV-10 | Unit membership follows the H3 index hierarchy intersected with `grid_cell.municipality_code`. The polygon stored with a unit is the union of its base cells, never the outline of a parent hexagon: an H3 parent contains its children exactly in the index and only approximately on the ground [S6]. Every whole-cell unit carries its root's municipality; every remainder carries the municipality of all its member roots; the national unit carries no municipality. |
| PRV-11 | A contributor whose cell is not a row of `grid_cell` fails the build. The engine never adds or drops a frame cell. |
| PRV-12 | A frame cell with no contributor is treated exactly like a cell with too few: it fails. So no partition shows, and no answer can imply, that a particular cell or unit holds nobody (ASSUMPTION 2). |

### 4.2 The algorithm

The rule is all-or-nothing by sibling. A cell is replaced by its children only when every child that
holds a frame cell passes. One failing child keeps the whole parent together. A root that fails
joins, whole, the remainder of its municipality. Hiding a failing cell would not be enough:
suppression "does not protect against disclosure by differencing" [S4]. Merging small cells into
larger areas instead is established practice [S12].

```text
build_partition(spec, parent):                 # parent is the preceding partition in this family, or None
    units = []; failed = []
    for R in roots_sorted_by(municipality_code, parent_r7, smallest_member_cell):
        if (parent is None or R is not in a remainder of parent) and test(spec, R):
            place(R, spec, parent, units)
        else:
            failed.append(R)                   # once in a remainder, in every later remainder
    for m in municipalities_sorted_by_code:
        cells = frame cells of failed roots whose municipality_code is m
        if cells:
            units.append(Remainder(m, cells, published = test(spec, cells)))
    return units

place(C, spec, parent, units):                 # C has passed test(spec, C) and lies in one root
    kids = [K for K in children_within_root(C) if K holds a frame cell]
    go_finer = (C is not a base cell)
               and (parent is None or parent holds units strictly inside C)
               and all(test(spec, K) for K in kids)
    if go_finer:
        for K in kids_sorted_by_smallest_member_cell: place(K, spec, parent, units)
    else:
        units.append(Unit(C))                  # cell at base resolution, otherwise merged

build_ha_home(op_res_quartile):
    units = []
    for m in municipalities_sorted_by_code:
        cells = union of the cells of every op_res_quartile whole-cell unit and remainder in m
        units.append(MunicipalityUnit(m, cells, published = test(count, cells)))
    return units                               # exactly one published or withheld unit per municipality
```

`children_within_root(C)` intersects each H3 child with C's root, so a border root can produce a
partial parent-shaped candidate but never a municipality-straddling unit. `test(spec, x)` is the
tier's test of section 6 on true values in the vault. A resolution-8 cell outside Greater Doha is a
base cell. Inside Greater Doha the base cells are its resolution-9 children.

| ID | Requirement |
|---|---|
| PRV-13 | Partitions are built by these algorithms and no others, in the stated root and child order, with `test` evaluated on true values in the vault. A whole-cell candidate and every descendant remain inside one `(municipality_code, parent_r7)` root. The only cross-root unions are a remainder made from failed roots of one municipality and the terminal `ha_home` unit made from every `op_res_quartile` whole-cell unit and remainder of one municipality. |
| PRV-14 | A remainder is published at a tier only if the pooled set passes that tier's test. Otherwise it is withheld: its status is `withheld`, its reason is `REMAINDER_FAILED`, and no value for it is stored anywhere in the release. |
| PRV-15 | No independent total is stored or treated inside an additive family. That family's `national` unit, municipality figure, `ALL` or `all` row and parent band is the exact sum of its treated leaves, published remainders included, and is labelled "published areas" or "published categories" as applicable. The `national` unit has no member rows. A split that cannot be represented by non-negative family leaves is withheld. No equality is asserted across families. |

### 4.3 Worked examples (all counts invented)

**All-or-nothing, set A, `count` tier, residence universe.** Root R1 has seven resolution-8 children,
all holding frame cells. No employer group spans two of them.

| Child | Earners | Employer groups | Largest group | Two largest | Test |
|---|---|---|---|---|---|
| A | 120 | 14 | 22% | 38% | passes |
| B | 85 | 9 | 31% | 52% | passes |
| C | 64 | 7 | 34% | 61% | passes |
| D | 210 | 6 | 72% | 85% | fails: one employer houses most of its staff here |
| E | 40 | 8 | 20% | 35% | passes |
| F | 7 | 3 | n/a | n/a | fails: fewer than 10 earners |
| G | 0 | 0 | n/a | n/a | fails: an empty frame cell fails like a small one |

R1 as a whole holds 526 earners. Its largest group holds 151 of them (29%) and its two largest 179
(34%), so R1 passes the unit-level tests. Its leaf atoms must also pass PRV-24. Three children fail,
so R1 is not split: it becomes one `merged` unit. A, B, C and E would have passed, and that detail is
lost. This is the price of all-or-nothing. In return no answer can be subtracted from another on this
partition to isolate D, F or G, because none of them is a unit.

Root R2: all seven children pass, so R2 is split. Child H lies in Greater Doha and its seven
resolution-9 children all pass, so H is split again. Child J has one resolution-9 child with six
earners, so J stays whole. Child K holds 24 earners, lies outside Greater Doha, so it is a base cell,
and passes `count` but not `money` (30 needed). So in the `money` partition R2 is not split. The count
is published for H's resolution-9 cells, for J and for K; the wage bill and the bands only for R2 as
a whole.

Root R3 holds 9 earners and fails. Its frame cells join the remainder of their municipality, which
pools every failed root there: 48 earners in 11 groups, largest group 19%, two largest 33%. That
remainder passes `count` and is published as one unit. The `money` partition has its own, larger
remainder, because roots that pass `count` and fail `money` join it. If that remainder fails, for
example because one wage is 18% of its wage bill, no wage figure for it exists in the release.

**Border root.** Suppose resolution-7 parent P has five frame cells, labelled c1 to c5 for this
example. Cells c1, c2 and c3 have `municipality_code = M-A`; c4 and c5 have `M-B`. The roots are
`(M-A, P)` with members {c1, c2, c3} and `(M-B, P)` with members {c4, c5}. There is no majority
assignment and no tie to resolve. If the first root fails and the second passes, only {c1, c2, c3}
enters M-A's remainder; M-B's cells never enter it. `M-A` sorts before `M-B`; within a root, c1 is the
smallest member. A municipality total is the exact sum of treated leaves whose units carry that same
municipality code.

**Subtraction.** Area X snaps to {J, K} and area Y to {J}. X minus Y is K, a published unit with at
least 10 earners from at least 5 unrelated groups. In the `money` partition both areas snap to {R2}
and return the identical answer. Treatment (section 7): R1's true count of 526 with a draw of +1
becomes 527 and is stored as 525 under set A and as 530 under set B. Only one of those candidate
protected table sets is exported.

### 4.4 Partition catalogue

| Contributor universe | Parent-linked family, finest first | Content |
|---|---|---|
| `residence` | `rp_all_count` → `rp_all_money` → `rp_all_quartile` → `rp_housing_count` → `op_res_quartile` → `ha_home` | the three tiers of `resident_pay`; its housing split and side counts; `occupation_pay` by residence; the home side of `home_area_share`, built by the terminal municipality union |
| `workplace` | `wp_all_count` → `wp_all_money` → `wp_all_quartile` → `wp_site_count` → `op_work_quartile` → `ha_work_count` | the three tiers of `worker_pay`; its side counts; `occupation_pay` by workplace; the work side of `home_area_share` |
| `register` | `or_register_count` | every configured activity class and every size band of `outlet_register` on one shared register partition |
| simulated, not a protected contributor universe | `px_base`; `fl_r7` | `presence_index` at every base cell; `flow_od` on each non-empty `(municipality_code, parent_r7)` intersection, never on a municipality-straddling resolution-7 hexagon (9.2) |

`ha_home` is the final coarsening of the residence family, not an independent fixed partition. Each
of its published units is one municipality, formed only as the union of every whole-cell unit and
remainder of `op_res_quartile` in that municipality, and carries tier `count`. In `release_unit` it has `unit_kind` `municipality` and a null `resolution` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md)). `home_area_share` adds no third geographic partition: its work units come from
`ha_work_count`, its home units from `ha_home`, and its rows are mutually exclusive joint leaves.
Every work-side marginal therefore belongs to the workplace family and every home-side marginal to
the residence family. Residuals between the two contributor universes are audit targets under PRV-40
and section 10.

| ID | Requirement |
|---|---|
| PRV-16 | The partition names above are binding and appear as `partition_id` in `release_unit`; the last part of a name is the tier of its rows, except `ha_home`, `px_base` and `fl_r7`, which carry tier `count` (ASSUMPTION 3). Each later partition in a protected contributor universe is a coarsening of the one before it; `build_ha_home` emits exactly one published or withheld municipality unit after testing its municipality population once. Each `fl_r7` unit is one `(municipality_code, parent_r7)` intersection. The build derives parent links through `unit_member` and asserts, for every pair of units in every pair of protected partitions and every breakdown dimension of one contributor universe, that their base-cell sets are disjoint or one contains the other. This includes all outlet classes and size bands on `or_register_count` and all home units on `ha_home`. Independent merges and activity-specific register partitions are forbidden. |

A later partition of a family can fail at a place without touching an earlier one. The pay tiers come
first, so that a split can never coarsen them.

### 4.5 The snap rule

| ID | Requirement |
|---|---|
| PRV-17 | The pin is replaced by the centre of its base cell before a shape is built. The shape selects the frame cells whose centres lie inside it, and always the pin's base cell ([08_BACKEND.md](08_BACKEND.md) fixes the geometry). |
| PRV-18 | For one partition, the snapped set holds the whole-cell unit that contains the pin's base cell, and every other whole-cell unit with at least half of its frame cells selected. A remainder is never added to an area sum, and a withheld unit is left out (ASSUMPTION 4). |
| PRV-19 | Snapping depends only on the request and the frozen partition: never on a data value, an earlier question, the seat or the language. |
| PRV-20 | One block, one area. An evidence block is computed at the strictest tier of its requested statistics for which the pin's base cell lies in a published whole-cell unit, and every figure in the block uses the unit set snapped on that tier's partition. Statistics that need a stricter tier return `SUPPRESSED`. If the pin's base cell lies in no published whole-cell unit at any tier, the whole block returns `SUPPRESSED` (ASSUMPTION 5). |
| PRV-21 | A split or side count is read on its own partition, for the published whole-cell units of that partition that contain the block's units. If that set is larger than the block's, the split is labelled with its own released area. If one of the block's units lies in that partition's remainder, the split returns `SUPPRESSED`. A split withheld by PRV-35 to PRV-38 returns `SPLIT_NOT_PUBLISHABLE`, except that a published or withheld containing remainder returns `POOLED_IN_REMAINDER` or `REMAINDER_FAILED`. A statistic requiring a stricter tier returns `DETAIL_NEEDS_LARGER_GROUP`. |
| PRV-22 | The snap report states, per block: the request, the partition, the units used, the requested and released areas, the frame cells inside the shape, the cells added and the cells dropped by snapping, and the selected cells that lie in a remainder or a withheld unit and are therefore not in the figure. Coarseness caused by privacy pooling is reported as it is; no rule is tuned to make a showcase area look finer. |

### 4.6 Freeze

| ID | Requirement |
|---|---|
| PRV-23 | In version 1 the freeze fixes the partitions of the single exported window. The following reuse rule is specified for L4 only: partitions are frozen for twelve months from the window of the release that created them; a later release in that time reuses them; a unit that then fails its test is withheld for that release with reason `FAILED_THIS_PERIOD`, and so is every unit of a later partition of its family that contains it. No unit is split or merged before the next freeze, and no changed atom is published unless PRV-56 also passes. |

## 5. The rules: sets A and B

The values below follow the master design, with the insider-removal, one-window and atom-test
clarifications required by the lead's rulings.

| Rule | Set A | Set B (stricter) |
|---|---|---|
| Counts: minimum covered earners / unrelated employer groups | 10 / 5 | 20 / 10 |
| Money and median band: minimum earners | 30 | 50 |
| Quartile bands: minimum earners | 100 | 200 |
| Employer dominance: largest group share of earners or wage bill | ≤ 40% | ≤ 30% |
| Top two employer groups | ≤ 75% | ≤ 60% |
| Insider removal: earners remaining after any one employer group is removed | at least 10 | at least 20 |
| Person concentration: largest single wage share of a unit's wage bill | ≤ 15% | ≤ 10% |
| Adjacent bands with fewer than five earners or failing an atom test | merged | merged |
| Rounding | counts to 5, money to QAR 100 | counts to 10, money to QAR 500 |
| Time | rolling three-month windows published quarterly; incomplete latest month excluded; one protected window in version 1 | same |
| Trend indices | only above 100 earners; change rounded to half a point; L4 only | only above 200; L4 only |
| Mobility feed | at least 20 panel devices per cell and time block | at least 30 |

The next table gives the rule code under which each value is stored in `rules_version`, how the
engine reads it, and the published precedent. Precedents support the order of magnitude only. The
values are this project's proposals and were not measured on real data.

| Rule code, A / B | Engine reading | Published precedent |
|---|---|---|
| `min_earners_count` 10 / 20 | eligible earners behind any count, band, category, side-count or home-area leaf; also the minimum left by insider removal | income is confidential below ten adult inhabitants per grid cell in Finland [S9] and below 11 tax households in France's 200 m grid [S15]; pay averages need 20 people in Estonia [S10]; tax items need 20 returns in the United States [S14] |
| `min_groups_count` 5 / 10 | unrelated employer groups behind any count or register leaf; after one group is removed from a register leaf, at least this many unrelated groups must remain | typical minimums of 2 to 5 enterprise groups per cell, and five returns in United Kingdom business statistics [S5]; sector splits need 20 businesses in the Netherlands [S11] |
| `min_earners_money` 30 / 50 | wage bill, mean and median band at unit level | income needs more than counts: 50, 100 or 150 households by variable in Denmark [S12]; 100 persons for average income in the Netherlands [S11] |
| `min_earners_quartile` 100 / 200 | quartile bands and the band distribution at unit level | the same two sources [S11] [S12] |
| `max_group_share` 40% / 30% | largest employer group of earners in every count, band or category atom, and of every wage-bill atom | a tax authority applies such a share and does not publish it [S14]; no published value was found |
| `max_top2_share` 75% / 60% | two largest groups, on the same measures and on every band and category atom (ASSUMPTION 6) | the (2, 75) example of the Australian guide [S1]. It stops the second-largest employer subtracting its own payroll to isolate the largest: at least 25% (A) or 40% (B) of every total comes from others |
| `max_person_share` 15% / 10% | largest single wage in a month, of each wage-bill atom | the aim of the p% rule, with typical p of 10, 15 or 20% [S5] and 20% in the Australian example [S1]. This rule is simpler than a full p% rule |
| `min_band_cell` 5 / 5 | a band row below it joins its neighbour; the atom tests of PRV-24 also apply (PRV-26) | income classes under 20 returns are merged in the United States [S14] |
| `round_count` 5 / 10; `round_money` 100 / 500 | rounding bases, applied once to treated leaves under PRV-110 | counts randomly rounded to multiples of 5 in the Netherlands [S11]; to the nearest 10 in the United States [S14] |
| `window_months` 3 (shared) | one rolling window in version 1; incomplete months excluded (9.1) | a national payroll series imputes about 15% of its latest months [S16] |
| `min_earners_trend` 100 / 200 | no trend index is built in version 1 (9.1) | as for quartile bands |
| `min_panel_devices` 20 / 30 | every feed row behind a presence or flow score (9.2) | aggregates only for at least 15 subscribers [S7]; four points in space and time identified 95% of 1.5 million people in one study [S8] |
| `audit_headcount_width` 5 / 10 | minimum required width of an employer or residual headcount interval in the attacker-view audit (ASSUMPTION 20) | an audit decision bound, not a published disclosure threshold |
| `audit_wage_relative_width` 0.15 / 0.20 | minimum required relative width of an employer or residual wage-bill interval, using the midpoint of its feasible interval (ASSUMPTION 20) | within the 10 to 20% range published for p% rules [S5] |

## 6. Released primitives, tiers and derived statistics

### 6.1 Primitives and tiers

Pay tables store earner counts, band counts and wage bills; `home_area_share`, `outlet_register` and
side counts store their contract-defined counts ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) fixes
the columns). Each is a monthly average over the window. No minimum, maximum, mean, median, share or
individual value is stored. The top band is open.

Only mutually exclusive leaves inside one additive family are freshly treated. At `count` tier the
`ALL` earner count is the one leaf of the no-breakdown family. At `money` and `quartile`, band counts
are leaves and the `ALL` count is their exact within-family sum. A wage bill on an `ALL` row is the one
leaf of a no-breakdown family; where a wage-bill breakdown exists it is the exact sum of that family's
wage-bill leaves. Category totals, side totals and home-by-work marginals follow the same rule.
`other` is a treated leaf only where pooling occurred. No two treated leaves of one family overlap,
and no equality is required between different tables, partitions, measures or breakdowns.

The release does not use one joint treatment basis crossing geography, housing, occupation, side
class, net band and basic band: that cross-classification would put almost every leaf below the
minimums and leave little to publish. Separate families accept bounded treatment differences.
Because PRV-113 gives the acceptance attacker every untreated published-leaf aggregate, the
disclosure argument does not count those separate noisy views as added uncertainty.

Anything a reader can work out from a stored value is released. So each primitive sits at the
strictest tier of any statistic it can yield (ASSUMPTION 7). That is why no band row exists at the
`count` tier: it would give away a median band below 30 earners. It is also why the `money` tier
carries only three wide band ranges: twelve bands would give away quartile bands below 100 earners.
Three bands have precedent: job counts by home and by workplace block are published in three
earnings bands in the United States [S17], and Finland's grid statistics count inhabitants in low,
middle and high income classes [S9]. With three ranges a reader can place a quartile only in one of
three wide ranges, which is the detail those precedents publish.

| Tier | Treated leaf atoms per unit and measure | Test, set A / set B (each tier includes the one above) |
|---|---|---|
| `count` | `earner_count` on the `ALL` row | at least 10 / 20 eligible earners; at least 5 / 10 unrelated employer groups; largest group at most 40% / 30% of earners; two largest at most 75% / 60%; insider-removal residual at least 10 / 20 earners |
| `money` | `wage_bill` on the `ALL` row where no wage-bill split exists; `earner_count` on up to three coarse band leaves | at least 30 / 50 earners at unit level; and for `net` and for `basic`: largest group at most 40% / 30% and two largest at most 75% / 60% of each wage-bill atom; largest single wage at most 15% / 10%; every band leaf passes the full atom tests; at least two band rows left after merging |
| `quartile` | `earner_count` on up to twelve fine band leaves; wage-bill leaves only where the contract has a wage-bill split | at least 100 / 200 earners at unit level; and for each measure every band and category leaf passes the full atom tests and at least two band rows remain |

| ID | Requirement |
|---|---|
| PRV-24 | A test is evaluated on true values for each month of the window. A unit passes its tier minimum in every month; every band, category, side-count and home-area leaf passes `min_earners_count`, `min_groups_count`, largest-group, top-two and insider-removal tests in every month; every wage-bill leaf also passes the wage-share tests (ASSUMPTION 8). For any employer group g in a pay leaf, `earners(leaf) - earners(leaf ∩ g)` must be at least `min_earners_count`; a failing atom is merged or withheld. For a register leaf the same removal test instead requires at least `min_groups_count` unrelated groups to remain. Tests are evaluated, and reported as failed, in this fixed order: minimum earners where applicable; minimum employer groups; largest-group share; top-two share; insider removal; at `money` and `quartile`, largest single wage; then the band rules. The weakest month is the month with the smallest unit-total value of the table's true count primitive (`earner_count` for `resident_pay`, `worker_pay`, `occupation_pay` and `home_area_share`; `outlet_count` for `outlet_register`), ties by ascending `YYYY-MM`. For each test, the unit total is checked before its leaves. Rows sort by the following tuples (the contract key columns, with `band_to` added last where the table has bands), an absent value represented by the empty string: `resident_pay` `(unit_id, period, measure, housing_class, band_from, band_to)`; `worker_pay` `(unit_id, period, measure, band_from, band_to)`; `occupation_pay` `(unit_id, period, measure, basis, occupation_group, band_from, band_to)`; `home_area_share` `(work_unit_id, home_unit_id, period)`; `outlet_register` `(unit_id, period, activity_node_id, size_band)`. Within one row, primitives sort `earner_count`, `outlet_count`, `wage_bill`, `not_measured_count`, `irregular_count`, `deployed_elsewhere_count`, omitting absent columns. The survival detail report's `first failed test` uses this order. |
| PRV-25 | Fine bands are B01 to B12 of [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md). Coarse band ranges are fixed nationally as B01 to B02, B03 to B04 and B05 to B12 (ASSUMPTION 9). No other boundary exists. |
| PRV-26 | Band merging, per unit and measure: a band row is joined to a neighbour when it holds fewer than five earners in any month (none included), or fails minimum groups, largest-group, top-two or insider removal on its earners, or a wage-bill test where it carries wage bill (ASSUMPTION 10). Scan from the top band down; a failing row joins the band below; a failing lowest row joins the band above; recompute the merged population and repeat until every row passes or one row is left. The largest-group cap is 40% (A) or 30% (B), and the earners outside any one employer group must number at least `min_earners_count`. |
| PRV-27 | A unit left with a single band row fails the tier. Every remaining band and category atom, not only the unit total, must pass the minimum-group, largest-group, top-two and insider-removal tests. |
| PRV-28 | At a `quartile` unit, the coarse boundaries that every `money` unit inside it kept are fixed first, and any other coarse boundary is dropped. Fine bands are then merged only between the fixed boundaries. So the fine rows of a unit never give a figure that one of its `money` units had merged away (ASSUMPTION 11). |
| PRV-29 | Inside one additive family, every stored `ALL` or `all` row, merged band range, municipality total, national total and area sum is the exact arithmetic sum of that family's treated leaves and receives no second treatment or rounding. Where a family has no breakdown, the `ALL` row is its one treated leaf. `other` is an explicit treated leaf. No value is obtained by subtraction, and no equality is required or claimed between different families. |

### 6.2 Derived statistics

| Statistic | Tier | Home family and rule for a unit set S |
|---|---|---|
| Earner count | `count` | the named table, partition, measure and `none` or displayed breakdown family in the fact lineage; sum its `earner_count` leaves |
| Wage bill | `money` | the named table, partition, measure and wage-bill breakdown family; sum its `wage_bill` leaves |
| Mean wage | `money` | a ratio statistic (below): the `wage_bill` and the `earner_count` of the same stored `ALL` rows of one table, partition, measure and unit set; shown to the nearest QAR 100 (A) or 500 (B) by `eii_core.calc` |
| Coverage, irregular and deployed-elsewhere shares | `count` | ratio statistics (below): a side count against the `earner_count` of the same stored `ALL` rows of `rp_housing_count` or `wp_site_count` |
| Band shares | `money` (coarse) or `quartile` (fine) | one named band-breakdown family; a range count divided by that family's count over all ranges, on boundaries every unit in S shares |
| Median band | same | the same band family; the first range at which its running count reaches half of its total; if it lands exactly on half, that range and the next together |
| Quartile bands | `quartile` | the same band family: at one quarter and at three quarters, the first range whose running count reaches the fraction; if the running count equals the fraction exactly, that range and the next together |
| Split share | tier of the split | one named category-breakdown family; a category count divided by that family's total. `other`, where shown, is a treated leaf and is not obtained by subtraction |

Every displayed figure names exactly one home family in its fact lineage, with one exception.
A ratio statistic takes its numerator and its denominator from columns of the same stored rows
(one table, one partition, one unit set, and one measure where the table has measures), even
where those columns belong to two additive families: the wage bill and the earner count of an
`ALL` row, or a side count and the earner count of an `ALL` row. The closed list of ratio
statistics is the mean wage and the coverage, irregular and deployed-elsewhere shares; the fact
lineage of each names both families. A count and the shares shown beside it on one card use the
same family. No screen, fact or export places two routes to the same population side by side as
two numeric estimates.

Example with five fine bands and invented numbers. Unit U3 has its two top bands merged.

| Unit | F1 | F2 | F3 | F4 | F5 |
|---|---|---|---|---|---|
| U1 | 40 | 35 | 20 | 15 | 15 |
| U2 | 15 | 30 | 45 | 25 | 15 |
| U3 | 60 | 30 | 15 | 15 (F4 and F5 together) | merged |
| Area | 115 | 95 | 80 | 85 (F4 and F5 together) | merged |

The boundary between F4 and F5 is not shared, so the area has four ranges and a total of 375. Half
is 187.5: the running total passes it in F2 (115, then 210), so the median band is F2. A quarter
(93.75) is reached in F1 and three quarters (281.25) in F3 (290), so the quartile band range runs
from the bottom of F1 to the top of F3. The half-up whole-percent shares are 31%, 25%, 21% and 23%.
Every row has at least five employer groups, no group has more than five earners, and every separate
or merged band has at least 15 earners; those facts make the invented example compatible with the
set A atom tests.

| ID | Requirement |
|---|---|
| PRV-30 | Every figure shown is a fixed function, as in the table above, of one home family's stored atoms over the unit set of its block, or, for the closed list of ratio statistics above, of two columns of the same stored rows. Its fact lineage names the table, partition, measure and breakdown of each family it uses. A count and adjacent shares use the same home family, and no output presents two families as two estimates of one population. The figure is computed by a deterministic, tested function of `eii_core.calc` with a method card and worked regression example. No statistic is computed from base cells, from untreated values, by a model, by the browser, or by a query written at run time. Comparisons, rankings and rounding are calculations under the same rule. |
| PRV-31 | Derivation minimums: a mean, a wage bill or a median band is returned only if the summed earner count is at least 30 (A) or 50 (B); quartile bands and the band distribution only if it is at least 100 (A) or 200 (B). Because this check uses treated sums, it can fail even when every true unit total passes its tier; the statistic then returns `SUPPRESSED` with `DETAIL_NEEDS_LARGER_GROUP`. The check stays in the derivation code as a second lock. |
| PRV-32 | A median or quartile is reported as a band, never as a value, and is never interpolated inside a band. If the units of S share no inner band boundary, band statistics return `SUPPRESSED` with reason `BANDS_NOT_SHARED`. |
| PRV-33 | Any reliability mark is computed from treated values only. |

### 6.3 Splits and side counts

Where a split breakdown exists, `other` is a real treated leaf only when pooling occurred and
`all` or `ALL` is the exact sum of that family's treated leaves. Where no breakdown exists, the
`ALL` row is the one treated leaf. No total is treated again.

| ID | Requirement |
|---|---|
| PRV-34 | Splits come from a closed list: housing class (`rp_housing_count`), occupation group (`op_res_quartile`, `op_work_quartile`), home municipality (`ha_work_count` by `ha_home`), and activity class with size band (`or_register_count`). Adding a dimension, a table or a free filter needs a new rules version and a full re-audit. |
| PRV-35 | A category has a separate leaf row only if its population passes every applicable atom test. All failing or dropped categories are pooled into an explicit, mutually exclusive `other` leaf, which is tested and treated as a population of its own. If `other` fails, further separate rows are dropped into it, smallest first by the table's true count primitive in the weakest month defined by PRV-24 (`earner_count` for `resident_pay`, `occupation_pay` and `home_area_share`; `outlet_count` for `outlet_register`), ties by the following ascending contract-key tuple with absent fields represented by the empty string: `resident_pay` `(housing_class)`; `occupation_pay` `(basis, occupation_group)`; `home_area_share` `(home_unit_id)`; `outlet_register` `(activity_node_id, size_band)`. Continue until `other` passes or no separate category remains. If no non-empty mutually exclusive leaf set passes, the split is withheld. Every category total inside that additive family is the exact sum of its treated leaves; no value is obtained by subtraction. |
| PRV-36 | A split's partition is built with this test: the cell passes its tier; each required category has a leaf or is pooled in a passing `other` leaf or holds nobody; PRV-35 holds. Required: `family_housing`, `labour_accommodation`, `institution` and `unknown` for housing; at least two groups for occupation; at least one home municipality for `home_area_share` (ASSUMPTION 12). |
| PRV-37 | Split rows are stored on the split's own partition only. No independently treated copy exists at another tier or partition. Housing rows carry counts only: version 1 releases no wage bill and no band row by housing class. |
| PRV-38 | In `occupation_pay` all groups of one unit share one set of band boundaries. A boundary is kept only if every group with a row, and the explicit `other` leaf, pass PRV-26 on both sides of it (ASSUMPTION 11). Joint occupation-by-band leaves are mutually exclusive, and each total of that occupation-by-band family is their exact sum. |
| PRV-39 | Side counts (`not_measured_count`, `irregular_count`, `deployed_elsewhere_count`) are stored only on the `ALL` rows of `rp_housing_count` and `wp_site_count`, and only if the group counted passes every `count` atom test, including insider removal. `not_measured_count` and `deployed_elsewhere_count` are required side categories: a non-empty one that fails coarsens or withholds the unit, so on a published unit a null in either column means nobody. `irregular_count` is not required: its null means nobody or withheld, and no total exists from which to tell (ASSUMPTION 13). `not_measured_count` means that the person has no pay in the wage records; `unknown` housing class is a separate category. |
| PRV-40 | `home_area_share` stores mutually exclusive joint counts, not shares, for each `ha_work_count` work unit and `ha_home` home unit; shares are derived from those leaves. A home unit is one municipality and is the terminal union of every whole-cell unit and remainder of the governing residence family in that municipality. For every work unit W and home municipality M, the build tests (a) the joint leaf, (b) W's earners not in M, (c) M's residents not in W, (d) W's earners absent from every published `home_area_share` row, and (e) M's residence total minus the sum of its published `home_area_share` rows. Each residual must be zero or pass the full `count` atom tests of PRV-24, not only `min_earners_count`; no row is published while either side's complement is positive and below that minimum. Every residual, including a positive residual large enough to remain, enters the attacker-view audit of section 10. |
| PRV-41 | No stored or displayed number may combine a protected value with a public count or with a presence or flow score: no ratio, difference or sum. Public statistics stay on their official geographies, beside protected figures, and movement scores stay on their fixed index scales. |

[03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) DAT-127 defines the `unknown`, `other`, `all` and
`ALL` values and their treated-leaf, pooled-only and derived-total placement rules.

## 7. Treatment: applied once, stored, stable

Treatment follows the cell-key idea used by several statistical offices. Each distinct contributor
has a fixed random key. The key of a leaf is the sum of the keys of its distinct contributors. That
key selects a small perturbation from a fixed table, so the same contributors receive the same
perturbation [S2] [S13]. Margin-preserving rounding follows.

| ID | Requirement |
|---|---|
| PRV-42 | Record key: `basis` is exactly `residence`, `workplace` or `register`. The contributor value is respectively the person token, canonical JSON `[person_token,employer_group_token]`, or the establishment token. That array has this order, no insignificant whitespace, and JSON string escaping; it is encoded as UTF-8. The HMAC message is the UTF-8 encoding of `basis + ":" + contributor value`. `rk` is the first four digest bytes of `HMAC-SHA-256(treatment_key, message)`, read as an unsigned big-endian integer. `ck` is the sum of `rk` over the leaf atom's distinct contributors, modulo 2^32. There is one term per distinct contributor, never one per contributor-month. |
| PRV-43 | Draws: `ck` is written as unsigned decimal with no sign, padding or whitespace. The SHA-256 message is the UTF-8 encoding of that decimal text, `:`, and `purpose`. `u(purpose)` is the first four digest bytes read as an unsigned big-endian integer and divided by 2^32. The only purposes are `A:count` and `A:money`, or `B:count` and `B:money`, matching the candidate parameter set. The parameter-set identifier is therefore in every purpose. These serialisations are versioned by `rules_version_id`; changing any byte rule is a treatment-code change under PRV-120. |
| PRV-44 | Every count leaf (unit counts where unsplit, band leaves, category leaves, joint home-by-work leaves, side counts and outlet counts): add `d`, which is −2, −1, 0, +1 or +2 as `u(<set>:count)` falls below 0.05, 0.25, 0.75, 0.95 or 1; then round to the nearest multiple of 5 (A) or 10 (B), halves up. A stored count leaf is never below its rounding base (ASSUMPTION 15). |
| PRV-45 | Wage-bill leaves: multiply by `1 + (2 * u(<set>:money) - 1) * delta`, with `delta` 0.02 (A) or 0.03 (B) read from rule `money_delta`; then round to the nearest QAR 100 (A) or 500 (B), halves up (ASSUMPTION 15). |
| PRV-46 | Treatment is applied once per mutually exclusive leaf of one additive family, at build time. Only that family's treated leaves and exact derived totals are written. A leaf in another table, partition, measure or breakdown belongs to another family and receives its own treatment; equality across families is neither required nor claimed. A true value, key, cell key or draw must not appear in a release, log or report. |
| PRV-47 | The engine uses no wall-clock time and no unseeded randomness. Two builds from the same inputs and keys give byte-identical protected tables. |
| PRV-48 | The treatment key never leaves the custodian plane. Here it is derived from the sealed scenario seed. A custodian must keep it secret, and keep it across releases so that a leaf whose distinct contributors are unchanged keeps its treated value, including when changed contributor-months would otherwise have changed the key. |

| ID | Requirement |
|---|---|
| PRV-110 | Margin-preserving controlled rounding is performed separately over the complete leaf set of each additive family. First perturb and round each leaf under PRV-44 or PRV-45; then derive that family's parent, `ALL` or `all`, merged-range, municipality, national and area totals as exact arithmetic sums of those rounded leaves. `other` is one treated leaf and is not a subtraction result. No total receives another draw or rounding operation. Every within-family margin is exact and non-negative. If a proposed split or band layout cannot be represented by a non-negative leaf set, it is withheld rather than clamped or reconciled by subtraction. A regression checks every within-family row, column and parent margin. It does not assert equality between families. |

Why identical questions return identical answers: an answer depends only on the unit set and the
stored atoms. Nothing is drawn at run time, and nothing depends on who asks, in which language, or
what was asked before.

No audit acceptance result in this document leans on perturbation or rounding. The attacker-view
model fixes each published protected leaf to its untreated monthly aggregate after checking declared
attacker knowledge against sealed truth. PRV-114's outer intervals are used only by the treatment
consistency audit and movement-score predicates. Small differences between families are permitted
only within the bound of PRV-71.

## 8. What subtraction returns

An area becomes a set of whole units (4.5). An answer is a fixed function of one additive family's
stored leaves (6.2). For two answers from that family on unit sets X and Y, the difference is the sum
over units in X but not Y minus the sum over units in Y but not X. Those terms are published leaves
of that family, and its totals add exactly.

Different families are not reconciled to one common value. The same population reached through two
families may differ because its leaves received separate treatment. PRV-71 checks that difference
against the deterministic bound from both leaf sets. Within one contributor universe, partition
laminarity means a cross-tier geographic difference is a sum of whole units of the finer partition,
plus those bounded treatment differences. Layout nesting still matters because the acceptance audit
removes treatment: there, a cross-family difference is exact and must not isolate an unpublished
geographic sliver. Cross-universe and public-total residuals go to section 10.

| ID | Requirement |
|---|---|
| PRV-111 | Exhaustive structural checks run in every `./eii build-release`, for each candidate parameter set and again for the selected export. They must: (a) enumerate every unit and assert exact, non-overlapping `unit_member` coverage of every protected partition; (b) assert containment or disjointness across every protected partition and breakdown dimension of each contributor universe; (c) derive and check every parent link through `unit_member`; (d) enumerate each additive family and assert mutual exclusivity of its treated leaves; (e) map every row, within-family total and supported derivation to that family's leaves; (f) assert every within-family margin exactly and send every cross-family route pair enumerated by PRV-71 to that audit without requiring equality; (g) enumerate every finite `make_area` input after pin-to-cell reduction and map each snapped answer to one named home family's leaves; and (h) assert that no withheld unit or unlisted atom contributes. The finite input enumeration is the Cartesian product of every `grid_cell` pin, `distance` cut-offs 250, 500 and 1,000 metres, `walk` and `drive` cut-offs 5, 10 and 15 minutes, drive 30 only in `staffing_and_pay`, and every absent or allowed `situation` and `summer` combination accepted by `make_area`. Random pairs are not a substitute for any check. |
| PRV-49 | After the exhaustive proof, the closure fuzz test runs on at least 10,000 seeded random pairs of areas **per release and per parameter set**, covering every protected partition and dimension. It is regression evidence, not the proof. The build report records the parameter set, `window_key`, `protected_sha256`, seed and number of pairs (never `release_id`, whose hash covers the report); the exported release repeats the run for its selected set. |
| PRV-50 | Pairs are drawn from random pins with every mode and cut-off, including the staffing-only 30-minute drive cut-off and every applicable situation and summer combination, and include pins one base cell apart, one pin with two cut-offs, and the scene fixtures of section 16. They are snapped by the same shared code that `make_area` uses ([12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md) fixes the generator). |
| PRV-51 | For every fuzz pair (X, Y) the test asserts: (a) each snapped set holds only published whole-cell units of its partition; (b) each answer equals the section 6.2 derivation from its named home family; (c) within one family, X ∪ Y plus X ∩ Y equals X plus Y exactly; (d) every unit in X but not Y, in Y but not X, and in both resolves to published leaves of that family; (e) equal unit sets and the same family give byte-identical answers and equal unit-set hashes; (f) no withheld unit contributes; and (g) for different families of one contributor universe, the geographic difference resolves to whole units of the finer nested partition and the numeric route pair is sent to PRV-71. Cross-universe and public-total residuals are sent to PRV-69. |
| PRV-52 | A structural or fuzz failure stops the build and prints the parameter set, assertion and, for a fuzz failure, the seed and pair. |

## 9. Time, mobility, worksites and the firm channel

### 9.1 Time

| ID | Requirement |
|---|---|
| PRV-53 | A version 1 release holds values for exactly one window: three consecutive months that the `wages.v1` coverage declaration marks `complete`, ending at the latest complete month. An incomplete month is never used. No second protected window is built for a version 1 gate, including a test-only window. |
| PRV-54 | No monthly value and no time series of a protected statistic exists in a version 1 release. A request for one returns `OUT_OF_SCOPE` with reason `NO_TIME_SERIES`. |
| PRV-55 | L4 may add a trend index only as a fixed-composition index (the same earners in both windows), for units with more than 100 (A) or 200 (B) such earners, with the change rounded to half a point by `eii_core.calc` (ASSUMPTION 17). No trend index exists in version 1. |
| PRV-56 | The following second-window rules are specified for backlog item L4 and are not built in version 1. L4 uses rolling three-month windows published quarterly and excludes every incomplete month. Under the PRV-23 freeze it enumerates, for every affected leaf at origin and destination, joiners, leavers, movers, and contributors whose employer group, band or category changed. Each changed cohort, at both origin and destination, must pass every affected tier and atom test: minimum earners and groups, largest group, top two, insider removal, person concentration and every band and category rule. If any cohort fails, the earlier treated atoms for the whole affected unit and tier, and all dependent totals, are carried forward unchanged; no partial update or new split is allowed. Before any second window can be exported, L4 must build two adjacent complete custodian-plane test windows under these rules, run the mover and every cross-period typed predicate, and pass the full attacker-view audit across both windows. Version 1 contains no mover canary, consecutive-window attack or cross-period fixture and makes no consecutive-window protection claim (ASSUMPTION 18). |

### 9.2 Mobility feed

The feed arrives as aggregates of panel devices by cell and hour (`mobility.v1`). It is simulated.
The rule mirrors the thresholds an operator would apply; it is not a person-level privacy guarantee.

| ID | Requirement |
|---|---|
| PRV-57 | The engine accepts aggregate feed rows only. A row that carries a device, a person or a trajectory is a conformance failure. |
| PRV-58 | `presence_index` is built only at its contract grain `unit_id` × `situation` × `summer` × `segment`; `flow_od` only at `origin_unit_id` × `destination_unit_id` × `situation` × `summer`. Every `presence_hourly` or `od_hourly` feed row behind a release row must exist and have at least 20 (A) or 30 (B) `panel_devices`. Complementary suppression is by complete publication group: all three segments of one `presence_index` `(unit_id, situation, summer)` group are present or all are absent with `BELOW_PANEL_MINIMUM`; all destinations of one `flow_od` `(origin_unit_id, situation, summer)` group are present or all are absent with that reason. A presence area marginal is returned only when every selected unit group is complete. An OD origin or destination marginal is the exact sum of the same published OD leaves and is returned only when every origin group needed for that marginal is complete. No independent OD marginal is stored. |
| PRV-59 | The shared rules `presence_scale` and `flow_scale` are positive decimal values fixed and committed before any protected or simulated row is read, and are identical for A and B. `presence_score` is `100 × arithmetic_mean(expanded_presence over the feed hours of the situation) / presence_scale`; `flow_score` is `100 × sum(expanded_trips over the feed hours of the situation) / flow_scale`. Both are rounded half-up to four decimal places. Neither scale is computed from a national mean, a sum over protected rows or any other released row. No total of presence or flow is stored; no normalisation equation imposes a recoverable sum over protected rows. `panel_devices` and `expansion_factor` never enter a release. A missing, non-positive or late-configured scale fails the build (ASSUMPTION 24). |
| PRV-60 | Presence and flow are unitless scores on fixed pre-committed scales, never counts of people or devices and never facts for a named place. No person-level protection claim is made for movement. A real aggregate feed must not carry such a claim unless its provider supplies auditable cross-row contribution limits covering cells, situations, segments and OD rows; the release has no device identifiers with which to test that property itself. |

The presence formula averages hourly presence, while the flow formula sums trips over the situation.
Area aggregation sums released `presence_score` leaves over units, as the release contract permits,
and the same tested formula is shared with [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md)
and [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md). The four-decimal score is an interval in the
attacker-view audit, not an exact count.

### 9.3 Worksites

| ID | Requirement |
|---|---|
| PRV-61 | `worker_pay` counts located jobs only: jobs whose worksite is the registered address of the establishment. A job whose worksite is unknown is not located. |
| PRV-62 | Jobs registered at an address but worked elsewhere are reported only as `deployed_elsewhere_count` under PRV-39. They carry no wage statistic and are never drawn at a location. |

### 9.4 The firm channel in version 1

| ID | Requirement |
|---|---|
| PRV-63 | Version 1 releases no fact about a single firm, establishment, owner or person: no name, size band, flag, pay or headcount. No tool returns a row that describes one. A request for one returns `OUT_OF_SCOPE` with reason `NO_FIRM_OR_PERSON_FACTS`. |
| PRV-64 | `outlet_register` holds mutually exclusive activity-class × size-band leaves, `no_payroll` included, for the activity classes listed in the rules configuration (version 1: the food-service classes of the `site_check` playbook), all on `or_register_count`. An establishment is counted once, under its primary activity. Every non-empty joint leaf, every activity-class leaf and every size-band leaf must have at least 5 (A) or 10 (B) unrelated employer groups, largest-group and top-two shares within the caps, and at least `min_groups_count` unrelated groups after any one group is removed. If any category leaf fails, the geographic unit merges; there are no activity-specific partitions and no separately dropped register rows. Every outlet total inside its activity-by-size additive family is the exact sum of that family's treated leaves (ASSUMPTION 19). |
| PRV-65 | A real named place from public listings carries Public facts only. No protected figure is attached to it or computed for its footprint alone. |
| PRV-66 | Oversight roll-ups of questions are statistics about companies. They show no company identity and only groups of at least the distinct-organisation minimum of open item OI-08. |

## 10. Audits that gate a release

All audits run in the custodian plane on both candidate protected table sets before selection and
before the vault is deleted. One failure stops the build and no protected table set is exported.
Only aggregate outcomes for the unselected set may enter the selected release's reports. The
attacker-view audit is evidence under the stated model, not a general non-disclosure proof.

| ID | Audit | The build fails when |
|---|---|---|
| PRV-67 | Rule audit, employer and hidden-group dominance included: recompute from the vault the fixed-order tests of PRV-24 for every treated leaf and every materialised total (unit, band, category, joint home-by-work, side count and register leaf), using employer groups. | any population fails its applicable test |
| PRV-68 | Exhaustive structural closure proof and fuzz regression (section 8). | any assertion of PRV-111 or PRV-51 fails, or fewer than 10,000 pairs ran for any release and parameter set |
| PRV-69 | The one attacker-view acceptance model of PRV-112 to PRV-116, run once per target class against every protected table of the candidate release, both parameter sets' released survival values, every row and source in the signed public-total inventory, and every verified local, insider and colluder fixture. Version 1 has no cross-period variables. | a knowledge fixture disagrees with sealed truth; a published-leaf exact aggregate, attacker-knowledge, published-means-passed, survival or public-total constraint is absent or violated; any applicable inventory entry is absent or not enabled; any target is recovered under PRV-116; any directly computed positive home-area or applicable public count residual is below `min_earners_count`; the base model is infeasible; a solve has an unaccepted status; the measured time budget is exceeded; or any observable release field required by this model is omitted |
| PRV-70 | Group disclosure: every published band set has at least two rows; every band, category and side leaf passes PRV-24; every split satisfies PRV-35; no treated leaf has a true value of zero. | any of these is false |
| PRV-71 | Treatment consistency, separate from acceptance: the build enumerates every family route and deterministically pairs all routes with the same contributor universe, protected period, primitive and source-population selector after expanding geography and pooled categories. Every within-family total equals the exact sum of its treated leaves; every treated count and wage-bill leaf contains its untreated aggregate in the PRV-114 outer interval; and every enumerated cross-family pair is checked by the count or wage-bill bound in section 10.3. The report lists every family, pair, leaf count and bound; its pair count must equal the independently recomputed Cartesian grouping by those four keys. | a route or pair is missing or extra; a within-family margin differs; an untreated leaf lies outside its outer interval; an absolute cross-family route difference exceeds its formula bound; a margin is negative; or a row references a unit outside its partition or family |
| PRV-72 | Release scan: search both candidate protected table sets, the selected release, manifests and reports, the built web bundle, logs and recorded model payloads for vault tokens, synthetic identifiers, canary markers and each canary's exact pay value. | one hit |
| PRV-73 | Typed attack suite (below). | any controls-on predicate is recovered under either parameter set, or a controls-off release predicate is not recovered |

### 10.1 Attacker-view inputs and truth separation

| ID | Requirement |
|---|---|
| PRV-112 | `artefacts/attacker_view_audit.json` is a versioned canonical JSON artefact listed with its SHA-256 in `manifest.artefacts`. It fixes the model schema version, candidate parameter set, `window_key`, `protected_sha256` and `rules_version_id` (never `release_id`, whose hash covers this artefact), target classes, signed local-knowledge, insider and colluder fixtures, solver tolerances, and the audit rule `time_budget_seconds`. That budget is set from a measured full run at the start of slice S5; the artefact records the command, machine class, elapsed seconds and run hash from which it was set. Before optimisation, the build compares every signed knowledge fixture with sealed truth: containing published units for local knowledge, and own staff, sites and payroll for each insider and colluder. Any disagreement fails the build; only a matching fixture becomes a constraint. The model then holds the untreated monthly aggregate of every published protected leaf and no other person-level or employer-level true value. It does not hold a target's true pay, band, unknown category, side class or hidden contribution. Sealed target truth is read only after a solve to score a typed predicate. The model outputs only pass or fail, outward-rounded interval widths, target-class and solve counts, and elapsed time. No untreated aggregate, fixture value, person value or employer value leaves the custodian plane. The model is not relaxed when it exceeds its budget; an over-budget run fails. |

The attacker is given the frame, closed category and band keys, released rows and the verified
knowledge granted by PRV-03. A pay run has one contribution class for the target employer group,
one for each insider and colluder group, and an aggregate class for every other contributor. A person
target also has its own binary membership and wage variables. No hidden-group list or undeclared
group contribution is supplied.

Targets with the same containing published residence and workplace units, the same contribution
class and the same complete months form one target class and are solved once. The vault may be used
to enumerate targets and compute that class signature; only the published-unit memberships that
PRV-03 grants and the class label enter the constraints. The audit report lists person classes,
employer-group classes and solve counts.

### 10.2 Variables and constraints

| ID | Requirement |
|---|---|
| PRV-113 | The audit uses the one finite mixed-integer linear model below for each target class. Every published protected leaf is fixed to its untreated aggregate in each complete month. The model includes the verified attacker knowledge, the linear forms of every published rule, both parameter sets' protected-count-dependent `survival_report` values and the enabled public-total relations. It has no released-value acceptance interval and no constraint for the failure branch implied by a merged band, pooled category, merged sibling, withheld remainder or reason code. Omitting any constraint named below fails the audit build. |

The category tuples are finite and contain source-level values, never an `ALL` or `other` total:

- `residence`: `d = (housing_class, occupation_group, side_class)`, where `housing_class` is
  `family_housing`, `labour_accommodation`, `institution` or `unknown`; `occupation_group` is `0` to
  `9` or `unmapped`; and `side_class` is `eligible`, `not_measured` or `irregular`. Only `eligible`
  has pay bands and wage variables.
- `workplace`: `d = (occupation_group, home_cell, side_class)`, with the same occupation values,
  `home_cell` either a `grid_cell` key or `unresolved`, and `side_class` equal to `eligible`,
  `irregular` or `deployed_elsewhere`. Home municipality is derived through
  `grid_cell.municipality_code`; `unresolved` can occur only in a side count, not a located pay leaf.
- `register`: `d = (activity_node_id, size_band)`, using the configured `activity_class` nodes and
  the four contract size bands.

For any split, a released `other` leaf is a declared union of source-level category tuples in the
audit configuration, not a latent attribute.

The following variables and constraints are mandatory. A sum for leaf `l` ranges over exactly the
base cells and source categories mapped to that released leaf. `H` is the finite set of single-group
classes: target employer group, insiders and colluders.

1. **Eligible pay variables.** For `u` in `residence` or `workplace`,
   `N[u,c,m,h,d,b_net,b_basic]` is a non-negative integer person count.
   `W_net[u,c,m,h,d,b_net,b_basic]` and
   `W_basic[u,c,m,h,d,b_net,b_basic]` are non-negative wage sums. Both band indices range from B01
   to B12. A net row sums over `b_basic`; a basic row sums over `b_net`. A non-pay side population
   uses a separate non-negative integer `S[u,c,m,h,d]` and has no band or wage variable.
   `R[c,m,h,d]` is a non-negative integer establishment count for `register`. Target eligible membership
   is the binary `x_p[u,c,m,h,d,b_net,b_basic]`, target side membership is the binary
   `x_p_side[u,c,m,h,d]`, target location `loc_p[u,c,m]` is binary and separate from coverage, and
   target wages are `w_p_q[u,c,m,h,d,b_net,b_basic]` for `q` in `{net, basic}`. At every identical
   tuple add `x_p <= N`, `x_p_side <= S`, `0 <= w_p_q <= W_q`, `L(b_q) x_p <= w_p_q` and, for a
   finite band, `w_p_q <= U(b_q) x_p`. Where the tuple maps to a published wage-bill leaf `l`, also
   add `w_p_q <= A_wage[l,m,q] x_p`. The target wage for a leaf is the sum of its matching `w_p_q`
   variables; the target band is read from the corresponding `x_p` variables. All variables exist
   for every complete month, including a zero contribution.
2. **Band bounds.** For every joint-band cell,
   `L(b_net) N <= W_net <= U(b_net) N` and
   `L(b_basic) N <= W_basic <= U(b_basic) N`, where the upper inequality is omitted for the open
   band. Because B12 has no upper bound, the band inequalities alone do not empty a cell: for
   every joint-band tuple introduce a binary `z`, add `z <= N`, and add the indicator constraint
   `z = 0 => W_net = 0 and W_basic = 0`. Where the tuple maps to a published wage-bill leaf `l`,
   `W_q <= A_wage[l,m,q] z` is its linear form. For B01,
   `L = 0`, `U = 1,000.49`. For every later finite band, `L` is the previous published upper amount
   plus QAR 0.50 and `U` is its published upper amount plus QAR 0.49. B12 has
   `L = 49,999.50` and no upper bound. Thus QAR 4,999.49 is B02 and QAR 4,999.50 is B03.
3. **Deduplication and known geography.** PRV-08 identities apply. For each target person and month,
   `x_p + x_p_side` sums to at most one in residence and at most one per permitted employer group in
   workplace. For each universe granted by a verified local-knowledge fixture, `loc_p` sums to one.
   For every containing published unit listed by that fixture, `loc_p` sums to one over the unit's
   base cells and zero outside it; all nested unit constraints apply. At each cell and month, the sum
   of eligible and side membership is at most `loc_p`. Thus a covered target cannot move outside the
   known units, while every covered-membership variable may be zero. Location is fixed; coverage,
   side class, source category, net band, basic band and pay are not.
4. **Exact published-leaf equalities.** Let `A_count[l,m]`, `A_wage[l,m,q]` and
   `A_register[l,m]` be sealed untreated monthly aggregates computed from the vault for a published
   protected leaf. For every month:

   ```text
   sum(N matching eligible pay/count leaf l) = A_count[l,m]
   sum(S matching side-count leaf l) = A_count[l,m]
   sum(W_net matching net wage-bill leaf l) = A_wage[l,m,net]
   sum(W_basic matching basic wage-bill leaf l) = A_wage[l,m,basic]
   sum(R matching register leaf l) = A_register[l,m]
   ```

   A merged band sums its member joint-band cells. A category leaf sums its source category;
   `other` sums only the categories assigned by the released layout. A joint `home_area_share` leaf
   sums matching work cells and home cells. Derived `ALL`, `all`, parent-band, area, municipality,
   national and marginal rows add no equation unless they are the one treated leaf of a
   no-breakdown family. The build first checks each stored within-family total against its leaves.
5. **Known payroll.** After the PRV-112 truth check, each insider and colluder fixture fixes that
   class's staff membership, site membership, net wage and basic wage in the applicable variables.
   It fixes no value for another class.
6. **Published pay leaf means passed.** For each published pay count leaf `l`, month `m` and
   `h` in `H`, let `C` be total earners, `C_h` that class's earners, `z_h` a binary contribution
   indicator, `C_other = C - sum_h C_h`, and `G_other` the integer number of unrelated employer
   groups in `C_other`. `C` is fixed to `A_count[l,m]`; use that constant as the finite big-M:

   ```text
   z_h <= C_h <= A_count[l,m] z_h
   C_h <= max_group_share C
   C_h + C_k <= max_top2_share C                    for every distinct h,k in H
   C - C_h >= min_earners_count
   G_other >= min_groups_count - sum_h z_h
   0 <= G_other <= C_other
   C >= min_earners_count
   ```

   The applicable unit total also satisfies `min_earners_count`, `min_earners_money` or
   `min_earners_quartile` for its tier. For a wage-bill leaf and measure `q`, let `V`, `V_h` and
   `w_p` be its total wage bill, class wage bill and target-person wage. Add:

   ```text
   V_h <= max_group_share V
   V_h + V_k <= max_top2_share V                    for every distinct h,k in H
   w_p <= max_person_share V
   ```

   All shares use the active candidate parameter set. These are necessary linear consequences of a
   published leaf; they do not reconstruct anonymous employer groups.
7. **Published register leaf means passed.** Let `E`, `E_h`, `z_h` and `G_other` be the analogous
   establishment counts, single-group contribution indicators and other-group count. Add the count
   share and pair constraints from item 6 with `E`, plus:

   ```text
   G = sum_h z_h + G_other
   G >= min_groups_count
   G - z_h >= min_groups_count                       for every h in H
   0 <= G_other <= E - sum_h E_h
   ```

   Register leaves have no wage constraints.
8. **Survival report.** For each `parameter_set`, `table_name`, `partition_id` row of
   `survival_report` for A and B, the four unit-count fields equal counts recomputed from
   `release_unit` for that partition and table mapping. Let `p` be its integer whole-percent
   `earners_published_share`, `P` the sum of eligible person-months in its published units and `D`
   the sum in all its units over the three complete months. For `outlet_register`, which has no
   eligible-earner population, `p` must be zero and no ratio constraint is added. For every other
   row, `D = 0`, a fractional `p`, or `p` outside 0 to 100 fails the build. Half-up rounding is
   imposed linearly:

   ```text
   p = 0:       0 <= 200 P <= D - 1
   0 < p < 100: (2p - 1) D <= 200 P <= (2p + 1) D - 1
   p = 100:     199 D <= 200 P <= 200 D
   ```

9. **Public totals and movement.** Every enabled PRV-115 entry adds its declared equality or safe
   inequality over exactly its mapped latent population. Equality is permitted only for matching
   scope and period; a covered subset of a larger Public population uses an upper bound. Published
   presence and flow scores retain the PRV-114 score interval. OD and presence marginals sum only
   their published leaves. PRV-59 permits no presence or flow total, public or derivable: a release
   containing one fails, and a suppressed movement residual therefore has no total equation and is
   unbounded in this model.
10. **Excluded layout implications.** The model adds no failed-rule disjunction for a merged band,
    pooled category, merged sibling, withheld remainder or reason code. Section 17 states this limit
    and PRV-76 requires a typed attack for each signal.
11. **Time, L4 only.** When L4 exists, the variables gain a window index and the PRV-56
    changed-cohort, origin, destination and carry-forward identities. Version 1 has none.

| ID | Requirement |
|---|---|
| PRV-121 | Exact reduction. The model of PRV-113 is written over base cells so that it is unambiguous; an implementation need not build it at that size. It may remove or merge variables and constraints only by exact presolve: substituting a constant for a sum that an equality fixes; merging variables that enter every constraint and every target expression only through their sum; and dropping a variable that no constraint links, directly or through other variables, to the target expression of the run. A reduction that changes the feasible set of any target expression is a defect. The audit tests solve one small fixture world in both the full and the reduced form and require identical statuses and identical minimum and maximum for every target class. No other approximation, no sampling of targets and no relaxation is allowed (PRV-112). |

### 10.3 Treatment consistency and score intervals

| ID | Requirement |
|---|---|
| PRV-114 | The formulas below define a conservative outer interval `[L_i,U_i]` around the untreated monthly-average value of each treated leaf. They are not acceptance constraints in the attacker-view model. PRV-71 uses them to check each treated count or wage-bill leaf against its sealed untreated aggregate and to bound a declared cross-family route difference. Movement scores use their separate rounding interval in PRV-113 and PRV-116. A derived within-family total inherits the sum of its leaves and receives no interval of its own. |

For a count leaf under PRV-44, the perturbation is in `[-2, +2]`:

```text
if y = r:       0 <= T <= 3r/2 + 2
if y > r:       max(0, y - r/2 - 2) <= T <= y + r/2 + 2
```

The first case includes the lower clamp on a stored count leaf. A treated count leaf with `y < r`
or with `y` not a multiple of `r` is a build failure, so no other case is required. For a wage-bill
leaf under PRV-45, with `delta` equal to 0.02 (A) or 0.03 (B):

```text
max(0, (y - r/2) / (1 + delta)) <= T <= (y + r/2) / (1 - delta)
```

For a released presence or flow score `s`, with the applicable fixed `scale`, the latent expanded
value `E` (mean presence or summed trips before normalisation) satisfies:

```text
max(0, (s - 0.00005) × scale / 100) <= E <= (s + 0.00005) × scale / 100
```

For two count-family routes `A` and `B` enumerated by PRV-71 for the same untreated population and
period, let `Y_A = sum_i y_i` and `Y_B = sum_j y_j`, using each route's treated leaves, and define
`e_count(i) = max(y_i - L_i, U_i - y_i)`. PRV-71 requires:

```text
abs(Y_A - Y_B) <= sum_i e_count(i) + sum_j e_count(j)
```

For two wage-bill-family routes, define the wage interval by the wage formula above and
`e_wage(i) = max(y_i - L_i, U_i - y_i)`. It requires:

```text
abs(Y_A - Y_B) <= sum_i e_wage(i) + sum_j e_wage(j)
```

The build also requires `L_i <= T_i <= U_i` for every sealed untreated leaf aggregate `T_i`.
These formulas bound implementation differences caused by separately treated families; they do not
make those families equal.

### 10.4 Enumerated, versioned public totals

| ID | Requirement |
|---|---|
| PRV-115 | `artefacts/attacker_view_public_totals.json` is a canonical, versioned, signed artefact listed with its SHA-256 in `manifest.artefacts`. Its entry identifiers must equal, with no missing, duplicate or extra entry, the deterministic set `{source:<source_id> for every source_registry row} union {row:<table_name>:<canonical primary-key JSON> for every row of every manifest table whose provenance_class is public}`. Primary-key fields and table names are exactly those in [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) section 7; the JSON object has key columns in contract order and UTF-8 canonical values. A source entry has `public_total_id`, `inventory_version`, `source_id`, `status` and null row-mapping fields. A row entry also has `table_name`, exact key-column selectors and `source_id`. Status is `enabled` or `not_applicable`; a not-applicable entry has one closed reason: `different_measure`, `disjoint_population`, `incompatible_period`, `unreconciled_source`, `no_licensed_scope_mapping` or `source_only`. An enabled row additionally has `period`, `geography_rule`, `population_rule`, `relation`, `value_column` and `unit`; `equal`, `upper` and `lower` have their literal mathematical meanings. It reads its value only from the named Public row and maps deterministically to PRV-113 variables. Every applicable count, wage-bill or coverage total is enabled. An absent, unconfigured, ambiguously mapped or unsafely related applicable total fails the build; `unreconciled_source` cannot bypass one. The complete inventory and applicability outcomes participate in release identity. |

The inventory includes `pub_census_zone` and every other Public row, including rows that cannot
constrain a protected residual. Licence-activity counts are not establishment or employer-group
counts and must not be equated to them. While OI-03 is open, a public wage row may carry
`unreconciled_source` only when a deterministic scope review finds it inapplicable; a potentially
applicable unresolved row fails. Utility, transport, customs, property, hotel, price and place rows
are `different_measure` unless a reviewed population rule makes one applicable.

[03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) sections 7.2 and 7.3 and DAT-128 define the Public
tables, primary keys, count indicators and units used by this inventory.

### 10.5 Targets, recovery predicates and solver acceptance

| ID | Requirement |
|---|---|
| PRV-116 | The audit runs once per target class of section 10.1 for every person behind a published pay leaf, every employer group behind a published protected leaf and every configured residual. It minimises and maximises numeric targets and tests each candidate value of a band or Boolean. Solver settings are `feasibility_tolerance = 1e-7`, `integrality_tolerance = 1e-6`, `optimality_tolerance = 1e-9` and `outward_bound = 1e-6`, read from `rules_version` (ASSUMPTION 25). A finite interval is expanded outwards by `outward_bound` before scoring. Accepted statuses are: `OPTIMAL` for each finite minimum or maximum; `UNBOUNDED` for an open numeric side, scored not recovered; `FEASIBLE` for a conditioned candidate, scored possible; and `INFEASIBLE` for a conditioned candidate, scored impossible. `INFEASIBLE` for the unconditioned base model fails the build. `INF_OR_UNBD`, a time, node, iteration, solution or gap limit, a numerical failure, interruption, or any other status fails the build. A run over PRV-112's budget also fails. A person-pay target must retain at least two feasible released bands in each month and measure. A headcount interval must be wider than `audit_headcount_width`; a pay-related wage-bill interval must have `(upper - lower) / max(1, (upper + lower) / 2)` greater than `audit_wage_relative_width`. Any directly computed positive `public total or protected municipality total minus the sum of the untreated aggregates of the published leaves mapped to it` below `min_earners_count` fails. A predicate is recovered only under the table below. A fact that every published atom has because it passed a published rule is not a recovery. Concentration and dominance predicates refer to their scenario-labelled population, which may be an unpublished cell. |

The typed predicate registry is closed and versioned in the audit artefact. "Matches truth" is
checked only after the attacker-view optimisation has produced its result.

| Predicate type | Target and recovery condition | Version 1 gate |
|---|---|---|
| `person_pay_band` | For a scenario-labelled person, month and measure, first condition the candidate solve on covered membership being TRUE, then enumerate the released band ranges that can contain the person by mapping feasible B01-to-B12 values through that leaf's released layout. Recovered only when covered membership is forced TRUE and exactly one released range is feasible and contains sealed truth. | coverage is not forced TRUE or at least two released ranges are feasible; no matching singleton |
| `small_cell_membership` | A binary variable for a scenario-labelled person's membership of the covered population of a scenario-labelled target atom. Recovered only when TRUE is forced and sealed truth is TRUE. Forced FALSE is not recovery. | TRUE is not forced |
| `three_employer_concentration` | For three declared employer groups and a scenario-labelled population, whether all three contribute and every other group's aggregate contributor count is zero (establishments for `register`, earners otherwise). Recovered only when TRUE is forced and sealed truth is TRUE. | TRUE is not forced |
| `employer_headcount` | The target employer group's residual distinct-earner count in a pay atom, or its residual establishment count in a register atom, after declared insider and colluder contributions are removed. Recovered when interval width is at most `audit_headcount_width` and the interval contains sealed truth. | width greater than the bound or truth outside it |
| `employer_wage_bill` | The same target's residual wage bill for one measure. Recovered when relative interval width is at most `audit_wage_relative_width` and the interval contains sealed truth. | relative width greater than the bound or truth outside it |
| `hidden_group_dominance` | Whether a scenario-labelled hidden group supplies more than half of a scenario-labelled population's earners, establishments or wage bill. Recovered only when TRUE is forced and sealed truth is TRUE (ASSUMPTION 26). | TRUE is not forced |
| `band_or_category_residual` | The count or wage bill of a band range merged away, a withheld side count, or a withheld category within an explicit `other` leaf. A published leaf's own total is not a residual target. Recovered under the corresponding headcount or wage interval rule and a truth match. | interval wider than the applicable bound or truth outside it |
| `home_area_residual` | Any complement of PRV-40, including a municipality residence total against its `home_area_share` column sum and a work-unit total against its row sum. Recovered when the count interval is at most `audit_headcount_width` and contains truth. | wider interval; separately, no actual positive residual below `min_earners_count` |
| `public_coverage_residual` | An enabled public-total equation's uncovered or unpublished population, including a public zone total minus the sum of the model's untreated aggregates for the published protected leaves mapped to that zone. Recovered when the count interval is at most `audit_headcount_width` and contains truth. | wider interval; no directly computed positive residual below `min_earners_count` |
| `mobility_residual` | A suppressed presence or flow score, or an incomplete OD marginal, in expanded units. Recovered only when both bounds are finite, their score-equivalent width is at most 0.0001 plus twice `outward_bound`, and the interval contains sealed truth. PRV-59's absence of a total leaves the suppressed residual unbounded unless another declared constraint bounds it. | unbounded or wider interval, or truth outside it; no person-level claim |
| `mover_status` | L4 only: a person's origin, destination and employer change between adjacent windows. Recovered when a Boolean or destination is forced and matches truth. | deferred; absent from version 1 |
| `named_entity_fact` | Any fact, payload or page asserting a protected attribute of a named person or employer. Recovery is one confirmed occurrence. | zero occurrences |
| `record_token_key_egress` | Any record, raw identifier, linkage token, treatment key, cell key or draw outside the custodian plane. Recovery is one confirmed occurrence. | zero occurrences |
| `assistant_tool_escape` | Any tool call outside the nine-tool list, argument outside a closed schema, unknown claim or component, invalid fact slot, or model-written prose reaching execution or display. Recovery is one confirmed occurrence. | zero occurrences |

### 10.6 Attack suite

| ID | Requirement |
|---|---|
| PRV-74 | The suite is written and run by a reviewer from a different maker than the engine's builder, who also adds attacks of their own. The builder does not edit it. Fixtures live in `evals/`. |
| PRV-75 | Version 1 uses the sealed scenario's very high earner, small affluent cell and sector with three firms in one area, together with planted hidden-group and aggregate mobility targets. The person who changes employer between two quarters is an L4 canary only. Every version 1 canary and every success condition of section 2 maps to at least one predicate of PRV-116. Values and identifiers are unknown to the attack author; fixtures and reports refer to scenario labels only. |
| PRV-76 | It covers at least: small areas; nested and adjacent areas; shapes that snap to the same units; the typed phrase "the city minus this cell" being declined; linked tables across bases, tiers, splits and measures; every cross-family route pair enumerated by PRV-71; an insider employer subtracting its own payroll; declared colluding employer groups; every enabled public total; every `home_area_share` complement; presence and flow marginals; covered earners against public resident counts; public place listings combined with area statistics; and, through the assistant, repeated and paraphrased questions and injection strings in both languages. It has at least one typed attack for each layout signal excluded from the acceptance model: a merged band, a category pooled into `other`, merged siblings, a withheld remainder and a released reason code. No consecutive-window or cross-period attack is in version 1. |
| PRV-77 | Controls off: the release attacks run against a naive twin that exists only at build time in the custodian plane and returns exact statistics for any set of base cells and any month. Every release-attack predicate must be recovered and match sealed truth. This demonstrates that each release attack can recover its planted target when the controls are absent. Assistant, egress and scene boundary attacks have no controls-off run. |
| PRV-78 | Controls on: the suite receives the selected protected table set, the other set's aggregate survival and attack results, all Public data, `artefacts/attacker_view_public_totals.json`, `artefacts/attacker_view_audit.json`, this document and the source code, but no key or unselected protected table set. Verified local, insider and colluder fixtures are supplied as attacker knowledge. A canary or threat outcome is recovered only when its PRV-116 predicate succeeds and matches sealed truth where required. None may be recovered under either candidate parameter set. |
| PRV-79 | The outcome is written to a signed attack report (Ed25519, like the other build-time reports) and listed in the selected release manifest. It names its release by `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set`, never by `release_id`, whose hash covers the report. It holds, for each attack, its scenario label, predicate type, configuration hash, controls-off outcome and aggregate controls-on outcome for each parameter set. It names no canary identifier and holds no canary marker, exact pay value, recovered band, record, token, key, true atom value or other untreated value. Only aggregate counts and pass/fail outcomes for the unselected set are exported. |

## 11. The survival report

| ID | Requirement |
|---|---|
| PRV-80 | `survival_report` holds, in the selected release, one aggregate row per `parameter_set`, `table_name` and `partition_id`: `units_total`, `units_published`, `units_pooled`, `units_withheld` and `earners_published_share`, using the columns of [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md). Pooled units are published `merged` and `remainder` units; the earner share is rounded to whole percent. It contains no unselected protected-table row. |
| PRV-81 | A signed survival detail report adds, per partition: the share of frame cells and of earners in units at resolution 9, 8 and 7, in a published remainder and in a withheld one; the share of failing roots by first failed test in the fixed order of PRV-24, at national level only; and, for each showcase pin, the tier reached and the requested and released areas of the default walk and drive areas under A and B. The flagship pin and default cut-offs are confirmed only after this report exists in slice S5. |
| PRV-82 | The Proof room shows both with the sentence: "Measured on synthetic data. Rates on real data are unknown until the engine runs inside a custodian's environment." |

## 12. Run-time behaviour and the privacy receipt

| ID | Requirement |
|---|---|
| PRV-83 | Tools read release tables only, through the store interface of [08_BACKEND.md](08_BACKEND.md). No tool evaluates a test, a dominance share or a treatment: none of their inputs exists at run time. |
| PRV-84 | Whether a figure is withheld is read from the release (`release_unit.status`, absent rows, null side counts) and from the fixed checks of PRV-31. It never depends on an earlier question, the seat, the language or the time of day. |
| PRV-85 | A `suppressed` fact carries no value, no range, no band and no reliability mark. |
| PRV-86 | The alternative offered beside a blank (a wider cut-off, or the published remainder as a separate, labelled fact) is chosen from the request and the frozen partition only. |
| PRV-87 | Every tool result that reads a protected or simulated table carries a privacy receipt with the fields below. Its JSON Schema is written in `contracts/` in slice S5. |
| PRV-88 | Every tool call writes a ledger row with the seat, the tool, the typed arguments, the release and, per block, the unit-set hash, status and reason codes. |
| PRV-89 | Area requests are rate-limited per seat (default 30 a minute; ASSUMPTION 21, to be tuned). A rate-limit reply depends only on the request rate. Logs and limits are operational controls; no privacy claim rests on them (PRV-03). |
| PRV-117 | Seat selection is carried by the signed session cookie `eii_seat`, and presenter controls require the per-session header `X-EII-Presenter-Token`. These provide query isolation after a seat is selected and stage control only; they are not an identity system or tenant authentication, and no disclosure claim rests on them. |

| Receipt field | Content |
|---|---|
| `release_id`, `rules_version_id`, `parameter_set`, `period` | the selected release, the rules version, the exported set (`A` or `B`) and the single window behind the answer |
| `area_id`, `request` | the area and how it was asked: the pin's base cell, mode and cut-off |
| `blocks` | one entry per evidence block, with the fields below |
| `block`, `partition_id`, `tier` | the block, the partition it was snapped on and its tier |
| `unit_ids`, `unit_set_sha256` | the units used, sorted, and the SHA-256 of that list |
| `snap` | requested and released area in km²; frame cells inside, added, dropped, and left out (PRV-22) |
| `treatments` | what stands behind the figures: `cell_key_perturbation`, `margin_preserving_rounding`, `rounding_count` and `rounding_money` with their bases, `band_merging` where bands were joined |
| `audit` | versions and hashes of `artefacts/attacker_view_audit.json` and `artefacts/attacker_view_public_totals.json` |
| `withheld` | each withheld statistic with its reason code |
| `fact_ids` | the facts the block produced |
| `statement` | the fixed sentence "Every figure is a sum of published units of this release. Nothing was computed from records for this request." |

The application adds what was sent to the model and the result of the check that runs before
display ([09_AI_ASSISTANT.md](09_AI_ASSISTANT.md)). The receipt shows the five accounting-gate checks
(sources, assumptions, nothing invented, scope and limits stated) under "Checked before display";
its Arabic label is pending the owner's review.

## 13. Reason codes behind every blank

| ID | Requirement |
|---|---|
| PRV-90 | `suppression_reason` holds the two catalogues below: the label as `label_en`, the sentence as `explanation_en`. `release_unit.suppression_reason_code` holds `REMAINDER_FAILED` or `FAILED_THIS_PERIOD` for a withheld unit, and nothing else. |
| PRV-91 | A reason attached to a blank never says which test failed, or by how much: that would describe the withheld group. How often each test fails appears only as national shares in the survival detail report (ASSUMPTION 22). |
| PRV-92 | The application chooses the sentence from the code. The model never writes or changes one. Arabic labels and sentences are prepared strings pending native review (open item OI-09); this document gives none. |

| Code | Status | Label | English sentence |
|---|---|---|---|
| `SNAPPED_TO_WHOLE_UNITS` | `OK` (note) | Fitted to whole cells | Your area was fitted to whole grid cells under the release's disclosure-control rules. The figure describes the fitted area. |
| `PART_OF_AREA_POOLED` | `OK` (note) | Partly pooled | Part of your area is counted at municipality level and is not in this figure. The snap report shows which part. |
| `BANDS_MERGED` | `OK` (note) | Bands joined | Some pay bands were joined together here, so the band shown is wider. |
| `DEPLOYED_ELSEWHERE_NOT_MAPPED` | `OK` (note) | Counted, not mapped | These jobs are registered at an address here, but the work is done elsewhere. They are counted, not placed on the map. |
| `POOLED_IN_REMAINDER` | `SUPPRESSED` | Pooled with the municipality | This place is counted together with other small places of its municipality. It has no figure of its own. |
| `REMAINDER_FAILED` | `SUPPRESSED` | Withheld | This place is counted together with other small places of its municipality, and even together they do not meet the rules. No figure is shown. |
| `FAILED_THIS_PERIOD` | `SUPPRESSED` | Withheld this period | This unit met the rules when the map was fixed for the year, but not in this period. No figure is shown. |
| `DETAIL_NEEDS_LARGER_GROUP` | `SUPPRESSED` | Needs a larger group | This detail needs a larger group than this place holds. A wider area will show it. |
| `SPLIT_NOT_PUBLISHABLE` | `SUPPRESSED` | Split not shown | This split is not shown here, because one of its parts would be too small or too concentrated. A wider area will show it. |
| `BANDS_NOT_SHARED` | `SUPPRESSED` | No common band | Pay bands were joined differently in the cells of this area, so no common band can be shown. |
| `BELOW_PANEL_MINIMUM` | `SUPPRESSED` | Too few devices | Too few devices of the simulated panel were present here at this time to show an index. |
| `NOT_MEASURED` | `NO_DATA` | Not measured | The wage record does not cover these earners, so there is no figure for them. This is a gap in coverage, not a zero. |
| `OUTSIDE_FRAME` | `OUT_OF_SCOPE` | Outside the map | This point is outside the mapped land area. |
| `NO_FIRM_OR_PERSON_FACTS` | `OUT_OF_SCOPE` | No single company or person | This product holds no figure about any single company or person, so it cannot answer that. |
| `DIMENSION_NOT_OFFERED` | `OUT_OF_SCOPE` | Split not offered | This product does not split figures by nationality, or by sex for an area. |
| `AREAS_FROM_PINS_ONLY` | `OUT_OF_SCOPE` | Pin-based areas only | Areas are built only from a pin with a distance or a travel time. Free shapes and "everything except" areas are not offered. |
| `NO_TIME_SERIES` | `OUT_OF_SCOPE` | One window only | This release describes one three-month window. It holds no history for small areas. |
| `EGRESS_BLOCKED` | none (application stop) | Stopped by a safety check | The answer was stopped by a safety check, and the event was recorded. |

Rule explanations. These describe a rule. They are shown as the list of rules behind a blank and in
the Trust centre, and are never attached to one unit.

| Code | Label | English sentence |
|---|---|---|
| `BELOW_MIN_EARNERS` | Minimum earners | A figure is shown only when enough earners stand behind it. |
| `BELOW_MIN_EMPLOYER_GROUPS` | Minimum employers | A figure is shown only when enough separate employers stand behind it. |
| `EMPLOYER_DOMINANCE` | One employer's share | A figure is not shown when one employer accounts for too much of the people or the pay behind it. |
| `TOP_TWO_DOMINANCE` | Two employers' share | A figure is not shown when two employers together account for too much of it. |
| `PERSON_CONCENTRATION` | One person's share | A pay figure is not shown when one person's pay is too large a part of it. |
| `BAND_TOO_SMALL` | Small pay band | A pay band with fewer than five earners is joined to the band next to it. |

## 14. Linkage design, shown on synthetic identifiers

```mermaid
flowchart LR
  R["business_register"] --> T["tokeniser: keyed tokens"]
  E["employment"] --> T
  W["wages: pay fields only"] --> T
  H["residence: base cell and housing class"] --> T
  T --> V[("vault: linked tables, tokens only")]
  M["mobility: aggregate feed"] --> P
  V --> P["privacy engine and audits: candidate A and B"]
  P --> S["select exactly one parameter set"]
  S --> REL[("one exported release: treated leaf sums")]
  V -.->|"deleted when the build ends"| X["nothing kept"]
```

```text
arrives       SYN-P-K7Q2M9XD        a synthetic person identifier, as the feed carries it
normalised    SYN-P-K7Q2M9XD        trimmed, upper case, pattern checked, placeholders rejected
token         HMAC-SHA-256(link_key, "person:SYN-P-K7Q2M9XD")      64 hexadecimal characters
kept          the token only; the identifier is dropped
```

| ID | Requirement |
|---|---|
| PRV-93 | A token is `HMAC-SHA-256(link_key, namespace + ":" + normalised_identifier)`, kept at its full 64 hexadecimal characters, with one namespace per identifier kind. The link key is held by the linkage role only and is never in the product plane, the repository or a log. Here it is derived from the sealed scenario seed. |
| PRV-94 | Identifiers are normalised and validated before tokenising, as [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) requires. A placeholder is rejected, never repaired. Raw identifiers are dropped as rows enter the linked tables. |
| PRV-95 | A test proves that no linked table holds a raw identifier, that every token has full length, and that no token equals an unkeyed hash of its identifier. |
| PRV-96 | The address is reduced to a base cell and a housing class before the residence feed is written. No address, street, building or coordinate enters the vault, and none meets a wage. |
| PRV-97 | The wages adapter loads only the pay fields of the contract. A bank, account, payer or name field is never loaded: a test feeds a row with such an extra field and asserts that the build stops. |
| PRV-98 | Joins use tokens only. A registration that covers several establishments is never a join key by itself. Rows that do not link are counted and reported as unknown, never guessed. |
| PRV-99 | Mobility never enters linkage. It reaches the release only as aggregate scores and meets wage statistics only area to area. |

## 15. The AI boundary and canary tripwires

The assistant is specified in [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md). The rules below are the ones
the privacy argument depends on. They apply published mitigations for prompt injection: least
privilege, separation of untrusted content, and validated output [S18].

| ID | Requirement |
|---|---|
| PRV-100 | The privacy argument does not need the model to behave. A model that ignores every instruction can still obtain only what the nine production tools return, and they return release facts only. The scene-only endpoint of PRV-119 is not an assistant tool and is not model-callable. |
| PRV-101 | No production tool accepts a query, a table name, a column name, a cell or a unit list from the model, and no production tool returns a row about one person, firm or establishment. Protected tables are read only through an `area_id` from `make_area`. The manifest-listed fixture route of PRV-119 is the sole scene-only exception and accepts no arbitrary area, cells or unit ids. |
| PRV-102 | Canary markers are strings that match `CANARY-[0-9A-HJKMNP-TV-Z]{10}`. The sealed scenario plants one in every free-text field of every canary record (ASSUMPTION 23). A canary's identifier and its exact pay value are canary strings too. |
| PRV-103 | Tripwire at run time: every outbound model payload and every API response is scanned for the canary marker pattern and for synthetic identifiers (`SYN-`, a capital letter, a hyphen). A hit blocks the payload, shows the sentence of `EGRESS_BLOCKED`, and writes an incident row that the oversight seat shows. Canaries never appear on a rendered page, in an export or in a payload; a replay or proof panel uses only the scenario label. |
| PRV-104 | Text written by third parties (place names, labels) reaches the model only as JSON string values inside tool results, declared as untrusted data. |
| PRV-109 | The typed-decision gateway is build-time and evaluation-only, defaults to provider `none`, and is absent from privacy, release-building and serving imports. It takes no part in any rule, audit, tripwire or scene step. Its only visible trace is the fixed activity-spine lineage sentence in the Proof room, rendered from the human review log; no provider output or score is displayed. |
| PRV-118 | The application-owned structured brief has only `headline_key`; `decision_template_key`; `observed[]` and `inferred[]`, each `{claim_key, slots}` with typed fact ids and, for inferred items, `strength` (`strong`, `indicative` or `illustrative`); `still_to_test[]` and `not_measured[]` chosen by the application from fact caveat and coverage keys; `next_questions[]`, each `{question_key, slots}`; `layout[]` as ordered component instances `{component, props}`; and `stage[]` directives, all from the versioned application catalogues. The model may select and order only the claims, components, questions and directives; its brief carries `catalogue_version`. English and Arabic prose is rendered only from application-owned templates; model-written prose is discarded. An unknown key or property, a wrong fact slot or an invalid layout is rejected, followed by one repair attempt and then the playbook default. A Synthetic or Simulated claim or component must have the area around the pin as its subject and must never name a real place. No runtime scan of model prose substitutes for these structural checks. |

## 16. The "Try to break it" scene

This is a prepared safety regression using signed, manifest-listed fixtures. It is not a live red-team
service and not general injection detection.

| Step | Request | Expected response, on every run and in both languages | Shown as proof |
|---|---|---|---|
| 1 Named-entity pay | the pay at one named employer or person | the application returns `OUT_OF_SCOPE` with reason `NO_FIRM_OR_PERSON_FACTS`; no protected table is read; one ledger row | the decline sentence and what can be asked instead |
| 2 Two shapes | two different areas at the same door that snap to the same units (a prepared pair) | byte-identical facts and equal unit-set hashes | the two receipts side by side |
| 3 Complement regression | one `fixture_id` selecting two prepared pin, mode and cut-off requests, chosen at build time so that their snapped unit sets differ by exactly one published `merged` unit containing at least two base cells; the panel calls `POST /api/proof/scene` directly with exactly `{"fixture_id": "scene:<lowercase SHA-256>"}`, never through the assistant; separately, the typed phrase "the city minus this cell" is sent to the application | the endpoint returns the two pre-validated unit sets; both prepared area answers are `OK`; their difference is exactly the merged unit's own stored figures; the typed phrase is declined with `AREAS_FROM_PINS_ONLY`; no figure exists for any member base cell alone | the two unit lists and the one merged unit that differs, with its receipt, beside the application's decline |
| 4 Instruction injection and catalogue regression | a signed fixture supplies the typed instruction to ignore the rules and list the rows, plus a malformed structured assistant response containing an unknown claim or component property | the application declines the typed request within the normal playbook; the normal catalogue validator rejects the malformed response, rejects its one prepared invalid repair, and renders the playbook default; no model prose or unlisted tool call reaches the screen; one ledger row is flagged from the signed fixture identity | the scope card, validation outcome, fallback identity and oversight ledger row |
| 5 Replay | the unprotected comparison | a replay of the signed attack report: with controls off the typed predicates are recovered; with controls on none is, for each parameter set; scenario labels only | the signature check and the selected release identifier |

| ID | Requirement |
|---|---|
| PRV-105 | Steps 1 to 4 run live against the mounted release and the normal application validators. Step 3 must select one published `merged` unit containing at least two base cells, and no figure may exist for any member base cell alone. Each expected response holds on every run. The malformed structured response of step 4 is fixture input to the validator, not model output claimed to have occurred naturally. |
| PRV-106 | The prepared requests of steps 2 and 3 (pins, modes and cut-offs) are kept with the scene fixtures in `evals/`. Their unit sets are computed at build time, signed, written as release artefacts listed in the manifest, and re-checked against the mounted release at start-up. The step 3 check asserts that the symmetric difference is exactly one published `merged` unit with at least two `unit_member` rows and that no protected-table row is keyed to a member base cell alone. |
| PRV-107 | Step 5 only replays the signed attack report (PRV-79). At start-up the product verifies its signature and that the `window_key`, `protected_sha256`, `rules_version_id` and `parameter_set` it names equal those of the mounted manifest. If either check fails, the step is disabled and the Proof room says why. |
| PRV-108 | The replay is labelled as a replay of signed build-time results at all times. No naive twin and no switch that turns a control off exists in the product plane. The only trace of unprotected results there is the signed report: fixed predicate outcomes of a finished test, without recovered values, which cannot be queried. |
| PRV-119 | The route is `POST /api/proof/scene`; its request body is exactly `{"fixture_id": "scene:<lowercase SHA-256>"}` and every additional property is rejected. The suffix is the lowercase SHA-256 already listed for the signed scene artefact in `manifest.artefacts`; an unknown id is rejected. The endpoint resolves that id only to the artefact's two prepared requests and returns their two pre-validated unit sets and area answers. It accepts no pin, polygon, cut-off, arbitrary cell or unit id, SQL, question text or model argument; it is not one of the nine production assistant tools and has no custodian-plane path. Step 4's `injection_flag` is true if and only if the presented fixture id matches the manifest-listed injection fixture and its signature and artefact hash verify; it is not inferred from visitor text. |

## 17. Limits and non-claims

- **No formal guarantee.** Thresholds with stable perturbation and rounding are established practice and carry no mathematical privacy guarantee. Differential privacy is not used and not claimed.
- **No certification.** The rule checks, one exact-aggregate attacker model and typed attack suite are stated evidence on synthetic data, not certification.
- **Averaging attacks.** A published attack removed bounded noise from a national statistics office's online table builder by writing different queries that evaluate to the same answer [S3]. Here each leaf has one stored value and no query language exists. Routes inside one family add exactly; routes across families may differ only within PRV-71's bound and are not shown side by side as two estimates. Audit acceptance assumes all treatment has been removed, so it does not rely on noise resisting averaging. Every new table is a new route and needs a new consistency audit and attack review.
- **Real suppression rates are unknown.** The survival report describes a synthetic world. How much survives on real data is unknown until the engine runs inside a custodian's environment.
- **Outside knowledge.** A reader who knows almost everyone in a unit may learn about the rest. The audit includes the verified local, insider and colluder knowledge declared in its fixtures; it does not enumerate other facts an attacker may know. Public totals outside `artefacts/attacker_view_public_totals.json` are outside the tested attacker model. Adding one requires a new audit and rules version. No claim extends beyond that model.
- **Layout signals are not in the acceptance model.** A merged band, a category pooled into `other`, merged siblings, a withheld remainder and a reason code each show that a population passed or failed part of the published procedure. PRV-113 does not model those failure branches or their deterministic merge and pooling paths. PRV-76 requires at least one typed attack for each signal. A passing optimisation therefore says only that the stated exact-aggregate model found no recovery; it does not address every inference from the layout. One typed attack for each kind of signal can miss a disclosure at another released instance of the same kind; two independent reviewers recorded that objection (open item OI-36). Before any real-data pilot, either the failure branches are modelled or an attack runs against every released instance.
- **Time.** Version 1 avoids the one-mover attack by holding a single window. That is a restriction, not a method and not a consecutive-window claim. PRV-56 must be built and attacked under L4 before a second window exists.
- **Movement.** The per-row panel minimum and complementary suppression do not prove person-level protection for a linked presence and flow cube. No device identifiers are available for such a proof. A real feed needs auditable provider controls across rows before anyone may make that claim.
- **Cost in detail.** All-or-nothing pooling is blunt. One empty or dominated cell keeps its whole parent together, a later partition of a family is never finer than the one before it, and a five-minute walk can be fitted to a unit of several square kilometres. The snap report and survival report state that loss honestly; no privacy rule is tuned for a finer showcase. If the survival report shows too much loss, pooling of failing siblings is the next step ([decision 0007](decisions/0007-disclosure-control-by-pooling-and-stable-treatment.md)).
- **Coverage complement.** On real data, a low count of covered earners in a populated place hints at who is not covered. Data owners should weigh `not_measured_count` with particular care.
- **One export.** Differently ruled layouts of one window can be differenced, and each export multiplies the routes an auditor must check. Therefore only the selected parameter set's protected tables leave the custodian plane. The unselected set contributes aggregate survival and attack outcomes only. Untreated aggregates, knowledge-fixture values, target truth, keys, variables and the unselected protected rows stay in the custodian plane. The reason is not that treatment noise must remain secret.
- **One treatment per window.** PRV-120 derives `window_key` only from the protected period and the manifest's `feed_sha256` of the four protected feeds (`business_register.v1`, `employment.v1`, `residence.v1`, `wages.v1`). It does not change when a Public or Simulated table, a scene fixture, a report or a treatment rule changes; a change that alters one of the four feeds under the same `world_seed` creates a second `window_key`, which is refused. No invariance to scenario text is claimed. Continuous integration permits one protected hash per key and one key per world seed. A stage machine accepts only a bundle whose matching register line is on the base branch and in the application archive built from that branch. There is no receipt-file substitute for that allow-list. Unfrozen synthetic builds stay on the build machine. Two different protected input sets that describe nearly the same population, such as a revision, are not covered; that is the second-window problem of backlog item L4.
- **Not legal advice.** Whether and how real records may be linked is for the data owners.

## Open questions and assumptions

Each ASSUMPTION is the simplest safe choice where the master design is silent.

1. The `(municipality_code, parent_r7, smallest_member_cell)` processing order and final `unit_id` tie-break are deterministic implementation choices. Root intersections themselves are binding and need no majority-assignment tie rule.
2. An empty frame cell fails like a small one: an exact zero would tell a reader that nobody in a known building is a covered earner.
3. Partition names follow the release contract's naming scheme. Each contributor universe has one family, ordered so that a split can fail without coarsening a pay tier. `ha_home`, `px_base` and `fl_r7` carry tier `count` because the contract requires a tier.
4. Snap by best fit (the pin's unit, plus units at least half selected), remainders never added: a scattered remainder would swamp a local figure. Any deterministic rule on whole units is equally safe.
5. One block, one area: a count and a median band on two different areas would mislead.
6. The top-two cap applies to the same measures as the largest-group cap.
7. Each primitive sits at the strictest tier of anything derivable from it; hence coarse bands at `money` and fine bands at `quartile`. Without this the 30 and 100 minimums could be bypassed by reading band rows.
8. A test must hold in every month of the window: the strictest reading of a monthly average.
9. Coarse ranges B01 to B02, B03 to B04, B05 to B12: three ranges on existing boundaries.
10. Employer caps, top-two and insider-removal tests apply inside every band and category row: a small or employer-dominated band would otherwise show an employer's pay scale after payroll subtraction. Register leaves use the remaining-group form of insider removal.
11. Shared band boundaries across tiers and across occupation groups, so that no merged range can be recovered by subtraction; `occupation_pay` sits at the `quartile` tier so that one partition serves the median and the quartile bands.
12. Required categories per split, and "or hold nobody" inside a unit that passes: a split with no gap shows which categories are empty in any case. `other` is an explicit treated leaf, never a subtraction result.
13. Side counts live on one partition per table. Required side categories coarsen or withhold a unit when non-empty and failing; only the non-required `irregular_count` has an ambiguous null.
14. Home units are municipalities formed by the terminal union of every whole-cell unit and remainder of the governing residence family: the coarsest reading of "a large pooled district", with both sides' complements audited.
15. The perturbation table, the wage-bill factor and the key construction: small, symmetric and stable.
16. Version 1 has one protected window; the L4 carry-forward rule is only a proposal until two adjacent test windows pass every cohort and cross-period attack.
17. A trend index, if ever added under L4, tracks the same earners in both windows, so a mover cannot show.
18. The carry-forward rule is a proposal for the second window; data owners may choose another only through a new decision record and a fresh attack audit.
19. `outlet_register` covers food-service classes only, with the group minimum on every size band and one shared register partition. Expect detail to survive only for large units.
20. The attacker-audit width bounds are 5 / 10 earners and 15% / 20% relative wage-bill width around the feasible midpoint. They are proposed audit decision bounds, not proof of a privacy level; the wage range lies within the 10 to 20% range published for p% rules [S5].
21. The rate limit of 30 area requests a minute per seat is a starting value.
22. Reasons do not name the failed test: naming it would describe the withheld group.
23. The canary marker pattern, planted in the free-text fields of canary records.
24. The index formulas use 100 as a display base and positive `presence_scale` and `flow_scale` denominators fixed before the feeds are read. Their numeric values are to be confirmed at the slice S1 spike and frozen before the first slice S4 world build; no national mean or protected-row sum may set them.
25. The four solver tolerances are deterministic engineering proposals chosen so that every interval can be expanded outwards before a recovery decision; they are not measured privacy parameters.
26. The hidden-group dominance predicate means more than half of the target atom, which makes the Boolean linear and avoids an arbitrary near-tie share threshold.
27. Set A is the default exported set (PRV-120): it is the baseline proposal, and the cost of the stricter set B stays visible in the survival report. The choice is made before any world is built and is never changed to make an area look finer.

Open items from the master design that touch this document: OI-11 (every value here is a proposal);
OI-35 (which parameter set is exported; default A);
OI-08 (distinct-organisation minimum, PRV-66); OI-09 (Arabic reason sentences); OI-01 (assistant
attacks run against a recorded provider until the key exists); OI-07 (a prospect list of firms would
reopen the firm channel and needs new rules); OI-03 (a public wage row is marked
`unreconciled_source` only after a deterministic non-applicability finding; any applicable unresolved
row fails the build); OI-04 (only a Public source with its required licence and scope mapping may be
enabled in the public-total inventory).

Open question: whether a human attacker session is added before any real-data pilot (recommended by
the panel research, not required here). The public-total inventory is not an open choice: every
applicable total must be configured before the release gate, and an unconfigured one fails the build.

## Sources

Retrieved 2026-11-11. "Re-checked" means the author of this document opened the page that day;
the others were read by the pack's research on the same date.

- [S1] Australian Bureau of Statistics, Data Confidentiality Guide, "Treating aggregate data" (released 8 November 2021). Re-checked. https://www.abs.gov.au/about/data-services/data-confidentiality-guide/treating-aggregate-data
- [S2] Office for National Statistics (United Kingdom), "Protecting personal data in Census 2021 results" (9 March 2023). Re-checked. https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/methodologies/protectingpersonaldataincensus2021results
- [S3] "Averaging Attacks on Bounded Noise-based Disclosure Control Algorithms", Proceedings on Privacy Enhancing Technologies, 2020, issue 2, pages 358 to 378. Re-checked. https://www.petsymposium.org/popets/2020/popets-2020-0031.php
- [S4] Government Analysis Function (United Kingdom), "Statistical Disclosure Control for tables produced from administrative data" (19 August 2026). Re-checked. https://analysisfunction.civilservice.gov.uk/policy-store/sdc-for-tables-produced-from-administrative-data/
- [S5] Government Analysis Function (United Kingdom), "An introduction to Statistical Disclosure Control (SDC)" (19 August 2026). Re-checked. https://analysisfunction.civilservice.gov.uk/policy-store/an-introduction-to-sdc/
- [S6] H3 documentation, cell statistics by resolution and hierarchical indexing. Re-checked. https://h3geo.org/docs/core-library/restable/ and https://h3geo.org/docs/highlights/indexing/
- [S7] Flowminder Foundation, "Understanding CDR aggregates: Fundamentals". Re-checked. https://covid19.flowminder.org/cdr-aggregates/understanding-cdr-aggregates-fundamentals
- [S8] "Unique in the Crowd: The privacy bounds of human mobility", Scientific Reports, 2013. Re-checked. https://dspace.mit.edu/handle/1721.1/88233
- [S9] Statistics Finland, Grid Database: thresholds from its user manual (2025), read by the pack's research; the product page was re-checked and refers to that manual. https://stat.fi/en/services/statistical-data-services/geographic-data/grid-database
- [S10] Statistics Estonia, earnings application, "Background". Re-checked. https://palgad.stat.ee/en/background
- [S11] Statistics Netherlands, "Toelichting Wijk- en Buurtkaart 2023, 2024 en 2025" (28 November 2025). Re-checked. https://www.cbs.nl/nl-nl/longread/diversen/2025/toelichting-wijk-en-buurtkaart-2023-2024-en-2025?onepage=true
- [S12] Statistics Denmark, "Statistics on the Danish national grid". Re-checked. https://www.dst.dk/en/TilSalg/produkter/geodata/kvadratnet
- [S13] Statistics Sweden, "Development of disclosure protection". Re-checked. https://www.scb.se/en/documentation/statistical-areas-under-change/development-of-disclosure-protection/
- [S14] United States Internal Revenue Service, Statistics of Income, county and ZIP code data documentation guides. Pack's research. https://www.irs.gov/pub/irs-soi/23incydocguide.docx
- [S15] INSEE (France), gridded income data at 200 m. Pack's research. https://www.insee.fr/fr/statistiques/8735162
- [S16] Office for National Statistics (United Kingdom), "User guide to earnings and employment from Pay As You Earn Real Time Information" (revised 25 July 2025). Re-checked. https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/methodologies/userguidetoearningsandemploymentfrompayasyouearnrealtimeinformation
- [S17] United States Census Bureau, origin-destination employment statistics (LODES), technical documentation. Pack's research. https://lehd.ces.census.gov/data/
- [S18] OWASP, "LLM01:2025 Prompt Injection". Pack's research. https://genai.owasp.org/llmrisk/llm01-prompt-injection/
