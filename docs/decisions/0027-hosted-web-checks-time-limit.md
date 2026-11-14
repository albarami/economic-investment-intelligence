# 0027 — The web checks may run 3,000 seconds on the hosted runner

| | |
|---|---|
| Status | Accepted, 2026-11-14 |
| Date | 2026-11-14 |
| Owner | albarami |
| Decided by | The owner, in his note of 2026-11-14 on the time limit of the web checks (task S1-T16) |
| Amends | Nothing. It is the decision record that TST-03 of document 12 requires before a tolerance of a check is widened. |
| Purpose | Record that the time limit of the suite `web-checks` in the whole test command is 3,000 seconds on GitHub's hosted runner and 1,800 seconds everywhere else, for how long, and that nothing else of the checks changes. |
| Read first | [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md) TST-03, [TASKS.md](../../TASKS.md) tasks S1-T15 and S1-T16 |

## Context

The whole test command (`./eii test`) gives each suite a time limit, a guard against a run that hangs. The suite `web-checks` has 1,800 seconds. On GitHub's hosted runners the same passing tests of one commit took about 1,030 to 1,040 seconds on some runners, 1,330 to 1,380 on others, close to 1,800 on a third group, and more than 1,800 on a fourth, where the run then failed on the limit with every test green (the lead's reading of the hosted logs on 2026-11-14). Several hosted runs ended that way, on pull requests that change no browser code, and twice on the main branch itself. Task S1-T15 is making the browser tests faster without removing or weakening any of them; until that holds on the slow runners, a failure says something about the runner and nothing about the code.

## Decision

The owner's words: "I allow the web-checks time limit of the whole test command to be raised to 3,000 seconds on GitHub's hosted runner only (task S1-T16). The local limit stays 1,800 seconds. No test, assertion, bound or suite changes. When S1-T15 makes the suite fast enough on slow runners, the hosted limit goes back to 1,800 seconds."

1. The limit of the suite `web-checks` is 3,000 seconds when the whole test command runs on a GitHub-hosted runner, which the command recognises by the two facts of its environment that the sandbox proof already uses (`GITHUB_ACTIONS` is `true` and `RUNNER_ENVIRONMENT` is `github-hosted`), held in one shared definition.
2. Everywhere else the limit stays 1,800 seconds.
3. No test, assertion, bound, planted case or suite changes; no other suite's limit changes; nothing is skipped, retried or moved out of the command; the workflow file is not changed.
4. The hosted value is a stopgap. When task S1-T15 has made the suite fast enough on slow hosted runners, the hosted value is removed and the limit is 1,800 seconds everywhere again (open item OI-158).

## Evidence

The tests of task S1-T16 in `scripts/tests/`, which plant each environment case, and the run recorded for the task in [PROGRESS.md](../../PROGRESS.md).

## Consequences

- TST-03 forbids widening a tolerance without an approved decision record; this record is that approval for this one limit and for nothing else.
- A run that hangs on a hosted runner is found after 3,000 seconds instead of 1,800; the tests job's own limit of 90 minutes still holds it.

## Amended passages

None. The limit is a constant of `scripts/run_tests.py`; no requirement of the pack states it.

## What would change this decision

Task S1-T15 meeting its criteria on hosted runners (the hosted value is then removed), or a new owner note.

## Open questions and assumptions

None.

## Sources

The owner's note of 2026-11-14; tasks S1-T15 and S1-T16.
