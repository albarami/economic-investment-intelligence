# Decision 0060: The custodian suite runs in two named parts under the unchanged limit

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-18 |
| Owner | The owner |
| Decided by | The owner's note of 2026-11-18 22:03 (relayed by the owner's advisor) and the lead's rulings L-902 and L-1006, under AGENTS.md rule 46 |
| Amends | The suite table of `scripts/run_tests.py` (the second of the twelve conventions of `./eii test` in open item OI-46's confirmation request: six suites become seven); README.md's sentence on the suites; TASKS.md S2-T34; the height fixtures' zip writer |
| Purpose | Keep every custodian test running once, under its unchanged 600-second suite limit, on the slower hosted runner. |
| Read first | AGENTS.md rules 12, 36, 37 and 39; [decision 0027](0027-hosted-web-checks-time-limit.md); TASKS.md S2-T34 |

## Context

The hosted `tests` check of pull request 87 failed with `python-custodian: no result within 600 s; the process group
was killed`, at 92 percent of the suite. The same 7,189 custodian tests had taken 386 and 569 seconds on two earlier
hosted runs; the failing head holds 7,349 and ran in 277 seconds locally on one quiet core. The hosted runner is
between 1.4 and 2.4 times slower and varies from run to run. The local durations spread thinly over 253 test modules
(the slowest 48.7 seconds), so removing waste in a few tests would not give a lasting margin (ruling L-902, 2(b)).

## Decision

1. **Two named parts.** The suite `python-custodian` is replaced by `python-custodian-1` and `python-custodian-2`, in
   its place in the table. Each runs `pytest` over `custodian/tests` with the same 600-second limit. No other suite
   changes.
2. **A stable split by module.** A test belongs to a part by its module's repository-relative path: SHA-256 of the
   path, modulo 2, plus 1. Items outside the part are deselected through pytest's own hook, never skipped. A new test
   module lands in a part with no list to update. Without the part option, `pytest custodian/tests` runs everything.
3. **The manifest guard.** A guard test proves on every run of `python-guards` that the two parts are disjoint, that
   their union equals the whole collection by test id and by count, and that neither is empty, with planted
   violations.
4. **What does not change.** The 600-second limit of every suite, the 3,600-second guard limit, decision 0027's web
   limits, the hosted check names and every test and assertion. No test is deselected from the whole run. The limit
   stays as the regression alarm: a part that nears it again is split by a further record, never by a raised limit.
5. **A random failure found with the measurement is fixed at its cause.** The first measurement of part 1 failed
   `test_two_runs_give_identical_file_hashes` once: the height fixtures packed their zip members with the wall-clock
   time, and the manifest records each input's hash, so two builds on either side of a two-second step of the zip time
   field differed. The fixtures now write every member with the zip format's first date, a test proves their bytes do
   not depend on the clock, and the byte-equality assertion is unchanged (open item OI-286).

## Sources

- The hosted run of pull request 87 (run https://github.com/albarami/economic-investment-intelligence/actions/runs/44364506690, the `tests` job) and the hosted runs of the base branch at
  b380109 and of pull request 86.
- The lead's local measurement of the failing head 396ef6e on one core (project records of the run).
