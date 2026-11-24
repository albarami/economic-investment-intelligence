# Decision 0109: The product suite runs in two named parts under the unchanged limit

| | |
|---|---|
| Status | Accepted, 2026-11-24. The lead corrected the measured premise (ruling L-1784): the slow figures were measured on the slice S6 stack, not on main; see Context |
| Date | 2026-11-24 |
| Owner | The owner |
| Decided by | As briefed: the owner's standing approval of changes that raise speed without losing quality (his note of 2026-11-22, item 91) and the lead's ruling L-1777 item 2a, under AGENTS.md rule 46 |
| Amends | The suite table of `scripts/run_tests.py` (ten suites become eleven); the suite matrix of `.github/workflows/ci.yml` and its pinned hash; README.md's sentence on the suites; document 12 section 2.1 |
| Purpose | Keep every product test running once under its unchanged 600-second suite limit when several whole tests share the machine. |
| Read first | AGENTS.md rules 12, 33, 36, 37, 38 and 46; [decision 0060](0060-the-custodian-suite-runs-in-two-named-parts.md); [decision 0086](0086-custodian-part-limit-and-watch.md) |

## Context

The custodian suite met the same problem and was split into named parts by decision 0060, then decision 0086.

On main at `015647659a17c55407754eaeb72b0b90e9c855cc`, `product/tests` holds 816 tests and runs in about 11 to 14
seconds (the builder's runs; PROGRESS.md row "2026-11-23, Lead whole test on the train head", 13.5 seconds). The
slice S6 tasks add their card, route and contract tests to the same suite: on the S6 stacks of 2026-11-24 the suite
holds 3706 tests, ran alone in 460 and 490 seconds (77 to 82 percent of its 600-second limit), ran 510.5 seconds
(85.1 percent) in a whole test beside others, and passed 600 seconds twice when three whole tests shared the
machine; every timeout costs a whole rerun. The lead's brief first gave those figures as main's; the builder measured
main, found 13.5 seconds, and withheld the word Accepted until the lead named the suite (open item PO-S2-P93-01,
answered by ruling L-1784).

The split lands now, with slice S2, because the suite table, the hosted matrix and the part plugin are shared
infrastructure that every later slice is re-cut onto, and because on main it costs only one more hosted matrix entry
running in parallel with the others.

## Decision

1. **Two named parts.** The suite `python-product` is replaced by `python-product-1` and `python-product-2`, in its
   place in the table. Each runs `pytest` over `product/tests` with the same 600-second limit on every runner. No
   other suite and no limit changes.
2. **A stable split by module.** A test belongs to a part by its module's repository-relative POSIX path: SHA-256 of
   the path, modulo 2, plus 1 (decision 0060 item 2's method). Items outside the part are deselected through pytest's
   own hook, never skipped. A new test module lands in a part with no list to update. Without the part option,
   `pytest product/tests` runs everything.
3. **One plugin.** `scripts/pytest_custodian_part.py` serves both suites from one table of part counts (custodian 5,
   product 2) and one option per suite, `--custodian-part` and `--product-part`. The custodian parts, their test ids
   and their guard are unchanged. Giving both options at once is a usage error.
4. **The manifest guard.** `scripts/tests/test_product_parts.py` proves on every run of `python-guards` that the two
   parts are disjoint, that their union equals the whole collection by test id and by count, that neither is empty,
   that no module is split between them and that every product test file is collected, each clause with a planted
   violation. It uses the custodian guard's own assertions, given the suite name and the part count.
5. **What does not change.** Every suite's limit, the custodian parts and their hosted limit (decision 0101), the six
   required hosted check names, and every test and assertion. No test is deselected from the whole run.

## Consequences

- `./eii test` prints eleven suite lines. The hosted job `suite` runs one more matrix entry; the required check
  `tests` still needs every entry to succeed, and the pinned hash of `ci.yml` moves with the matrix.
- The parts are uneven by count (247 and 569 at the base) because whole modules stay together; one module holds 433
  cases. The split is by path, not by duration, as decision 0097 item 1 requires of the custodian parts.
- On main the split gains no time and costs one more hosted runner start, in parallel. On the S6 stacks each part
  stays well inside the 600-second limit under shared load.

## Open questions and assumptions

PO-S2-P93-01 in [OPEN_ITEMS.md](../../OPEN_ITEMS.md) is answered: the 460 and 490 seconds were measured on the slice
S6 stack (ruling L-1784).

## Sources

- The task brief of S2-P93 and the lead's rulings L-1777 item 2a and L-1784 (the lead's project records), with the S6 whole-test outputs they cite.
- The builder's runs recorded in [PROGRESS.md](../../PROGRESS.md) under **S2-P93 — the product suite in two named parts**.
- [PROGRESS.md](../../PROGRESS.md), the row "2026-11-23, Lead whole test on the train head".
- [Decision 0060](0060-the-custodian-suite-runs-in-two-named-parts.md) item 2, [decision 0086](0086-custodian-part-limit-and-watch.md), [decision 0097](0097-custodian-shard-headroom.md) item 1 and [decision 0101](0101-custodian-part-hang-guard-and-suite-job-cap.md) item 3.
