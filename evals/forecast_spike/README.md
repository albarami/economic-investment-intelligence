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
fixtures. The generated formula and Auto-labelled prefix stubs are declared as
fixtures; they are not implementations or measurements of AutoETS, AutoTheta or
AutoARIMA. `fixture.py` proves the harness in fresh CPU processes with worker
counts one and two. Stable result bytes exclude process, timing and memory
metadata, which are written separately to stderr. Memory is the largest worker's
peak, not aggregate process memory. No batch budget or serving-performance pass
is asserted. The socket patches in the arithmetic workers are fixture guards,
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

`evidence/invented_run.json` records the initial fixture run: registration and
result hashes, candidate/family scores and coverage counts, CPU batch times and
worker peaks. Its workload includes the parallel series jobs and their joint
family scoring. It is experimental evidence, not a test baseline or a library
performance result.

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
package installation are intentionally absent. The weights report accepts only
an experiment folder or an invented temporary folder inside the repository.
