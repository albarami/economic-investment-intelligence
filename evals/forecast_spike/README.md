# S6-T27 offline forecast experiment

This package is an experiment under TASKS.md S6-T27 and ruling L-1228. It has no
production caller. It imports the unchanged C30 baseline predictors and Decimal
context; nothing in core imports this package. It cannot promote a candidate,
emit a product fact or certify a Public/released-series acceptance run.

`contract.py` freezes the series, family strata, ordered candidates, horizon,
exact levels and target origins before fitting. `backtest.py` computes the
spike-only `s6-t27-prefix-mase-v1` score. Document 07's section “S6-T27 spike-only
score and procedure” specifies the arithmetic. Each result carries its contract
and input hashes. The original C30 score, interval and candidate list are intact.

`preregistration.json` preregisters invented annual, quarterly and monthly
fixtures. The generated formula stays invented. `statistical.py` now fits real
AutoETS, AutoTheta and AutoARIMA through StatsForecast 2.1.1 (retreat 2.1.0,
not tried), as fixed prefix callbacks. The fixture command has no stub route;
prefix-last test doubles live only in named unit-test helpers. `fixture.py`
checks the real statistical adapters in fresh CPU processes with worker
counts one and two. Stable result bytes exclude process, timing and memory
metadata, which are written separately to stderr. Library warnings are retained
in that stream and summarised in the evidence. BLAS/OpenMP environment limits
are set before library imports, and threadpoolctl limits each actual fit to one
thread, including when the caller has already loaded a wider thread pool.
Memory is the largest worker's
peak, not aggregate process memory. No batch budget or serving-performance pass
is asserted. The socket patches in the fixture workers are fixture guards,
not a security sandbox or permission to execute an unreviewed model.

`adapters.py` contains CPU/pin/hash admission and training-boundary classification
for Chronos-2, then TimesFM 2.5. Both actual integrations remain **blocked**:
no package is in the lock, no weights or exact revision/file hashes are supplied,
and the official inference/median APIs cannot be confirmed offline. Even a
complete invented metadata fixture cannot clear `inference_api_unconfirmed`.
The tests distinguish verification of admission machinery from model execution.
`check_models.py` emits those blockers with exit 2; it neither fetches nor loads
a model. A later implementation must read the official pages, pin compatible
packages/revisions/hashes and retreat versions, verify a documented median,
enforce CPU-only offline inference, preregister model-boundary strata, and prove
each actual model deterministic across fresh processes and worker counts.

Public targets strictly after a reliably documented training boundary form
`post_cutoff`; overlapping/uncertain targets are descriptive only. Generated
targets remain `generated` and require go-live re-fitting/re-backtesting. Each
comparison uses a separate preregistration for its eligible stratum, with the
same paired targets for its comparator. Eligibility is not performance or model
admission. Unknown overlap never establishes an uncontaminated Public comparison.

The source audit is
`custodian/publicdata/review/s6_t27_forecast_audit.md`. Missing receipts, units,
continuity, revision mappings and dependency inputs keep their families blocked.
Calculation-level invented substitution does not establish source-to-release
parity, actual volumes or the real-source go-live gate.

`evidence/invented_run.json` preserves the initial stub fixture run: registration and
result hashes, candidate/family scores and coverage counts, CPU batch times and
worker peaks. Its workload includes the parallel series jobs and their joint
family scoring. It is experimental evidence, not a test baseline or a library
performance result. `evidence/real_statsforecast_run.json` separately records
the real-model run; it never replaces a test baseline. Tiny prefixes can be
refused by the real library. Missing required forecasts/calibration keep cells
blocked on the original registered targets; no fallback, later start, reduced
minimum or new target selection is applied.

Every actual fit uses the family's season length and requests exactly 80 or 90
from its rational preregistered level. Native mean/interval arrays are checked
and converted losslessly from their finite binary floats to Decimal. The API
names the statistical point `mean`. The harness takes only the finite point;
its intervals remain the candidate's own prospective conformal residuals.
Native interval variance can be undefined on short prefixes; the separate native
interval adapter refuses non-finite bounds and never supplies them to scoring.

## Validation and proposed command contracts

Tests are `scripts/tests/test_forecast_spike*.py`. They use invented values and
temporary assets/lock files only, except for reading the tracked registration and
the real lock's dependency metadata. Temporary fixtures use the runner's
documented temporary directory, including `.overnight/tmp` in this build. No
test opens a data cache or obtains weights. Tests exercise the fixture commands
as internal invented-fixture proofs under L-1228 point 8.

The return proposes direct fixture and model-report commands for rule 44.
**The lead must add them to both rules files before direct execution.** No new
command is authorised by this README. Model fetching/inference commands and
package installation are intentionally absent. The weights report accepts a
repository path excluding `data` and `.private`. Tests may explicitly supply
`--fixture-temp-root`: an existing fixture directory strictly below the system
temporary root (including a configured TMPDIR); weights must then lie strictly
below that named directory. Forbidden components remain forbidden, the entire
temporary root is refused, and arbitrary outside paths remain refused.
