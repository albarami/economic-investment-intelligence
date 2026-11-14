# Privacy rules configuration

This folder holds the rules configuration and its check. PRV-01 places the privacy engine in the custodian plane, and PRV-04 reads every threshold from one versioned rules configuration. The engine itself is a later task.

The committed file fixes four entries of `rules_version` for task S1-T09, under one `rules_version_id` of `rv-1.0.0-s1`:

- `export_parameter_set` is `A` (shared). Its unit is `parameter set` (PRV-05, PRV-120).
- `window_months` is `23` (shared). Its unit is `months`. By SYN-12 and SYN-29 the window is expected to be January 2024 to November 2025 (`2024-01` to `2025-11`), the 23 complete months of the reference period, because December 2025 is left incomplete on purpose; the engine takes the months that the `wages.v1` coverage declaration marks complete (PRV-53), and the task that builds it checks that they are these.
- `round_movement` is `50` for set A and `100` for set B. Its unit is `people or vehicle trips` (PRV-59).

`presence_base`, `presence_scale` and `flow_scale` are not entries. The check refuses those names. Version 1 releases no presence or flow index (PRV-59).

A rule code that is in the closed lists of DAT-129 and is not one of these three rules is accepted when it is present and is not required when it is absent. The task that builds the privacy engine adds those codes and applies the exact-set test of DAT-129.

The two range values of SYN-77 are not fixed in this file; the first is the nominal expansion factor, one over `mob.panel_penetration`, whose starting value in the synthetic-world document is 10% (5% to 20%, swept); the second is `mob.range_multiple`, which has no value yet: its cell of the starting table reads "fixed at slice S1", and until it has a value the world build refuses to start (SYN-69).

This task cannot prove that no world is built with another file. No world build exists yet. The tasks that build the world and the release are where that is tested (PRV-120, TST-193).

The check is a function. Tests call it. There is no command.

See [PRV-59](../../../../docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md), [DAT-129](../../../../docs/03_DATA_CONTRACTS.md), [SYN-12](../../../../docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md) and [PLN-25](../../../../docs/14_IMPLEMENTATION_PLAN.md).
