# Decision 0097: Custodian shards retain headroom under the existing limit

| | |
|---|---|
| Status | Proposed implementation under authorised ruling L-1517 item 2; independent review pending |
| Date | 2026-11-23 |
| Owner | The owner |
| Amends | Decision 0086 item 1; document 12 section 2.1; the runner suite table and hosted suite matrix |
| Purpose | Keep every custodian test in exactly one whole-module shard below the measured headroom target |

## Decision

1. Use five named parts, `python-custodian-1` through `python-custodian-5`, by SHA-256 of the repository-relative POSIX module path modulo 5, plus one. New modules use the same rule. There is no duration table or exceptional module assignment.
2. Keep every part at 1,200 seconds and the green hosted watch at 720 seconds. Keep every other suite, the seed rule and process-group kill unchanged. The workflow matrix adds only the corresponding parts; its six required check names and aggregate verdict contract remain unchanged.
3. The manifest compares complete test IDs and counts, refuses overlap, missing tests, empty parts and a wrong part count, checks every custodian test file is collected, and refuses splitting a module's cases across parts. Missing-module, duplicated-module and off-by-one plants each fail for their specific reason.

## Measurement and limits

The builder measured each original part once on a shared machine, with four-core affinity, offline and with one fixed seed. Per-module seconds sum JUnit testcase durations, including setup, call and teardown. The candidate predictions add the largest measured run overhead to each part. No idle-machine scaling is supported or applied. The measured table, alternative splits and selected prediction are in the S2-P67 return; PROGRESS.md records the summary and real command exits. Prediction is not a hosted timing measurement. Different-maker review and the lead whole test remain pending.

## Sources

- Ruling L-1517 item 2 and the S2-P67 brief.
- [Decision 0086](0086-custodian-part-limit-and-watch.md), items 1 to 4.
- [Document 12](../12_TESTING_AND_QUALITY.md), section 2.1.
- [PROGRESS.md](../../PROGRESS.md), **S2-P67 — custodian shard headroom**.

## Recorded measurements — S2-P67

All seconds below were measured or calculated from the original three parts on a shared machine, seed `1794000123`, Python `3.14.6`, affinity `6,7,16,17`, offline with workspace temporary files. No idle scaling was applied.

| Original part | Modules | Tests | Wall seconds | JUnit case seconds |
|---|---:|---:|---:|---:|
| 1 | 119 | 4310 | 1003.371 | 988.350 |
| 2 | 127 | 5365 | 939.867 | 928.514 |
| 3 | 117 | 4084 | 840.072 | 825.584 |

Each predicted shard adds the largest measured overhead, 15.021 seconds, to its modules' summed JUnit durations. This is a prediction, not a run of the new split.

| Candidate | Part | Tests | Predicted seconds | Share of limit (%) | Meets target |
|---|---:|---:|---:|---:|---|
| SHA modulo 4 | 1 | 3202 | 420.652 | 35.054 | no |
| SHA modulo 4 | 2 | 2916 | 754.296 | 62.858 | no |
| SHA modulo 4 | 3 | 4478 | 723.869 | 60.322 | no |
| SHA modulo 4 | 4 | 3163 | 903.715 | 75.310 | no |
| SHA modulo 5 | 1 | 1944 | 383.624 | 31.969 | yes |
| SHA modulo 5 | 2 | 2767 | 650.693 | 54.224 | yes |
| SHA modulo 5 | 3 | 2147 | 592.711 | 49.393 | yes |
| SHA modulo 5 | 4 | 3787 | 521.383 | 43.449 | yes |
| SHA modulo 5 | 5 | 3114 | 669.142 | 55.762 | yes |

Selected: **5 parts, SHA modulo**. The first SHA candidate that fits takes priority over a measured table. When neither SHA candidate fits, the first balanced candidate that fits is selected.

Measurement receipt: `.overnight/OUT/measurements.json`; original command record: `.overnight/OUT/measurement-command.txt`; per-module table: `.overnight/RETURN.md`. These local artefacts are the builder's evidence, not a release input.

- `part-1-collect.txt`: SHA-256 `a6288d43344a5d38bf8b11601ab74701db24ad587168b0eff86b4abeec343458`.

- `part-1-measure.txt`: SHA-256 `0f5e4e9145df93ee48dbe915c70d42a9f847a711eadffcda8f78df92fc581e0e`.

- `part-1.xml`: SHA-256 `6358e031f5bda6d49bd885264c5251e725d0dba495ff409bd34c270da675ad8a`.

- `part-2-collect.txt`: SHA-256 `3b326ea5b80dc88fafd71932f20d00d204aab472ad7707025f0b3eb73f1c6ee3`.

- `part-2-measure.txt`: SHA-256 `4c99ca868192a6f0e5a03b077d4a7831fffa78848f8aad897aed2c077faeb288`.

- `part-2.xml`: SHA-256 `de552b1dae3e63973ff7c7216368f96c8a408a8a1e5e59e86f34a4d95be0376b`.

- `part-3-collect.txt`: SHA-256 `f3f74315f4ed487c23a39ba97b62f87ff8709374e7692398eaaf42b65a4aa390`.

- `part-3-measure.txt`: SHA-256 `02786b76ac89ad991cd6c857d241a8e9c2714577ba03646308a12977d859b907`.

- `part-3.xml`: SHA-256 `1da21620ed888c620c0deb9f6278fc0b6e2b59d96faac6232536b177d6783767`.
