# core/ — shared Python library `eii_core`

This folder will hold `eii_core`, the Python library shared by the custodian plane and the product plane: provenance, the fact model, the manifest, grid helpers and the calculation layer (`eii_core.calc`).

## Rules

- `eii_core` imports neither `eii_custodian` nor `eii_product` (ARC-06, BE-01).
- Every displayed number comes from deterministic, tested code. No model calculates.

The package includes the calculation layer under `src/eii_core/calc/`, with the
deterministic apportioning of `eii_core.calc.apportion` (task S2-T13), and its
regression tests under `tests/`. Calculation arithmetic uses the Python standard
library; callers supply typed rows and source chains.

Read: [02_ARCHITECTURE.md](../docs/02_ARCHITECTURE.md), [08_BACKEND.md](../docs/08_BACKEND.md)

The calculation layer uses a single fully specified Decimal context (precision
50, half-up) independent of caller and process defaults. The Decimal and text
admission checks reject subclasses. Repeated iterable inputs are snapshotted
once; list and generator inputs have the same checks and results. Typed C3
calculations refuse a zero baseline mean before constructing display facts.
These contracts are exercised by `tests/test_decimal_context_contract.py` and
`tests/test_b5_boundaries.py`, which run in the whole test command (`./eii test`).
Calculations carry exact rationals to the output and round once, half up, at the
output. The stated fifty-digit context applies only to a root that is not rational
and its derived values, with refusal near a rounding or comparison boundary.
