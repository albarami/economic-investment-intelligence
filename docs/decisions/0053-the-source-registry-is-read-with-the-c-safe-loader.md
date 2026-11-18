# Decision 0053: The source registry is read with the C safe loader

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-18 |
| Owner | The owner |
| Decided by | The lead's ruling L-902 and task S2-T31 brief, under AGENTS.md rule 46 |
| Amends | The registry loader and its safety guards; TASKS.md S2-T31; the accepted-record sentence and Decision records table of docs/README.md |
| Purpose | Remove repeated pure-Python registry parsing overhead without weakening safe loading, tests or the suite limit. |
| Read first | AGENTS.md rules 12 and 33 to 39; TASKS.md S2-T31; ruling L-902 |

## Context

The lead's measurements of 2026-11-18, supplied in the S2-T31 evidence brief, report the whole custodian suite at train-1 head `8d00c27`: 5620 passed in 834.6 seconds against its unchanged 600-second limit. The hosted job on that head also stopped at the limit. The same three test files (208 tests) took 52 seconds at `a3e1254` and 166 seconds at `8d00c27`.

The committed source registry grew from 171,402 to 479,638 bytes. The lead's profile of `test_pub67_all_nine_values_structural_unreviewed_and_frame_key` attributed 2.30 of 2.44 seconds to `read_yaml`, reached through `load_registry`, using the pure-Python `yaml.safe_load` scanner on every load. On that registry, the lead measured 0.295 seconds with `yaml.SafeLoader` and 0.031 seconds with `yaml.CSafeLoader`; the loaded objects compared equal. The locked environment reported `yaml.__with_libyaml__ is True`.

The lead's discarded, uncommitted probe changed only `read_yaml` to the C safe loader. The suite then reported 5619 passed and one failed in 226.4 seconds. The failure was the old text guard requiring `safe_load` and forbidding `yaml.load`. These are the lead's measurements, not this decision's acceptance run.

## Decision items

1. **Use only the C safe loader in `read_yaml`.** Parse with `yaml.load(..., Loader=yaml.CSafeLoader)`. No pure-Python fallback is permitted: absent libyaml or an absent C loader fails loudly. Keep `RegistryError("malformed yaml")` for every `yaml.YAMLError`. Change no other function or module's loader.

2. **Replace the old guard with stronger safety and parity guards.** The replacement docstring identifies this decision. Temporary YAML files with inert invented `!!python/object/apply:` and `!!python/name:` targets must raise `RegistryError` without constructing anything. A source scan forbids unsafe loaders and functions, including `yaml.Loader`, `FullLoader`, `UnsafeLoader`, `unsafe_load`, `full_load`, `yaml.unsafe` and all `load_all` calls; every `yaml.load` call must pass `Loader=yaml.CSafeLoader`. Permanent planted violations include `Loader=yaml.Loader`, `yaml.full_load` and a bare `yaml.load(text)`. The locked-environment guard requires libyaml and its C loader; missing-loader plants prove refusal without fallback. The committed registry must compare equal under `yaml.SafeLoader` and `read_yaml`, with a planted changed result refused. No other tests change.

3. **Keep the regression alarm.** The whole custodian suite must pass under its unchanged 600-second limit with margin. No test is deselected, skipped or weakened to achieve that result. The task records its actual run time and count separately from the lead's earlier measurements.

## Consequences

The lead's probe demonstrates that removing repeated pure-Python parsing overhead can restore suite-time margin; the task's full-suite acceptance run must confirm it. Libyaml becomes a requirement of the locked environment, already met by the pinned wheel in the lead's measurement and checked by the new guard. A missing C loader is a hard failure. Parsed values and the YAML-error boundary stay unchanged. The 600-second limit remains a regression alarm; the missed growth in suite time is recorded as an open item.

## Alternatives rejected

- **Raise the limit:** forbidden by ruling L-902; remove waste first.
- **Parallel runner or split suite:** later options only if spread-out time remains after removing the measured waste; neither is part of this task.
- **Parsed-registry cache:** introduces shared mutable state across tests and callers; changing the parser avoids that new state.

## Sources

- The lead's measurements of 2026-11-18, supplied as `EVIDENCE-suite-time.md` with task S2-T31, measurements 1 to 6.
- The S2-T31 task brief, B1 to B4 and Checks; lead ruling L-902.
- AGENTS.md rules 12 and 33 to 39; TASKS.md S2-T31; `custodian/src/eii_custodian/publicdata/fetch/registry.py`, function `read_yaml`; `custodian/tests/test_publicdata_registry.py`, safe-loader guards.
