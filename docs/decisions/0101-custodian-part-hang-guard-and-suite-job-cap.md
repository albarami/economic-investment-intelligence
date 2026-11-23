# Decision 0101: Custodian parts have a longer hang guard, and the hosted suite job a longer cap

| | |
|---|---|
| Status | Accepted, 2026-11-23; the owner's standing decision relayed through his delegated advisor, applied by lead ruling L-1559 |
| Date | 2026-11-23 |
| Owner | The owner |
| Decided by | The owner's words of 2026-11-21 23:11 and 2026-11-23 08:22, the advisor's delegated decision of 2026-11-23 08:22, and lead ruling L-1559 |
| Amends | [Decision 0086](0086-custodian-part-limit-and-watch.md) items 2 and 3; [decision 0097](0097-custodian-shard-headroom.md) item 2; [decision 0027](0027-hosted-web-checks-time-limit.md) item 4's one-value-everywhere wording as applied to the custodian parts; document 12 section 2.1; the hosted workflow's job `suite` cap |
| Purpose | Stop a slow hosted or loaded runner from voiding a whole test run, while a hung custodian part is still stopped. |
| Read first | AGENTS.md rules 12, 33, 36, 37 and 46; decisions 0027, 0086 and 0097; document 12 section 2.1 |

## Context

The owner's words, quoted exactly from the relayed note of 2026-11-23 08:22: “i say tihs again those ime limtis we chose if it is affecting my develpmented enhance them.” His earlier words of 2026-11-21 23:11 are quoted in decision 0086. The advisor read the evidence and decided to change the limits, not defend them.

That evidence, read by the advisor: a hosted custodian part reached its 1,200-second limit on the train of pull request 127 (1,200.1 seconds). Two local whole runs failed the same way under machine load. A passing local run used 77 percent of the limit. Decision 0027 records hosted times of 1,030 to 1,380 seconds for one unchanged test set, so the hosted runner varies widely. A green hosted run of an earlier train used 74 of the 90 minutes of the job `suite`.

## Decision

1. **Hosted runner.** On a GitHub-hosted runner, each custodian part `python-custodian-1` to `python-custodian-5` has a 2,400-second limit. The runner recognises one by the two variables of decision 0027 item 1, through the shared `ci_environment.is_hosted_runner`: `GITHUB_ACTIONS` is `true` and `RUNNER_ENVIRONMENT` is `github-hosted`.
2. **Everywhere else.** Each custodian part has an 1,800-second limit. A hung part is still stopped within 30 minutes on the build machine.
3. **Other suites unchanged.** `python-core`, `python-product` and `web-unit` stay at 600 seconds, `python-guards` at 3,600 seconds, and `web-checks` at 1,800 seconds. Each of them has one value on every runner.
4. **Hosted job cap.** In `.github/workflows/ci.yml` the cap of the job `suite` rises from 90 to 150 minutes, so that the job cap does not become the next wall. The pins that check the workflow move with it: the declared job value, the pinned workflow hash and the planted cases. The six required check names, the matrix and every other job are unchanged.
5. **Printed share.** The runner prints each suite's elapsed time as a share of the limit that applied on that runner. Before this record it printed the share of the table value.
6. **Watch.** A custodian part whose **green hosted** time passes 1,680 seconds (70 percent of 2,400) is split by a further decision record using decision 0060's method; it is not raised again. Local times taken under machine load are not the trigger. The watch is a review trigger, not a second kill threshold.
7. **Rules 12 and 36.** A longer hang guard is not a skip, a retry or a weakened check:
   - every test, assertion, bound, planted case and suite still runs, once;
   - a part over its limit still fails with `FAIL timeout`, and its process group is still killed;
   - the dedicated kill test keeps its own small limit.

   The five-part split of decision 0097 stays, because it is a speed gain on its own.

## Tests

- **The limit test.** The runner's table test pins 1,800 seconds for each custodian part. A hosted-runner test checks six environment rows. Only both hosted variables, with their exact values, select 2,400 seconds; every other row gives 1,800.
- **The launch test.** A real custodian part launches with the limit of its runner, and its `FAIL timeout` line and printed share name that limit.
- **The planted case.** One fixture suite runs past its table limit but within its hosted limit. It passes on a hosted runner and fails with `FAIL timeout` everywhere else.
- **Red without the change.** With the hosted branch of `suite_timeout` disabled, these tests fail.

## What would change this decision

A green hosted custodian part above 1,680 seconds calls for a split record. Any other limit change needs a further decision record.

## Sources

- The owner's relayed words, 2026-11-23 08:22, and the advisor's delegated decision of the same time.
- [Decision 0086](0086-custodian-part-limit-and-watch.md) and [decision 0097](0097-custodian-shard-headroom.md).
- [Decision 0027](0027-hosted-web-checks-time-limit.md), items 1 and 4.
- [Document 12](../12_TESTING_AND_QUALITY.md), section 2.1.
- [PROGRESS.md](../../PROGRESS.md), **S2-P69 — custodian hang guard and suite job cap**.
