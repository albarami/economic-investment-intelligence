# Decision 0106: The parameters of card C12 fixed at slice S2

| | |
|---|---|
| Status | Proposed: drafted for open item OI-394 under ruling L-1633 item 1; the four choices ruled by the lead under ruling L-1641, 2026-11-23; accepted under the lead's delegation once another maker APPROVES |
| Date | 2026-11-23 |
| Scope | [Document 07](../07_ECONOMIC_METHODS.md) **C12 Reachable-access score** and MTH-46; [document 03](../03_DATA_CONTRACTS.md) DAT-151, DAT-153 and DAT-154 and the `access_score` and `access_score_grid` rows; [document 08](../08_BACKEND.md) the `reachable_access` contract; [TASKS.md](../../TASKS.md) S6-T13 |
| Amends | Nothing until accepted. Once accepted, it fills the values that document 07 C12, DAT-151, DAT-153 and DAT-154 say are "fixed at slice S2", and closes the C12 entry of document 07's open questions and the matching OPEN entry of document 03 |
| Purpose | Fix the decay `f`, the cut-offs `t0` of each mode, the supply layers, the modes, the presence keys and the traffic settings that `access_score` and `access_score_grid` store, and the largest cut-off of each mode, which bounds `travel_time_matrix` |
| Read first | AGENTS.md rules 4, 16, 25 and 46; document 07 C12, MTH-46, MTH-66 and MTH-67; document 03 DAT-76, DAT-151, DAT-153 and DAT-154 |

## Context and evidence

Document 07 C12 (**Inputs**, **Formula**) says the cut-offs `t0` of each
mode and the decay `f` are "fixed at slice S2". Its open questions add that
the supply layers, the modes and presence keys that `access_score` stores, and
the largest cut-off of each mode (which bounds `travel_time_matrix`), are fixed
there too. Document 03 says the same in DAT-151, DAT-153 and DAT-154 and in its
OPEN entry. No S2 task or record fixes them.

The lead's ruling L-1633 item 1 says that S6-T13 builds C12 with these values
held as one typed, closed parameter object with no default values, and that its
tests use the C12 worked example as an invented fixture. Pinning the values is
open item OI-394 for the S2 gate: a decision record, starting from the worked
example. The same ruling holds that MTH-67 governs: no drive time or drive-time
area of the live traffic provider enters an access score.

What the pack itself fixes, and what it leaves open:

| Parameter | Fixed by the pack | Left open |
|---|---|---|
| Decay `f` | its shape: `f(t) = 0` when `t > t0`, `f(0) = 1`, never increasing (C12 **Formula**) | the form inside `t0` and any parameter of it |
| Cut-offs `t0` | one score per cut-off; `reachable_access` takes one as a closed value (C12 **Inputs**; document 08); no drive cut-off above 30 minutes anywhere (document 08 `make_area`, decision 0023 item 17) | the values for each mode |
| Supply layers | their kind: an activity spine key with Public places of a mapped category in `pub_place`, or the key of a reviewed list of gazetteer points (C12 **Inputs**; `access_score` row of document 03) | which keys |
| Modes | the domain `walk`, `drive` (DAT-151, DAT-153, DAT-154; document 08) | nothing (item 4) |
| Presence keys | the domain: the `presence_count` key (`day_type`, `hour`, `summer`) of segment `resident` (DAT-151), within the combinations DAT-76 allows | which keys are stored |
| Traffic settings | `free_flow` for both modes, `hourly` for `drive` only; the grid table at `free_flow` only (DAT-151, DAT-153, DAT-154) | nothing (item 6) |

Where the pack gives no value, this record does not pick one. It sets out the
options, each ruled by the lead under ruling L-1641, with the options tables
kept as the record of what was weighed.

## Symbols used for the row counts

These symbols state each choice's effect on stored rows as a formula. No count
is computed here.

- `U`: the published `px_base` units of the release (the demand locations of
  `access_score`, DAT-72).
- `G`: the cells of `worldpop_qat_2020` with a population value above zero and
  a centre in the frame (DAT-154).
- `L`: the number of supply layers (item 3).
- `C_walk`, `C_drive`: the sets of cut-offs of each mode (item 2), and
  `max C_m` the largest cut-off of mode `m`.
- `P`: the set of stored presence keys (item 5); `|P|` its size.
- `N_m(t, k)`: the number of ordered unit pairs `(from, to)` whose time by mode
  `m` under traffic key `k` is at most `t` minutes. `N_m(t, k) <= U²`, and it
  never decreases as `t` grows.

## Proposed decision

### 1. The decay `f`: ruled

**Basis.** The C12 **Formula** fixes the shape (zero beyond `t0`, `f(0) = 1`,
never increasing). The worked example uses binary decay, `f = 1` within `t0`
(C12 **Worked example**; MTH-66). The research note used "a Gaussian decay" for
a 10-minute drive and records neither the Gaussian's form nor its parameter
(C12 **Research note**). MTH-46 re-derives that research regression "with the
decay form fixed at slice S2". If it does not reproduce, MTH-04 applies.

**Effect on stored rows.** None on the row count: every form gives one row per
key. The form changes the `score` value of each row and the cut-off sentence
of the Source chain (C12 **Limits and wording**: "The cut-off and the decay are
choices, named in the Source chain").

| Option | Value | Gained | Lost |
|---|---|---|---|
| A | binary: `f(t) = 1` for `t <= t0`, `0` beyond | no parameter to source; the fixture of MTH-66 and the stored scores share one form; the allowed sentence "Within {t0} minutes' drive … there are about {score} … places per 10,000 people" reads literally; a score depends only on whether a pair is in `travel_time_matrix` | MTH-46 runs the research regression again with a form other than the research's, so it may not reproduce, and then MTH-04 applies; a place just inside `t0` counts the same as one next door |
| B | Gaussian truncated at `t0`, with the form and parameter that the research used, read from the research's own record in the uncommitted cache (PUB-12) and written into this record before acceptance | MTH-46 reproduces the research directly; nearer places weigh more | the pack does not hold the form or the parameter today, so the record cannot be accepted until the lead finds them; the "within {t0} minutes" sentence no longer reads literally; the MTH-66 fixture stays binary, so the function must accept both forms, and the parameter object must name which one is stored |

**Ruling (L-1641).** A, binary. It is the only form the pack holds (C12 worked
example, MTH-66). This is no cut: the pack never fixed a Gaussian, and its form
and parameter are not recorded. MTH-46 re-derives with binary; if it does not
reproduce, MTH-04 applies.

Whichever option is ruled, the parameter object names the form by a closed key
(`binary` or `gaussian`), with no default (L-1633 item 1).

### 2. The cut-offs `t0` of each mode: ruled

**Basis.** The worked example and the research note both use `t0` = 10
minutes, the research by drive. Document 08 `make_area` offers 5, 10 and 15
minutes for walk and drive, and sets no drive cut-off above 30 minutes
anywhere (decision 0023 item 17). `reachable_access` takes "one of the cut-offs
that method card C12 stores for the chosen mode … not the `make_area` list":
the tool checks the value against C12's own list, which may hold the same
numbers. C39 uses 10, 20 and 30 minutes' drive for its own catchments (S6-T20).

**Effect on stored rows.**

- `access_score`: `U × L × |P| × (|C_walk| + 2 × |C_drive|)`. The factor 2 is
  the drive rows at `free_flow` and at `hourly` (item 6).
- `access_score_grid`: `G × L × (|C_walk| + |C_drive|)`.
- `travel_time_matrix`: `N_walk(max C_walk, free_flow) + N_drive(max C_drive, free_flow) + Σ over k in P of N_drive(max C_drive, k)`.
  Only the largest cut-off of each mode enters; smaller cut-offs add no rows
  (DAT-153). Each term is at most `U²`.

| Option | `C_walk` | `C_drive` | Gained | Lost |
|---|---|---|---|---|
| A | 5, 10, 15 | 5, 10, 15 | the same numbers as the `make_area` walk and drive list, so an area and its access score speak of the same minutes; holds the research and fixture value 10; the smallest drive bound that covers the `make_area` minutes (`max C_drive` = 15) | no drive score at 20 or 30 minutes, the minutes of C39's catchments |
| B | 5, 10, 15 | 10, 20, 30 | drive cut-offs match C39's 10, 20 and 30; holds 10; stays within the 30-minute ceiling | `max C_drive` = 30 makes the drive terms of `travel_time_matrix` the largest of the three options, once for `free_flow` and again for each key of `P`; drive 5 and 15 are lost |
| C | 10 | 10 | only the value the pack already uses; the fewest score rows (`|C_walk|` = `|C_drive|` = 1) | the user cannot change the cut-off, so a score has no choice beside it; walk 10 is not tested by the research |

**Ruling (L-1641).** A, walk 5/10/15 and drive 5/10/15. These are the
`make_area` minutes and hold the research value 10. No pack value is dropped:
C39's catchments are C39's own.

### 3. The supply layers: ruled

**Basis.** C12 **Inputs**: "Public points of one category from `pub_place`, or
a reviewed list of gazetteer points". The `access_score` row of document 03
names the key: an activity spine key with places of a mapped category, or the
key of a reviewed gazetteer list. Document 07 C6 keeps C12 on `pub_place`
only until a reviewed change adds `pub_place_fsq`. The pack names no layer.

**Effect on stored rows.** `L` multiplies every row of `access_score` and
`access_score_grid` (item 2 formulas). It does not change `travel_time_matrix`,
whose pairs are unit-to-unit and serve every layer (DAT-153).

| Option | Value | Gained | Lost |
|---|---|---|---|
| A | every activity spine key that has a reviewed mapping to a `pub_place` category | every activity the product can name has a stored score, so `reachable_access` returns `OK` or a status, never a missing layer, for an activity in the spine | `L` is the size of the mapped spine, the largest of the three; spine keys whose places are few give scores of little meaning |
| B | a closed list of spine keys that the lead names in this record, each with a mapped `pub_place` category | `L` is small and known; each layer is chosen for journey D2 | an activity outside the list returns `NO_DATA` ("a layer is missing", document 08); the lead must name the keys, which this draft does not invent |
| C | option B plus one reviewed list of gazetteer points, named by its key | adds a supply layer that `pub_place` lacks | needs a reviewed gazetteer list for this use, which no task builds yet; `L` grows by one |

**Ruling (L-1641).** A, every activity spine key with a reviewed mapping to a
`pub_place` category. This is the full value: B or C would make an activity
outside a list return `NO_DATA`, a cut under rule 9.

### 4. The modes

**Value.** `walk` and `drive`, in both `access_score` and `access_score_grid`.

**Basis.** DAT-151, DAT-153 and DAT-154 give `mode` the domain `walk`, `drive`,
and `reachable_access` accepts both as inputs (document 08). Storing only one
would make the other input always `NO_DATA`, which the tool contract does not
list. No option is open.

**Effect on stored rows.** Both terms of `(|C_walk| + 2 × |C_drive|)` and
`(|C_walk| + |C_drive|)` are present (item 2), and `travel_time_matrix` holds
both modes.

### 5. The presence keys stored in `access_score`: ruled

**Basis.** DAT-151: the demand is the residents present of `presence_count`
(segment `resident`) at the row's `day_type`, `hour` and `summer`. DAT-76
allows `summer = true` only for `weekday`, `friday` and `saturday`; the other
three day types have `summer = false` only. `situation_windows` (document 03)
gives each dial situation its day type, hours and allowed `summer` values.
S6-T13 asks for a score "by hour of day where congestion changes travel time".
`reachable_access` takes an optional `day_key` and `hour_key`. Every row of
`access_score` carries a presence key, also at `free_flow`, because the demand
changes by hour.

**Effect on stored rows.** `|P|` multiplies every row of `access_score`, and
the hourly drive terms of `travel_time_matrix` run over `P` (item 2 formulas).
`access_score_grid` has no presence key and is not affected.

| Option | `P` | `|P|` as a formula | Gained | Lost |
|---|---|---|---|---|
| A | every `(day_type, hour, summer)` that DAT-76 allows | `24 × (3 × 2 + 3 × 1)` | any `day_key` and `hour_key` of the release has a stored score; no new status in `reachable_access` | the largest `access_score`, and `travel_time_matrix` holds one drive term per key of `P` |
| B | the keys of `situation_windows`: for each situation `s`, its day type, each of its hours and each of its `summer_values` | `Σ over s of (number of hours of s × number of summer_values of s)`; the four situations share no key | the hours the product's dial already uses; a much smaller `access_score` and `travel_time_matrix` | a `day_key` and `hour_key` outside the set has no stored score, so document 08 must add a `NO_DATA` reason for an unstored key; hours outside the windows are not scored by hour |
| C | option B for `hourly` drive rows and their `travel_time_matrix` terms, option A for `free_flow` rows | `free_flow` rows over A's keys, `hourly` rows over B's keys | free-flow access by any hour; the hourly matrix stays at B's size | two key sets in one table; a request at an hour outside B gives a free-flow score and no hourly one, which document 08 must state |

**Ruling (L-1641).** A, every `(day_type, hour, summer)` that DAT-76 allows,
for `free_flow` and `hourly`. The full value: B would leave hours unscored, a
cut under rule 9.

**Size.** S6-T13 measures the real row counts of `access_score` and
`travel_time_matrix` over these keys. If a size limit of the pack is breached,
any narrowing goes to the owner first with the value lost (OWNER_RULES 9 as
recorded in L-1641); the build never narrows it.

### 6. The traffic settings stored

**Value.** `access_score`: `free_flow` for `walk` and `drive`; `hourly` for
`drive` only, timed by `traffic_hourly` at the row's own presence key.
`access_score_grid`: `free_flow` only. `travel_time_matrix`: `free_flow` for
both modes, and `hourly` for `drive` at each key of `P`. No `situation` row is
stored: the `traffic` column of `access_score` has no situation value, and
`reachable_access` takes no situation input.

**Basis.** DAT-151 (`traffic`: `free_flow`, or `hourly` for `drive` only), DAT-153
(its `traffic` column and null keys at `free_flow`), DAT-154 (`free_flow`
only, because an hourly time is Simulated), and MTH-67 with C25: no drive time
or drive-time area of the live traffic provider enters an access score. The
provider is off by default and never needed (AGENTS.md rule 4; L-1633 item 1).
A live drive-time area may be shown beside a score, never scored.

**Effect on stored rows.** This is the factor 2 on the drive term of
`access_score` and the `Σ over k in P` term of `travel_time_matrix` (item 2).

### 7. The largest cut-off of each mode, which bounds `travel_time_matrix`

**Value.** `max C_walk` and `max C_drive` of the option ruled in item 2:
15 and 15 under option A, 15 and 30 under B, 10 and 10 under C.

**Basis.** DAT-153: the artefact holds every ordered pair whose time is at most
the largest cut-off of the mode; an absent pair is beyond it or has no route.

**Effect on stored rows.** The `travel_time_matrix` formula of item 2.

### 8. The parameter object

S6-T13 holds items 1 to 7 as one typed, closed parameter object with no
default values (L-1633 item 1): the decay form key and its parameter, if any;
`C_walk` and `C_drive`; the supply-layer keys; the modes; the presence keys;
the traffic settings. A missing or unknown field is refused. The release
build reads the values this record fixes. The tests read the worked example
as an invented fixture, which stays binary with `t0` = 10 whatever is ruled
here.

## What each document will say once this record is accepted

- Document 07 **C12 Reachable-access score**: the **Inputs** bullet on cut-offs
  and decay, and the decay line of the **Formula**, name the values of items 1
  and 2 and cite this record. The C12 entry of the open questions is removed.
  MTH-46 names the decay form of item 1.
- Document 03: DAT-151 names the supply layers, modes, cut-offs, presence keys
  and traffic settings of items 2 to 6; DAT-153 names the bound of item 7 and
  the hourly keys of item 5; DAT-154 names the supply layers, modes and
  cut-offs of the grid table. The `access_score` and `access_score_grid` rows
  cite this record for `cutoff`. The C12 OPEN entry is removed.
- Document 08 `reachable_access`: no change follows. With option A ruled for
  items 3 and 5, every activity spine key has a stored layer and every
  `(day_type, hour, summer)` that DAT-76 allows has a stored score, so no
  `NO_DATA` reason is added.
- [TASKS.md](../../TASKS.md) S6-T13 cites this record for its parameter values.
- Open item OI-394 is closed by acceptance.

## Consequences and limits

- No value in this record comes from real custodian data. Every value is a pack
  value, a pack bound or an option for the lead to rule.
- The row-count effects are formulas. `U`, `G` and the `N_m` terms are known
  only once a release is built; this record computes none of them.
- The live traffic provider adds no traffic setting, now or under any option.

## What would change this decision

Any change to a value fixed here (a decay form or parameter, a cut-off, a
supply layer, a mode, a presence key or a traffic setting) needs a further
decision record. Under AGENTS.md rule 12, a change to the export of a frozen
release also needs a new `world_seed` and a new build.

## Sources

- The lead's ruling L-1633 item 1, 2026-11-23 (open item OI-394).
- [Document 07](../07_ECONOMIC_METHODS.md): **C12 Reachable-access score**
  (Inputs, Formula, Storage, Worked example, Research note, Limits and
  wording), MTH-46, MTH-66, MTH-67, the open questions on C12, and C6 on
  `pub_place_fsq`.
- [Document 03](../03_DATA_CONTRACTS.md): DAT-72, DAT-76, `situation_windows`,
  DAT-151, DAT-153 and DAT-154, the `access_score` and `access_score_grid` rows,
  and the OPEN entry on C12.
- [Document 08](../08_BACKEND.md): the `make_area` and `reachable_access`
  contracts.
- [Document 04](../04_PUBLIC_DATA_PACK.md): PUB-12 and the `worldpop_qat_2020`
  row.
- [Decision 0023](0023-ten-additions-and-the-data-rule.md) item 17.
- [TASKS.md](../../TASKS.md): S6-T13 and S6-T20.
