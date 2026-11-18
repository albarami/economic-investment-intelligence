# 18 — Mutation Testing Handoff

| | |
|---|---|
| Status | Draft handoff; historical measurements, incomplete work and recorded repairs distinguished |
| Date | 2026-11-18 |
| Owner | The project owner |
| Purpose | Explain the mutation work and preserve enough evidence for a new team to decide and complete the work after go live. |
| Read first | [Testing and Quality](12_TESTING_AND_QUALITY.md), [Task ledger](../TASKS.md), [Open items](../OPEN_ITEMS.md), [decision on background campaigns](decisions/0052-mutation-campaigns-run-in-a-background-lane.md) |

## Overview

Mutation testing asks whether tests notice deliberately wrong code. This work strengthened tests, exposed real defects and left substantial unfinished investigation. A surviving change is a question to investigate, rather than proof that the unchanged application is wrong.

The owner stopped mutation campaigns because their elapsed time was delaying the work. The present application uses invented labour and residence records; the owner wants a full team to consider this additional work after go live, particularly before a future move to real records. No campaign or new survivor investigation is to start before then. The team chooses how to carry out the work.

[Decision on background campaigns](decisions/0052-mutation-campaigns-run-in-a-background-lane.md) previously allowed ordinary development to proceed while mutation work continued, but required every campaign to close before its slice could finish. [Decision 0055](decisions/0055-mutation-testing-moves-to-after-go-live.md) records the owner’s deferral of mutation campaigns and survivor investigations until after go live, without a pre-launch wait for closure; approval of the written record is pending. Ordinary unit, property, integration and parity tests, independent review, provenance accounting, privacy checks, numerical checks and the complete test suite with fresh seeds remain required. A confirmed wrong number or wrong refusal remains recorded work; postponement does not erase it.

This document is an evidence snapshot. Its status tables preserve repeated runs and unsuccessful starts. A last recorded measurement is not proof that the eventual merged version has been measured. Recorded repairs remain historical claims until their source and tests are checked on the delivered version.

## 1. How to read the evidence

Start with the method and the test-quality rules, then find a task and source file in the campaign table. The original run records are not kept in the repository; this document holds every figure taken from them. A record identifier such as R001 names one original record, and its fingerprint lets anyone who later holds that record check that it has the same bytes. A record fingerprint is not the fingerprint of the source file under test; retain both when completing future work.

The meanings of the outcome columns are:

- **Considered:** changes generated for a complete campaign, or enumerated in a partial record. An unsuccessful start with no result says unknown; it is not evidence that no changes were possible.
- **Killed:** a test noticed the change. The original code must pass that test, and the failure must concern the intended behavior.
- **Survived:** tests returned without noticing the change.
- **Explained:** the file and complete change text match an entry in the available written equivalence record. A historical statement that everything was explained does not establish such a match.
- **Open:** a recorded change has no exact matching explanation in this snapshot. A later repair may already address it; reconcile versions before writing another test.
- **Not compared:** original and changed text are absent. Even an earlier claim of equivalence remains unverified here.
- **Timed out:** the changed test run did not finish within its fixed allowance. This is an inconclusive result, counted separately from a kill or survival.
- **Not covered:** the recorded change did not have an executing test. **Not run / incomplete** means there was no completed outcome. Neither establishes coverage.

Some older records include changes that survived and changes not covered in the same undifferentiated list. Their explained and open columns say **combined**. The separate outcome counts remain as recorded; there is no invented allocation between them. Counts are occurrences within records, including repeats. Shared files appear under more than one task, so totals must not be read as a count of distinct defects.

“Latest measured” marks the last recorded measurement for that task and file. “On latest identified task head” additionally requires a recorded commit identity matching the latest identified task version. Unknown identities remain unproved. These marks describe the measurement history; they do not certify a later merged version. Earlier rows remain visible as superseded measurements. Where a row names a group rather than individual files, the original summary did not provide the split.

Sources: the R-numbered records in section 9 and the written equivalence records at the commits named in each status row. Explained requires an exact match of both file and complete change text at the measured commit, latest identified task commit or recorded base commit; unresolved revisions remain unknown. Missing values remain unknown. Proposed investigations in the detailed tables are explicitly hypotheses, not confirmed defects or claims about tests added later.

## 2. A worked example

In `web/spikes/performance/main.ts`, the original condition is:

```text
if (environmentGate(spike.profile, plant)) {
```

The inserted change was:

```text
if (true) {
```

The changed condition applies a deliberately inserted page failure even when the smoke profile should ignore it. The test named `the smoke profile skips the empty-canvas gate`, in `web/spikes/performance/tests/mutation-page.node-test.mjs`, checks the page's actual failure field. With the change, that field contained `capped-frame-rate`; with the original condition, it was empty. The recorded changed-code test exited 1 and the restored-code test exited 0. This is a useful kill because it checks visible behavior rather than the spelling of the condition. The word in the quoted test title refers to the page's own condition.

A survivor can also preserve behavior. In `custodian/src/eii_custodian/assignment_spike/delay.py`, `situation_mean` originally returns:

```text
return sum(minutes, Fraction(0)) / len(minutes)
```

The surviving change is:

```text
return sum(minutes, ) / len(minutes)
```

The written reason says that removing the explicit rational zero leaves the same rational sum for nonempty typed inputs; empty inputs are refused before a result is returned. That is an equivalence argument about the admitted inputs and the preceding refusal, not an inference from examples passing. If that input contract or refusal changes, the reason must be checked again.

Sources: R008 for the performance example and R005 for the `situation_mean` change, with its written reason at `a5219f5`. The status appendix separately preserves the broader performance campaign; the focused example does not close the whole file's campaign.

## 3. Method and rules to retain

A campaign starts from a fixed source version and a passing unmodified test suite. Make a small deliberate change, run the relevant tests, record the result, then restore the source. Repeat over the complete intended set of changes. Keep the original and changed text, function, outcome, source fingerprint, test identity and source version together. A failed start before any change runs is a test-environment problem to investigate, not a mutation result.

A behavior-changing alteration that no test notices exposes a hole in the evidence established by the tests. Close it with a test that distinguishes the altered behavior from a valid control. If the change cannot alter behavior for any admitted input, write down why. Trace every reachable branch and every caller restriction on which that reason relies. Passing selected examples is insufficient proof of equivalence. An explanation belongs to the exact file and change text; moving text or changing a caller can invalidate it.

For a new test, prove both sides: it fails on the exact deliberate change and passes on the restored original. Check exact results and side effects. Restore the source before continuing. Preserve existing assertions, privacy rules, numerical tolerances and refusal behavior. If the investigation exposes a defect in the original source, distinguish that defect from the artificial alteration and give its repair an explicit record. Do not relabel it as equivalence.

A campaign closes only on the version that merges. If production code, test behavior or a relied-on contract changes, repeat the affected campaign on the final version. An earlier successful run remains historical evidence and does not close a different source fingerprint. A shared file changed by several tasks needs a campaign on the version containing their combined changes.

The earlier rule for stopping a superseded run required all of the following: the replacing change had passed an execution check in the environment where it would run and was approved; the affected module was measured again immediately on that replacement; and readable per-module counts and the killed, survived and timed-out identities were preserved before stopping. All other work was allowed to finish, except for a safety or quality failure or a hung run with no output. An earlier stop that did not meet those conditions does not establish closure. The owner's later postponement explicitly authorised the remaining stops after partial records were saved; it did not transform those partial results into completed campaigns.

Stop a changed test run that exceeds a fixed time allowance and record it as timed out. Keep the exact alteration and repeat it alone at normal load before interpreting the outcome. Preserve the allowance, the intended change set and test selection; changing them to obtain a better result destroys comparability. Record any resource exhaustion separately from behavior detected by a test. Bound process growth and terminate the whole affected process family when containment fails; an infrastructure termination is not a kill or survival.

The records explain different causes of nontermination here. Some registry tests created child processes after a parent had started native background threads. A child could inherit a lock held by a thread that no longer existed in that child and wait indefinitely. An allowance based only on processor time did not end a sleeping wait. Separately, emptying a response function left pending requests waiting for a response that never ended. Some repeats were run during competing work, which makes their timing inconclusive. Repeating a timeout alone distinguishes contention from a persistent hang; a successful repeat alone does not explain a previously random failure.

Keep the work register current: campaign, task, module, tested version and fingerprint, completed changes against the intended set, elapsed time, outcomes, open investigations and the person responsible for each next action. Keep completed and superseded rows. Before postponement, an unfinished campaign could proceed beside development, but could not delay ordinary development when competing for resources. The later owner decision suspends that activity until after go live. Independent confirmation of survivor dispositions remains part of finishing the deferred work.

Sources: [background-campaign decision](decisions/0052-mutation-campaigns-run-in-a-background-lane.md), the later owner decision identified in the opening section, and the retained rules on stopping superseded work, preserving partial evidence, isolating timeout repeats and bounding process growth. These conditions are stated here in full.

## 4. Defects and test defects found

These are recorded findings and repairs. Their presence on the eventual merged source must be checked before the deferred work resumes. The campaign tables are measurement history, not evidence that each repair has already received a complete campaign on its final version.

### Quarterly workbook continuity

`workbook` in `custodian/src/eii_custodian/publicdata/fetch/page_shapes.py` accepted `2031-Q1` followed by `2032-Q1`. When encountering a first quarter after an earlier observation, it checked the incremented year but did not require the preceding observation to be the final quarter of that year. Missing intervening quarters could therefore be accepted as a continuous sequence.

The recorded repair `de70c0c` requires the first quarter to follow the previous year's final quarter, with deliberately broken examples to distinguish the bad sequence from a valid year transition. The later partial campaign measures the repaired source family, but is incomplete and cannot close it. R112 records the defect and repair; R043 preserves the unfinished follow-up measurement.

### Tests using the machine's trust store

Tests in the page-acquisition and pinned-record families created certificate contexts while the machine's normal certificate roots were visible. An invented certificate fixture did not establish isolation: an unrelated trusted certificate from the host could change what was accepted. This was a test-validity defect, even when the expected test happened to pass.

The recorded repairs isolate both `SSL_CERT_FILE` and `SSL_CERT_DIR` within the test fixture, supply only the invented root or an empty root set, and inspect the actual accepted root certificates. They restore the environment after the test. Related tests had also replaced a real pin loader with a stub, bypassing the refusal path they purported to check. Those were changed to use the real loader, allowing a forwarding observation that still calls it. Recorded repairs are `4ab2842`, `fde84ac` and `0474927`; subsequent explicit text-encoding repairs are `56687a0` and `fbca009`.

### Investment archive and evidence integrity

R112 records defects in `custodian/src/eii_custodian/publicdata/investment_build.py` and `custodian/src/eii_custodian/publicdata/investment_evidence.py`: an archive audit accepted manifest bytes without comparing their digest with the selected pointer; it accepted an empty page list; milestone status could be trusted without the required independent archived evidence; repeated fetch attempts could overwrite each other; and caller rows could be read again after comparison rather than retained as validated copies.

The recorded repair `b198113` checks the manifest digest before parsing, refuses an empty page list, derives milestone independence from the archived candidate, refuses a duplicate attempt before writing, and copies caller rows before comparison. Deliberately broken cases distinguished these behaviors. The archive-audit helper was reported to have no production caller at discovery; that limits demonstrated reach, but does not make its wrong acceptance equivalent behavior.

### Missing fetch-host lineage

`verify_child` in `custodian/src/eii_custodian/publicdata/comtrade/assemble.py` could accept an unknown response class with an empty fetch host because the missing expected-host template also defaulted to empty. Correctly hashed input bodies did not restore the missing provenance. The record assigned repair `999c176`; verify that repair and its negative test in the merged source. Measurements from before that repair do not certify the repaired branch.

### Unsupported archive members

`parse_archive` in `custodian/src/eii_custodian/publicdata/baci/parse.py` accepted a directly constructed configuration containing an extra, unconfirmed member, and separately an unknown member kind that was hashed but never parsed. The recorded repairs are `9e79881` for the extra-member case and `da272a7` for unsupported member kinds, with refusal before output publication. A test of only the configuration constructor would miss a directly constructed configuration reaching the parser.

### Reachable tests and honest equivalence reasons

The evidence also records constant-derived expectations, assertions of truthiness when exact values were known, text reads depending on the current folder or encoding, tests inspecting a source copy other than the changed copy, and reasons that omitted a reachable symbolic-link branch. These are addressed by the following rules. They must be applied to retained tests as well as new ones.

Sources: R112, R040–R053 and R109–R111. These records establish what was reported and repaired; they do not establish that the whole later source version was mutation-complete.

## 5. Test-quality rules

The following before/after examples are modelled on this repository's certificate, fetch, archive and calculation tests. They explain what a person should verify; they do not prescribe an implementation. The original recorded checklist defines these classes.

### C1 — Keep the real security boundary

Do not replace a loader, opener or certificate-context constructor with a stub that skips its refusals. A forwarding observation is acceptable only if it calls the original boundary and preserves its behavior.

**Before:** a page-record test replaces `load_pin` with a function returning a ready-made pin, then declares the pin admission path covered. **After:** create an invented pin file, let the real loader read it, observe the forwarded call if needed, and check both acceptance and the precise refusal when the pin is wrong. This is modelled on the recorded correction to `custodian/tests/test_page_records_survivors_2.py`.

### C2 — Isolate certificate trust

A test that creates a default certificate context must hide both host trust sources. Scope an invented root file or empty file and an empty certificate directory to the fixture. Check the context's actual certificate set, not just its configuration, and restore the environment afterwards.

**Before:** make a default context and assume the temporary certificate is its only root. **After:** isolate `SSL_CERT_FILE` and `SSL_CERT_DIR`, make the context through the real boundary, and assert that only the invented root is present. This is modelled on the page-acquisition and page-record corrections described above. A context silently accepting the host roots must fail the test.

### C3 — Use an independent expected value

Do not import the production constant as its own expected answer. Write the value required by the contract, derived independently of the code under test.

**Before:** compare the returned refusal reason with the same constant used to return it. **After:** compare it with the literal `lineage_missing`, including the field where the reason belongs. Literal diagnostic checks in `core/tests/test_public_series_mutation.py` show the same principle; the example here uses a provenance refusal. If the source and test both use a changed constant, the test has not checked the contract.

### C4 — Check exact values when known

An assertion of non-emptiness establishes only that something happened. It does not establish correct attempts, order, delays, counts or totals.

**Before:** `assert calls and sleeps`. **After:** check the exact request sequence, exact refusal reason and `assert sleeps == [1.0, 2.0, 4.0]` for the retry fixture in the retained example. `custodian/tests/test_tenders.py` is the related repository test family. Include a successful control so that refusing every request cannot satisfy the negative assertions.

### C5 — Make text reads independent of machine defaults

Specify text encoding and derive repository-relative input locations from the test file or the established repository-root reference. Do not rely on the current folder, ambient encoding or a folder belonging to another checkout.

**Before:** `read_text()` on a relative source filename. **After:** use the same intended file resolved from the test's location with `read_text(encoding="utf-8")`, and prove the fixture exists. This is modelled on the awards and page-acquisition test corrections. A missing source must fail explicitly rather than produce an empty scan that passes.

### C6 — Prove that the changed source is exercised

A fresh process can import installed or original code instead of the changed copy. A source-text check can silently inspect an empty folder. Neither measures the intended alteration.

**Before:** start a fresh process, see a passing test and assume it used the altered module. **After:** assert that the imported module's `__file__` belongs to the intended changed copy, supply all files needed by the check, and demonstrate that the exact alteration makes the assertion about behavior fail. R112 records correcting this source-selection problem in the page-record tests. Source-structure checks still belong in the ordinary suite; an incompatibility while preparing changed code is not a behavioral kill.

### C7 — Explain every reachable branch

An equivalence reason must cover every reachable caller and branch, including restrictions imposed by another module. State those restrictions and invalidate the explanation when they change.

**Before:** explain a file-opening change by saying that all file paths are refused, while ignoring the path for an in-folder symbolic link. **After:** trace that path and the ordinary path through their real callers, distinguish the refusal from successful admission, and write a reason that accounts for both. If a branch changes an observable result, add a distinguishing test instead of an explanation. This is modelled on the correction to a page-record explanation that had omitted the symbolic-link branch.

## 6. Open items and the order of remaining work

R112 uses open-item identifiers also used for different issues in the repository. Their meanings are distinguished below.

- The **run-local OI-16** is an unexplained operating-system failure in the unmodified tests of the pinned-page campaign. Temporary storage exhaustion during overlapping work was a proposed cause, but the actual error number was not captured. It remains open. A later successful run does not explain or close it. Record the error number, storage state and overlap on a reproducible failing case before deciding the cause.
- The **run-local OI-17** is loss of exact timeout identities when temporary changed source was removed. Some complete campaign records contain timeout counts without the alterations needed to repeat them. Preserve the exact text and stable identity of every timed-out change in future records, and recover missing changes before claiming that the old repeats were completed.
- The repository's [OI-16 — Activity-mapping sign-off](../OPEN_ITEMS.md#oi-16--activity-mapping-sign-off) concerns who may approve activity mappings and whether batch approval is permitted. It is a separate unresolved decision. Until decided, no new mapping is admitted merely because its tests pass.
- The repository's [OI-17 — Gateway measurement panel](../OPEN_ITEMS.md#oi-17--gateway-measurement-panel) concerns whether internal measurement scores are shown to visitors. Keep the current absence of a panel until that presentation decision is made. Internal scores must not be mistaken for product evidence or calibrated confidence.
- A hostile in-process key object with stateful equality, or a sequence object that compares equal to empty, could bypass assumptions in `build_project_evidence`. The production callers recorded in R112 passed ordinary parsed strings and sequences, so that record treated this as a hardening question rather than a demonstrated external-input defect. Recheck the callers in the eventual source and decide whether to enforce plain values at the boundary. Earlier proposed equivalence reasons must not omit such reachable inputs.
- The status rows identify exactly which explanation revisions resolve and which remain unknown. Reconcile unknown source versions and final task changes before treating a historical survivor as new work. [Decision 0055](decisions/0055-mutation-testing-moves-to-after-go-live.md) defers mutation work until after go live while preserving ordinary checks; the owner accepted its written record on 2026-11-18. Empty investigation returns and missing per-change evidence must remain explicit gaps.

After go live, and only if the team accepts the deferred work, take it in this order:

1. Establish the source version actually merged. Inventory all affected numerical, refusal and provenance code, including shared files and browser-facing modules not yet measured. Recover final tests, written reasons, full commit identities and file fingerprints. Read the decision amendment and reconcile any task-status changes made with it.
2. Verify the recorded production repairs above in that source and preserve a failing reproducer and passing repair test for each. Resolve any confirmed wrong result or wrong refusal that remains; keep these separate from missing-test investigations.
3. Repair the test environment and test validity first. Apply C1 through C7 to existing tests, resolve the unexplained operating-system failure, isolate certificate trust, prove source selection, and prevent inherited-lock hangs. Preserve unsuccessful evidence while doing so.
4. Recover the exact alterations for the incomplete page-source and registry campaigns and for unidentified timeouts. Use the partial-function register below as an index to missing changes, not as a substitute for their text. The last page-source run did not finish all enumerated changes. The archive module with no generated changes needs explicit behavior tests and a coverage assessment; an empty result cannot qualify it.
5. Reconcile shared public-build work across its tasks. A measurement of an earlier build file does not cover later task additions. Establish complete measurement coverage of the combined source before declaring that family finished. Review unmeasured browser-facing source as part of the inventory rather than assuming the earlier page experiment covered it.
6. Work through unmatched changes from the latest measurements below. Investigate actual output, refusal and provenance effects first. Prove each distinguishing test on the precise alteration, or write a complete equivalence reason. Historical proposals can guide investigation, but become accepted explanations only after exact matching and checking their contracts on the current version.
7. Repeat timed-out changes individually at normal load, keeping their identity, allowance, outcome and cause. Resolve changes not covered and changes not run. Then complete each affected module's campaign on the final version containing all accepted changes.
8. Preserve the resulting evidence and accepted dispositions together with that final source version. Compare the recorded identities with the merged identities. Any intervening code or relevant test change reopens the affected measurement.

Sources: [repository open items](../OPEN_ITEMS.md), R112 for the distinct run-local issues and caller-boundary investigation, and R043 and R108 for the partial results. The order above is a proposed work sequence; it makes no duration estimate.

## 7. When a module counts as finished

A module is finished only when all the following can be checked from its retained record:

- The intended scope is explicit, including functions the campaign could not alter. A lack of generated changes is a coverage limitation, not a successful measurement.
- The original tests pass in the intended isolated environment and execute the exact source under examination. Failed starts and random failures are explained rather than removed from history.
- The full intended campaign completes on the merged source version, with its full commit identity, source fingerprint, relevant test identities and environmental conditions retained. A different source or relied-on contract requires a new measurement.
- Every change has an outcome. There are no unaccounted changes, unresolved lack-of-coverage cases, unfinished changes or unidentified timeouts. A persistent timeout has an individually repeated, documented disposition and cause; it contributes no behavioral kill.
- Each surviving change has either a distinguishing test proved against the exact change, or an individually checkable equivalence reason matched to its full text and input contracts. Unknown or merely proposed reasons do not satisfy this requirement.
- Tests retain valid controls, exact expectations, the real security boundary, isolated trust and independence from the host environment. Existing assertions and privacy and numerical controls remain intact.
- Confirmed production defects have separately verified repairs. A test that merely reproduces a wrong result is not a repair.
- A second person has confirmed the dispositions, their evidence and the final source identities. Superseded records remain available and clearly marked.

These are completion criteria for deferred mutation work. They do not reinstate a pre-launch wait that the owner removed.

## 8. Measurement limits and risks

The elapsed cost table below is a measured subtotal of the records in section 9, not the complete cost of the project or an estimate for the remaining work. Parallel campaign durations overlap. Summing elapsed campaign hours measures accumulated run durations, not elapsed calendar time. Allocated core-hours multiply a reserved processor count by elapsed hours; they do not measure actual processor use. Missing processor counts or durations stay unknown, and recorded rounded zero durations do not establish that a campaign cost nothing. Test-writing costs are listed separately to avoid charging a campaign again for each module or mixing investigation time into execution time.

Both final partial records have a written timestamp inconsistent with the campaign history. No elapsed duration is inferred from that timestamp. R041 retains only the opening header of the superseded page-source run, without per-module outcomes. These are evidence gaps, not completed work.

Snapshot mismatch is the main interpretation risk. A successful historical result may have been followed by source changes; a historical unmatched change may already have a new test or written reason at a later commit. Neither direction can be resolved by optimistic labelling. Short recorded commits are preserved as short identities, without invented missing digits.

The archive module's only function is a decorated generator. The recorded campaign could not alter that function. Its empty outcome therefore describes a limitation of the approach used, and must be supplemented by explicit behavior tests and a fresh coverage assessment. Other source groups have only combined counts in the older summaries, so their per-file outcomes remain unknown.

A high count of kills does not prove correct calculations, adequate privacy protection or complete security coverage. Equivalent changes can inflate survivor counts, weak tests can inflate apparent kills, and unmodified-suite failures can prevent any measurement. Certificate trust, source-copy selection and caller restrictions all affect whether a test provides the evidence it claims. Applying C1 through C7 matters as much as adding assertions.

The preserved counts are not a project-wide defect count or a project-wide percentage. They mix repeated measurements and shared files, and some older summaries lack per-file details. No unique unresolved-defect total can be derived honestly from them. The detailed investigations below are proposed discriminating tests; they do not assert that every historical survivor is a current production defect.

Original-span, enclosing-function and timeout-identity gaps are labelled individually. String-wrapping changes retain their exact changed text.

## 9. Campaign status and retained evidence

The tables retain every campaign and module status row, including failed starts and superseded measurements. Each row names its record and commits; missing evidence stays unknown. Section 10 consolidates the work by file and separates earlier measurements from the latest work list.

<!-- GENERATED-EVIDENCE -->

### Evidence inventory

| Record | Input file | SHA-256 |
| --- | --- | --- |
| R001 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R002 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R003 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R004 | S1-T08.lead.mutation.txt | 76dbd00a307972e4af288d372d43adabe1a15a6bb9bd291b75e735e707bdbbf7 |
| R005 | S1-T09.lead.mutation.txt | fb7cf8cdc84e23f378820a107cccaa19cb4a8d432fb3038fe55300efdf4b8389 |
| R006 | S1-T11.lead.mutation-python.txt | cff9b9737866033ebffd6b47a2eb4397ad82d8f2ab16b5888cb140acce0de622 |
| R007 | S1-T18.mutation-web.txt | 1512e60d62d881e8343db12009b0730862177c5789f06f82d50e8d0eb42d52ee |
| R008 | S1-T18.mutation-replay.txt | 73c8480e4bbfc61b74736658c866c10d9b329c5a448ededd7c381439c26d27e6 |
| R009 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R010 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R011 | S2-T03.mutation.txt | 16512a8846e25fccc8ee53621ec7b29e8d46f4013d8f0c74e8138e4fbb4b06db |
| R012 | S2-T03.mutation-core.txt | f47a9a8caf2e6693c24a959e8814e8e8cb5f6a7007151144860dc0e2ff6157fc |
| R013 | S2-T03.mutation-core.final.txt | cdd09524837fd1dc939a3cc2bd4dd5477032e965e85b20ebc53649f284fad664 |
| R014 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R015 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R016 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R017 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R018 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R019 | S2-T08A.camp3 | 28873e1448f02eee34ce1f5602d7bbf0916259f642a3a23c020bb9f671b58193 |
| R020 | S2-T08A.camp4.txt | 87f1732f2439c07489e4d4587d1c4bf53fa8f86f3c6738f68bd1330b46029ca0 |
| R021 | S2-T08A.camp5.txt | ba71d7a34dba28ea44aace04746a24328989db35994d9cef52532837b31af146 |
| R022 | S2-T08A.camp6.txt | 661c7b29538a4627dafd654683763120ecbfa030c8d08c65cf5ac54531925106 |
| R023 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R024 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R025 | S2-T21.fix1d.campaign.txt | 79ebfd5db4a5c3fccca32db51ea2c088ddacf3854690a9ba2644b84140434ae5 |
| R026 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R027 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R028 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R029 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R030 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R031 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R032 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R033 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R034 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R035 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R036 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R037 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R038 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R039 | S2-T29.camp1.txt | 7d1b9f7d077df6e9d9b910d8a08755b0693b5aa61a2d1bb60238d0d323f2732e |
| R040 | S2-T29.camp2.txt | 6dee56bc7e9165e9c6f2f4567d3823337ba8b61fa2c6374762c8e01193e870b0 |
| R041 | S2-T29.k3.camp.run1-baseline-fail.txt | b0e10d0bb422a45c17028dfd8e7b8eedb971f347b1f40bbe86637ce99df71c8f |
| R042 | S2-T29.k3.camp.txt | 53e002adc826b6fcb59a705f0051919d2296501aba9d8178775d2faa9efe0c37 |
| R043 | S2-T29.camp3.txt | eca9fb7804a8979556c48a66c8e78217160bedb26634484a5a3c0352e01f4d60 |
| R044 | S2-T29.camp4.partial/RECORD.md | 730d23fb9b32bc555343d23bfaa51eb521f38651ccde12531a065eaa0b92e885 |
| R045 | S2-T30.camp1.txt | f8a762b05a330e3a09f2d29ce6300f9b60b29f19addd77ff8da1a5b83159c77a |
| R046 | S2-T30.k1c.camp.txt | 518d2e14110019e9a6402f7164c901a08334c74d81c21844476ffe334da59805 |
| R047 | S2-T30.k1a.camp.txt | 4dd5167b3dd1ac4585aa65c11a9559645abe098f7057b8d524266dc27bfc1b38 |
| R048 | S2-T30.k1c2.camp.txt | 181fa639e1fac368f456bfad0337c9962ae7f28f3582ec51afe9d9846760d344 |
| R049 | S2-T30.k1b.camp.txt | eb1234832b8c214d0de0632d260ff76c516758f4414acbb663de7284d881f403 |
| R050 | S2-T30.j1.camp.txt | 2263dabb4d2d6bcd63fe79575c70fcccbcc2154a525f263999917b2b6b1689b1 |
| R051 | S2-T30.j2.camp.txt | 29e53302ff2a466596448c9bfde483caa28039f80380f060d76e61b5fef2264d |
| R052 | S2-T30.k1d.camp.txt | db292d665a712537e094f1f0ecd9fccf797fbcbabcdb2de6e4181e091995e5f2 |
| R053 | S2-T30.st.camp.txt | 6e9fbc47e9bc82322764530829125d5c499c7b4da26de05532fdba4578d2a0cd |
| R054 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R055 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R056 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R057 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R058 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R059 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R060 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R061 | S3-T07mB.campaign.after.txt | 9625cd15648bc3e5c519e1177e16acd7a6bb9d69b87893227278269c3a777d50 |
| R062 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R063 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R064 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R065 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R066 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R067 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R068 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R069 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R070 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R071 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R072 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R073 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R074 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R075 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R076 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R077 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R078 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R079 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R080 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R081 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R082 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R083 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R084 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R085 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R086 | S4-T04.camp-confirm | 7c13b92d5350021838aca27de540acd751c3b13da0d84b652cdd3b7bc895cd26 |
| R087 | S4-T07.mutation.campaign5.txt | 8a9057317c38cac0c19c272ba52d93ce964ff7c06be37b1c8f857d03c2326511 |
| R088 | S4-T07.mutation.txt | a5e874894f502728555d18f727ecf802d343a3c21e1c4f9b7ca4543a17038391 |
| R089 | S4-T07.camp-replay | 43dd5679234f27bd1a26a14b2309d7cb38922675f10026468a5236c7d3033d6d |
| R090 | S4-T08.camp-verify | d07adc1131f1f0fa149463fc87d0527d9ed9a119fea49be02951644e722d8762 |
| R091 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R092 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R093 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R094 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R095 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R096 | S4-T14.lead.mut.ca38e73.out | b8f181053415ef4bca46b138b9624bde16d33ae36e1c17077782f456350decb5 |
| R097 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R098 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R099 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R100 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R101 | T1.camp1.A.txt | 2133869018140b1d7674c054e0bbbcc3ddccbfa505d29d6675b8a2afb7c03880 |
| R102 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R103 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R104 | T1.camp1.B.partial-record.md | c1dfe9d480c8798504697628fc991c051b63c33d81920e1459f1ec4080920dfb |
| R105 | T1.camp1.C.txt | 797683ecba6746de501c63e9a5bd89da94130f4162d42fcad6b5f0f8412fca20 |
| R106 | T1.campB2.baseline-fail.txt | 98272a0d5b34386895642c451f0026aef775924c7cd1668cba83cdcf615c530c |
| R107 | T1.campB2a.txt | e94ccd39a4fa363beddbc370406f2aa88ceefe07b3580d8cf7006327d6f921a2 |
| R108 | T1.campB3.partial/RECORD.md | 204f3fe053c86987a4fcd6ba35425ebf5b867be29beda0f0a18f1e3426781e4e |
| R109 | T1.camp1.D.txt | 9cd88191994fb37d76791e5371ccc023502daf405b2c1d61da4b7893020288a4 |
| R110 | T1.vcampD2.txt | 8e4d8f16a80e6894e2c9dcf21e5955f91abbfbb5104f54c2aa37bd3fa77627bd |
| R111 | T1.vcampD1.txt | d3c0bd91d81fce83108cea94b67a5c46d0d1313a73030b12abca8577db5a40cd |
| R112 | rules/LOG-mutation-lines.md | 0cb100cbd86b52b86b1de66365d1caab01e0d6a9e4c7993bd1b914feb1baf733 |
| R113 | T3.camp2.txt | 4554eeea32edb8e78e427b521643c398d82a129af10f1d5516da25c4d3212c64 |
| R114 | MUTATION_VALUE.tsv | 0395b7ef4baa1e2d86d851fa6daef068546eca5e768c8ce8ef6f7baa880804ba |
| R115 | TRAIN-B4.campaign.custodian.txt | 4fc74496b19d1e79c5b3ca3a83a80802e420a8ca039661f8ac097cc3ea8a9aa1 |

### Status for every campaign and module

Unknown is missing evidence. Not compared means survivor text is absent. Explained requires module and exact mutation text in the repository's written equivalence record. Old outcome objects combine survived and not-covered changes without identifying each object's outcome; those cells say combined. No earlier reported explanation is promoted to an exact match.

| Record | Task | Source file | Commit measured | Considered | Killed | Survived | Explained | Open | Timed out | Not covered | Not run / incomplete | Version status | Limits | Latest identified task commit | Explanation comparison |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R001 | S2-T02 | custodian/src/eii_custodian/publicdata/frame/build.py | b00244a | unknown | unknown | 9 | not compared | not compared: 9 | unknown | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked b00244a: read; 0fc2776: read; origin/main (a5219f5): read |
| R001 | S2-T02 | custodian/src/eii_custodian/publicdata/frame/live.py | b00244a | unknown | unknown | 11 | not compared | not compared: 11 | unknown | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked b00244a: read; 0fc2776: read; origin/main (a5219f5): read |
| R001 | S2-T02 | custodian/src/eii_custodian/publicdata/frame/municipality_output.py | b00244a | unknown | unknown | 2 | not compared | not compared: 2 | unknown | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked b00244a: read; 0fc2776: read; origin/main (a5219f5): read |
| R001 | S2-T06 | custodian/src/eii_custodian/publicdata/places/integrate.py | b00244a | unknown | unknown | 3 | not compared | not compared: 3 | unknown | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked b00244a: read; 0fc2776: read; origin/main (a5219f5): read |
| R001 | S2-T03, S2-T07 | custodian/src/eii_custodian/publicdata/series/figures.py | b00244a | unknown | unknown | 75 | not compared | not compared: 75 | unknown | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked b00244a: read; 0fc2776: read; origin/main (a5219f5): read |
| R001 | S2-T03, S2-T07 | custodian/src/eii_custodian/publicdata/series/frame.py | b00244a | unknown | unknown | 1 | not compared | not compared: 1 | unknown | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked b00244a: read; 0fc2776: read; origin/main (a5219f5): read |
| R001 | S2-T03, S2-T07 | custodian/src/eii_custodian/publicdata/series/parse.py | b00244a | unknown | unknown | 36 | not compared | not compared: 36 | unknown | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked b00244a: read; 0fc2776: read; origin/main (a5219f5): read |
| R001 | S2-T03, S2-T07 | custodian/src/eii_custodian/publicdata/series/support.py | b00244a | unknown | unknown | 10 | not compared | not compared: 10 | unknown | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked b00244a: read; 0fc2776: read; origin/main (a5219f5): read |
| R001 | S2-T03 | custodian/src/eii_custodian/publicdata/stage.py | b00244a | unknown | unknown | 2 | not compared | not compared: 2 | unknown | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked b00244a: read; 0fc2776: read; origin/main (a5219f5): read |
| R002 | background campaign covering S2-T02, S2-T03, S2-T06, S2-T07 | 9 modules (combined) (individual files not recorded) | 0fc2776 | 4409 | unknown | 59 | not compared | not compared: 59 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 0fc2776 | no exact matches; checked 0fc2776: read; origin/main (a5219f5): read |
| R003 | S2-T03, S2-T07 | custodian/src/eii_custodian/publicdata/series/figures.py | 4fa9c78 | 2279 | 2241 | 38 | not compared | not compared: 38 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 4fa9c78 | no exact matches; checked 4fa9c78: read; origin/main (a5219f5): read |
| R003 | S2-T03, S2-T07 | custodian/src/eii_custodian/publicdata/stage.py | 4fa9c78 | 116 | 114 | 2 | not compared | not compared: 2 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 4fa9c78 | no exact matches; checked 4fa9c78: read; origin/main (a5219f5): read |
| R004 | S1-T08 | evals/typed_decisions/interval.py | 34bd6e10970100204eb3642a001d42e5d1c2a4c5 | 89 | 89 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; on latest identified task head |  | 34bd6e10970100204eb3642a001d42e5d1c2a4c5 | no exact matches; checked 34bd6e10970100204eb3642a001d42e5d1c2a4c5: read; origin/main (a5219f5): read |
| R004 | S1-T08 | evals/typed_decisions/reproduction.py | 34bd6e10970100204eb3642a001d42e5d1c2a4c5 | 153 | 153 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; on latest identified task head |  | 34bd6e10970100204eb3642a001d42e5d1c2a4c5 | no exact matches; checked 34bd6e10970100204eb3642a001d42e5d1c2a4c5: read; origin/main (a5219f5): read |
| R004 | S1-T08 | evals/typed_decisions/requalify.py | 34bd6e10970100204eb3642a001d42e5d1c2a4c5 | 787 | 776 | 11 | not compared | not compared: 11 | 0 | 0 | 0 | latest measured; on latest identified task head |  | 34bd6e10970100204eb3642a001d42e5d1c2a4c5 | no exact matches; checked 34bd6e10970100204eb3642a001d42e5d1c2a4c5: read; origin/main (a5219f5): read |
| R004 | S1-T08 | evals/typed_decisions/route.py | 34bd6e10970100204eb3642a001d42e5d1c2a4c5 | 62 | 62 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; on latest identified task head |  | 34bd6e10970100204eb3642a001d42e5d1c2a4c5 | no exact matches; checked 34bd6e10970100204eb3642a001d42e5d1c2a4c5: read; origin/main (a5219f5): read |
| R005 | S1-T09 | individual file not recorded | b6413cecbe6583455e8d50976bb2ee6bec79b880 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | latest attempt without a result; on latest identified task head | No mutant result: unmodified tests failed or result not saved | b6413cecbe6583455e8d50976bb2ee6bec79b880 | no exact matches; checked b6413cecbe6583455e8d50976bb2ee6bec79b880: read; origin/main (a5219f5): read |
| R006 | S1-T11 | custodian/src/eii_custodian/assignment_spike/assign.py | unknown | 39 | 39 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R006 | S1-T11 | custodian/src/eii_custodian/assignment_spike/delay.py | unknown | 76 | 73 | 3 | 3 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | a5219f5: 3 exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R006 | S1-T11 | custodian/src/eii_custodian/assignment_spike/inputs.py | unknown | 360 | 360 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R006 | S1-T11 | custodian/src/eii_custodian/assignment_spike/params.py | unknown | 248 | 248 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R006 | S1-T11 | custodian/src/eii_custodian/assignment_spike/paths.py | unknown | 91 | 91 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R006 | S1-T11 | custodian/src/eii_custodian/assignment_spike/run.py | unknown | 174 | 174 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R006 | S1-T11 | product/src/eii_product/areas_spike/traffic.py | unknown | 907 | 901 | 6 | 6 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | a5219f5: 6 exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R007 | S1-T18 | web/spikes/performance/main.ts | unknown | 517 | 409 | 70 | 10 | 60 | 38 | 0 | 0 | latest measured; latest task head unproved |  | unknown | a5219f5: 10 exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R007 | S1-T18 | web/spikes/performance/server.mjs | unknown | 455 | 195 | 18 | 0 | 18 | 242 | 0 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R008 | S1-T18 | web/spikes/performance/server.mjs | db0b98e6ed83ffe12c11b4c43e7815d7086ad6ba | 3 | 2 | 0 | 0 | 0 | 1 | 0 | 0 | individual replay; supplements the module campaign | Individual replay only; not a module campaign | unknown | no exact matches; checked db0b98e6ed83ffe12c11b4c43e7815d7086ad6ba: read; measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R009 | S1-T20 | custodian/src/eii_custodian/publicdata/places_fsq/policy.py | e9eb1ed | 307 | unknown | 3 | not compared | not compared: 3 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | e9eb1ed | no exact matches; checked e9eb1ed: read; origin/main (a5219f5): read |
| R010 | S1-T20 | custodian/src/eii_custodian/publicdata/places_fsq/policy.py | e9eb1ed | 307 | 304 | 3 | not compared | not compared: 3 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | e9eb1ed | no exact matches; checked e9eb1ed: read; origin/main (a5219f5): read |
| R011 | S2-T03 | custodian/src/eii_custodian/publicdata/series/baskets.py | unknown | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | latest attempt without a result; latest task head unproved | No mutant result: unmodified tests failed or result not saved | 2ae067e | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 2ae067e: read; origin/main (a5219f5): read |
| R011 | S2-T03 | custodian/src/eii_custodian/publicdata/series/figures.py | unknown | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | latest attempt without a result; latest task head unproved | No mutant result: unmodified tests failed or result not saved | 2ae067e | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 2ae067e: read; origin/main (a5219f5): read |
| R011 | S2-T03 | custodian/src/eii_custodian/publicdata/series/reconcile.py | unknown | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | latest attempt without a result; latest task head unproved | No mutant result: unmodified tests failed or result not saved | 2ae067e | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 2ae067e: read; origin/main (a5219f5): read |
| R012 | S2-T03 | core/src/eii_core/calc/public_series.py | 2ae067e | 130 | 118 | 12 | 0 | 12 | 0 | 0 | 0 | superseded measurement |  | 2ae067e | no exact matches; checked 2ae067e: read; origin/main (a5219f5): read |
| R013 | S2-T03 | core/src/eii_core/calc/public_series.py | unknown | 130 | 127 | 3 | 0 | 3 | 0 | 0 | 0 | latest measured; latest task head unproved | Uncommitted tree later recorded as dde9aee; execution commit not saved | 2ae067e | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 2ae067e: read; origin/main (a5219f5): read |
| R014 | S2-T03 | custodian/src/eii_custodian/publicdata/frame/municipality_output.py | unknown | 42 | unknown | 15 | not compared | not compared: 15 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R014 | S2-T03 | custodian/src/eii_custodian/publicdata/series/figures.py | unknown | 1928 | unknown | 159 | not compared | not compared: 159 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R014 | S2-T03 | custodian/src/eii_custodian/publicdata/series/frame.py | unknown | 64 | unknown | 5 | not compared | not compared: 5 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R015 | S2-T06 | custodian/src/eii_custodian/publicdata/places/fetch.py | b505c2d | 363 | 206 | 102 | not compared | not compared: 102 | unknown | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 36fa382 | no exact matches; checked b505c2d: read; 36fa382: read; origin/main (a5219f5): read |
| R016 | S2-T06 | custodian/src/eii_custodian/publicdata/places/fetch.py | 36fa382 | 363 | 354 | 9 | not compared | not compared: 9 | unknown | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 36fa382 | no exact matches; checked 36fa382: read; origin/main (a5219f5): read |
| R017 | S2-T08 | completeness, draw, figures_review, gate_report (individual files not recorded) | 7839e0d | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | latest attempt without a result; latest task head unproved | Unmodified tests or preparation failed; no mutant ran | d346768 | no exact matches; checked 7839e0d: read; d346768: read; origin/main (a5219f5): read |
| R018 | S2-T08 | custodian/src/eii_custodian/publicdata/completeness.py | 7c4b69e | 587 | unknown | 182 | not compared | not compared: 182 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | d346768 | no exact matches; checked 7c4b69e: read; d346768: read; origin/main (a5219f5): read |
| R018 | S2-T08 | custodian/src/eii_custodian/publicdata/draw.py | 7c4b69e | 148 | unknown | 24 | not compared | not compared: 24 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | d346768 | no exact matches; checked 7c4b69e: read; d346768: read; origin/main (a5219f5): read |
| R018 | S2-T08 | custodian/src/eii_custodian/publicdata/figures_review.py | 7c4b69e | 86 | unknown | 11 | not compared | not compared: 11 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | d346768 | no exact matches; checked 7c4b69e: read; d346768: read; origin/main (a5219f5): read |
| R018 | S2-T08 | custodian/src/eii_custodian/publicdata/gate_report.py | 7c4b69e | 439 | unknown | 82 | not compared | not compared: 82 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | d346768 | no exact matches; checked 7c4b69e: read; d346768: read; origin/main (a5219f5): read |
| R019 | S2-T08 | custodian/src/eii_custodian/publicdata/completeness.py | 934f5f4 | 587 | 570 | 17 | 17 | 0 | 0 | 0 | 0 | superseded measurement |  | d346768 | 934f5f4: 17 exact matches; checked 934f5f4: read; d346768: read; origin/main (a5219f5): read |
| R019 | S2-T08 | custodian/src/eii_custodian/publicdata/draw.py | 934f5f4 | 148 | 145 | 3 | 3 | 0 | 0 | 0 | 0 | superseded measurement |  | d346768 | 934f5f4: 3 exact matches; checked 934f5f4: read; d346768: read; origin/main (a5219f5): read |
| R019 | S2-T08 | custodian/src/eii_custodian/publicdata/figures_review.py | 934f5f4 | 86 | 86 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | d346768 | no exact matches; checked 934f5f4: read; d346768: read; origin/main (a5219f5): read |
| R019 | S2-T08 | custodian/src/eii_custodian/publicdata/gate_report.py | 934f5f4 | 439 | 438 | 1 | 1 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | d346768 | 934f5f4: 1 exact matches; checked 934f5f4: read; d346768: read; origin/main (a5219f5): read |
| R020 | S2-T08 | custodian/src/eii_custodian/publicdata/completeness.py | 255c925 | 595 | 575 | 20 | 16 | 4 | 0 | 0 | 0 | superseded measurement |  | d346768 | 255c925: 15 exact matches; d346768: 1 exact matches; checked 255c925: read; d346768: read; origin/main (a5219f5): read |
| R020 | S2-T08 | custodian/src/eii_custodian/publicdata/draw.py | 255c925 | 148 | 145 | 3 | 3 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | d346768 | 255c925: 3 exact matches; checked 255c925: read; d346768: read; origin/main (a5219f5): read |
| R021 | S2-T08 | custodian/src/eii_custodian/publicdata/completeness.py | e446940 | 596 | 579 | 17 | 17 | 0 | 0 | 0 | 0 | superseded measurement |  | d346768 | e446940: 15 exact matches; d346768: 2 exact matches; checked e446940: read; d346768: read; origin/main (a5219f5): read |
| R022 | S2-T08 | custodian/src/eii_custodian/publicdata/completeness.py | d346768 | 596 | 579 | 17 | 17 | 0 | 0 | 0 | 0 | latest measured; on latest identified task head |  | d346768 | d346768: 17 exact matches; checked d346768: read; origin/main (a5219f5): read |
| R023 | S2-T11 | custodian/src/eii_custodian/publicdata/additions/property_venues.py | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | attempt without a result | Unmodified tests or preparation failed; no mutant ran | 5615e42 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 5615e42: read; origin/main (a5219f5): read |
| R024 | S2-T11 | custodian/src/eii_custodian/publicdata/additions/property_venues.py | 5615e42 | 1153 | 977 | 17 | not compared | not compared: 17 | 159 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 5615e42 | no exact matches; checked 5615e42: read; origin/main (a5219f5): read |
| R025 | S2-T21 | custodian/src/eii_custodian/publicdata/fetch/build.py | unknown | 489 | 394 | 90 | 0 combined | 95 combined | 0 | 5 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R025 | S2-T21 | custodian/src/eii_custodian/publicdata/fetch/kinds.py | unknown | 843 | 549 | 294 | 12 | 282 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | a5219f5: 12 exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R025 | S2-T21 | custodian/src/eii_custodian/publicdata/fetch/registry.py | unknown | 544 | 425 | 119 | 0 | 119 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R026 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/config.py | 4738f64 | 499 | unknown | 97 | not compared | not compared: 97 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 4738f64: read; 9f2d645: read; origin/main (a5219f5): read |
| R026 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/contracts.py | 4738f64 | 369 | unknown | 86 | not compared | not compared: 86 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 4738f64: read; 9f2d645: read; origin/main (a5219f5): read |
| R026 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/fetch.py | 4738f64 | 547 | unknown | 54 | not compared | not compared: 54 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 4738f64: read; 9f2d645: read; origin/main (a5219f5): read |
| R026 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/parse.py | 4738f64 | 590 | unknown | 134 | not compared | not compared: 134 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 4738f64: read; 9f2d645: read; origin/main (a5219f5): read |
| R027 | S2-T24 | baci modules (individual files not recorded) | e169c22 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | latest attempt without a result; latest task head unproved | Unmodified tests or preparation failed; no mutant ran | 9f2d645 | no exact matches; checked e169c22: read; 9f2d645: read; origin/main (a5219f5): read |
| R028 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/config.py | 2180f7f | unknown | unknown | 10 | not compared | not compared: 10 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 2180f7f: read; 9f2d645: read; origin/main (a5219f5): read |
| R028 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/contracts.py | 2180f7f | unknown | unknown | 8 | not compared | not compared: 8 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 2180f7f: read; 9f2d645: read; origin/main (a5219f5): read |
| R028 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/fetch.py | 2180f7f | unknown | unknown | 17 | not compared | not compared: 17 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 2180f7f: read; 9f2d645: read; origin/main (a5219f5): read |
| R028 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/parse.py | 2180f7f | unknown | unknown | 6 | not compared | not compared: 6 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 2180f7f: read; 9f2d645: read; origin/main (a5219f5): read |
| R029 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/config.py | 9f2d645 | unknown | 1923 | 10 | not compared | not compared: 10 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 9f2d645: read; origin/main (a5219f5): read |
| R029 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/contracts.py | 9f2d645 | unknown | 1923 | 8 | not compared | not compared: 8 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 9f2d645: read; origin/main (a5219f5): read |
| R029 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/fetch.py | 9f2d645 | unknown | 1923 | 4 | not compared | not compared: 4 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 9f2d645: read; origin/main (a5219f5): read |
| R029 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/parse.py | 9f2d645 | unknown | 1923 | 6 | not compared | not compared: 6 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 9f2d645 | no exact matches; checked 9f2d645: read; origin/main (a5219f5): read |
| R030 | S2-T26 | core/src/eii_core/calc/trade_reconciliation.py | 3e07e34 | 346 | 289 | 51 | not compared | not compared: 51 | 6 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 3e07e34 | no exact matches; checked 3e07e34: read; origin/main (a5219f5): read |
| R031 | S2-T27 | custodian/src/eii_custodian/publicdata/fetch/cadence.py | c85a9dd | 244 | unknown | 17 | not compared | not compared: 17 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6bcccd7 | no exact matches; checked c85a9dd: read; 6bcccd7: read; origin/main (a5219f5): read |
| R031 | S2-T27 | custodian/src/eii_custodian/publicdata/fetch/receipts.py | c85a9dd | 183 | unknown | 32 | not compared | not compared: 32 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6bcccd7 | no exact matches; checked c85a9dd: read; 6bcccd7: read; origin/main (a5219f5): read |
| R031 | S2-T27 | custodian/src/eii_custodian/publicdata/fetch/snapshots.py | c85a9dd | 538 | unknown | 65 | not compared | not compared: 65 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6bcccd7 | no exact matches; checked c85a9dd: read; 6bcccd7: read; origin/main (a5219f5): read |
| R032 | S2-T27 | custodian/src/eii_custodian/publicdata/comtrade/fetch.py | c85a9dd | 1359 | 1062 | 296 | not compared | not compared: 296 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 6bcccd7 | no exact matches; checked c85a9dd: read; 6bcccd7: read; origin/main (a5219f5): read |
| R032 | S2-T27 | custodian/src/eii_custodian/publicdata/fetch/build.py | c85a9dd | 1192 | 830 | 362 | not compared | not compared: 362 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6bcccd7 | no exact matches; checked c85a9dd: read; 6bcccd7: read; origin/main (a5219f5): read |
| R033 | S2-T27 | custodian/src/eii_custodian/publicdata/comtrade/fetch.py | 6bcccd7 | 1359 | unknown | 50 | not compared | not compared: 50 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 6bcccd7 | no exact matches; checked 6bcccd7: read; origin/main (a5219f5): read |
| R034 | S2-T28 | custodian/src/eii_custodian/publicdata/fetch/partitions.py | 2c88009 | 214 | 171 | 43 | not compared | not compared: 43 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 102ec83 | no exact matches; checked 2c88009: read; 102ec83: read; origin/main (a5219f5): read |
| R035 | S2-T28 | custodian/src/eii_custodian/publicdata/fetch/build.py | 2c88009 | 0 | unknown | 0 | 0 | 0 | unknown | unknown | unknown | attempt without a result | Summary only; exact survivor text absent | 102ec83 | no exact matches; checked 2c88009: read; 102ec83: read; origin/main (a5219f5): read |
| R036 | S2-T28 | custodian/src/eii_custodian/publicdata/fetch/listing.py | 0acfdb1 | 270 | 261 | 9 | not compared | not compared: 9 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 102ec83 | no exact matches; checked 0acfdb1: read; 102ec83: read; origin/main (a5219f5): read |
| R037 | S2-T28 | custodian/src/eii_custodian/publicdata/fetch/build.py | 2c88009 | 714 | 566 | 143 | not compared | not compared: 143 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 102ec83 | no exact matches; checked 2c88009: read; 102ec83: read; origin/main (a5219f5): read |
| R038 | S2-T28 | custodian/src/eii_custodian/publicdata/fetch/partitions.py | 102ec83 | 214 | unknown | 0 | 0 | 0 | 0 | unknown | unknown | attempt without a result | Summary only; exact survivor text absent | 102ec83 | no exact matches; checked 102ec83: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/award_checks.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/awards.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/certificate_pins.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_acquire.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_archive.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_html.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_requests.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_schema.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_workbook.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R039 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/partitions.py | 6aa8a39 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 6aa8a39: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/award_checks.py | 59d5211 | 407 | 321 | 86 | 2 | 84 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 177a85b: 2 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/awards.py | 59d5211 | 965 | 636 | 329 | 17 | 312 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 177a85b: 17 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/certificate_pins.py | 59d5211 | 356 | 293 | 63 | 1 | 62 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 177a85b: 1 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_acquire.py | 59d5211 | 1366 | 958 | 406 | 18 | 388 | 2 | 0 | 0 | superseded measurement |  | 177a85b | 177a85b: 18 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_archive.py | 59d5211 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | attempt without a result |  | 177a85b | no exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_html.py | 59d5211 | 197 | 132 | 58 | 1 combined | 64 combined | 0 | 7 | 0 | superseded measurement |  | 177a85b | 177a85b: 1 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | 59d5211 | 991 | 692 | 299 | 16 | 283 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 177a85b: 16 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_requests.py | 59d5211 | 188 | 44 | 144 | 1 | 143 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 177a85b: 1 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_schema.py | 59d5211 | 706 | 522 | 184 | 9 | 175 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 177a85b: 9 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | 59d5211 | 1227 | 984 | 243 | 13 | 230 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 177a85b: 13 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_workbook.py | 59d5211 | 349 | 226 | 123 | 39 | 84 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 177a85b: 39 exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R040 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/partitions.py | 59d5211 | 351 | 288 | 18 | 0 combined | 63 combined | 0 | 45 | 0 | superseded measurement |  | 177a85b | no exact matches; checked 59d5211: read; 177a85b: read; origin/main (a5219f5): read |
| R041 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/certificate_pins.py | unknown | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 177a85b: read; origin/main (a5219f5): read |
| R041 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | unknown | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 177a85b: read; origin/main (a5219f5): read |
| R041 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_requests.py | unknown | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 177a85b: read; origin/main (a5219f5): read |
| R042 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/certificate_pins.py | 2ca29f6 | 356 | 355 | 1 | 1 | 0 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 2ca29f6: 1 exact matches; checked 2ca29f6: read; 177a85b: read; origin/main (a5219f5): read |
| R042 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | 2ca29f6 | 991 | 975 | 16 | 16 | 0 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 2ca29f6: 16 exact matches; checked 2ca29f6: read; 177a85b: read; origin/main (a5219f5): read |
| R042 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_requests.py | 2ca29f6 | 188 | 187 | 1 | 1 | 0 | 0 | 0 | 0 | superseded measurement |  | 177a85b | 2ca29f6: 1 exact matches; checked 2ca29f6: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/award_checks.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/awards.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/certificate_pins.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_acquire.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_archive.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_html.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_requests.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_schema.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_workbook.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R043 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/partitions.py | 74f09ec | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 177a85b | no exact matches; checked 74f09ec: read; 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/award_checks.py | 177a85b | 407 | 405 | 2 | not compared | not compared: 2 | 0 | 0 | 0 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/awards.py | 177a85b | 965 | 447 | 13 | not compared | not compared: 13 | 0 | 0 | 505 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/certificate_pins.py | 177a85b | 356 | 323 | 0 | 0 | 0 | 0 | 0 | 33 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_acquire.py | 177a85b | 1366 | 1345 | 18 | not compared | not compared: 18 | 3 | 0 | 0 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_archive.py | 177a85b | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | latest attempt without a result; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_html.py | 177a85b | 197 | 196 | 1 | not compared | not compared: 1 | 0 | 0 | 0 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | 177a85b | 991 | 942 | 16 | not compared | not compared: 16 | 0 | 0 | 33 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_requests.py | 177a85b | 188 | 187 | 1 | not compared | not compared: 1 | 0 | 0 | 0 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_schema.py | 177a85b | 706 | 697 | 9 | not compared | not compared: 9 | 0 | 0 | 0 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | 177a85b | 1235 | 1216 | 19 | not compared | not compared: 19 | 0 | 0 | 0 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/page_workbook.py | 177a85b | 349 | 310 | 39 | not compared | not compared: 39 | 0 | 0 | 0 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R044 | S2-T29 | custodian/src/eii_custodian/publicdata/fetch/partitions.py | 177a85b | 351 | 351 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; on latest identified task head | Partial; survivor text not compared | 177a85b | no exact matches; checked 177a85b: read; origin/main (a5219f5): read |
| R045 | S2-T30 | custodian/src/eii_custodian/publicdata/fetch/build.py | 7111474 | 1811 | 1217 | 586 | 0 combined | 594 combined | 0 | 8 | 0 | latest measured; latest task head unproved |  | 769edaa | no exact matches; checked 7111474: read; 769edaa: read; origin/main (a5219f5): read |
| R045 | S2-T30 | custodian/src/eii_custodian/publicdata/fetch/report.py | 7111474 | 26 | 23 | 3 | 0 | 3 | 0 | 0 | 0 | superseded measurement |  | 769edaa | no exact matches; checked 7111474: read; 769edaa: read; origin/main (a5219f5): read |
| R045 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_build.py | 7111474 | 2586 | 1329 | 1239 | 36 combined | 1221 combined | 0 | 18 | 0 | superseded measurement |  | 769edaa | 769edaa: 36 exact matches; checked 7111474: read; 769edaa: read; origin/main (a5219f5): read |
| R045 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_contracts.py | 7111474 | 197 | 129 | 57 | 7 combined | 61 combined | 0 | 11 | 0 | superseded measurement |  | 769edaa | 769edaa: 7 exact matches; checked 7111474: read; 769edaa: read; origin/main (a5219f5): read |
| R045 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_evidence.py | 7111474 | 2619 | 1638 | 950 | 22 combined | 959 combined | 0 | 31 | 0 | superseded measurement |  | 769edaa | 769edaa: 22 exact matches; checked 7111474: read; 769edaa: read; origin/main (a5219f5): read |
| R046 | S2-T30 | custodian/src/eii_custodian/publicdata/fetch/report.py | 1545212 | 26 | 26 | 0 | 0 | 0 | 0 | 0 | 0 | superseded measurement |  | 769edaa | no exact matches; checked 1545212: read; 769edaa: read; origin/main (a5219f5): read |
| R046 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_contracts.py | 1545212 | 197 | 188 | 9 | 7 | 2 | 0 | 0 | 0 | superseded measurement |  | 769edaa | 769edaa: 7 exact matches; checked 1545212: read; 769edaa: read; origin/main (a5219f5): read |
| R047 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_build.py | 6ca418b | 2586 | 2544 | 42 | 36 | 6 | 0 | 0 | 0 | superseded measurement |  | 769edaa | 769edaa: 36 exact matches; checked 6ca418b: read; 769edaa: read; origin/main (a5219f5): read |
| R048 | S2-T30 | custodian/src/eii_custodian/publicdata/fetch/report.py | f6c9aaf | 26 | 26 | 0 | 0 | 0 | 0 | 0 | 0 | superseded measurement |  | 769edaa | no exact matches; checked f6c9aaf: read; 769edaa: read; origin/main (a5219f5): read |
| R048 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_contracts.py | f6c9aaf | 197 | 190 | 7 | 7 | 0 | 0 | 0 | 0 | superseded measurement |  | 769edaa | f6c9aaf: 7 exact matches; checked f6c9aaf: read; 769edaa: read; origin/main (a5219f5): read |
| R049 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_evidence.py | d943407 | 2619 | 2551 | 68 | 22 | 46 | 0 | 0 | 0 | superseded measurement |  | 769edaa | 769edaa: 22 exact matches; checked d943407: read; 769edaa: read; origin/main (a5219f5): read |
| R050 | S2-T30 | custodian/src/eii_custodian/publicdata/fetch/report.py | 337ea64 | 26 | 26 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 769edaa | no exact matches; checked 337ea64: read; 769edaa: read; origin/main (a5219f5): read |
| R050 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_contracts.py | 337ea64 | 197 | 190 | 7 | 7 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 769edaa | 337ea64: 7 exact matches; checked 337ea64: read; 769edaa: read; origin/main (a5219f5): read |
| R050 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_evidence.py | 337ea64 | 2650 | 2577 | 73 | 28 | 45 | 0 | 0 | 0 | superseded measurement |  | 769edaa | 769edaa: 28 exact matches; checked 337ea64: read; 769edaa: read; origin/main (a5219f5): read |
| R051 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_build.py | 38da4e3 | 2664 | 2581 | 83 | 37 | 46 | 0 | 0 | 0 | superseded measurement |  | 769edaa | 38da4e3: 37 exact matches; checked 38da4e3: read; 769edaa: read; origin/main (a5219f5): read |
| R052 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_evidence.py | 5106e3b | 2650 | 2622 | 28 | 28 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 769edaa | 5106e3b: 28 exact matches; checked 5106e3b: read; 769edaa: read; origin/main (a5219f5): read |
| R053 | S2-T30 | custodian/src/eii_custodian/publicdata/investment_build.py | 7b422a0 | 2664 | 2628 | 36 | 36 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 769edaa | 7b422a0: 36 exact matches; checked 7b422a0: read; 769edaa: read; origin/main (a5219f5): read |
| R054 | S2-T19 | custodian/src/eii_custodian/publicdata/additions/split_policy.py | 072ae84 | 733 | 730 | 2 | not compared | not compared: 2 | 1 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R055 | S2-T20 | heights read.py/match.py (individual files not recorded) | 072ae84 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | latest attempt without a result; on latest identified task head | Unmodified tests or preparation failed; no mutant ran | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R056 | S2-T17 | custodian/src/eii_custodian/publicdata/fetch/forecast_series.py | 072ae84 | 194 | unknown | 1 | not compared | not compared: 1 | 11 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R056 | S2-T19 | custodian/src/eii_custodian/publicdata/property/bulletin.py | 072ae84 | 323 | unknown | 28 | not compared | not compared: 28 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R056 | S2-T19 | custodian/src/eii_custodian/publicdata/property/quarter.py | 072ae84 | 253 | unknown | 31 | not compared | not compared: 31 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R056 | S2-T19 | custodian/src/eii_custodian/publicdata/property/use_map.py | 072ae84 | 78 | unknown | 4 | not compared | not compared: 4 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R057 | S2-T17 | custodian/src/eii_custodian/publicdata/fetch/forecast_series.py | 072ae84 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | Summary only; exact survivor text absent | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R058 | S2-T19 | custodian/src/eii_custodian/publicdata/singles/bank_credit.py | 072ae84 | unknown | unknown | 26 | not compared | not compared: 26 | unknown | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R058 | S2-T19 | custodian/src/eii_custodian/publicdata/singles/dcool.py | 072ae84 | unknown | unknown | 14 | not compared | not compared: 14 | unknown | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R058 | S2-T19 | custodian/src/eii_custodian/publicdata/singles/tenders.py | 072ae84 | unknown | unknown | 196 | not compared | not compared: 196 | unknown | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 072ae84 | no exact matches; checked 072ae84: read; origin/main (a5219f5): read |
| R059 | S3-T01 | not logged (individual files not recorded) | unknown | unknown | unknown | unknown | not compared | unknown | 75 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R060 | S3-T06 | product/src/eii_product/tools/fact_builder.py | c934799 | 148 | unknown | 0 | 0 | 0 | 0 | unknown | unknown | latest attempt without a result; on latest identified task head | Summary only; exact survivor text absent | c934799 | no exact matches; checked c934799: read; origin/main (a5219f5): read |
| R060 | S3-T06 | product/src/eii_product/tools/sector_facts.py | c934799 | 1791 | unknown | 10 | not compared | not compared: 10 | 1 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | c934799 | no exact matches; checked c934799: read; origin/main (a5219f5): read |
| R061 | S3-T07 | product/src/eii_product/assistant/catalogue/directives.py | unknown | 350 | 350 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R061 | S3-T07 | product/src/eii_product/assistant/catalogue/entries.py | unknown | 988 | 988 | 0 | 0 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R062 | S3-T08 | product/src/eii_product/assistant/accounting.py | 9fce4cd | 194 | unknown | 72 | not compared | not compared: 72 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 9fce4cd: read; 6f2c7e7: read; origin/main (a5219f5): read |
| R062 | S3-T08 | product/src/eii_product/assistant/playbooks/engine.py | 9fce4cd | 309 | unknown | 0 | 0 | 0 | 0 | unknown | unknown | latest attempt without a result; latest task head unproved | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 9fce4cd: read; 6f2c7e7: read; origin/main (a5219f5): read |
| R062 | S3-T08 | product/src/eii_product/assistant/playbooks/registry.py | 9fce4cd | 45 | unknown | 0 | 0 | 0 | 18 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 9fce4cd: read; 6f2c7e7: read; origin/main (a5219f5): read |
| R062 | S3-T08 | product/src/eii_product/assistant/templates/writer.py | 9fce4cd | 142 | unknown | 0 | 0 | 0 | 0 | unknown | unknown | latest attempt without a result; latest task head unproved | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 9fce4cd: read; 6f2c7e7: read; origin/main (a5219f5): read |
| R063 | S3-T08 | product/src/eii_product/api/answers.py | 9fce4cd | unknown | unknown | 76 | not compared | not compared: 76 | 26 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 9fce4cd: read; 6f2c7e7: read; origin/main (a5219f5): read |
| R063 | S3-T08 | product/src/eii_product/api/playbooks.py | 9fce4cd | unknown | unknown | 1 | not compared | not compared: 1 | 18 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 9fce4cd: read; 6f2c7e7: read; origin/main (a5219f5): read |
| R063 | S3-T08 | product/src/eii_product/assistant/catalogue/brief.py | 9fce4cd | unknown | unknown | 1 | not compared | not compared: 1 | 1 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 9fce4cd: read; 6f2c7e7: read; origin/main (a5219f5): read |
| R063 | S3-T08 | product/src/eii_product/ledger/local.py | 9fce4cd | unknown | unknown | 4 | not compared | not compared: 4 | 2 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 9fce4cd: read; 6f2c7e7: read; origin/main (a5219f5): read |
| R063 | S3-T08 | product/src/eii_product/tools/areas.py | 9fce4cd | unknown | unknown | 8 | not compared | not compared: 8 | 2 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 9fce4cd: read; 6f2c7e7: read; origin/main (a5219f5): read |
| R064 | S3-T08 | product/src/eii_product/assistant/accounting.py | 6f2c7e7 | 194 | unknown | 9 | not compared | not compared: 9 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 6f2c7e7 | no exact matches; checked 6f2c7e7: read; origin/main (a5219f5): read |
| R065 | S3-T16 | product/src/eii_product/api/map_modes.py | unknown | 149 | unknown | 44 | not compared | not compared: 44 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 2c68b92 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 2c68b92: read; origin/main (a5219f5): read |
| R065 | S3-T16 | product/src/eii_product/photoreal_tiles/limit.py | unknown | 150 | unknown | 47 | not compared | not compared: 47 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 2c68b92 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 2c68b92: read; origin/main (a5219f5): read |
| R065 | S3-T16 | product/src/eii_product/photoreal_tiles/proxy.py | unknown | 151 | unknown | 44 | not compared | not compared: 44 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 2c68b92 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 2c68b92: read; origin/main (a5219f5): read |
| R066 | S3-T16 | map_modes, limit, proxy (individual files not recorded) | b7c6768 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | latest attempt without a result; latest task head unproved | Unmodified tests or preparation failed; no mutant ran | 2c68b92 | no exact matches; checked b7c6768: read; 2c68b92: read; origin/main (a5219f5): read |
| R067 | S3-T16 | product/src/eii_product/api/map_modes.py | 2c68b92 | 149 | unknown | 6 | not compared | not compared: 6 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 2c68b92 | no exact matches; checked 2c68b92: read; origin/main (a5219f5): read |
| R067 | S3-T16 | product/src/eii_product/photoreal_tiles/limit.py | 2c68b92 | 150 | unknown | 5 | not compared | not compared: 5 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 2c68b92 | no exact matches; checked 2c68b92: read; origin/main (a5219f5): read |
| R067 | S3-T16 | product/src/eii_product/photoreal_tiles/proxy.py | 2c68b92 | 151 | unknown | 9 | not compared | not compared: 9 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 2c68b92 | no exact matches; checked 2c68b92: read; origin/main (a5219f5): read |
| R068 | S3-T17 | core/src/eii_core/calc/firms_per_tower.py | unknown | 423 | 378 | 45 | not compared | not compared: 45 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | adc0684 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); adc0684: read; origin/main (a5219f5): read |
| R069 | S3-T17 | product/src/eii_product/api/layers.py | 34dca96 | 475 | 333 | 142 | not compared | not compared: 142 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | adc0684 | no exact matches; checked 34dca96: read; adc0684: read; origin/main (a5219f5): read |
| R069 | S3-T17 | product/src/eii_product/register_file.py | 34dca96 | 448 | 359 | 89 | not compared | not compared: 89 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | adc0684 | no exact matches; checked 34dca96: read; adc0684: read; origin/main (a5219f5): read |
| R070 | S3-T17 | product/src/eii_product/api/layers.py | 2630f5a | 495 | 487 | 8 | not compared | not compared: 8 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | adc0684 | no exact matches; checked 2630f5a: read; adc0684: read; origin/main (a5219f5): read |
| R071 | S3-T17 | product/src/eii_product/api/layers.py | adc0684 | 495 | 488 | 7 | not compared | not compared: 7 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | adc0684 | no exact matches; checked adc0684: read; origin/main (a5219f5): read |
| R072 | S4-T01 | readers, release, feed (individual files not recorded) | 6ec076e | 0 | unknown | 0 | 0 | 0 | unknown | unknown | unknown | attempt without a result | Summary only; exact survivor text absent | 38e0566 | no exact matches; checked 6ec076e: read; 38e0566: read; origin/main (a5219f5): read |
| R073 | S4-T01 | readers, release, feed (individual files not recorded) | 435b671 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | latest attempt without a result; latest task head unproved | Summary only; exact survivor text absent | 38e0566 | no exact matches; checked 435b671: read; 38e0566: read; origin/main (a5219f5): read |
| R074 | S4-T01 | custodian/src/eii_custodian/conformance/feed.py | f1b1fdb | 1304 | unknown | 362 | not compared | not compared: 362 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 38e0566 | no exact matches; checked f1b1fdb: read; 38e0566: read; origin/main (a5219f5): read |
| R074 | S4-T01 | custodian/src/eii_custodian/conformance/readers.py | f1b1fdb | 209 | unknown | 35 | not compared | not compared: 35 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 38e0566 | no exact matches; checked f1b1fdb: read; 38e0566: read; origin/main (a5219f5): read |
| R074 | S4-T01 | custodian/src/eii_custodian/conformance/release.py | f1b1fdb | 1531 | unknown | 508 | not compared | not compared: 508 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 38e0566 | no exact matches; checked f1b1fdb: read; 38e0566: read; origin/main (a5219f5): read |
| R075 | S4-T01 | custodian/src/eii_custodian/conformance/feed.py | 279e7bd | 1304 | 1269 | 35 | not compared | not compared: 35 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 38e0566 | no exact matches; checked 279e7bd: read; 38e0566: read; origin/main (a5219f5): read |
| R075 | S4-T01 | custodian/src/eii_custodian/conformance/readers.py | 279e7bd | 225 | 212 | 13 | not compared | not compared: 13 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 38e0566 | no exact matches; checked 279e7bd: read; 38e0566: read; origin/main (a5219f5): read |
| R076 | S4-T01 | custodian/src/eii_custodian/conformance/feed.py | 38e0566 | 1304 | 1273 | 31 | not compared | not compared: 31 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 38e0566 | no exact matches; checked 38e0566: read; origin/main (a5219f5): read |
| R076 | S4-T01 | custodian/src/eii_custodian/conformance/readers.py | 38e0566 | 225 | 212 | 13 | not compared | not compared: 13 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 38e0566 | no exact matches; checked 38e0566: read; origin/main (a5219f5): read |
| R077 | S4-T02 | custodian/src/eii_custodian/worldgen/calibration/table.py | 2c10bfb | 616 | unknown | 7 | not compared | not compared: 7 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 2394b8e | no exact matches; checked 2c10bfb: read; 2394b8e: read; origin/main (a5219f5): read |
| R077 | S4-T02 | custodian/src/eii_custodian/worldgen/employment/allocation.py | 2c10bfb | 195 | unknown | 10 | not compared | not compared: 10 | 2 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 2394b8e | no exact matches; checked 2c10bfb: read; 2394b8e: read; origin/main (a5219f5): read |
| R077 | S4-T02 | custodian/src/eii_custodian/worldgen/employment/stock.py | 2c10bfb | 1488 | unknown | 13 | not compared | not compared: 13 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 2394b8e | no exact matches; checked 2c10bfb: read; 2394b8e: read; origin/main (a5219f5): read |
| R078 | S4-T02 | custodian/src/eii_custodian/worldgen/employment/allocation.py | 2c10bfb | 195 | unknown | 10 | not compared | not compared: 10 | 19 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 2394b8e | no exact matches; checked 2c10bfb: read; 2394b8e: read; origin/main (a5219f5): read |
| R079 | S4-T02 | custodian/src/eii_custodian/worldgen/employment/stock.py | 2394b8e | unknown | unknown | 13 | not compared | not compared: 13 | unknown | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 2394b8e | no exact matches; checked 2394b8e: read; origin/main (a5219f5): read |
| R080 | S4-T02 | custodian/src/eii_custodian/worldgen/employment/allocation.py | 2394b8e | 195 | unknown | 10 | not compared | not compared: 10 | 19 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 2394b8e | no exact matches; checked 2394b8e: read; origin/main (a5219f5): read |
| R081 | S4-T03 | linkage modules (individual files not recorded) | 63fcec8 | 0 | unknown | 0 | 0 | 0 | unknown | unknown | unknown | attempt without a result | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked 63fcec8: read; 7fe92e4: read; origin/main (a5219f5): read |
| R082 | S4-T03 | linkage modules (individual files not recorded) | af7d6f3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | latest attempt without a result; latest task head unproved | Unmodified tests or preparation failed; no mutant ran | 7fe92e4 | no exact matches; checked af7d6f3: read; 7fe92e4: read; origin/main (a5219f5): read |
| R083 | S4-T03 | custodian/src/eii_custodian/linkage/assemble.py | unknown | 615 | unknown | 12 | not compared | not compared: 12 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 7fe92e4: read; origin/main (a5219f5): read |
| R083 | S4-T03 | custodian/src/eii_custodian/linkage/dedup.py | unknown | 109 | unknown | 13 | not compared | not compared: 13 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 7fe92e4: read; origin/main (a5219f5): read |
| R083 | S4-T03 | custodian/src/eii_custodian/linkage/wages.py | unknown | 107 | unknown | 6 | not compared | not compared: 6 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 7fe92e4: read; origin/main (a5219f5): read |
| R084 | S4-T03 | custodian/src/eii_custodian/worldgen/wages/coverage.py | unknown | 125 | unknown | 7 | not compared | not compared: 7 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 7fe92e4: read; origin/main (a5219f5): read |
| R084 | S4-T03 | custodian/src/eii_custodian/worldgen/wages/levels.py | unknown | 454 | unknown | 84 | not compared | not compared: 84 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 7fe92e4: read; origin/main (a5219f5): read |
| R084 | S4-T03 | custodian/src/eii_custodian/worldgen/wages/reference.py | unknown | 863 | unknown | 163 | not compared | not compared: 163 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 7fe92e4: read; origin/main (a5219f5): read |
| R085 | S4-T03 | custodian/src/eii_custodian/linkage/assemble.py | 7fe92e4 | 615 | unknown | 9 | not compared | not compared: 9 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked 7fe92e4: read; origin/main (a5219f5): read |
| R085 | S4-T03 | custodian/src/eii_custodian/linkage/dedup.py | 7fe92e4 | 109 | unknown | 2 | not compared | not compared: 2 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked 7fe92e4: read; origin/main (a5219f5): read |
| R085 | S4-T03 | custodian/src/eii_custodian/linkage/wages.py | 7fe92e4 | 107 | unknown | 1 | not compared | not compared: 1 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked 7fe92e4: read; origin/main (a5219f5): read |
| R085 | S4-T03 | custodian/src/eii_custodian/worldgen/wages/coverage.py | 7fe92e4 | 125 | unknown | 0 | 0 | 0 | 0 | unknown | unknown | attempt without a result | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked 7fe92e4: read; origin/main (a5219f5): read |
| R085 | S4-T03 | custodian/src/eii_custodian/worldgen/wages/levels.py | 7fe92e4 | 454 | unknown | 4 | not compared | not compared: 4 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked 7fe92e4: read; origin/main (a5219f5): read |
| R085 | S4-T03 | custodian/src/eii_custodian/worldgen/wages/reference.py | 7fe92e4 | 863 | unknown | 5 | not compared | not compared: 5 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 7fe92e4 | no exact matches; checked 7fe92e4: read; origin/main (a5219f5): read |
| R086 | S4-T04 | custodian/src/eii_custodian/mobility/panel.py | edff503 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | latest attempt without a result; on latest identified task head | No mutant result: unmodified tests failed or result not saved | edff503 | no exact matches; checked edff503: read; origin/main (a5219f5): read |
| R087 | S4-T07 | custodian/src/eii_custodian/mobility/visitors.py | unknown | 2330 | 2282 | 46 | 42 | 4 | 2 | 0 | 0 | superseded measurement |  | fad41e5 | fad41e5: 42 exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); fad41e5: read; origin/main (a5219f5): read |
| R088 | S4-T07 | custodian/src/eii_custodian/mobility/visitors.py | unknown | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | fad41e5 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); fad41e5: read; origin/main (a5219f5): read |
| R089 | S4-T07 | custodian/src/eii_custodian/mobility/visitors.py | fad41e5 | 2330 | 2286 | 42 | 42 | 0 | 2 | 0 | 0 | latest measured; on latest identified task head |  | fad41e5 | fad41e5: 42 exact matches; checked fad41e5: read; origin/main (a5219f5): read |
| R090 | S4-T08 | custodian/src/eii_custodian/mobility/trips.py | 86a9172 | 567 | 558 | 9 | 9 | 0 | 0 | 0 | 0 | latest measured; on latest identified task head |  | 86a9172 | 86a9172: 9 exact matches; checked 86a9172: read; origin/main (a5219f5): read |
| R091 | S4-T13 | custodian/src/eii_custodian/conformance/coverage_check.py | unknown | 444 | unknown | 161 | not compared | not compared: 161 | 4 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | d718c29 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); d718c29: read; origin/main (a5219f5): read |
| R091 | S4-T13 | custodian/src/eii_custodian/conformance/feed.py | unknown | 1332 | unknown | 369 | not compared | not compared: 369 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | d718c29 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); d718c29: read; origin/main (a5219f5): read |
| R091 | S4-T13 | custodian/src/eii_custodian/conformance/rules_employment.py | unknown | 668 | unknown | 247 | not compared | not compared: 247 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | d718c29 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); d718c29: read; origin/main (a5219f5): read |
| R091 | S4-T13 | custodian/src/eii_custodian/worldgen/employment/gender.py | unknown | 335 | unknown | 37 | not compared | not compared: 37 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | d718c29 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); d718c29: read; origin/main (a5219f5): read |
| R091 | S4-T13 | custodian/src/eii_custodian/worldgen/employment/stock.py | unknown | 1626 | unknown | 34 | not compared | not compared: 34 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | d718c29 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); d718c29: read; origin/main (a5219f5): read |
| R092 | S4-T13 | custodian/src/eii_custodian/worldgen/employment/gender.py | b077b0e | 335 | 334 | 1 | not compared | not compared: 1 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | d718c29 | no exact matches; checked b077b0e: read; d718c29: read; origin/main (a5219f5): read |
| R092 | S4-T13 | custodian/src/eii_custodian/worldgen/employment/stock.py | b077b0e | 1626 | 1609 | 17 | not compared | not compared: 17 | 0 | unknown | unknown | latest measured; latest task head unproved | Summary only; exact survivor text absent | d718c29 | no exact matches; checked b077b0e: read; d718c29: read; origin/main (a5219f5): read |
| R093 | S4-T13 | custodian/src/eii_custodian/conformance/coverage_check.py | d718c29 | 444 | 431 | 13 | not compared | not compared: 13 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | d718c29 | no exact matches; checked d718c29: read; origin/main (a5219f5): read |
| R093 | S4-T13 | custodian/src/eii_custodian/conformance/rules_employment.py | d718c29 | 668 | 649 | 19 | not compared | not compared: 19 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | d718c29 | no exact matches; checked d718c29: read; origin/main (a5219f5): read |
| R094 | S4-T14 | custodian/src/eii_custodian/worldgen/adapters/employment_swap.py | 1f3bf12 | 307 | unknown | 24 | not compared | not compared: 24 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | ca38e73 | no exact matches; checked 1f3bf12: read; ca38e73: read; origin/main (a5219f5): read |
| R095 | S4-T14 | custodian/src/eii_custodian/worldgen/adapters/employment_swap.py | unknown | 307 | 303 | 4 | not compared | not compared: 4 | unknown | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | ca38e73 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); ca38e73: read; origin/main (a5219f5): read |
| R096 | S4-T14 | custodian/src/eii_custodian/worldgen/adapters/employment_swap.py | ca38e73 | 307 | 303 | 4 | 4 | 0 | 0 | 0 | 0 | latest measured; on latest identified task head |  | ca38e73 | ca38e73: 4 exact matches; checked ca38e73: read; origin/main (a5219f5): read |
| R097 | S4-T15 | custodian/src/eii_custodian/worldgen/adapters/wage_swap.py | 7824729 | 417 | 376 | 41 | not compared | not compared: 41 | 0 | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 785d09b | no exact matches; checked 7824729: read; 785d09b: read; origin/main (a5219f5): read |
| R098 | S4-T15 | custodian/src/eii_custodian/worldgen/adapters/wage_swap.py | unknown | 0 | unknown | 0 | 0 | 0 | unknown | unknown | unknown | attempt without a result | Summary only; exact survivor text absent | 785d09b | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 785d09b: read; origin/main (a5219f5): read |
| R099 | S4-T15 | custodian/src/eii_custodian/worldgen/adapters/wage_swap.py | unknown | 417 | 404 | 13 | not compared | not compared: 13 | unknown | unknown | unknown | superseded measurement | Summary only; exact survivor text absent | 785d09b | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 785d09b: read; origin/main (a5219f5): read |
| R100 | S4-T15 | custodian/src/eii_custodian/worldgen/adapters/wage_swap.py | 785d09b | 417 | 410 | 7 | not compared | not compared: 7 | unknown | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 785d09b | no exact matches; checked 785d09b: read; origin/main (a5219f5): read |
| R101 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/build.py | 4d7933a | 1736 | 1172 | 556 | 0 combined | 564 combined | 0 | 8 | 0 | latest measured; latest task head unproved |  | 4432bc3 | no exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R102 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/build.py | unknown | 0 | unknown | 0 | 0 | 0 | unknown | unknown | unknown | attempt without a result | Summary only; exact survivor text absent | 4432bc3 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 4432bc3: read; origin/main (a5219f5): read |
| R103 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/build.py | 393ca5e | 1736 | 0 | 0 | 0 | 0 | 0 | 0 | 1736 | attempt without a result | Unmodified tests or preparation failed; no mutant ran | 4432bc3 | no exact matches; checked 393ca5e: read; 4432bc3: read; origin/main (a5219f5): read |
| R104 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/checks.py | 4d7933a | 375 | 246 | 129 | not compared | not compared: 129 | 0 | 0 | 0 | superseded measurement | Partial; survivor text not compared | 4432bc3 | no exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R104 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/kinds.py | 4d7933a | 1941 | 1868 | 73 | not compared | not compared: 73 | 0 | 0 | 0 | superseded measurement | Partial; survivor text not compared | 4432bc3 | no exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R104 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/registry.py | 4d7933a | 1117 | 124 | 0 | 0 | 0 | 23 | 0 | 970 | superseded measurement | Partial; survivor text not compared | 4432bc3 | no exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R105 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/listing.py | 4d7933a | 270 | 261 | 9 | 9 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 4432bc3 | 4d7933a: 9 exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R105 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/transport.py | 4d7933a | 588 | 415 | 169 | 0 combined | 173 combined | 0 | 4 | 0 | latest measured; latest task head unproved |  | 4432bc3 | no exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R106 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/checks.py | 2ae1299 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 4432bc3 | no exact matches; checked 2ae1299: read; 4432bc3: read; origin/main (a5219f5): read |
| R106 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/kinds.py | 2ae1299 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 4432bc3 | no exact matches; checked 2ae1299: read; 4432bc3: read; origin/main (a5219f5): read |
| R106 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/registry.py | 2ae1299 | unknown | unknown | unknown | not compared | unknown | unknown | unknown | unknown | attempt without a result | No mutant result: unmodified tests failed or result not saved | 4432bc3 | no exact matches; checked 2ae1299: read; 4432bc3: read; origin/main (a5219f5): read |
| R107 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/checks.py | 2ae1299 | 375 | 246 | 129 | 0 | 129 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 4432bc3 | no exact matches; checked 2ae1299: read; 4432bc3: read; origin/main (a5219f5): read |
| R107 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/kinds.py | 2ae1299 | 1941 | 1868 | 73 | 38 | 35 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 4432bc3 | 2ae1299: 38 exact matches; checked 2ae1299: read; 4432bc3: read; origin/main (a5219f5): read |
| R108 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/registry.py | 4432bc3 | 1120 | 666 | 0 | 0 | 0 | 73 | 0 | 381 | latest measured; on latest identified task head | Partial; survivor text not compared | 4432bc3 | no exact matches; checked 4432bc3: read; origin/main (a5219f5): read |
| R109 | S2-T25 | custodian/src/eii_custodian/publicdata/atlas/fetch.py | 4d7933a | 576 | 514 | 62 | 0 | 62 | 0 | 0 | 0 | superseded measurement |  | 4432bc3 | no exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R109 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/fetch.py | 4d7933a | 520 | 516 | 4 | 4 | 0 | 0 | 0 | 0 | superseded measurement |  | 4432bc3 | 4d7933a: 4 exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R109 | S2-T23 | custodian/src/eii_custodian/publicdata/comtrade/assemble.py | 4d7933a | 779 | 462 | 317 | 0 | 317 | 0 | 0 | 0 | superseded measurement |  | 4432bc3 | no exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R109 | S2-T23 | custodian/src/eii_custodian/publicdata/comtrade/fetch.py | 4d7933a | 1359 | 1308 | 51 | 50 | 1 | 0 | 0 | 0 | superseded measurement |  | 4432bc3 | 4d7933a: 50 exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R109 | S2-T25 | custodian/src/eii_custodian/publicdata/gravity/fetch.py | 4d7933a | 538 | 482 | 56 | 0 | 56 | 0 | 0 | 0 | superseded measurement |  | 4432bc3 | no exact matches; checked 4d7933a: read; 4432bc3: read; origin/main (a5219f5): read |
| R110 | S2-T25 | custodian/src/eii_custodian/publicdata/atlas/fetch.py | 8954058 | 576 | 571 | 5 | 5 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 4432bc3 | 8954058: 5 exact matches; checked 8954058: read; 4432bc3: read; origin/main (a5219f5): read |
| R110 | S2-T24 | custodian/src/eii_custodian/publicdata/baci/fetch.py | 8954058 | 520 | 515 | 4 | 4 | 0 | 1 | 0 | 0 | latest measured; latest task head unproved |  | 4432bc3 | 8954058: 4 exact matches; checked 8954058: read; 4432bc3: read; origin/main (a5219f5): read |
| R110 | S2-T23 | custodian/src/eii_custodian/publicdata/comtrade/fetch.py | 8954058 | 1359 | 1316 | 43 | 43 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 4432bc3 | 8954058: 43 exact matches; checked 8954058: read; 4432bc3: read; origin/main (a5219f5): read |
| R110 | S2-T25 | custodian/src/eii_custodian/publicdata/gravity/fetch.py | 8954058 | 538 | 535 | 3 | 3 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 4432bc3 | 8954058: 3 exact matches; checked 8954058: read; 4432bc3: read; origin/main (a5219f5): read |
| R111 | S2-T23 | custodian/src/eii_custodian/publicdata/comtrade/assemble.py | 6882f12 | 779 | 758 | 21 | 21 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | 4432bc3 | 6882f12: 21 exact matches; checked 6882f12: read; 4432bc3: read; origin/main (a5219f5): read |
| R112 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | custodian/src/eii_custodian/publicdata/fetch/registry.py | unknown | 26 | 13 | 13 | not compared | not compared: 13 | 0 | 0 | 0 | individual replay; supplements the module campaign | Individual repeats; exact changes absent; does not close the module | 4432bc3 | no exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); 4432bc3: read; origin/main (a5219f5): read |
| R113 | S2-T03, S2-T07 | custodian/src/eii_custodian/publicdata/series/figures.py | 360034d | 2513 | 2494 | 19 | 19 | 0 | 0 | 0 | 0 | superseded measurement |  | 625fa5e | 360034d: 19 exact matches; checked 360034d: read; 625fa5e: read; origin/main (a5219f5): read |
| R114 | S2-T03, S2-T07 | custodian/src/eii_custodian/publicdata/series/figures.py | 625fa5e | 2513 | 2494 | 19 | not compared | not compared: 19 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 625fa5e | no exact matches; checked 625fa5e: read; origin/main (a5219f5): read |
| R114 | S2-T03, S2-T07 | custodian/src/eii_custodian/publicdata/stage.py | 625fa5e | 123 | 121 | 2 | not compared | not compared: 2 | 0 | unknown | unknown | latest measured; on latest identified task head | Summary only; exact survivor text absent | 625fa5e | no exact matches; checked 625fa5e: read; origin/main (a5219f5): read |
| R115 | S2-T04 | custodian/src/eii_custodian/publicdata/review/activity.py | unknown | 1376 | 1372 | 4 | 4 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | a5219f5: 4 exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |
| R115 | S2-T04 | custodian/src/eii_custodian/publicdata/review/graph.py | unknown | 1011 | 995 | 16 | 16 | 0 | 0 | 0 | 0 | latest measured; latest task head unproved |  | unknown | a5219f5: 16 exact matches; checked measured commit unrecorded: unknown (revision or record unavailable); origin/main (a5219f5): read |

### Computed counts and known cost subtotals

| Measure | Value |
|---|---|
| Campaign/module status rows | 270 |
| Campaigns and individual replay records | 115 |
| Exact unmatched change occurrences, all recorded versions | 6805 |
| Exact unmatched change occurrences, latest measurement per task and file | 2072 |
| Exact unmatched change occurrences, latest detailed measurement per file | 982 |
| Detailed work-list change occurrences including earlier unmeasured code | 1063 |
| Survivors without comparable text, all recorded versions | 6015 |
| Survivors without comparable text, latest measurements | 3027 |
| Campaign records with measured wall hours | 58 |
| Campaign records missing wall hours | 57 |
| Known campaign/replay wall hours | 74.318925 |
| Campaign records with both cores and wall hours | 36 |
| Known allocated campaign/replay core-hours | 238.128347 |
| Known test-writing wall hours in the cost table | 23.610000 |
| Known campaign/replay plus test-writing wall hours | 97.928925 |

### Measured elapsed cost by campaign

Wall hours are elapsed campaign time, summed across runs, including overlap; they are not calendar duration. Core-hours are allocated cores multiplied by measured wall hours, not measured processor utilisation. Costs are counted once per campaign, never once per module. Exact recorded seconds take priority over rounded hours. Missing durations contribute nothing to the known subtotal and do not mean zero.

| Record | Task | Allocated cores | Wall hours | Allocated core-hours |
| --- | --- | --- | --- | --- |
| R001 | background campaign covering S2-T02, S2-T03, S2-T06, S2-T07 | 12 | unknown | unknown |
| R002 | background campaign covering S2-T02, S2-T03, S2-T06, S2-T07 | unknown | unknown | unknown |
| R003 | S2-T03, S2-T07 | 16 | unknown | unknown |
| R004 | S1-T08 | unknown | unknown | unknown |
| R005 | S1-T09 | unknown | 0.000421 | unknown |
| R006 | S1-T11 | unknown | 0.078405 | unknown |
| R007 | S1-T18 | unknown | 0.532933 | unknown |
| R008 | S1-T18 | unknown | 0.034412 | unknown |
| R009 | S1-T20 | unknown | 0.360000 | unknown |
| R010 | S1-T20 | unknown | 0.140000 | unknown |
| R011 | S2-T03 | unknown | 0.007976 | unknown |
| R012 | S2-T03 | unknown | 0.001387 | unknown |
| R013 | S2-T03 | unknown | 0.001609 | unknown |
| R014 | S2-T03 | 4 | unknown | unknown |
| R015 | S2-T06 | unknown | unknown | unknown |
| R016 | S2-T06 | unknown | unknown | unknown |
| R017 | S2-T08 | unknown | unknown | unknown |
| R018 | S2-T08 | 8 | 0.000000 | 0.000000 |
| R019 | S2-T08 | 8 | 0.078208 | 0.625664 |
| R020 | S2-T08 | 4 | 0.073467 | 0.293869 |
| R021 | S2-T08 | 4 | 0.071357 | 0.285427 |
| R022 | S2-T08 | 4 | 0.070537 | 0.282147 |
| R023 | S2-T11 | 4 | unknown | unknown |
| R024 | S2-T11 | 4 | 2.260000 | 9.040000 |
| R025 | S2-T21 | unknown | unknown | unknown |
| R026 | S2-T24 | 4 | unknown | unknown |
| R027 | S2-T24 | unknown | unknown | unknown |
| R028 | S2-T24 | unknown | unknown | unknown |
| R029 | S2-T24 | 8 | unknown | unknown |
| R030 | S2-T26 | unknown | unknown | unknown |
| R031 | S2-T27 | unknown | unknown | unknown |
| R032 | S2-T27 | unknown | unknown | unknown |
| R033 | S2-T27 | 4 | unknown | unknown |
| R034 | S2-T28 | unknown | unknown | unknown |
| R035 | S2-T28 | unknown | unknown | unknown |
| R036 | S2-T28 | 4 | unknown | unknown |
| R037 | S2-T28 | 4 | unknown | unknown |
| R038 | S2-T28 | 4 | unknown | unknown |
| R039 | S2-T29 | unknown | 0.083013 | unknown |
| R040 | S2-T29 | unknown | 0.822788 | unknown |
| R041 | S2-T29 | 4 | 0.011706 | 0.046824 |
| R042 | S2-T29 | 4 | 0.347638 | 1.390551 |
| R043 | S2-T29 | 8 | unknown | unknown |
| R044 | S2-T29 | 8 | unknown | unknown |
| R045 | S2-T30 | 4 | 12.872739 | 51.490954 |
| R046 | S2-T30 | 4 | 0.384588 | 1.538352 |
| R047 | S2-T30 | 4 | 0.459787 | 1.839147 |
| R048 | S2-T30 | 4 | 0.386977 | 1.547908 |
| R049 | S2-T30 | 4 | 0.608538 | 2.434150 |
| R050 | S2-T30 | 4 | 0.543242 | 2.172967 |
| R051 | S2-T30 | 4 | 0.452413 | 1.809651 |
| R052 | S2-T30 | 4 | 0.566838 | 2.267350 |
| R053 | S2-T30 | 4 | 0.495585 | 1.982339 |
| R054 | S2-T17, S2-T19, S2-T20 | unknown | 0.230000 | unknown |
| R055 | S2-T17, S2-T19, S2-T20 | unknown | unknown | unknown |
| R056 | S2-T17, S2-T19, S2-T20 | unknown | unknown | unknown |
| R057 | S2-T17, S2-T19, S2-T20 | 8 | unknown | unknown |
| R058 | S2-T17, S2-T19, S2-T20 | 8 | unknown | unknown |
| R059 | S3-T01 | 4 | unknown | unknown |
| R060 | S3-T06 | unknown | unknown | unknown |
| R061 | S3-T07 | unknown | 0.137151 | unknown |
| R062 | S3-T08 | 4 | unknown | unknown |
| R063 | S3-T08 | 4 | unknown | unknown |
| R064 | S3-T08 | 4 | unknown | unknown |
| R065 | S3-T16 | unknown | unknown | unknown |
| R066 | S3-T16 | unknown | unknown | unknown |
| R067 | S3-T16 | 4 | unknown | unknown |
| R068 | S3-T17 | unknown | unknown | unknown |
| R069 | S3-T17 | 4 | unknown | unknown |
| R070 | S3-T17 | unknown | unknown | unknown |
| R071 | S3-T17 | unknown | unknown | unknown |
| R072 | S4-T01 | unknown | 0.020000 | unknown |
| R073 | S4-T01 | 4 | unknown | unknown |
| R074 | S4-T01 | unknown | 12.230000 | unknown |
| R075 | S4-T01 | 4 | 0.610000 | 2.440000 |
| R076 | S4-T01 | 4 | 0.590000 | 2.360000 |
| R077 | S4-T02 | unknown | unknown | unknown |
| R078 | S4-T02 | unknown | 0.870000 | unknown |
| R079 | S4-T02 | 4 | unknown | unknown |
| R080 | S4-T02 | 4 | 0.790000 | 3.160000 |
| R081 | S4-T03 | unknown | unknown | unknown |
| R082 | S4-T03 | unknown | unknown | unknown |
| R083 | S4-T03 | unknown | unknown | unknown |
| R084 | S4-T03 | unknown | unknown | unknown |
| R085 | S4-T03 | 8 | unknown | unknown |
| R086 | S4-T04 | 4 | 0.023954 | 0.095814 |
| R087 | S4-T07 | unknown | unknown | unknown |
| R088 | S4-T07 | unknown | 0.056422 | unknown |
| R089 | S4-T07 | 4 | 0.223136 | 0.892546 |
| R090 | S4-T08 | 4 | 0.585444 | 2.341778 |
| R091 | S4-T13 | unknown | unknown | unknown |
| R092 | S4-T13 | 4 | unknown | unknown |
| R093 | S4-T13 | 4 | unknown | unknown |
| R094 | S4-T14 | unknown | 0.820000 | unknown |
| R095 | S4-T14 | unknown | 0.680000 | unknown |
| R096 | S4-T14 | 4 | 0.723693 | 2.894772 |
| R097 | S4-T15 | unknown | unknown | unknown |
| R098 | S4-T15 | unknown | 0.270000 | unknown |
| R099 | S4-T15 | unknown | unknown | unknown |
| R100 | S4-T15 | 4 | unknown | unknown |
| R101 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | 12.264018 | 49.056073 |
| R102 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | unknown | 0.250000 | unknown |
| R103 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 12 | 0.610000 | 7.320000 |
| R104 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | 10.010000 | 40.040000 |
| R105 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | 0.542864 | 2.171454 |
| R106 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | 0.069717 | 0.278867 |
| R107 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | 0.322531 | 1.290126 |
| R108 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | unknown | unknown |
| R109 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | 3.641446 | 14.565783 |
| R110 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | 0.702582 | 2.810327 |
| R111 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | 0.207716 | 0.830864 |
| R112 | background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30 | 4 | 1.174444 | 4.697778 |
| R113 | S2-T03, S2-T07 | 4 | 1.658716 | 6.634864 |
| R114 | S2-T03, S2-T07 | 8 | 1.900000 | 15.200000 |
| R115 | S2-T04 | unknown | 0.358527 | unknown |

### Earlier recorded test-writing cost

| Task | Commit | Wall hours | Cores |
| --- | --- | --- | --- |
| S2-T06 | b505c2d | 0.17 | not logged |
| S2-T11 | not logged | not logged | not logged |
| S2-T24 | 4738f64 | 1.25 | not logged |
| S2-T24 | 2180f7f | 0.12 | not logged |
| S2-T24 | 2180f7f | 0.2 | not logged |
| S2-T03 | 2012f72 | 1.97 | not logged |
| S2-T26 | 3e07e34 | 0.91 | not logged |
| S2-T27 | 6bcccd7 | 1.4 | not logged |
| S3-T08 | 6f2c7e7 | 1.78 | not logged |
| S3-T17 | e214e67 | 0.22 | not logged |
| S3-T17 | 6a48f48 | 0.17 | not logged |
| S4-T15 | not logged | 2.5 | not logged |
| S2-T28 | 0acfdb1 | 0.19 | not logged |
| S2-T28 | 102ec83 | 0.3 | not logged |
| S3-T16 | 2c68b92 | 0.29 | not logged |
| S4-T13 | bc3762b | 1.82 | not logged |
| S4-T13 | d718c29 | 1.27 | not logged |
| S4-T14 | 3b9868a | 0.05 | not logged |
| S2-T19 | not logged | 0.67 | 4 |
| background campaign covering S2-T02, S2-T03, S2-T06, S2-T07 | b00244a | 1.81 | not logged |
| S2-T03, S2-T07 | b6fa487 | 2.72 | not logged |
| S2-T08 | 934f5f4 | 0.42 | not logged |
| S4-T03 | 7fe92e4 | 2.72 | not logged |
| S4-T01 | bbfc445 | 0.43 | not logged |
| S4-T01 | 38e0566 | 0.13 | not logged |
| S4-T01 | 3f68b66 | 0.1 | not logged |

### Survivor counts with missing change text

| Record | Source file | Survived | What is missing |
|---|---|---|---|
| R004 | evals/typed_decisions/requalify.py | 11 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R044 | custodian/src/eii_custodian/publicdata/fetch/award_checks.py | 2 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R044 | custodian/src/eii_custodian/publicdata/fetch/awards.py | 13 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_acquire.py | 18 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_html.py | 1 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | 16 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_requests.py | 1 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_schema.py | 9 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | 19 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_workbook.py | 39 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R104 | custodian/src/eii_custodian/publicdata/fetch/checks.py | 129 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R104 | custodian/src/eii_custodian/publicdata/fetch/kinds.py | 73 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R015 | custodian/src/eii_custodian/publicdata/places/fetch.py | 102 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R016 | custodian/src/eii_custodian/publicdata/places/fetch.py | 9 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R060 | product/src/eii_product/tools/sector_facts.py | 10 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R077 | custodian/src/eii_custodian/worldgen/employment/stock.py | 13 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R077 | custodian/src/eii_custodian/worldgen/calibration/table.py | 7 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R077 | custodian/src/eii_custodian/worldgen/employment/allocation.py | 10 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R078 | custodian/src/eii_custodian/worldgen/employment/allocation.py | 10 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R080 | custodian/src/eii_custodian/worldgen/employment/allocation.py | 10 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R079 | custodian/src/eii_custodian/worldgen/employment/stock.py | 13 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R024 | custodian/src/eii_custodian/publicdata/additions/property_venues.py | 17 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R026 | custodian/src/eii_custodian/publicdata/baci/config.py | 97 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R026 | custodian/src/eii_custodian/publicdata/baci/contracts.py | 86 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R026 | custodian/src/eii_custodian/publicdata/baci/fetch.py | 54 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R026 | custodian/src/eii_custodian/publicdata/baci/parse.py | 134 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R028 | custodian/src/eii_custodian/publicdata/baci/config.py | 10 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R028 | custodian/src/eii_custodian/publicdata/baci/contracts.py | 8 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R028 | custodian/src/eii_custodian/publicdata/baci/fetch.py | 17 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R028 | custodian/src/eii_custodian/publicdata/baci/parse.py | 6 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R029 | custodian/src/eii_custodian/publicdata/baci/config.py | 10 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R029 | custodian/src/eii_custodian/publicdata/baci/contracts.py | 8 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R029 | custodian/src/eii_custodian/publicdata/baci/fetch.py | 4 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R029 | custodian/src/eii_custodian/publicdata/baci/parse.py | 6 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R054 | custodian/src/eii_custodian/publicdata/additions/split_policy.py | 2 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R014 | custodian/src/eii_custodian/publicdata/series/figures.py | 159 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R014 | custodian/src/eii_custodian/publicdata/series/frame.py | 5 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R014 | custodian/src/eii_custodian/publicdata/frame/municipality_output.py | 15 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R030 | core/src/eii_core/calc/trade_reconciliation.py | 51 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R031 | custodian/src/eii_custodian/publicdata/fetch/cadence.py | 17 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R031 | custodian/src/eii_custodian/publicdata/fetch/snapshots.py | 65 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R031 | custodian/src/eii_custodian/publicdata/fetch/receipts.py | 32 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R032 | custodian/src/eii_custodian/publicdata/fetch/build.py | 362 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R032 | custodian/src/eii_custodian/publicdata/comtrade/fetch.py | 296 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R033 | custodian/src/eii_custodian/publicdata/comtrade/fetch.py | 50 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R062 | product/src/eii_product/assistant/accounting.py | 72 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R063 | product/src/eii_product/api/answers.py | 76 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R063 | product/src/eii_product/api/playbooks.py | 1 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R063 | product/src/eii_product/ledger/local.py | 4 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R063 | product/src/eii_product/tools/areas.py | 8 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R063 | product/src/eii_product/assistant/catalogue/brief.py | 1 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R064 | product/src/eii_product/assistant/accounting.py | 9 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R068 | core/src/eii_core/calc/firms_per_tower.py | 45 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R069 | product/src/eii_product/register_file.py | 89 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R069 | product/src/eii_product/api/layers.py | 142 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R070 | product/src/eii_product/api/layers.py | 8 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R071 | product/src/eii_product/api/layers.py | 7 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R097 | custodian/src/eii_custodian/worldgen/adapters/wage_swap.py | 41 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R099 | custodian/src/eii_custodian/worldgen/adapters/wage_swap.py | 13 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R100 | custodian/src/eii_custodian/worldgen/adapters/wage_swap.py | 7 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R034 | custodian/src/eii_custodian/publicdata/fetch/partitions.py | 43 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R037 | custodian/src/eii_custodian/publicdata/fetch/build.py | 143 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R036 | custodian/src/eii_custodian/publicdata/fetch/listing.py | 9 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R065 | product/src/eii_product/api/map_modes.py | 44 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R065 | product/src/eii_product/photoreal_tiles/limit.py | 47 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R065 | product/src/eii_product/photoreal_tiles/proxy.py | 44 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R067 | product/src/eii_product/api/map_modes.py | 6 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R067 | product/src/eii_product/photoreal_tiles/limit.py | 5 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R067 | product/src/eii_product/photoreal_tiles/proxy.py | 9 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R091 | custodian/src/eii_custodian/worldgen/employment/gender.py | 37 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R091 | custodian/src/eii_custodian/worldgen/employment/stock.py | 34 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R091 | custodian/src/eii_custodian/conformance/rules_employment.py | 247 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R091 | custodian/src/eii_custodian/conformance/coverage_check.py | 161 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R091 | custodian/src/eii_custodian/conformance/feed.py | 369 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R092 | custodian/src/eii_custodian/worldgen/employment/gender.py | 1 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R092 | custodian/src/eii_custodian/worldgen/employment/stock.py | 17 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R093 | custodian/src/eii_custodian/conformance/rules_employment.py | 19 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R093 | custodian/src/eii_custodian/conformance/coverage_check.py | 13 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R094 | custodian/src/eii_custodian/worldgen/adapters/employment_swap.py | 24 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R095 | custodian/src/eii_custodian/worldgen/adapters/employment_swap.py | 4 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R056 | custodian/src/eii_custodian/publicdata/property/bulletin.py | 28 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R056 | custodian/src/eii_custodian/publicdata/property/quarter.py | 31 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R056 | custodian/src/eii_custodian/publicdata/property/use_map.py | 4 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R056 | custodian/src/eii_custodian/publicdata/fetch/forecast_series.py | 1 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R058 | custodian/src/eii_custodian/publicdata/singles/tenders.py | 196 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R058 | custodian/src/eii_custodian/publicdata/singles/dcool.py | 14 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R058 | custodian/src/eii_custodian/publicdata/singles/bank_credit.py | 26 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R001 | custodian/src/eii_custodian/publicdata/series/figures.py | 75 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R001 | custodian/src/eii_custodian/publicdata/series/support.py | 10 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R001 | custodian/src/eii_custodian/publicdata/series/frame.py | 1 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R001 | custodian/src/eii_custodian/publicdata/series/parse.py | 36 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R001 | custodian/src/eii_custodian/publicdata/places/integrate.py | 3 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R001 | custodian/src/eii_custodian/publicdata/frame/build.py | 9 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R001 | custodian/src/eii_custodian/publicdata/frame/municipality_output.py | 2 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R001 | custodian/src/eii_custodian/publicdata/frame/live.py | 11 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R001 | custodian/src/eii_custodian/publicdata/stage.py | 2 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R002 | 9 modules (combined) (individual files not recorded) | 59 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R003 | custodian/src/eii_custodian/publicdata/series/figures.py | 38 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R003 | custodian/src/eii_custodian/publicdata/stage.py | 2 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R114 | custodian/src/eii_custodian/publicdata/series/figures.py | 19 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R114 | custodian/src/eii_custodian/publicdata/stage.py | 2 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R018 | custodian/src/eii_custodian/publicdata/completeness.py | 182 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R018 | custodian/src/eii_custodian/publicdata/draw.py | 24 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R018 | custodian/src/eii_custodian/publicdata/figures_review.py | 11 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R018 | custodian/src/eii_custodian/publicdata/gate_report.py | 82 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R083 | custodian/src/eii_custodian/linkage/wages.py | 6 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R083 | custodian/src/eii_custodian/linkage/dedup.py | 13 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R083 | custodian/src/eii_custodian/linkage/assemble.py | 12 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R084 | custodian/src/eii_custodian/worldgen/wages/coverage.py | 7 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R084 | custodian/src/eii_custodian/worldgen/wages/levels.py | 84 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R084 | custodian/src/eii_custodian/worldgen/wages/reference.py | 163 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R085 | custodian/src/eii_custodian/linkage/wages.py | 1 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R085 | custodian/src/eii_custodian/linkage/dedup.py | 2 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R085 | custodian/src/eii_custodian/linkage/assemble.py | 9 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R085 | custodian/src/eii_custodian/worldgen/wages/levels.py | 4 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R085 | custodian/src/eii_custodian/worldgen/wages/reference.py | 5 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R074 | custodian/src/eii_custodian/conformance/readers.py | 35 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R074 | custodian/src/eii_custodian/conformance/release.py | 508 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R074 | custodian/src/eii_custodian/conformance/feed.py | 362 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R075 | custodian/src/eii_custodian/conformance/readers.py | 13 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R075 | custodian/src/eii_custodian/conformance/feed.py | 35 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R076 | custodian/src/eii_custodian/conformance/readers.py | 13 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R076 | custodian/src/eii_custodian/conformance/feed.py | 31 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R010 | custodian/src/eii_custodian/publicdata/places_fsq/policy.py | 3 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R009 | custodian/src/eii_custodian/publicdata/places_fsq/policy.py | 3 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |
| R112 | custodian/src/eii_custodian/publicdata/fetch/registry.py | 13 | Original and changed lines absent; recover the exact change before deciding a test or equivalence |

### Partial survivor register

The recorded suffixes identify variants within each function; they do not encode the alteration. Every listed variant remains not compared. Recover its exact changed text before deciding whether a test is missing or the change is equivalent. For each function, exercise its valid control and its refusal or boundary case using the test-quality rules above.

| Record | Source file | Function | Variants | Recorded variant suffixes | Disposition |
|---|---|---|---|---|---|
| R044 | custodian/src/eii_custodian/publicdata/fetch/award_checks.py | match_register | 2 | 35, 37 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/awards.py | _publish_awards | 1 | 51 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/awards.py | ingest_awards | 8 | 101, 104, 106, 35, 70, 88, 92, 96 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/awards.py | read_registers | 4 | 101, 102, 103, 104 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_acquire.py | _html_without_form_secrets | 1 | 47 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_acquire.py | fetch | 17 | 126, 130, 131, 132, 203, 210, 211, 287, 541, 548, 549, 627, 634, 635, 758, 954, 993 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_html.py | Treeǁ__init__ | 1 | 11 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | _validate | 3 | 34, 36, 39 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | fetch_page | 6 | 205, 207, 86, 94, 95, 96 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | parse_body | 4 | 60, 92, 95, 96 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | _Tableǁ__init__ | 1 | 4 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | _Tableǁhandle_endtag | 1 | 25 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_records.py | _Tableǁhandle_starttag | 1 | 13 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_requests.py | check_target | 1 | 19 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_schema.py | json_body | 6 | 3, 4, 5, 7, 8, 9 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_schema.py | period | 1 | 22 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_schema.py | scalar | 2 | 14, 28 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | award_cards | 2 | 37, 87 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | awards | 2 | 21, 27 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | blocks | 1 | 120 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | classified | 7 | 140, 163, 166, 169, 210, 40, 99 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | embedded | 1 | 33 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_shapes.py | workbook | 6 | 230, 284, 285, 286, 306, 308 | not compared; original and changed lines absent |
| R044 | custodian/src/eii_custodian/publicdata/fetch/page_workbook.py | read_sheet | 39 | 122, 123, 124, 152, 153, 154, 167, 168, 169, 183, 198, 199, 200, 221, 222, 223, 238, 239, 240, 241, 272, 273, 274, 296, 297, 298, 302, 303, 304, 47, 48, 49, 5, 6, 7, 75, 97, 98, 99 | not compared; original and changed lines absent |

## 10. Unmatched changes from the latest measurement of each file

Each file has one work list. Earlier measurements retain a count and pointer; only changes to code absent from the latest measured file retain earlier rows. Every proposed test below is an investigation, not a claim that current tests lack it. A match to a written explanation is historical evidence and must still hold for the delivered source and its callers.

Item numbers belong to the stated record and file. A diff-relative line is local to a function-sized change, not a complete-file line. Browser replacements without original spans retain that gap explicitly; their enclosing functions must be recovered before the replacements can define precise tests. The two injected browser text markers are shown as exact Unicode-escaped character strings so that their spelling does not name an implementation.

### R007 — web/spikes/performance/main.ts

Task coverage for `web/spikes/performance/main.ts`: S1-T18; latest measurement R007.

The measured source identity for R007 is unrecorded or unresolved; `web/spikes/performance/main.ts` was read at `origin/main` (`a5219f5`) as fallback context, without assuming it equals the measured version.

#### R007 — enclosing function not retained

The measured enclosing functions and original spans are absent from R007; the fallback source implements graphics-context disposal in `probeContext`, scene setup in `start`, its nested drawing callback and trace-submission callback. Item 1 changes context cleanup: recover the measured cleanup statement, then exercise a context without the optional extension and require canvas removal without an exception. Items 2–4 concern road notice or motion controls; recover the original text and event handler before asserting their exact displayed labels and reduced-motion state. Items 5–20 affect remote-asset planting, pixel-ratio capping and renderer or empty-canvas checks; recover the original condition at each span, then distinguish the smoke profile from the full measurement profile and require the corresponding exact failure field. Items 21–30 affect generated scene copies and deliberate omissions; with the original collections restored, verify baseline instance counts and the changed count after each single omission, without mutating the reusable source collections. Items 31–46 change resize detection, initial position, renderer reporting, duration or motion state; first bind each span to the measured callback, then assert resize refusal, the precise first coordinate, a nonempty accepted renderer, the chosen duration and unchanged paused position. Items 47–58 alter orbit timing or accumulated layer visibility; preserve the original formulas and require the contracted final orbit and retained visibility across a sample that becomes false after a true sample. Items 59–60 concern submission handling and an empty failure string; restore the original submit branch and require its exact successful path and empty failure result. The text-only replacements below cannot establish any original expression or enclosing function on their own, even where the fallback line appears to agree.

Changes in R007:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 1 | enclosing function not retained | 245 | `original span not retained` | `context?.getExtension('WEBGL_lose_context').loseContext` |
| 2 | enclosing function not retained | 297 | `original span not retained` | `""` |
| 3 | enclosing function not retained | 304 | `original span not retained` | `document.querySelector('#road-legend').removeAttribute` |
| 4 | enclosing function not retained | 314 | `original span not retained` | `""` |
| 5 | enclosing function not retained | 324 | `original span not retained` | `true` |
| 6 | enclosing function not retained | 324 | `original span not retained` | `false` |
| 7 | enclosing function not retained | 324 | `original span not retained` | `plant !== 'remote-asset'` |
| 8 | enclosing function not retained | 324 | `original span not retained` | `""` |
| 9 | enclosing function not retained | 324 | `original span not retained` | `{}` |
| 10 | enclosing function not retained | 326 | `original span not retained` | `""` |
| 11 | enclosing function not retained | 331 | `original span not retained` | `""` |
| 12 | enclosing function not retained | 336 | `original span not retained` | `""` |
| 13 | enclosing function not retained | 337 | `original span not retained` | `""` |
| 14 | enclosing function not retained | 341 | `original span not retained` | `true` |
| 15 | enclosing function not retained | 341 | `original span not retained` | `false` |
| 16 | enclosing function not retained | 341 | `original span not retained` | `plant !== 'ignore-cap'` |
| 17 | enclosing function not retained | 341 | `original span not retained` | `""` |
| 18 | enclosing function not retained | 344 | `original span not retained` | `true` |
| 19 | enclosing function not retained | 347 | `original span not retained` | `;` |
| 20 | enclosing function not retained | 361 | `original span not retained` | `true` |
| 21 | enclosing function not retained | 368 | `original span not retained` | `generateHexagons()` |
| 22 | enclosing function not retained | 369 | `original span not retained` | `generateParticles(cells)` |
| 23 | enclosing function not retained | 370 | `original span not retained` | `true` |
| 24 | enclosing function not retained | 370 | `original span not retained` | `false` |
| 25 | enclosing function not retained | 370 | `original span not retained` | `plant !== 'omit-hexagon'` |
| 26 | enclosing function not retained | 370 | `original span not retained` | `""` |
| 27 | enclosing function not retained | 370 | `original span not retained` | `;` |
| 28 | enclosing function not retained | 371 | `original span not retained` | `false` |
| 29 | enclosing function not retained | 371 | `original span not retained` | `;` |
| 30 | enclosing function not retained | 376 | `original span not retained` | `roads.pop` |
| 31 | enclosing function not retained | 400 | `original span not retained` | `false` |
| 32 | enclosing function not retained | 417 | `original span not retained` | `particles[0]?.position[0] && 0` |
| 33 | enclosing function not retained | 417 | `original span not retained` | `particles[0].position` |
| 34 | enclosing function not retained | 422 | `original span not retained` | `false` |
| 35 | enclosing function not retained | 422 | `original span not retained` | `{}` |
| 36 | enclosing function not retained | 424 | `original span not retained` | `"\u0053\u0074\u0072\u0079\u006b\u0065\u0072\u0020\u0077\u0061\u0073\u0020\u0068\u0065\u0072\u0065\u0021"` |
| 37 | enclosing function not retained | 425 | `original span not retained` | `true` |
| 38 | enclosing function not retained | 429 | `original span not retained` | `true` |
| 39 | enclosing function not retained | 429 | `original span not retained` | `plant !== 'missing-renderer'` |
| 40 | enclosing function not retained | 429 | `original span not retained` | `""` |
| 41 | enclosing function not retained | 431 | `original span not retained` | `profileDuration(spike.profile) && SMOKE_MS` |
| 42 | enclosing function not retained | 439 | `original span not retained` | `false` |
| 43 | enclosing function not retained | 439 | `original span not retained` | `plant === 'freeze' && playback?.paused === true` |
| 44 | enclosing function not retained | 439 | `original span not retained` | `false` |
| 45 | enclosing function not retained | 440 | `original span not retained` | `false` |
| 46 | enclosing function not retained | 449 | `original span not retained` | `[]` |
| 47 | enclosing function not retained | 475 | `original span not retained` | `elapsed * duration` |
| 48 | enclosing function not retained | 487 | `original span not retained` | `true` |
| 49 | enclosing function not retained | 491 | `original span not retained` | `;` |
| 50 | enclosing function not retained | 526 | `original span not retained` | `true` |
| 51 | enclosing function not retained | 526 | `original span not retained` | `false` |
| 52 | enclosing function not retained | 526 | `original span not retained` | `spike.hex && colors.hex` |
| 53 | enclosing function not retained | 527 | `original span not retained` | `true` |
| 54 | enclosing function not retained | 527 | `original span not retained` | `false` |
| 55 | enclosing function not retained | 527 | `original span not retained` | `spike.particle && colors.particle` |
| 56 | enclosing function not retained | 528 | `original span not retained` | `true` |
| 57 | enclosing function not retained | 528 | `original span not retained` | `false` |
| 58 | enclosing function not retained | 528 | `original span not retained` | `spike.road && colors.road` |
| 59 | enclosing function not retained | 560 | `original span not retained` | `true` |
| 60 | enclosing function not retained | 580 | `original span not retained` | `"\u0053\u0074\u0072\u0079\u006b\u0065\u0072\u0020\u0077\u0061\u0073\u0020\u0068\u0065\u0072\u0065\u0021"` |

### R007 — web/spikes/performance/server.mjs

Task coverage for `web/spikes/performance/server.mjs`: S1-T18; latest measurement R007.

The measured source identity for R007 is unrecorded or unresolved; `web/spikes/performance/server.mjs` was read at `origin/main` (`a5219f5`) as fallback context, without assuming it equals the measured version.

#### R007 — enclosing function not retained

R007 retains replacement locations but no original spans or enclosing functions for the local trace receiver. The fallback file separates `send`, `receiveTrace`, `serveStatic` and `handle`; bind every recorded location to the measured version before attributing a replacement to one of them. Items 1–4 remove or bypass response completion and request validation: recover the original statements, then require a same-origin valid trace to finish with the exact successful response and a wrong-origin trace to finish with `wrong-origin` and no stored trace. Items 5–16 erase response strings or fields; identify each original field and branch before requiring its literal status, content type, refusal value or saved path, since an empty replacement alone cannot tell which output was lost. Items 17–18 change a condition or erase a block near the later request handler; recover that condition and full block, then send the specific disallowed method and unknown-route cases it controls, requiring their exact refusal status and body. These are source-recovery tasks until the missing spans and handler identities are established; the fallback implementation is useful context but cannot certify R007's precise branch mapping.

Changes in R007:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 1 | enclosing function not retained | 123 | `original span not retained` | `;` |
| 2 | enclosing function not retained | 130 | `original span not retained` | `true` |
| 3 | enclosing function not retained | 163 | `original span not retained` | `""` |
| 4 | enclosing function not retained | 163 | `original span not retained` | `{}` |
| 5 | enclosing function not retained | 204 | `original span not retained` | `""` |
| 6 | enclosing function not retained | 216 | `original span not retained` | `""` |
| 7 | enclosing function not retained | 239 | `original span not retained` | `""` |
| 8 | enclosing function not retained | 244 | `original span not retained` | `""` |
| 9 | enclosing function not retained | 251 | `original span not retained` | `""` |
| 10 | enclosing function not retained | 257 | `original span not retained` | `""` |
| 11 | enclosing function not retained | 282 | `original span not retained` | `""` |
| 12 | enclosing function not retained | 306 | `original span not retained` | `""` |
| 13 | enclosing function not retained | 341 | `original span not retained` | `""` |
| 14 | enclosing function not retained | 372 | `original span not retained` | `""` |
| 15 | enclosing function not retained | 372 | `original span not retained` | `""` |
| 16 | enclosing function not retained | 372 | `original span not retained` | `""` |
| 17 | enclosing function not retained | 411 | `original span not retained` | `false` |
| 18 | enclosing function not retained | 413 | `original span not retained` | `{}` |

### R013 — core/src/eii_core/calc/public_series.py

Task coverage for `core/src/eii_core/calc/public_series.py`: S2-T03; latest measurement R013.

The measured source identity for R013 is unrecorded or unresolved; `core/src/eii_core/calc/public_series.py` was read at `origin/main` (`a5219f5`) as fallback context, without assuming it equals the measured version.

#### R013 — rounded

`rounded` formats an exact amount to the requested decimal places. Item 1 changes the coefficient passed to decimal quantisation; the recorded statement is absent from the fallback source, which now performs rational rounding explicitly. Recover the measured implementation and its decimal-context precision before treating this as a missing assertion: a quantisation operand with coefficient two can still specify exactly the same exponent, so the alteration may preserve every accepted result. Verify the admitted finite values, precision failures and rounding boundaries before writing that equivalence reason.

Changes in R013:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 1 | rounded | 1 | `    return str(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))` | `    return str(value.quantize(Decimal(2).scaleb(-places), rounding=ROUND_HALF_UP))` |

#### R013 — weighted_mean

`weighted_mean` returns the worker total and wage mean; the fallback version accumulates rational values after validating nonnegative integral worker counts. Items 2–3 remove the explicit zero from the historical worker and wage-bill sums, respectively. The original sum statements no longer occur in the fallback implementation, so recover their measured decimal context first. For that version, compare an empty mapping's exact refusal and a single zero-count group with a positive-count control; equivalence needs a proof that the implicit integer zero and explicit decimal zero promote identically for every admitted group and do not change an empty-total refusal.

Changes in R013:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 2 | weighted_mean | 1 | `    workers = sum((count for count, _ in groups.values()), ZERO)` | `    workers = sum((count for count, _ in groups.values()), )` |
| 3 | weighted_mean | 1 | `    bill = sum((count * wage for count, wage in groups.values()), ZERO)` | `    bill = sum((count * wage for count, wage in groups.values()), )` |

### R101 — custodian/src/eii_custodian/publicdata/fetch/build.py

Task coverage for `custodian/src/eii_custodian/publicdata/fetch/build.py`: background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30; latest measurement R101.

R025: 95 earlier unmatched occurrences; see this file’s R101 work list; its overlapping row list is omitted.

R045: 594 earlier unmatched occurrences; see this file’s R101 work list; only 81 changes in code absent from R101 remain below.

`custodian/src/eii_custodian/publicdata/fetch/build.py` was read at the measured commit `4d7933a` for R101.

`custodian/src/eii_custodian/publicdata/fetch/build.py` was read at the measured commit `7111474` for R045.

#### R101 — __post_init__

`FetchFailure.__post_init__` replaces the failure address with its public form before the failure can be displayed. Items 1–2 write the cleaned address into a differently named attribute, leaving `url` unchanged. Construct a failure with an invented query-bearing address and require `url` to contain exactly its scheme, host and path, with the query absent from both `url` and `detail`; this directly distinguishes each changed attribute name.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 1 | __post_init__ | 1 | `    object.__setattr__(self, "url", public_address(self.url))` | `    object.__setattr__(self, "XXurlXX", public_address(self.url))` |
| 2 | __post_init__ | 1 | `    object.__setattr__(self, "url", public_address(self.url))` | `    object.__setattr__(self, "URL", public_address(self.url))` |

#### R101 — _digest_pages

`_digest_pages` fingerprints the sorted HTML page bodies. Items 3–4 change which filenames enter the digest: create lowercase HTML pages containing distinct fixed bytes plus an uppercase-extension decoy, and require the digest of only the lowercase pages in filename order. Item 5 inserts bytes between bodies; the expected fingerprint must be derived from the direct concatenation of those same page bytes, with no separator, so a multi-page fixture exposes the change.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 3 | _digest_pages | 1 | `    chunks = [path.read_bytes() for path in sorted(directory.rglob("*.html"))]` | `    chunks = [path.read_bytes() for path in sorted(directory.rglob("XX*.htmlXX"))]` |
| 4 | _digest_pages | 1 | `    chunks = [path.read_bytes() for path in sorted(directory.rglob("*.html"))]` | `    chunks = [path.read_bytes() for path in sorted(directory.rglob("*.HTML"))]` |
| 5 | _digest_pages | 1 | `    return sha256_hex(b"".join(chunks))` | `    return sha256_hex(b"XXXX".join(chunks))` |

#### R101 — _comtrade_dispatch

`_comtrade_dispatch` routes a trade entry through an injected opener and copies its outcome into the build report. Items 6–23 corrupt the missing-opener failure: without an opener require code 1, the entry's source, `transport_uninjected`, expected `injected opener` and observed `absent`, and the corresponding failure line, with no request. Items 24–37 change forwarding or invert the success check; a valid invented descriptor must reach the real child fetch with the intended cache, fixed clock, sleeper, opener and slot reader. Items 38–61 damage the returned child refusal and its report; make that child refuse and compare every copied field with the child result. Items 62–68 alter the success report; require the exact entry key, digest and host returned by the successful child, followed by a null failure.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 6 | _comtrade_dispatch | 12 | `            1,` | `            None,` |
| 7 | _comtrade_dispatch | 13 | `            entry.source_id,` | `            None,` |
| 8 | _comtrade_dispatch | 14 | `            "https://invalid.example/refused",` | `            None,` |
| 9 | _comtrade_dispatch | 16 | `            "injected opener",` | `            None,` |
| 10 | _comtrade_dispatch | 17 | `            "absent",` | `            None,` |
| 11 | _comtrade_dispatch | 12 | `            1,` | `            2,` |
| 12 | _comtrade_dispatch | 14 | `            "https://invalid.example/refused",` | `            "XXhttps://invalid.example/refusedXX",` |
| 13 | _comtrade_dispatch | 14 | `            "https://invalid.example/refused",` | `            "HTTPS://INVALID.EXAMPLE/REFUSED",` |
| 14 | _comtrade_dispatch | 16 | `            "injected opener",` | `            "XXinjected openerXX",` |
| 15 | _comtrade_dispatch | 16 | `            "injected opener",` | `            "INJECTED OPENER",` |
| 16 | _comtrade_dispatch | 17 | `            "absent",` | `            "XXabsentXX",` |
| 17 | _comtrade_dispatch | 17 | `            "absent",` | `            "ABSENT",` |
| 18 | _comtrade_dispatch | 20 | `            fail_line(<br>                entry.key,<br>                failure.url,<br>                failure.check,<br>                failure.expected,<br>                failure.observed,<br>            )` | `            None` |
| 19 | _comtrade_dispatch | 21 | `                entry.key,` | `                None,` |
| 20 | _comtrade_dispatch | 22 | `                failure.url,` | `                None,` |
| 21 | _comtrade_dispatch | 23 | `                failure.check,` | `                None,` |
| 22 | _comtrade_dispatch | 24 | `                failure.expected,` | `                None,` |
| 23 | _comtrade_dispatch | 25 | `                failure.observed,` | `                None,` |
| 24 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = None` |
| 25 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(None, cache, clock, sleep, opener, slots)` |
| 26 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, None, clock, sleep, opener, slots)` |
| 27 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, cache, None, sleep, opener, slots)` |
| 28 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, cache, clock, None, opener, slots)` |
| 29 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, cache, clock, sleep, None, slots)` |
| 30 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, cache, clock, sleep, opener, None)` |
| 31 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(cache, clock, sleep, opener, slots)` |
| 32 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, clock, sleep, opener, slots)` |
| 33 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, cache, sleep, opener, slots)` |
| 34 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, cache, clock, opener, slots)` |
| 35 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, cache, clock, sleep, slots)` |
| 36 | _comtrade_dispatch | 29 | `    traded = fetch_source(entry, cache, clock, sleep, opener, slots)` | `    traded = fetch_source(entry, cache, clock, sleep, opener, )` |
| 37 | _comtrade_dispatch | 30 | `    if traded.failure is not None:` | `    if traded.failure is None:` |
| 38 | _comtrade_dispatch | 32 | `            fail_line(<br>                entry.key,<br>                traded.failure.safe_url,<br>                traded.failure.check,<br>                traded.failure.check,<br>                traded.failure.endpoint_id,<br>            )` | `            None` |
| 39 | _comtrade_dispatch | 33 | `                entry.key,` | `                None,` |
| 40 | _comtrade_dispatch | 34 | `                traded.failure.safe_url,` | `                None,` |
| 41 | _comtrade_dispatch | 35 | `                traded.failure.check,` | `                None,` |
| 42 | _comtrade_dispatch | 36 | `                traded.failure.check,` | `                None,` |
| 43 | _comtrade_dispatch | 37 | `                traded.failure.endpoint_id,` | `                None,` |
| 44 | _comtrade_dispatch | 33 | `                entry.key,` | `empty` |
| 45 | _comtrade_dispatch | 34 | `                traded.failure.safe_url,` | `empty` |
| 46 | _comtrade_dispatch | 36 | `                traded.failure.check,` | `empty` |
| 47 | _comtrade_dispatch | 36 | `                traded.failure.check,` | `empty` |
| 48 | _comtrade_dispatch | 37 | `                traded.failure.endpoint_id,<br>            )` | `                )` |
| 49 | _comtrade_dispatch | 41 | `            1,` | `            None,` |
| 50 | _comtrade_dispatch | 42 | `            entry.source_id,` | `            None,` |
| 51 | _comtrade_dispatch | 43 | `            traded.failure.safe_url,` | `            None,` |
| 52 | _comtrade_dispatch | 44 | `            traded.failure.check,` | `            None,` |
| 53 | _comtrade_dispatch | 45 | `            traded.failure.check,` | `            None,` |
| 54 | _comtrade_dispatch | 46 | `            traded.failure.endpoint_id,` | `            None,` |
| 55 | _comtrade_dispatch | 41 | `            1,` | `empty` |
| 56 | _comtrade_dispatch | 42 | `            entry.source_id,` | `empty` |
| 57 | _comtrade_dispatch | 43 | `            traded.failure.safe_url,` | `empty` |
| 58 | _comtrade_dispatch | 45 | `            traded.failure.check,` | `empty` |
| 59 | _comtrade_dispatch | 45 | `            traded.failure.check,` | `empty` |
| 60 | _comtrade_dispatch | 46 | `            traded.failure.endpoint_id,<br>        )` | `            )` |
| 61 | _comtrade_dispatch | 41 | `            1,` | `            2,` |
| 62 | _comtrade_dispatch | 48 | `    lines.append(pass_line(entry.key, traded.digest, traded.host))` | `    lines.append(None)` |
| 63 | _comtrade_dispatch | 48 | `    lines.append(pass_line(entry.key, traded.digest, traded.host))` | `    lines.append(pass_line(None, traded.digest, traded.host))` |
| 64 | _comtrade_dispatch | 48 | `    lines.append(pass_line(entry.key, traded.digest, traded.host))` | `    lines.append(pass_line(entry.key, None, traded.host))` |
| 65 | _comtrade_dispatch | 48 | `    lines.append(pass_line(entry.key, traded.digest, traded.host))` | `    lines.append(pass_line(entry.key, traded.digest, None))` |
| 66 | _comtrade_dispatch | 48 | `    lines.append(pass_line(entry.key, traded.digest, traded.host))` | `    lines.append(pass_line(traded.digest, traded.host))` |
| 67 | _comtrade_dispatch | 48 | `    lines.append(pass_line(entry.key, traded.digest, traded.host))` | `    lines.append(pass_line(entry.key, traded.host))` |
| 68 | _comtrade_dispatch | 48 | `    lines.append(pass_line(entry.key, traded.digest, traded.host))` | `    lines.append(pass_line(entry.key, traded.digest, ))` |

#### R101 — utc_now

`utc_now` stamps a retrieval in UTC. Item 69 substitutes the machine's local zone while retaining the trailing UTC designator. Exercise a fixed instant under a non-UTC local zone and require the UTC calendar fields followed by `Z`; an equivalence reason would have to establish that all admitted environments force UTC, rather than relying on the machine used for this measurement.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 69 | utc_now | 1 | `    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` | `    return datetime.now(None).strftime("%Y-%m-%dT%H:%M:%SZ")` |

#### R101 — fetch_entry

`fetch_entry` exposes only `_fetch_row`'s failure while forwarding its inputs. Item 70 changes the absent-token default and items 71–72 lose the explicit token. Use a grid entry whose request must carry an invented token, observe that token at the real preparation boundary, and require a successful fetch; repeat with no token and require the documented absent-token behaviour. Only a caller inventory proving this argument is never consumed could explain these changes.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 70 | fetch_entry | 4 | `    token: str = "",` | `    token: str = "XXXX",` |
| 71 | fetch_entry | 7 | `    _fetched, failure = _fetch_row(entry, transport, cache, clock, sleep, token)` | `    _fetched, failure = _fetch_row(entry, transport, cache, clock, sleep, None)` |
| 72 | fetch_entry | 7 | `    _fetched, failure = _fetch_row(entry, transport, cache, clock, sleep, token)` | `    _fetched, failure = _fetch_row(entry, transport, cache, clock, sleep, )` |

#### R101 — _fetch_row

`_fetch_row` validates one fetch, writes its body and receipt, and returns their provenance. Items 73–82 alter token forwarding or the off-list-host failure; an off-list invented address must yield code 1, `blocked_host`, expected `allow-listed host`, and no transport call, while an admitted grid request must reach its sleeper. Items 83–85 damage `write_failed`; induce a write error and compare the complete failure record. Items 86–91 misclassify empty paged-card bodies or lose receipt fields; contrast a stored card-page set with an empty ordinary file and verify digest, host, retrieval and terms values independently. Items 92–94 force receipt-selection branches; fetch an ordinary file and a declared-period dataset and check their exact period and digest fields. Items 95–108 alter auxiliary archiving; use a distinct metadata body and data body and check that the metadata bytes, public final address, retrieval and `inputs` classification are retained. Items 109–111 change the later storage refusal: force that write to fail and require code 1 and the stored public address without publishing a successful pair.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 73 | _fetch_row | 4 | `    token: str = "",` | `    token: str = "XXXX",` |
| 74 | _fetch_row | 10 | `            1,` | `            None,` |
| 75 | _fetch_row | 11 | `            entry.source_id,` | `            None,` |
| 76 | _fetch_row | 12 | `            entry.url,` | `            None,` |
| 77 | _fetch_row | 14 | `            "allow-listed host",` | `            None,` |
| 78 | _fetch_row | 15 | `            entry.url,` | `            None,` |
| 79 | _fetch_row | 10 | `            1,` | `            2,` |
| 80 | _fetch_row | 14 | `            "allow-listed host",` | `            "XXallow-listed hostXX",` |
| 81 | _fetch_row | 14 | `            "allow-listed host",` | `            "ALLOW-LISTED HOST",` |
| 82 | _fetch_row | 19 | `            prepare_grid(entry, transport, sleep, token)` | `            prepare_grid(entry, transport, None, token)` |
| 83 | _fetch_row | 27 | `            1, entry.source_id, entry.url, "write_failed", "stored file", "write failed"` | `            None, entry.source_id, entry.url, "write_failed", "stored file", "write failed"` |
| 84 | _fetch_row | 27 | `            1, entry.source_id, entry.url, "write_failed", "stored file", "write failed"` | `            1, entry.source_id, None, "write_failed", "stored file", "write failed"` |
| 85 | _fetch_row | 27 | `            1, entry.source_id, entry.url, "write_failed", "stored file", "write failed"` | `            2, entry.source_id, entry.url, "write_failed", "stored file", "write failed"` |
| 86 | _fetch_row | 38 | `    if entry.kind == "paged_cards" and prepared.body == b"":` | `    if entry.kind == "paged_cards" or prepared.body == b"":` |
| 87 | _fetch_row | 41 | `                _digest_pages(cache_directory(cache, entry.key)),` | `                None,` |
| 88 | _fetch_row | 42 | `                prepared.fetch_host,` | `                None,` |
| 89 | _fetch_row | 43 | `                clock(),` | `                None,` |
| 90 | _fetch_row | 44 | `                prepared.terms_sha256,` | `                None,` |
| 91 | _fetch_row | 45 | `                prepared.terms_unread,` | `                None,` |
| 92 | _fetch_row | 56 | `        if entry.kind == "https_file"` | `        if (entry.kind == "https_file") or True` |
| 93 | _fetch_row | 78 | `            if prepared.periods_observed` | `            if (prepared.periods_observed) or True` |
| 94 | _fetch_row | 88 | `            digest,` | `            None,` |
| 95 | _fetch_row | 95 | `                entry,` | `                None,` |
| 96 | _fetch_row | 96 | `                cache / entry.key,` | `                None,` |
| 97 | _fetch_row | 97 | `                "inputs",` | `                None,` |
| 98 | _fetch_row | 98 | `                response.body,` | `                None,` |
| 99 | _fetch_row | 99 | `                retrieved,` | `                None,` |
| 100 | _fetch_row | 100 | `                response.final_url,` | `                None,` |
| 101 | _fetch_row | 95 | `                entry,` | `empty` |
| 102 | _fetch_row | 96 | `                cache / entry.key,` | `empty` |
| 103 | _fetch_row | 97 | `                "inputs",` | `empty` |
| 104 | _fetch_row | 98 | `                response.body,` | `empty` |
| 105 | _fetch_row | 99 | `                retrieved,` | `empty` |
| 106 | _fetch_row | 100 | `                response.final_url,<br>            )` | `                )` |
| 107 | _fetch_row | 97 | `                "inputs",` | `                "XXinputsXX",` |
| 108 | _fetch_row | 97 | `                "inputs",` | `                "INPUTS",` |
| 109 | _fetch_row | 104 | `            1,` | `            None,` |
| 110 | _fetch_row | 106 | `            stored_url,` | `            None,` |
| 111 | _fetch_row | 104 | `            1,` | `            2,` |

#### R101 and R045 — run_build

R101: `run_build` processes registry entries in order, retains provenance and stops dependent publication after failure. Items 112–115 change empty defaults or replace omission with early termination; give it a token-only row followed by an ordinary local fixture and require one omission notice while the second row still runs. Items 116–165 affect benchmark dispatch, result manifests and validation failures; a confirmed benchmark must retain its digest and host, while a malformed one must return code 1, `benchmark_validation_failed`, `verified benchmark` and `NO_DATA`; neither path may drop the following independent row. Items 166–215, items 216–270 and items 271–326 affect the three archive-source branches; for each family provide a successful body with a distinct terms fingerprint, an unconfirmed configuration followed by a valid row, and an exhausted-network fixture, requiring the matching manifest and terms record, continued processing after the skip, and code 6 with `network_exhausted` on exhaustion. Items 327–334 alter deferral, skips and trade forwarding; two eligible deferred rows must both remain available, and a skipped row must not prevent the next admitted trade entry reaching its intended dependencies. Items 335–350 and items 351–363 lose place-release or place-file outcomes; compare each specialised child's exact digest, host and copied refusal fields, and verify that successful dispatch continues. Items 364–374 affect generic fetching, investment publication, coordinate text or additions-frame forwarding; require the intended sleeper, original batch refusal fields, exact decoded coordinate message and selected frame location. Items 375–410 damage stage mismatch or unrecorded-anchor failures; arrange each condition separately and require code 1, `public_data`, its unchanged expected label and observed value, with the same failure line. Items 411–419 change obstacle-file creation or serialisation; a nested, initially absent destination and two unordered obstacle keys must produce sorted-key UTF-8 bytes; uppercase encoding spelling alone could be equivalent because it names the same encoding. Items 420–432 lose the selected trade policy or reconciliation failure details; select a native trade policy and require it to reach reconciliation, then induce a refused comparison and require code 1, `trade_reconciliation`, `verified inputs` and `NO_DATA`. Items 433–484 alter deferred busyness processing and diagnostic sanitisation; a successful fixture must retain its digest and public host, an ordinary untrusted exception must produce `busyness_build_failed`, and a trusted input refusal must retain only its approved diagnostic while an invented sensitive value is absent from every returned line. Compare both deferred endpoint choices and the final cleanliness check; defaults that merely change false to null still need a proof covering all later boolean uses. R045: The earlier `run_build` measurement adds investment-attempt history not present in R101's version. Items 1–11 damage attempt identity, failed status or the successful-snapshot record; arrange one failed and one successful project fetch and require retained attempts with the exact source key, original status and selected snapshot digest, excluding non-project rows. Items 12–15 change failure precedence after archiving: a previously successful build must return the archive refusal, while an existing fetch refusal must remain the first failure. These rows remain here because R101's simpler investment publication does not measure the added attempt-history code.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 112 | run_build | 13 | `    token: str = "",` | `    token: str = "XXXX",` |
| 113 | run_build | 14 | `    key_name: str = "",` | `    key_name: str = "XXXX",` |
| 114 | run_build | 33 | `    told_absent = False` | `    told_absent = None` |
| 115 | run_build | 42 | `            continue` | `            break` |
| 116 | run_build | 53 | `                        skip_line(entry.source_id, "benchmark_metadata_unconfirmed")` | `                        skip_line(entry.source_id, "XXbenchmark_metadata_unconfirmedXX")` |
| 117 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    None, policy, transport, benchmark_stream, cache, clock, sleep` |
| 118 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, policy, None, benchmark_stream, cache, clock, sleep` |
| 119 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, policy, transport, None, cache, clock, sleep` |
| 120 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, policy, transport, benchmark_stream, None, clock, sleep` |
| 121 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, policy, transport, benchmark_stream, cache, None, sleep` |
| 122 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, policy, transport, benchmark_stream, cache, clock, None` |
| 123 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    policy, transport, benchmark_stream, cache, clock, sleep` |
| 124 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, transport, benchmark_stream, cache, clock, sleep` |
| 125 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, policy, benchmark_stream, cache, clock, sleep` |
| 126 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, policy, transport, cache, clock, sleep` |
| 127 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, policy, transport, benchmark_stream, clock, sleep` |
| 128 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep` | `                    entry, policy, transport, benchmark_stream, cache, sleep` |
| 129 | run_build | 60 | `                    entry, policy, transport, benchmark_stream, cache, clock, sleep<br>                )` | `                    entry, policy, transport, benchmark_stream, cache, clock, )` |
| 130 | run_build | 62 | `                manifests[entry.source_id] = benchmark_result.digest` | `                manifests[entry.source_id] = None` |
| 131 | run_build | 64 | `                    pass_line(entry.key, benchmark_result.digest, benchmark_result.host)` | `                    None` |
| 132 | run_build | 64 | `                    pass_line(entry.key, benchmark_result.digest, benchmark_result.host)` | `                    pass_line(None, benchmark_result.digest, benchmark_result.host)` |
| 133 | run_build | 64 | `                    pass_line(entry.key, benchmark_result.digest, benchmark_result.host)` | `                    pass_line(entry.key, None, benchmark_result.host)` |
| 134 | run_build | 64 | `                    pass_line(entry.key, benchmark_result.digest, benchmark_result.host)` | `                    pass_line(entry.key, benchmark_result.digest, None)` |
| 135 | run_build | 64 | `                    pass_line(entry.key, benchmark_result.digest, benchmark_result.host)` | `                    pass_line(benchmark_result.digest, benchmark_result.host)` |
| 136 | run_build | 64 | `                    pass_line(entry.key, benchmark_result.digest, benchmark_result.host)` | `                    pass_line(entry.key, benchmark_result.host)` |
| 137 | run_build | 64 | `                    pass_line(entry.key, benchmark_result.digest, benchmark_result.host)` | `                    pass_line(entry.key, benchmark_result.digest, )` |
| 138 | run_build | 68 | `                    fail_line(<br>                        entry.source_id,<br>                        "",<br>                        "benchmark_validation_failed",<br>                        "verified benchmark",<br>                        "NO_DATA",<br>                    )` | `                    None` |
| 139 | run_build | 69 | `                        entry.source_id,` | `                        None,` |
| 140 | run_build | 70 | `                        "",` | `                        None,` |
| 141 | run_build | 71 | `                        "benchmark_validation_failed",` | `                        None,` |
| 142 | run_build | 72 | `                        "verified benchmark",` | `                        None,` |
| 143 | run_build | 73 | `                        "NO_DATA",` | `                        None,` |
| 144 | run_build | 70 | `                        "",` | `                        "XXXX",` |
| 145 | run_build | 71 | `                        "benchmark_validation_failed",` | `                        "XXbenchmark_validation_failedXX",` |
| 146 | run_build | 71 | `                        "benchmark_validation_failed",` | `                        "BENCHMARK_VALIDATION_FAILED",` |
| 147 | run_build | 72 | `                        "verified benchmark",` | `                        "XXverified benchmarkXX",` |
| 148 | run_build | 72 | `                        "verified benchmark",` | `                        "VERIFIED BENCHMARK",` |
| 149 | run_build | 73 | `                        "NO_DATA",` | `                        "XXNO_DATAXX",` |
| 150 | run_build | 73 | `                        "NO_DATA",` | `                        "no_data",` |
| 151 | run_build | 77 | `                    1,` | `                    None,` |
| 152 | run_build | 78 | `                    entry.source_id,` | `                    None,` |
| 153 | run_build | 79 | `                    "",` | `                    None,` |
| 154 | run_build | 80 | `                    "benchmark_validation_failed",` | `                    None,` |
| 155 | run_build | 81 | `                    "verified benchmark",` | `                    None,` |
| 156 | run_build | 82 | `                    "NO_DATA",` | `                    None,` |
| 157 | run_build | 77 | `                    1,` | `                    2,` |
| 158 | run_build | 79 | `                    "",` | `                    "XXXX",` |
| 159 | run_build | 80 | `                    "benchmark_validation_failed",` | `                    "XXbenchmark_validation_failedXX",` |
| 160 | run_build | 80 | `                    "benchmark_validation_failed",` | `                    "BENCHMARK_VALIDATION_FAILED",` |
| 161 | run_build | 81 | `                    "verified benchmark",` | `                    "XXverified benchmarkXX",` |
| 162 | run_build | 81 | `                    "verified benchmark",` | `                    "VERIFIED BENCHMARK",` |
| 163 | run_build | 82 | `                    "NO_DATA",` | `                    "XXNO_DATAXX",` |
| 164 | run_build | 82 | `                    "NO_DATA",` | `                    "no_data",` |
| 165 | run_build | 84 | `            continue` | `            break` |
| 166 | run_build | 92 | `                lines.append(pass_line(entry.key, baci_result.digest, baci_result.host))` | `                lines.append(pass_line(None, baci_result.digest, baci_result.host))` |
| 167 | run_build | 92 | `                lines.append(pass_line(entry.key, baci_result.digest, baci_result.host))` | `                lines.append(pass_line(entry.key, None, baci_result.host))` |
| 168 | run_build | 92 | `                lines.append(pass_line(entry.key, baci_result.digest, baci_result.host))` | `                lines.append(pass_line(entry.key, baci_result.digest, None))` |
| 169 | run_build | 96 | `                        baci_result.terms_sha256,` | `                        None,` |
| 170 | run_build | 97 | `                        baci_result.retrieved_utc,` | `                        None,` |
| 171 | run_build | 99 | `                        lines,` | `                        None,` |
| 172 | run_build | 104 | `                        terms_unread_line(entry.key, baci_result.terms_unread, "")` | `                        terms_unread_line(None, baci_result.terms_unread, "")` |
| 173 | run_build | 104 | `                        terms_unread_line(entry.key, baci_result.terms_unread, "")` | `                        terms_unread_line(entry.key, baci_result.terms_unread, None)` |
| 174 | run_build | 104 | `                        terms_unread_line(entry.key, baci_result.terms_unread, "")` | `                        terms_unread_line(entry.key, baci_result.terms_unread, "XXXX")` |
| 175 | run_build | 108 | `                if reason == "baci_metadata_unconfirmed":` | `                if reason == "XXbaci_metadata_unconfirmedXX":` |
| 176 | run_build | 108 | `                if reason == "baci_metadata_unconfirmed":` | `                if reason == "BACI_METADATA_UNCONFIRMED":` |
| 177 | run_build | 109 | `                    lines.append(skip_line("cepii_baci", reason))` | `                    lines.append(skip_line(None, reason))` |
| 178 | run_build | 109 | `                    lines.append(skip_line("cepii_baci", reason))` | `                    lines.append(skip_line("XXcepii_baciXX", reason))` |
| 179 | run_build | 109 | `                    lines.append(skip_line("cepii_baci", reason))` | `                    lines.append(skip_line("CEPII_BACI", reason))` |
| 180 | run_build | 111 | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "")` | `                        None` |
| 181 | run_build | 111 | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "")` | `                        terms_unread_line(None, "terms_to_be_read", "")` |
| 182 | run_build | 111 | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_baci", None, "")` |
| 183 | run_build | 111 | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_baci", "terms_to_be_read", None)` |
| 184 | run_build | 111 | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "")` | `                        terms_unread_line("XXcepii_baciXX", "terms_to_be_read", "")` |
| 185 | run_build | 111 | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "")` | `                        terms_unread_line("CEPII_BACI", "terms_to_be_read", "")` |
| 186 | run_build | 111 | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_baci", "XXterms_to_be_readXX", "")` |
| 187 | run_build | 111 | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_baci", "TERMS_TO_BE_READ", "")` |
| 188 | run_build | 111 | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_baci", "terms_to_be_read", "XXXX")` |
| 189 | run_build | 113 | `                    continue` | `                    break` |
| 190 | run_build | 116 | `                    "cepii_baci",` | `                    None,` |
| 191 | run_build | 117 | `                    "",` | `                    None,` |
| 192 | run_build | 119 | `                    "validated source",` | `                    None,` |
| 193 | run_build | 120 | `                    "NO_DATA",` | `                    None,` |
| 194 | run_build | 115 | `                    6 if reason == "network_exhausted" else 1,` | `                    6 if (reason == "network_exhausted") and False else 1,` |
| 195 | run_build | 115 | `                    6 if reason == "network_exhausted" else 1,` | `                    7 if reason == "network_exhausted" else 1,` |
| 196 | run_build | 115 | `                    6 if reason == "network_exhausted" else 1,` | `                    6 if reason == "XXnetwork_exhaustedXX" else 1,` |
| 197 | run_build | 115 | `                    6 if reason == "network_exhausted" else 1,` | `                    6 if reason == "NETWORK_EXHAUSTED" else 1,` |
| 198 | run_build | 116 | `                    "cepii_baci",` | `                    "XXcepii_baciXX",` |
| 199 | run_build | 116 | `                    "cepii_baci",` | `                    "CEPII_BACI",` |
| 200 | run_build | 117 | `                    "",` | `                    "XXXX",` |
| 201 | run_build | 119 | `                    "validated source",` | `                    "XXvalidated sourceXX",` |
| 202 | run_build | 119 | `                    "validated source",` | `                    "VALIDATED SOURCE",` |
| 203 | run_build | 120 | `                    "NO_DATA",` | `                    "XXNO_DATAXX",` |
| 204 | run_build | 120 | `                    "NO_DATA",` | `                    "no_data",` |
| 205 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line(None, "", reason, "validated source", "NO_DATA")` |
| 206 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("cepii_baci", None, reason, "validated source", "NO_DATA")` |
| 207 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("cepii_baci", "", reason, None, "NO_DATA")` |
| 208 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("cepii_baci", "", reason, "validated source", None)` |
| 209 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("XXcepii_baciXX", "", reason, "validated source", "NO_DATA")` |
| 210 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("CEPII_BACI", "", reason, "validated source", "NO_DATA")` |
| 211 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("cepii_baci", "XXXX", reason, "validated source", "NO_DATA")` |
| 212 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("cepii_baci", "", reason, "XXvalidated sourceXX", "NO_DATA")` |
| 213 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("cepii_baci", "", reason, "VALIDATED SOURCE", "NO_DATA")` |
| 214 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("cepii_baci", "", reason, "validated source", "XXNO_DATAXX")` |
| 215 | run_build | 123 | `                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")` | `                    fail_line("cepii_baci", "", reason, "validated source", "no_data")` |
| 216 | run_build | 126 | `            continue` | `            break` |
| 217 | run_build | 145 | `                    pass_line(entry.key, gravity_result.digest, gravity_result.host)` | `                    None` |
| 218 | run_build | 145 | `                    pass_line(entry.key, gravity_result.digest, gravity_result.host)` | `                    pass_line(None, gravity_result.digest, gravity_result.host)` |
| 219 | run_build | 145 | `                    pass_line(entry.key, gravity_result.digest, gravity_result.host)` | `                    pass_line(entry.key, None, gravity_result.host)` |
| 220 | run_build | 145 | `                    pass_line(entry.key, gravity_result.digest, gravity_result.host)` | `                    pass_line(entry.key, gravity_result.digest, None)` |
| 221 | run_build | 150 | `                        gravity_result.terms_sha256,` | `                        None,` |
| 222 | run_build | 151 | `                        gravity_result.retrieved_utc,` | `                        None,` |
| 223 | run_build | 153 | `                        lines,` | `                        None,` |
| 224 | run_build | 158 | `                        terms_unread_line(entry.key, gravity_result.terms_unread, "")` | `                        None` |
| 225 | run_build | 158 | `                        terms_unread_line(entry.key, gravity_result.terms_unread, "")` | `                        terms_unread_line(None, gravity_result.terms_unread, "")` |
| 226 | run_build | 158 | `                        terms_unread_line(entry.key, gravity_result.terms_unread, "")` | `                        terms_unread_line(entry.key, None, "")` |
| 227 | run_build | 158 | `                        terms_unread_line(entry.key, gravity_result.terms_unread, "")` | `                        terms_unread_line(entry.key, gravity_result.terms_unread, None)` |
| 228 | run_build | 158 | `                        terms_unread_line(entry.key, gravity_result.terms_unread, "")` | `                        terms_unread_line(entry.key, gravity_result.terms_unread, "XXXX")` |
| 229 | run_build | 162 | `                if reason == "gravity_metadata_unconfirmed":` | `                if reason == "XXgravity_metadata_unconfirmedXX":` |
| 230 | run_build | 162 | `                if reason == "gravity_metadata_unconfirmed":` | `                if reason == "GRAVITY_METADATA_UNCONFIRMED":` |
| 231 | run_build | 163 | `                    lines.append(skip_line("cepii_gravity", reason))` | `                    lines.append(skip_line(None, reason))` |
| 232 | run_build | 163 | `                    lines.append(skip_line("cepii_gravity", reason))` | `                    lines.append(skip_line("XXcepii_gravityXX", reason))` |
| 233 | run_build | 163 | `                    lines.append(skip_line("cepii_gravity", reason))` | `                    lines.append(skip_line("CEPII_GRAVITY", reason))` |
| 234 | run_build | 165 | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")` | `                        None` |
| 235 | run_build | 165 | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")` | `                        terms_unread_line(None, "terms_to_be_read", "")` |
| 236 | run_build | 165 | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_gravity", None, "")` |
| 237 | run_build | 165 | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", None)` |
| 238 | run_build | 165 | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")` | `                        terms_unread_line("XXcepii_gravityXX", "terms_to_be_read", "")` |
| 239 | run_build | 165 | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")` | `                        terms_unread_line("CEPII_GRAVITY", "terms_to_be_read", "")` |
| 240 | run_build | 165 | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_gravity", "XXterms_to_be_readXX", "")` |
| 241 | run_build | 165 | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_gravity", "TERMS_TO_BE_READ", "")` |
| 242 | run_build | 165 | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")` | `                        terms_unread_line("cepii_gravity", "terms_to_be_read", "XXXX")` |
| 243 | run_build | 167 | `                    continue` | `                    break` |
| 244 | run_build | 170 | `                    "cepii_gravity",` | `                    None,` |
| 245 | run_build | 171 | `                    "",` | `                    None,` |
| 246 | run_build | 173 | `                    "validated source",` | `                    None,` |
| 247 | run_build | 174 | `                    "NO_DATA",` | `                    None,` |
| 248 | run_build | 169 | `                    6 if reason == "network_exhausted" else 1,` | `                    6 if (reason == "network_exhausted") and False else 1,` |
| 249 | run_build | 169 | `                    6 if reason == "network_exhausted" else 1,` | `                    7 if reason == "network_exhausted" else 1,` |
| 250 | run_build | 169 | `                    6 if reason == "network_exhausted" else 1,` | `                    6 if reason == "XXnetwork_exhaustedXX" else 1,` |
| 251 | run_build | 169 | `                    6 if reason == "network_exhausted" else 1,` | `                    6 if reason == "NETWORK_EXHAUSTED" else 1,` |
| 252 | run_build | 170 | `                    "cepii_gravity",` | `                    "XXcepii_gravityXX",` |
| 253 | run_build | 170 | `                    "cepii_gravity",` | `                    "CEPII_GRAVITY",` |
| 254 | run_build | 171 | `                    "",` | `                    "XXXX",` |
| 255 | run_build | 173 | `                    "validated source",` | `                    "XXvalidated sourceXX",` |
| 256 | run_build | 173 | `                    "validated source",` | `                    "VALIDATED SOURCE",` |
| 257 | run_build | 174 | `                    "NO_DATA",` | `                    "XXNO_DATAXX",` |
| 258 | run_build | 174 | `                    "NO_DATA",` | `                    "no_data",` |
| 259 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        None, "", reason, "validated source", "NO_DATA"` |
| 260 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "cepii_gravity", None, reason, "validated source", "NO_DATA"` |
| 261 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "cepii_gravity", "", reason, None, "NO_DATA"` |
| 262 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "cepii_gravity", "", reason, "validated source", None` |
| 263 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "XXcepii_gravityXX", "", reason, "validated source", "NO_DATA"` |
| 264 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "CEPII_GRAVITY", "", reason, "validated source", "NO_DATA"` |
| 265 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "cepii_gravity", "XXXX", reason, "validated source", "NO_DATA"` |
| 266 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "cepii_gravity", "", reason, "XXvalidated sourceXX", "NO_DATA"` |
| 267 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "cepii_gravity", "", reason, "VALIDATED SOURCE", "NO_DATA"` |
| 268 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "cepii_gravity", "", reason, "validated source", "XXNO_DATAXX"` |
| 269 | run_build | 178 | `                        "cepii_gravity", "", reason, "validated source", "NO_DATA"` | `                        "cepii_gravity", "", reason, "validated source", "no_data"` |
| 270 | run_build | 182 | `            continue` | `            break` |
| 271 | run_build | 193 | `                    pass_line(entry.key, atlas_result.digest, atlas_result.host)` | `                    None` |
| 272 | run_build | 193 | `                    pass_line(entry.key, atlas_result.digest, atlas_result.host)` | `                    pass_line(None, atlas_result.digest, atlas_result.host)` |
| 273 | run_build | 193 | `                    pass_line(entry.key, atlas_result.digest, atlas_result.host)` | `                    pass_line(entry.key, None, atlas_result.host)` |
| 274 | run_build | 193 | `                    pass_line(entry.key, atlas_result.digest, atlas_result.host)` | `                    pass_line(entry.key, atlas_result.digest, None)` |
| 275 | run_build | 198 | `                        atlas_result.terms_sha256,` | `                        None,` |
| 276 | run_build | 199 | `                        atlas_result.retrieved_utc,` | `                        None,` |
| 277 | run_build | 201 | `                        lines,` | `                        None,` |
| 278 | run_build | 206 | `                        terms_unread_line(entry.key, atlas_result.terms_unread, "")` | `                        None` |
| 279 | run_build | 206 | `                        terms_unread_line(entry.key, atlas_result.terms_unread, "")` | `                        terms_unread_line(None, atlas_result.terms_unread, "")` |
| 280 | run_build | 206 | `                        terms_unread_line(entry.key, atlas_result.terms_unread, "")` | `                        terms_unread_line(entry.key, None, "")` |
| 281 | run_build | 206 | `                        terms_unread_line(entry.key, atlas_result.terms_unread, "")` | `                        terms_unread_line(entry.key, atlas_result.terms_unread, None)` |
| 282 | run_build | 206 | `                        terms_unread_line(entry.key, atlas_result.terms_unread, "")` | `                        terms_unread_line(entry.key, atlas_result.terms_unread, "XXXX")` |
| 283 | run_build | 210 | `                if reason == "atlas_metadata_unconfirmed":` | `                if reason == "XXatlas_metadata_unconfirmedXX":` |
| 284 | run_build | 210 | `                if reason == "atlas_metadata_unconfirmed":` | `                if reason == "ATLAS_METADATA_UNCONFIRMED":` |
| 285 | run_build | 211 | `                    lines.append(skip_line("atlas_complexity", reason))` | `                    lines.append(skip_line(None, reason))` |
| 286 | run_build | 211 | `                    lines.append(skip_line("atlas_complexity", reason))` | `                    lines.append(skip_line("XXatlas_complexityXX", reason))` |
| 287 | run_build | 211 | `                    lines.append(skip_line("atlas_complexity", reason))` | `                    lines.append(skip_line("ATLAS_COMPLEXITY", reason))` |
| 288 | run_build | 213 | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")` | `                        None` |
| 289 | run_build | 213 | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")` | `                        terms_unread_line(None, "terms_to_be_read", "")` |
| 290 | run_build | 213 | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")` | `                        terms_unread_line("atlas_complexity", None, "")` |
| 291 | run_build | 213 | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")` | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", None)` |
| 292 | run_build | 213 | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")` | `                        terms_unread_line("XXatlas_complexityXX", "terms_to_be_read", "")` |
| 293 | run_build | 213 | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")` | `                        terms_unread_line("ATLAS_COMPLEXITY", "terms_to_be_read", "")` |
| 294 | run_build | 213 | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")` | `                        terms_unread_line("atlas_complexity", "XXterms_to_be_readXX", "")` |
| 295 | run_build | 213 | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")` | `                        terms_unread_line("atlas_complexity", "TERMS_TO_BE_READ", "")` |
| 296 | run_build | 213 | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")` | `                        terms_unread_line("atlas_complexity", "terms_to_be_read", "XXXX")` |
| 297 | run_build | 215 | `                    continue` | `                    break` |
| 298 | run_build | 218 | `                    "atlas_complexity",` | `                    None,` |
| 299 | run_build | 219 | `                    "",` | `                    None,` |
| 300 | run_build | 221 | `                    "validated source",` | `                    None,` |
| 301 | run_build | 222 | `                    "NO_DATA",` | `                    None,` |
| 302 | run_build | 217 | `                    6 if reason == "network_exhausted" else 1,` | `                    6 if (reason == "network_exhausted") and False else 1,` |
| 303 | run_build | 217 | `                    6 if reason == "network_exhausted" else 1,` | `                    7 if reason == "network_exhausted" else 1,` |
| 304 | run_build | 217 | `                    6 if reason == "network_exhausted" else 1,` | `                    6 if reason == "XXnetwork_exhaustedXX" else 1,` |
| 305 | run_build | 217 | `                    6 if reason == "network_exhausted" else 1,` | `                    6 if reason == "NETWORK_EXHAUSTED" else 1,` |
| 306 | run_build | 218 | `                    "atlas_complexity",` | `                    "XXatlas_complexityXX",` |
| 307 | run_build | 218 | `                    "atlas_complexity",` | `                    "ATLAS_COMPLEXITY",` |
| 308 | run_build | 219 | `                    "",` | `                    "XXXX",` |
| 309 | run_build | 221 | `                    "validated source",` | `                    "XXvalidated sourceXX",` |
| 310 | run_build | 221 | `                    "validated source",` | `                    "VALIDATED SOURCE",` |
| 311 | run_build | 222 | `                    "NO_DATA",` | `                    "XXNO_DATAXX",` |
| 312 | run_build | 222 | `                    "NO_DATA",` | `                    "no_data",` |
| 313 | run_build | 225 | `                    fail_line(<br>                        "atlas_complexity", "", reason, "validated source", "NO_DATA"<br>                    )` | `                    None` |
| 314 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        None, "", reason, "validated source", "NO_DATA"` |
| 315 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "atlas_complexity", None, reason, "validated source", "NO_DATA"` |
| 316 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "atlas_complexity", "", None, "validated source", "NO_DATA"` |
| 317 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "atlas_complexity", "", reason, None, "NO_DATA"` |
| 318 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "atlas_complexity", "", reason, "validated source", None` |
| 319 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "XXatlas_complexityXX", "", reason, "validated source", "NO_DATA"` |
| 320 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "ATLAS_COMPLEXITY", "", reason, "validated source", "NO_DATA"` |
| 321 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "atlas_complexity", "XXXX", reason, "validated source", "NO_DATA"` |
| 322 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "atlas_complexity", "", reason, "XXvalidated sourceXX", "NO_DATA"` |
| 323 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "atlas_complexity", "", reason, "VALIDATED SOURCE", "NO_DATA"` |
| 324 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "atlas_complexity", "", reason, "validated source", "XXNO_DATAXX"` |
| 325 | run_build | 226 | `                        "atlas_complexity", "", reason, "validated source", "NO_DATA"` | `                        "atlas_complexity", "", reason, "validated source", "no_data"` |
| 326 | run_build | 230 | `            continue` | `            break` |
| 327 | run_build | 233 | `            continue` | `            break` |
| 328 | run_build | 244 | `            continue` | `            break` |
| 329 | run_build | 247 | `                entry, cache, clock, sleep, opener, slots, lines` | `                entry, None, clock, sleep, opener, slots, lines` |
| 330 | run_build | 247 | `                entry, cache, clock, sleep, opener, slots, lines` | `                entry, cache, None, sleep, opener, slots, lines` |
| 331 | run_build | 247 | `                entry, cache, clock, sleep, opener, slots, lines` | `                entry, cache, clock, None, opener, slots, lines` |
| 332 | run_build | 247 | `                entry, cache, clock, sleep, opener, slots, lines` | `                entry, cache, clock, sleep, None, slots, lines` |
| 333 | run_build | 247 | `                entry, cache, clock, sleep, opener, slots, lines` | `                entry, cache, clock, sleep, opener, None, lines` |
| 334 | run_build | 252 | `            continue` | `            break` |
| 335 | run_build | 254 | `            released, refused = fetch_release(entry, transport, cache, clock, sleep)` | `            released, refused = fetch_release(entry, transport, cache, clock, None)` |
| 336 | run_build | 257 | `                    fail_line(<br>                        entry.key,<br>                        refused.url,<br>                        refused.check,<br>                        refused.expected,<br>                        refused.observed,<br>                    )` | `                    None` |
| 337 | run_build | 258 | `                        entry.key,` | `                        None,` |
| 338 | run_build | 259 | `                        refused.url,` | `                        None,` |
| 339 | run_build | 260 | `                        refused.check,` | `                        None,` |
| 340 | run_build | 261 | `                        refused.expected,` | `                        None,` |
| 341 | run_build | 262 | `                        refused.observed,` | `                        None,` |
| 342 | run_build | 266 | `                    refused.code,` | `                    None,` |
| 343 | run_build | 267 | `                    entry.source_id,` | `                    None,` |
| 344 | run_build | 270 | `                    refused.expected,` | `                    None,` |
| 345 | run_build | 271 | `                    refused.observed,` | `                    None,` |
| 346 | run_build | 275 | `            lines.append(pass_line(entry.key, released.digest, released.host))` | `            lines.append(None)` |
| 347 | run_build | 275 | `            lines.append(pass_line(entry.key, released.digest, released.host))` | `            lines.append(pass_line(None, released.digest, released.host))` |
| 348 | run_build | 275 | `            lines.append(pass_line(entry.key, released.digest, released.host))` | `            lines.append(pass_line(entry.key, None, released.host))` |
| 349 | run_build | 275 | `            lines.append(pass_line(entry.key, released.digest, released.host))` | `            lines.append(pass_line(entry.key, released.digest, None))` |
| 350 | run_build | 276 | `            continue` | `            break` |
| 351 | run_build | 279 | `                entry, transport, cache, clock, sleep` | `                entry, transport, cache, clock, None` |
| 352 | run_build | 284 | `                        entry.key,` | `                        None,` |
| 353 | run_build | 285 | `                        place_failure.url,` | `                        None,` |
| 354 | run_build | 286 | `                        place_failure.check,` | `                        None,` |
| 355 | run_build | 287 | `                        place_failure.expected,` | `                        None,` |
| 356 | run_build | 288 | `                        place_failure.observed,` | `                        None,` |
| 357 | run_build | 292 | `                    place_failure.code,` | `                    None,` |
| 358 | run_build | 293 | `                    entry.source_id,` | `                    None,` |
| 359 | run_build | 294 | `                    place_failure.url,` | `                    None,` |
| 360 | run_build | 296 | `                    place_failure.expected,` | `                    None,` |
| 361 | run_build | 297 | `                    place_failure.observed,` | `                    None,` |
| 362 | run_build | 301 | `            lines.append(pass_line(entry.key, placed.digest, placed.host))` | `            lines.append(pass_line(entry.key, placed.digest, None))` |
| 363 | run_build | 315 | `                    entry.key,` | `                    None,` |
| 364 | run_build | 335 | `            entry, cache, fetched.digest, transport, sleep, clock` | `            entry, cache, fetched.digest, transport, None, clock` |
| 365 | run_build | 341 | `                    batch.url,` | `                    None,` |
| 366 | run_build | 343 | `                    batch.expected,` | `                    None,` |
| 367 | run_build | 349 | `                entry.source_id,` | `                None,` |
| 368 | run_build | 350 | `                batch.url,` | `                None,` |
| 369 | run_build | 351 | `                batch.check,` | `                None,` |
| 370 | run_build | 352 | `                batch.expected,` | `                None,` |
| 371 | run_build | 353 | `                batch.observed,` | `                None,` |
| 372 | run_build | 359 | `            lines.append(counted.read_text(encoding="utf-8").strip())` | `            lines.append(counted.read_text(encoding=None).strip())` |
| 373 | run_build | 359 | `            lines.append(counted.read_text(encoding="utf-8").strip())` | `            lines.append(counted.read_text(encoding="UTF-8").strip())` |
| 374 | run_build | 366 | `            additions_frame,` | `            None,` |
| 375 | run_build | 384 | `                1,` | `                None,` |
| 376 | run_build | 386 | `                "",` | `                None,` |
| 377 | run_build | 388 | `                "section 10 anchor",` | `                None,` |
| 378 | run_build | 389 | `                stage.mismatch,` | `                None,` |
| 379 | run_build | 384 | `                1,` | `                2,` |
| 380 | run_build | 386 | `                "",` | `                "XXXX",` |
| 381 | run_build | 388 | `                "section 10 anchor",` | `                "XXsection 10 anchorXX",` |
| 382 | run_build | 388 | `                "section 10 anchor",` | `                "SECTION 10 ANCHOR",` |
| 383 | run_build | 392 | `                fail_line(<br>                    stage.mismatch,<br>                    "",<br>                    "public_data",<br>                    "section 10 anchor",<br>                    stage.mismatch,<br>                )` | `                None` |
| 384 | run_build | 393 | `                    stage.mismatch,` | `                    None,` |
| 385 | run_build | 394 | `                    "",` | `                    None,` |
| 386 | run_build | 395 | `                    "public_data",` | `                    None,` |
| 387 | run_build | 396 | `                    "section 10 anchor",` | `                    None,` |
| 388 | run_build | 397 | `                    stage.mismatch,` | `                    None,` |
| 389 | run_build | 394 | `                    "",` | `                    "XXXX",` |
| 390 | run_build | 395 | `                    "public_data",` | `                    "XXpublic_dataXX",` |
| 391 | run_build | 395 | `                    "public_data",` | `                    "PUBLIC_DATA",` |
| 392 | run_build | 396 | `                    "section 10 anchor",` | `                    "XXsection 10 anchorXX",` |
| 393 | run_build | 396 | `                    "section 10 anchor",` | `                    "SECTION 10 ANCHOR",` |
| 394 | run_build | 402 | `                1,` | `                None,` |
| 395 | run_build | 404 | `                "",` | `                None,` |
| 396 | run_build | 402 | `                1,` | `                2,` |
| 397 | run_build | 404 | `                "",` | `                "XXXX",` |
| 398 | run_build | 410 | `                fail_line(<br>                    stage.unrecorded,<br>                    "",<br>                    "public_data",<br>                    "local expectations record",<br>                    "missing",<br>                )` | `                None` |
| 399 | run_build | 411 | `                    stage.unrecorded,` | `                    None,` |
| 400 | run_build | 412 | `                    "",` | `                    None,` |
| 401 | run_build | 413 | `                    "public_data",` | `                    None,` |
| 402 | run_build | 414 | `                    "local expectations record",` | `                    None,` |
| 403 | run_build | 415 | `                    "missing",` | `                    None,` |
| 404 | run_build | 412 | `                    "",` | `                    "XXXX",` |
| 405 | run_build | 413 | `                    "public_data",` | `                    "XXpublic_dataXX",` |
| 406 | run_build | 413 | `                    "public_data",` | `                    "PUBLIC_DATA",` |
| 407 | run_build | 414 | `                    "local expectations record",` | `                    "XXlocal expectations recordXX",` |
| 408 | run_build | 414 | `                    "local expectations record",` | `                    "LOCAL EXPECTATIONS RECORD",` |
| 409 | run_build | 415 | `                    "missing",` | `                    "XXmissingXX",` |
| 410 | run_build | 415 | `                    "missing",` | `                    "MISSING",` |
| 411 | run_build | 422 | `        cache.mkdir(parents=True, exist_ok=True)` | `        cache.mkdir(parents=None, exist_ok=True)` |
| 412 | run_build | 422 | `        cache.mkdir(parents=True, exist_ok=True)` | `        cache.mkdir(exist_ok=True)` |
| 413 | run_build | 422 | `        cache.mkdir(parents=True, exist_ok=True)` | `        cache.mkdir(parents=False, exist_ok=True)` |
| 414 | run_build | 424 | `            json.dumps(benchmark_obstacles, sort_keys=True), encoding="utf-8"` | `            json.dumps(benchmark_obstacles, sort_keys=True), encoding=None` |
| 415 | run_build | 424 | `            json.dumps(benchmark_obstacles, sort_keys=True), encoding="utf-8"<br>        )` | `            json.dumps(benchmark_obstacles, sort_keys=True), )` |
| 416 | run_build | 424 | `            json.dumps(benchmark_obstacles, sort_keys=True), encoding="utf-8"` | `            json.dumps(benchmark_obstacles, sort_keys=None), encoding="utf-8"` |
| 417 | run_build | 424 | `            json.dumps(benchmark_obstacles, sort_keys=True), encoding="utf-8"` | `            json.dumps(benchmark_obstacles, ), encoding="utf-8"` |
| 418 | run_build | 424 | `            json.dumps(benchmark_obstacles, sort_keys=True), encoding="utf-8"` | `            json.dumps(benchmark_obstacles, sort_keys=False), encoding="utf-8"` |
| 419 | run_build | 424 | `            json.dumps(benchmark_obstacles, sort_keys=True), encoding="utf-8"` | `            json.dumps(benchmark_obstacles, sort_keys=True), encoding="UTF-8"` |
| 420 | run_build | 437 | `                native_policy = next(<br>                    (<br>                        e.comtrade_policy<br>                        for e in entries<br>                        if isinstance(e.comtrade_policy, TradePolicy)<br>                    ),<br>                    None,<br>                )` | `                native_policy = None` |
| 421 | run_build | 446 | `                    cache, selected_comparison, comtrade_policy=native_policy` | `                    cache, selected_comparison, comtrade_policy=None` |
| 422 | run_build | 446 | `                    cache, selected_comparison, comtrade_policy=native_policy<br>                )` | `                    cache, selected_comparison, )` |
| 423 | run_build | 458 | `                1,` | `                None,` |
| 424 | run_build | 459 | `                "trade_reconciliation",` | `                None,` |
| 425 | run_build | 460 | `                "",` | `                None,` |
| 426 | run_build | 462 | `                "verified inputs",` | `                None,` |
| 427 | run_build | 458 | `                1,` | `                2,` |
| 428 | run_build | 459 | `                "trade_reconciliation",` | `                "XXtrade_reconciliationXX",` |
| 429 | run_build | 459 | `                "trade_reconciliation",` | `                "TRADE_RECONCILIATION",` |
| 430 | run_build | 460 | `                "",` | `                "XXXX",` |
| 431 | run_build | 462 | `                "verified inputs",` | `                "XXverified inputsXX",` |
| 432 | run_build | 462 | `                "verified inputs",` | `                "VERIFIED INPUTS",` |
| 433 | run_build | 484 | `            detail = ""` | `            detail = None` |
| 434 | run_build | 485 | `            trusted = False` | `            trusted = None` |
| 435 | run_build | 485 | `            trusted = False` | `            trusted = True` |
| 436 | run_build | 489 | `                    transport,` | `                    None,` |
| 437 | run_build | 491 | `                    clock,` | `                    None,` |
| 438 | run_build | 492 | `                    environ if environ is not None else {},` | `                    environ if (environ is not None) or True else {},` |
| 439 | run_build | 501 | `                    "BESTTIME_API_KEY_PUBLIC",` | `                    "XXBESTTIME_API_KEY_PUBLICXX",` |
| 440 | run_build | 501 | `                    "BESTTIME_API_KEY_PUBLIC",` | `                    "besttime_api_key_public",` |
| 441 | run_build | 502 | `                    "EII_BESTTIME_RUN_CREDIT_LIMIT",` | `                    "XXEII_BESTTIME_RUN_CREDIT_LIMITXX",` |
| 442 | run_build | 502 | `                    "EII_BESTTIME_RUN_CREDIT_LIMIT",` | `                    "eii_besttime_run_credit_limit",` |
| 443 | run_build | 503 | `                    "forecast_credits",` | `                    "XXforecast_creditsXX",` |
| 444 | run_build | 503 | `                    "forecast_credits",` | `                    "FORECAST_CREDITS",` |
| 445 | run_build | 504 | `                    "query_credits",` | `                    "XXquery_creditsXX",` |
| 446 | run_build | 504 | `                    "query_credits",` | `                    "QUERY_CREDITS",` |
| 447 | run_build | 505 | `                    "source_page",` | `                    "XXsource_pageXX",` |
| 448 | run_build | 505 | `                    "source_page",` | `                    "SOURCE_PAGE",` |
| 449 | run_build | 506 | `                    "read_on",` | `                    "XXread_onXX",` |
| 450 | run_build | 506 | `                    "read_on",` | `                    "READ_ON",` |
| 451 | run_build | 507 | `                    "terms_words",` | `                    "XXterms_wordsXX",` |
| 452 | run_build | 507 | `                    "terms_words",` | `                    "TERMS_WORDS",` |
| 453 | run_build | 511 | `                    "busyness_build_failed",` | `                    None,` |
| 454 | run_build | 511 | `                    "busyness_build_failed",` | `                    "XXbusyness_build_failedXX",` |
| 455 | run_build | 511 | `                    "busyness_build_failed",` | `                    "BUSYNESS_BUILD_FAILED",` |
| 456 | run_build | 515 | `                        assert_clean(environ if environ is not None else {}, detail)` | `                        assert_clean(environ if (environ is not None) or True else {}, detail)` |
| 457 | run_build | 519 | `                endpoint = QUERY_URL if QUERY_URL in detail else FORECAST_URL` | `                endpoint = None` |
| 458 | run_build | 519 | `                endpoint = QUERY_URL if QUERY_URL in detail else FORECAST_URL` | `                endpoint = QUERY_URL if (QUERY_URL in detail) and False else FORECAST_URL` |
| 459 | run_build | 519 | `                endpoint = QUERY_URL if QUERY_URL in detail else FORECAST_URL` | `                endpoint = QUERY_URL if (QUERY_URL in detail) or True else FORECAST_URL` |
| 460 | run_build | 519 | `                endpoint = QUERY_URL if QUERY_URL in detail else FORECAST_URL` | `                endpoint = QUERY_URL if QUERY_URL not in detail else FORECAST_URL` |
| 461 | run_build | 521 | `                    1,` | `                    None,` |
| 462 | run_build | 523 | `                    endpoint,` | `                    None,` |
| 463 | run_build | 525 | `                    "valid build inputs and answer",` | `                    None,` |
| 464 | run_build | 526 | `                    "refused",` | `                    None,` |
| 465 | run_build | 521 | `                    1,` | `                    2,` |
| 466 | run_build | 522 | `                    "busy_besttime",` | `                    "XXbusy_besttimeXX",` |
| 467 | run_build | 525 | `                    "valid build inputs and answer",` | `                    "XXvalid build inputs and answerXX",` |
| 468 | run_build | 525 | `                    "valid build inputs and answer",` | `                    "VALID BUILD INPUTS AND ANSWER",` |
| 469 | run_build | 526 | `                    "refused",` | `                    "XXrefusedXX",` |
| 470 | run_build | 526 | `                    "refused",` | `                    "REFUSED",` |
| 471 | run_build | 529 | `                    fail_line(<br>                        entry.key, endpoint, check, failure.expected, failure.observed<br>                    )` | `                    None` |
| 472 | run_build | 530 | `                        entry.key, endpoint, check, failure.expected, failure.observed` | `                        None, endpoint, check, failure.expected, failure.observed` |
| 473 | run_build | 530 | `                        entry.key, endpoint, check, failure.expected, failure.observed` | `                        entry.key, None, check, failure.expected, failure.observed` |
| 474 | run_build | 530 | `                        entry.key, endpoint, check, failure.expected, failure.observed` | `                        entry.key, endpoint, None, failure.expected, failure.observed` |
| 475 | run_build | 530 | `                        entry.key, endpoint, check, failure.expected, failure.observed` | `                        entry.key, endpoint, check, None, failure.observed` |
| 476 | run_build | 530 | `                        entry.key, endpoint, check, failure.expected, failure.observed` | `                        entry.key, endpoint, check, failure.expected, None` |
| 477 | run_build | 534 | `            lines.append(pass_line(entry.key, digest, "besttime.app"))` | `            lines.append(None)` |
| 478 | run_build | 534 | `            lines.append(pass_line(entry.key, digest, "besttime.app"))` | `            lines.append(pass_line(None, digest, "besttime.app"))` |
| 479 | run_build | 534 | `            lines.append(pass_line(entry.key, digest, "besttime.app"))` | `            lines.append(pass_line(entry.key, None, "besttime.app"))` |
| 480 | run_build | 534 | `            lines.append(pass_line(entry.key, digest, "besttime.app"))` | `            lines.append(pass_line(entry.key, digest, None))` |
| 481 | run_build | 534 | `            lines.append(pass_line(entry.key, digest, "besttime.app"))` | `            lines.append(pass_line(entry.key, digest, "XXbesttime.appXX"))` |
| 482 | run_build | 534 | `            lines.append(pass_line(entry.key, digest, "besttime.app"))` | `            lines.append(pass_line(entry.key, digest, "BESTTIME.APP"))` |
| 483 | run_build | 537 | `    assert_clean(environ if environ is not None else {}, lines)` | `    assert_clean(environ if environ is not None else {}, None)` |
| 484 | run_build | 537 | `    assert_clean(environ if environ is not None else {}, lines)` | `    assert_clean(environ if (environ is not None) and False else {}, lines)` |

Changes in R045:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 1 | run_build | 334 | `                    entry.source_id,` | `                    None,` |
| 2 | run_build | 335 | `                    entry.key,` | `                    None,` |
| 3 | run_build | 336 | `                    "failed",` | `                    None,` |
| 4 | run_build | 337 | `                    fetched.digest,` | `                    None,` |
| 5 | run_build | 336 | `                    "failed",` | `                    "XXfailedXX",` |
| 6 | run_build | 336 | `                    "failed",` | `                    "FAILED",` |
| 7 | run_build | 359 | `        if entry.source_id in INVESTMENT_SOURCES:` | `        if entry.source_id not in INVESTMENT_SOURCES:` |
| 8 | run_build | 361 | `                FetchAttempt(entry.source_id, entry.key, "success", fetched.digest, "")` | `                FetchAttempt(None, entry.key, "success", fetched.digest, "")` |
| 9 | run_build | 361 | `                FetchAttempt(entry.source_id, entry.key, "success", fetched.digest, "")` | `                FetchAttempt(entry.source_id, None, "success", fetched.digest, "")` |
| 10 | run_build | 361 | `                FetchAttempt(entry.source_id, entry.key, "success", fetched.digest, "")` | `                FetchAttempt(entry.source_id, entry.key, "success", fetched.digest, None)` |
| 11 | run_build | 361 | `                FetchAttempt(entry.source_id, entry.key, "success", fetched.digest, "")` | `                FetchAttempt(entry.source_id, entry.key, "success", fetched.digest, "XXXX")` |
| 12 | run_build | 370 | `    if failure is None and attempt_failure is not None:` | `    if failure is None or attempt_failure is not None:` |
| 13 | run_build | 370 | `    if failure is None and attempt_failure is not None:` | `    if failure is not None and attempt_failure is not None:` |
| 14 | run_build | 370 | `    if failure is None and attempt_failure is not None:` | `    if failure is None and attempt_failure is None:` |
| 15 | run_build | 371 | `        failure = attempt_failure` | `        failure = None` |

#### R101 — _publish_additions

`_publish_additions` chooses review, frame and output locations before publishing additions tables. Items 485–494 change those choices: use distinct explicit locations and then omit each optional location, requiring the review default, the review-as-frame fallback and the cache's `additions` destination exactly as the source defines them. Items 495–516 corrupt the error conversion; a real parser refusal named by the fixture must leave no tables, append its additions failure line and return `(1, additions, empty address, same reason, published tables, same reason)` with every field checked. Path selection is observable even when both directories happen to exist, so a fixture must give them different contents.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 485 | _publish_additions | 10 | `    review_dir = review if review is not None else _review_dir()` | `    review_dir = review if (review is not None) or True else _review_dir()` |
| 486 | _publish_additions | 11 | `    frame_dir = frame if frame is not None else review_dir` | `    frame_dir = None` |
| 487 | _publish_additions | 11 | `    frame_dir = frame if frame is not None else review_dir` | `    frame_dir = frame if (frame is not None) and False else review_dir` |
| 488 | _publish_additions | 11 | `    frame_dir = frame if frame is not None else review_dir` | `    frame_dir = frame if (frame is not None) or True else review_dir` |
| 489 | _publish_additions | 11 | `    frame_dir = frame if frame is not None else review_dir` | `    frame_dir = frame if frame is None else review_dir` |
| 490 | _publish_additions | 12 | `    destination = output if output is not None else cache / "additions"` | `    destination = output if (output is not None) or True else cache / "additions"` |
| 491 | _publish_additions | 12 | `    destination = output if output is not None else cache / "additions"` | `    destination = output if output is not None else cache * "additions"` |
| 492 | _publish_additions | 12 | `    destination = output if output is not None else cache / "additions"` | `    destination = output if output is not None else cache / "XXadditionsXX"` |
| 493 | _publish_additions | 12 | `    destination = output if output is not None else cache / "additions"` | `    destination = output if output is not None else cache / "ADDITIONS"` |
| 494 | _publish_additions | 14 | `        build_additions(cache, entries, selected, review_dir, frame_dir, destination)` | `        build_additions(cache, entries, selected, review_dir, None, destination)` |
| 495 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            None` |
| 496 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line(None, "", error.name, "published tables", error.name)` |
| 497 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line("additions", None, error.name, "published tables", error.name)` |
| 498 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line("additions", "", None, "published tables", error.name)` |
| 499 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line("additions", "", error.name, None, error.name)` |
| 500 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line("additions", "", error.name, "published tables", None)` |
| 501 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line("XXadditionsXX", "", error.name, "published tables", error.name)` |
| 502 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line("ADDITIONS", "", error.name, "published tables", error.name)` |
| 503 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line("additions", "XXXX", error.name, "published tables", error.name)` |
| 504 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line("additions", "", error.name, "XXpublished tablesXX", error.name)` |
| 505 | _publish_additions | 17 | `            fail_line("additions", "", error.name, "published tables", error.name)` | `            fail_line("additions", "", error.name, "PUBLISHED TABLES", error.name)` |
| 506 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            None, "additions", "", error.name, "published tables", error.name` |
| 507 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            1, None, "", error.name, "published tables", error.name` |
| 508 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            1, "additions", None, error.name, "published tables", error.name` |
| 509 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            1, "additions", "", error.name, None, error.name` |
| 510 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            1, "additions", "", error.name, "published tables", None` |
| 511 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            2, "additions", "", error.name, "published tables", error.name` |
| 512 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            1, "XXadditionsXX", "", error.name, "published tables", error.name` |
| 513 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            1, "ADDITIONS", "", error.name, "published tables", error.name` |
| 514 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            1, "additions", "XXXX", error.name, "published tables", error.name` |
| 515 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            1, "additions", "", error.name, "XXpublished tablesXX", error.name` |
| 516 | _publish_additions | 20 | `            1, "additions", "", error.name, "published tables", error.name` | `            1, "additions", "", error.name, "PUBLISHED TABLES", error.name` |

#### R101 — _review_dir

`_review_dir` locates the repository's reviewed public-data inputs relative to this module. Items 517–524 change a path component, its case, the parent depth or the path constructor. Require the resolved repository-relative destination `custodian/publicdata/review` from an unrelated current directory and verify that its expected reviewed file exists; this detects a wrong but still constructible path as well as the invalid path operations.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 517 | _review_dir | 1 | `    return Path(__file__).resolve().parents[4] / "publicdata" / "review"` | `    return Path(__file__).resolve().parents[4] / "publicdata" * "review"` |
| 518 | _review_dir | 1 | `    return Path(__file__).resolve().parents[4] / "publicdata" / "review"` | `    return Path(__file__).resolve().parents[4] * "publicdata" / "review"` |
| 519 | _review_dir | 1 | `    return Path(__file__).resolve().parents[4] / "publicdata" / "review"` | `    return Path(None).resolve().parents[4] / "publicdata" / "review"` |
| 520 | _review_dir | 1 | `    return Path(__file__).resolve().parents[4] / "publicdata" / "review"` | `    return Path(__file__).resolve().parents[5] / "publicdata" / "review"` |
| 521 | _review_dir | 1 | `    return Path(__file__).resolve().parents[4] / "publicdata" / "review"` | `    return Path(__file__).resolve().parents[4] / "XXpublicdataXX" / "review"` |
| 522 | _review_dir | 1 | `    return Path(__file__).resolve().parents[4] / "publicdata" / "review"` | `    return Path(__file__).resolve().parents[4] / "PUBLICDATA" / "review"` |
| 523 | _review_dir | 1 | `    return Path(__file__).resolve().parents[4] / "publicdata" / "review"` | `    return Path(__file__).resolve().parents[4] / "publicdata" / "XXreviewXX"` |
| 524 | _review_dir | 1 | `    return Path(__file__).resolve().parents[4] / "publicdata" / "review"` | `    return Path(__file__).resolve().parents[4] / "publicdata" / "REVIEW"` |

#### R101 — _heights

`_heights` runs the building-height step after the public stage and converts a `HeightError` into a build failure. Items 525–542 change fields in that conversion or its accompanying line. Trigger an actual height-input refusal using an invented invalid height fixture; require source `heights`, code 1, an empty address, expected `valid height inputs`, and the original height reason in both the check and observed fields. A valid height fixture must still finish with a null failure, so an unconditional error cannot satisfy the check.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 525 | _heights | 24 | `                "",` | `                None,` |
| 526 | _heights | 25 | `                error.name,` | `                None,` |
| 527 | _heights | 26 | `                "valid height inputs",` | `                None,` |
| 528 | _heights | 27 | `                error.name,` | `                None,` |
| 529 | _heights | 24 | `                "",` | `                "XXXX",` |
| 530 | _heights | 26 | `                "valid height inputs",` | `                "XXvalid height inputsXX",` |
| 531 | _heights | 26 | `                "valid height inputs",` | `                "VALID HEIGHT INPUTS",` |
| 532 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            None, "heights", "", error.name, "valid height inputs", error.name` |
| 533 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            1, None, "", error.name, "valid height inputs", error.name` |
| 534 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            1, "heights", None, error.name, "valid height inputs", error.name` |
| 535 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            1, "heights", "", error.name, None, error.name` |
| 536 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            1, "heights", "", error.name, "valid height inputs", None` |
| 537 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            2, "heights", "", error.name, "valid height inputs", error.name` |
| 538 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            1, "XXheightsXX", "", error.name, "valid height inputs", error.name` |
| 539 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            1, "HEIGHTS", "", error.name, "valid height inputs", error.name` |
| 540 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            1, "heights", "XXXX", error.name, "valid height inputs", error.name` |
| 541 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            1, "heights", "", error.name, "XXvalid height inputsXX", error.name` |
| 542 | _heights | 31 | `            1, "heights", "", error.name, "valid height inputs", error.name` | `            1, "heights", "", error.name, "VALID HEIGHT INPUTS", error.name` |

#### R101 — _read_terms_apart

`_read_terms_apart` fingerprints and archives a separately fetched terms page without replacing the data fetch. Item 543 drops the archive's final public address. Read an invented terms body with a different data address and require the terms auxiliary receipt to carry the terms address exactly, together with its body fingerprint; accepting a null address would break that provenance link even if the fingerprint were right.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 543 | _read_terms_apart | 20 | `        entry, cache / entry.key, "terms", read.body, retrieved, entry.terms_url` | `        entry, cache / entry.key, "terms", read.body, retrieved, None` |

#### R101 — _previous_term_hashes

`_previous_term_hashes` reads the prior log and returns only nonempty visible-text fingerprints. Items 544–545 change the text encoding; a UTF-8 log containing non-ASCII text must remain readable under a different machine default, while `UTF-8` is an alias whose equivalence can be established explicitly. Item 546 stops at the first malformed list member; put an invalid member before a valid visible-text entry and require the later entry's exact key-to-digest mapping to survive.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 544 | _previous_term_hashes | 8 | `        loaded: object = json.loads(path.read_text(encoding="utf-8"))` | `        loaded: object = json.loads(path.read_text(encoding=None))` |
| 545 | _previous_term_hashes | 8 | `        loaded: object = json.loads(path.read_text(encoding="utf-8"))` | `        loaded: object = json.loads(path.read_text(encoding="UTF-8"))` |
| 546 | _previous_term_hashes | 19 | `            continue` | `            break` |

#### R101 — _write_citation

`_write_citation` writes a receipt for an entry that is cited without downloading a body. Items 547–554 replace the public fetch address, publisher, empty host, empty modification time or empty terms fingerprint. For an invented citation-only entry, read the committed receipt and require its address and publisher to match the entry and those deliberately empty fields to remain empty, alongside `CITATION_ONLY` and the absence of a downloaded body; neither null nor a filler string has the same schema meaning.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 547 | _write_citation | 3 | `        fetch_url=entry.url,` | `        fetch_url=None,` |
| 548 | _write_citation | 4 | `        fetch_host="",` | `        fetch_host=None,` |
| 549 | _write_citation | 6 | `        publisher=entry.publisher,` | `        publisher=None,` |
| 550 | _write_citation | 7 | `        source_modified="",` | `        source_modified=None,` |
| 551 | _write_citation | 9 | `        terms_sha256="",` | `        terms_sha256=None,` |
| 552 | _write_citation | 4 | `        fetch_host="",` | `        fetch_host="XXXX",` |
| 553 | _write_citation | 7 | `        source_modified="",` | `        source_modified="XXXX",` |
| 554 | _write_citation | 9 | `        terms_sha256="",` | `        terms_sha256="XXXX",` |

#### R101 — _write_log

`_write_log` writes the complete build log through a temporary file and atomic replacement. Items 555–557 disable key ordering; give `lines` and `terms` distinctive values and compare the final sorted-key JSON bytes including the final newline. Items 558–559 rename the temporary file: this may be equivalent only if no admitted consumer observes that name, concurrent writers are excluded and failure cleanup always removes the actual temporary file. Items 560–564 change encoding or cleanup behaviour; use non-ASCII report text and an induced replacement failure to require UTF-8 output on success and no partial file after failure, then distinguish an encoding alias from dependence on a machine default.

Changes in R101:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 555 | _write_log | 1 | `    payload = json.dumps({"lines": lines, "terms": terms}, sort_keys=True) + "\n"` | `    payload = json.dumps({"lines": lines, "terms": terms}, sort_keys=None) + "\n"` |
| 556 | _write_log | 1 | `    payload = json.dumps({"lines": lines, "terms": terms}, sort_keys=True) + "\n"` | `    payload = json.dumps({"lines": lines, "terms": terms}, ) + "\n"` |
| 557 | _write_log | 1 | `    payload = json.dumps({"lines": lines, "terms": terms}, sort_keys=True) + "\n"` | `    payload = json.dumps({"lines": lines, "terms": terms}, sort_keys=False) + "\n"` |
| 558 | _write_log | 1 | `    partial = cache / ".build-log.json.partial"` | `    partial = cache / "XX.build-log.json.partialXX"` |
| 559 | _write_log | 1 | `    partial = cache / ".build-log.json.partial"` | `    partial = cache / ".BUILD-LOG.JSON.PARTIAL"` |
| 560 | _write_log | 4 | `        partial.write_text(payload, encoding="utf-8")` | `        partial.write_text(payload, encoding=None)` |
| 561 | _write_log | 4 | `        partial.write_text(payload, encoding="utf-8")` | `        partial.write_text(payload, )` |
| 562 | _write_log | 4 | `        partial.write_text(payload, encoding="utf-8")` | `        partial.write_text(payload, encoding="UTF-8")` |
| 563 | _write_log | 7 | `        partial.unlink(missing_ok=True)` | `        partial.unlink(missing_ok=None)` |
| 564 | _write_log | 7 | `        partial.unlink(missing_ok=True)` | `        partial.unlink(missing_ok=False)` |

#### R045 — _archive_investment_attempts

`_archive_investment_attempts` records the expected project inputs and their fetch attempts, verifies selected snapshots, and reports evidence failures. Items 16–27 corrupt empty-body sidecar fields; require the source's exact address, host, publisher and fixed retrieval, with empty digest, zero bytes and empty modification and terms values. Items 28–34 alter project selection or bypass verified evidence: give a successful project attempt with a string snapshot identity, a failed attempt and a different-source attempt, requiring only the valid project selection and retention of the verification refusal if its snapshot is corrupted. Items 35–57 damage conversion of a read or verification exception; induce that exception and require code 1, source `investment_evidence`, check `evidence_audit_incomplete`, expected `archived attempt evidence` and observed `write or verification failed`. Items 58–81 lose the audit failure in the log or returned record; compare each forwarded field and preserve the empty public address. This entire helper is absent from R101's measured file and therefore needs this separate retained evidence within the same file work list.

Changes in R045:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 16 | _archive_investment_attempts | 17 | `            digest="",` | `            digest=None,` |
| 17 | _archive_investment_attempts | 18 | `            nbytes=0,` | `            nbytes=None,` |
| 18 | _archive_investment_attempts | 19 | `            fetch_url=entry.url,` | `            fetch_url=None,` |
| 19 | _archive_investment_attempts | 20 | `            fetch_host=entry.fetch_host,` | `            fetch_host=None,` |
| 20 | _archive_investment_attempts | 21 | `            retrieved_utc=retrieved,` | `            retrieved_utc=None,` |
| 21 | _archive_investment_attempts | 22 | `            publisher=entry.publisher,` | `            publisher=None,` |
| 22 | _archive_investment_attempts | 23 | `            source_modified="",` | `            source_modified=None,` |
| 23 | _archive_investment_attempts | 25 | `            terms_sha256="",` | `            terms_sha256=None,` |
| 24 | _archive_investment_attempts | 17 | `            digest="",` | `            digest="XXXX",` |
| 25 | _archive_investment_attempts | 18 | `            nbytes=0,` | `            nbytes=1,` |
| 26 | _archive_investment_attempts | 23 | `            source_modified="",` | `            source_modified="XXXX",` |
| 27 | _archive_investment_attempts | 25 | `            terms_sha256="",` | `            terms_sha256="XXXX",` |
| 28 | _archive_investment_attempts | 31 | `        project_registrations = tuple(<br>            registration<br>            for registration in expected<br>            if registration.source_id == "fdi_projects"<br>        )` | `        project_registrations = None` |
| 29 | _archive_investment_attempts | 34 | `            if registration.source_id == "fdi_projects"` | `            if registration.source_id == "XXfdi_projectsXX"` |
| 30 | _archive_investment_attempts | 34 | `            if registration.source_id == "fdi_projects"` | `            if registration.source_id == "FDI_PROJECTS"` |
| 31 | _archive_investment_attempts | 36 | `        projection = None` | `        projection = ""` |
| 32 | _archive_investment_attempts | 46 | `                and attempt.status == "success"<br>                and isinstance(attempt.snapshot_identity, str)` | `                and attempt.status == "success" or isinstance(attempt.snapshot_identity, str)` |
| 33 | _archive_investment_attempts | 49 | `            projection = build_cache_evidence(<br>                cache,<br>                projects=selections,<br>                milestones=(),<br>                expected=project_registrations,<br>                attempts=tuple(attempts),<br>            )` | `            projection = None` |
| 34 | _archive_investment_attempts | 58 | `            if isinstance(projection, InvestmentFailure)` | `            if (isinstance(projection, InvestmentFailure)) and False` |
| 35 | _archive_investment_attempts | 68 | `        audited = InvestmentFailure(<br>            1,<br>            "investment_evidence",<br>            "",<br>            "evidence_audit_incomplete",<br>            "archived attempt evidence",<br>            "write or verification failed",<br>        )` | `        audited = None` |
| 36 | _archive_investment_attempts | 69 | `            1,` | `            None,` |
| 37 | _archive_investment_attempts | 70 | `            "investment_evidence",` | `            None,` |
| 38 | _archive_investment_attempts | 71 | `            "",` | `            None,` |
| 39 | _archive_investment_attempts | 72 | `            "evidence_audit_incomplete",` | `            None,` |
| 40 | _archive_investment_attempts | 73 | `            "archived attempt evidence",` | `            None,` |
| 41 | _archive_investment_attempts | 74 | `            "write or verification failed",` | `            None,` |
| 42 | _archive_investment_attempts | 69 | `            1,` | `empty` |
| 43 | _archive_investment_attempts | 70 | `            "investment_evidence",` | `empty` |
| 44 | _archive_investment_attempts | 71 | `            "",` | `empty` |
| 45 | _archive_investment_attempts | 72 | `            "evidence_audit_incomplete",` | `empty` |
| 46 | _archive_investment_attempts | 73 | `            "archived attempt evidence",` | `empty` |
| 47 | _archive_investment_attempts | 74 | `            "write or verification failed",<br>        )` | `            )` |
| 48 | _archive_investment_attempts | 69 | `            1,` | `            2,` |
| 49 | _archive_investment_attempts | 70 | `            "investment_evidence",` | `            "XXinvestment_evidenceXX",` |
| 50 | _archive_investment_attempts | 70 | `            "investment_evidence",` | `            "INVESTMENT_EVIDENCE",` |
| 51 | _archive_investment_attempts | 71 | `            "",` | `            "XXXX",` |
| 52 | _archive_investment_attempts | 72 | `            "evidence_audit_incomplete",` | `            "XXevidence_audit_incompleteXX",` |
| 53 | _archive_investment_attempts | 72 | `            "evidence_audit_incomplete",` | `            "EVIDENCE_AUDIT_INCOMPLETE",` |
| 54 | _archive_investment_attempts | 73 | `            "archived attempt evidence",` | `            "XXarchived attempt evidenceXX",` |
| 55 | _archive_investment_attempts | 73 | `            "archived attempt evidence",` | `            "ARCHIVED ATTEMPT EVIDENCE",` |
| 56 | _archive_investment_attempts | 74 | `            "write or verification failed",` | `            "XXwrite or verification failedXX",` |
| 57 | _archive_investment_attempts | 74 | `            "write or verification failed",` | `            "WRITE OR VERIFICATION FAILED",` |
| 58 | _archive_investment_attempts | 78 | `            fail_line(<br>                audited.source_id,<br>                audited.url,<br>                audited.check,<br>                audited.expected,<br>                audited.observed,<br>            )` | `            None` |
| 59 | _archive_investment_attempts | 79 | `                audited.source_id,` | `                None,` |
| 60 | _archive_investment_attempts | 80 | `                audited.url,` | `                None,` |
| 61 | _archive_investment_attempts | 81 | `                audited.check,` | `                None,` |
| 62 | _archive_investment_attempts | 82 | `                audited.expected,` | `                None,` |
| 63 | _archive_investment_attempts | 83 | `                audited.observed,` | `                None,` |
| 64 | _archive_investment_attempts | 79 | `                audited.source_id,` | `empty` |
| 65 | _archive_investment_attempts | 80 | `                audited.url,` | `empty` |
| 66 | _archive_investment_attempts | 81 | `                audited.check,` | `empty` |
| 67 | _archive_investment_attempts | 82 | `                audited.expected,` | `empty` |
| 68 | _archive_investment_attempts | 83 | `                audited.observed,<br>            )` | `                )` |
| 69 | _archive_investment_attempts | 87 | `            1,` | `            None,` |
| 70 | _archive_investment_attempts | 88 | `            audited.source_id,` | `            None,` |
| 71 | _archive_investment_attempts | 89 | `            audited.url,` | `            None,` |
| 72 | _archive_investment_attempts | 90 | `            audited.check,` | `            None,` |
| 73 | _archive_investment_attempts | 91 | `            audited.expected,` | `            None,` |
| 74 | _archive_investment_attempts | 92 | `            audited.observed,` | `            None,` |
| 75 | _archive_investment_attempts | 87 | `            1,` | `empty` |
| 76 | _archive_investment_attempts | 88 | `            audited.source_id,` | `empty` |
| 77 | _archive_investment_attempts | 89 | `            audited.url,` | `empty` |
| 78 | _archive_investment_attempts | 90 | `            audited.check,` | `empty` |
| 79 | _archive_investment_attempts | 91 | `            audited.expected,` | `empty` |
| 80 | _archive_investment_attempts | 92 | `            audited.observed,<br>        )` | `            )` |
| 81 | _archive_investment_attempts | 87 | `            1,` | `            2,` |

### R105 — custodian/src/eii_custodian/publicdata/fetch/transport.py

Task coverage for `custodian/src/eii_custodian/publicdata/fetch/transport.py`: background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30; latest measurement R105.

`custodian/src/eii_custodian/publicdata/fetch/transport.py` was read at the measured commit `4d7933a` for R105.

#### R105 — open_https

`open_https` validates the requested address and certificate context, checks redirects and returns body provenance. Items 1–5 alter token defaults, reviewed-address membership or certificate requirements; separately try an unreviewed otherwise admitted URL, an invalid transport address, and contexts lacking either required certificate verification or hostname checking, requiring `blocked_host` for address failures and `unreachable` for unsafe contexts before any send. Items 6–47 change request construction, credential checks, read limits, final-address refusals, response metadata or keyed-response cleanup; use an invented admitted request with fixed body bytes, a distinct final address and known entity tag, requiring the original body, its independently derived digest, redirect sequence and tag. For a keyed fixture, require only its key-free endpoint, an empty redirect sequence and null tag, with cleaned response content; an absent required credential must refuse before a send. Inspect the specific altered argument in each listed row against this successful control, then add the corresponding failure case rather than accepting a refusal-only test.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 1 | open_https | 1 | `    token: str = "",` | `    token: str = "XXXX",` |
| 2 | open_https | 10 | `        and (url not in reviewed_urls or not _stream_allowed(url))` | `        and (url not in reviewed_urls and not _stream_allowed(url))` |
| 3 | open_https | 14 | `        ssl_context.verify_mode != ssl.CERT_REQUIRED or not ssl_context.check_hostname` | `        ssl_context.verify_mode != ssl.CERT_REQUIRED and not ssl_context.check_hostname` |
| 4 | open_https | 14 | `        ssl_context.verify_mode != ssl.CERT_REQUIRED or not ssl_context.check_hostname` | `        ssl_context.verify_mode == ssl.CERT_REQUIRED or not ssl_context.check_hostname` |
| 5 | open_https | 14 | `        ssl_context.verify_mode != ssl.CERT_REQUIRED or not ssl_context.check_hostname` | `        ssl_context.verify_mode != ssl.CERT_REQUIRED or ssl_context.check_hostname` |
| 6 | open_https | 16 | `        raise TransportFault("unreachable", url)` | `        raise TransportFault("unreachable", None)` |
| 7 | open_https | 21 | `        token,` | `        None,` |
| 8 | open_https | 22 | `        strict=reviewed_urls is not None,` | `        strict=None,` |
| 9 | open_https | 23 | `        reviewed_urls=reviewed_urls,` | `        reviewed_urls=None,` |
| 10 | open_https | 21 | `        token,` | `empty` |
| 11 | open_https | 22 | `        strict=reviewed_urls is not None,` | `empty` |
| 12 | open_https | 23 | `        reviewed_urls=reviewed_urls,` | `empty` |
| 13 | open_https | 22 | `        strict=reviewed_urls is not None,` | `        strict=reviewed_urls is None,` |
| 14 | open_https | 24 | `        keyed_url=str(url) if keyed else None,` | `        keyed_url=str(None) if keyed else None,` |
| 15 | open_https | 29 | `        opener = urllib.request.build_opener(<br>            guard, urllib.request.HTTPSHandler(context=ssl_context)<br>        )` | `        opener = None` |
| 16 | open_https | 30 | `            guard, urllib.request.HTTPSHandler(context=ssl_context)` | `            None, urllib.request.HTTPSHandler(context=ssl_context)` |
| 17 | open_https | 30 | `            guard, urllib.request.HTTPSHandler(context=ssl_context)` | `            guard, None` |
| 18 | open_https | 30 | `            guard, urllib.request.HTTPSHandler(context=ssl_context)` | `            urllib.request.HTTPSHandler(context=ssl_context)` |
| 19 | open_https | 30 | `            guard, urllib.request.HTTPSHandler(context=ssl_context)<br>        )` | `            guard, )` |
| 20 | open_https | 30 | `            guard, urllib.request.HTTPSHandler(context=ssl_context)` | `            guard, urllib.request.HTTPSHandler(context=None)` |
| 21 | open_https | 32 | `    request_headers = dict(headers) if headers else {}` | `    request_headers = dict(headers) if (headers) and False else {}` |
| 22 | open_https | 32 | `    request_headers = dict(headers) if headers else {}` | `    request_headers = dict(None) if headers else {}` |
| 23 | open_https | 35 | `    method = "GET"` | `    method = None` |
| 24 | open_https | 44 | `            raise TransportFault("blocked_host", FORECAST_URL)` | `            raise TransportFault(None, FORECAST_URL)` |
| 25 | open_https | 44 | `            raise TransportFault("blocked_host", FORECAST_URL)` | `            raise TransportFault("blocked_host", None)` |
| 26 | open_https | 44 | `            raise TransportFault("blocked_host", FORECAST_URL)` | `            raise TransportFault("XXblocked_hostXX", FORECAST_URL)` |
| 27 | open_https | 44 | `            raise TransportFault("blocked_host", FORECAST_URL)` | `            raise TransportFault("BLOCKED_HOST", FORECAST_URL)` |
| 28 | open_https | 47 | `            raise TransportFault("credentials", str(url))` | `            raise TransportFault(None, str(url))` |
| 29 | open_https | 47 | `            raise TransportFault("credentials", str(url))` | `            raise TransportFault("credentials", None)` |
| 30 | open_https | 47 | `            raise TransportFault("credentials", str(url))` | `            raise TransportFault("XXcredentialsXX", str(url))` |
| 31 | open_https | 47 | `            raise TransportFault("credentials", str(url))` | `            raise TransportFault("CREDENTIALS", str(url))` |
| 32 | open_https | 47 | `            raise TransportFault("credentials", str(url))` | `            raise TransportFault("credentials", str(None))` |
| 33 | open_https | 48 | `        address += "?" + urlencode({**url.parameters, parameter: url.environ[variable]})` | `        address += "XX?XX" + urlencode({**url.parameters, parameter: url.environ[variable]})` |
| 34 | open_https | 52 | `        with opener.open(request, timeout=HTTP_TIMEOUT_S) as response:` | `        with opener.open(request, timeout=None) as response:` |
| 35 | open_https | 57 | `                final not in reviewed_urls or not _stream_allowed(final)` | `                final not in reviewed_urls and not _stream_allowed(final)` |
| 36 | open_https | 59 | `                raise TransportFault("blocked_host", "")` | `                raise TransportFault(None, "")` |
| 37 | open_https | 59 | `                raise TransportFault("blocked_host", "")` | `                raise TransportFault("blocked_host", None)` |
| 38 | open_https | 59 | `                raise TransportFault("blocked_host", "")` | `                raise TransportFault("")` |
| 39 | open_https | 59 | `                raise TransportFault("blocked_host", "")` | `                raise TransportFault("blocked_host", )` |
| 40 | open_https | 59 | `                raise TransportFault("blocked_host", "")` | `                raise TransportFault("XXblocked_hostXX", "")` |
| 41 | open_https | 59 | `                raise TransportFault("blocked_host", "")` | `                raise TransportFault("BLOCKED_HOST", "")` |
| 42 | open_https | 59 | `                raise TransportFault("blocked_host", "")` | `                raise TransportFault("blocked_host", "XXXX")` |
| 43 | open_https | 64 | `        fault = "blocked_host"` | `        fault = "XXblocked_hostXX"` |
| 44 | open_https | 67 | `            raise TransportFault("http", url) from None` | `            raise TransportFault("http", None) from None` |
| 45 | open_https | 80 | `            body = json.dumps(_clean(json.loads(body))).encode()` | `            body = json.dumps(None).encode()` |
| 46 | open_https | 80 | `            body = json.dumps(_clean(json.loads(body))).encode()` | `            body = json.dumps(_clean(None)).encode()` |
| 47 | open_https | 83 | `        final, hops, etag = str(url), [], None` | `        final, hops, etag = str(None), [], None` |

#### R105 — _redirect_guard

`_redirect_guard` constructs the redirect handler with its captured token and strict-address policy. Item 48 changes the token when no argument is passed; construct the handler without a token and follow an invented admitted archive redirect, requiring no authorisation header. Item 49 makes default redirects strict; a normally admitted address with a harmless public query must remain admissible in non-strict mode, while explicitly strict mode must refuse it. If every production caller passes both arguments explicitly, document those call sites before claiming default-only changes equivalent.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 48 | _redirect_guard | 1 | `    token: str = "",` | `    token: str = "XXXX",` |
| 49 | _redirect_guard | 1 | `    strict: bool = False,` | `    strict: bool = True,` |

#### R105 — redirect_request

`_Guard.redirect_request` records each redirect, refuses keyed or sign-in destinations, then strips and selectively restores authorisation. Items 50–54 alter the keyed or sign-in refusal: require `blocked_host` with the original key-free endpoint for a keyed redirect, and `credential_missing_or_not_accepted` for the sign-in host. Items 55–66 affect strict validation, checked address membership or header forwarding; compare an admitted non-strict destination, the same destination in strict mode and an unreviewed destination, checking the exact redirect list and rejection before a second request. An invented header may reach only an authorised granule host, and a redirected request must never inherit it merely because the previous request had it.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 50 | redirect_request | 19 | `                raise TransportFault("blocked_host", keyed_url)` | `                raise TransportFault(None, keyed_url)` |
| 51 | redirect_request | 19 | `                raise TransportFault("blocked_host", keyed_url)` | `                raise TransportFault("blocked_host", None)` |
| 52 | redirect_request | 19 | `                raise TransportFault("blocked_host", keyed_url)` | `                raise TransportFault("XXblocked_hostXX", keyed_url)` |
| 53 | redirect_request | 19 | `                raise TransportFault("blocked_host", keyed_url)` | `                raise TransportFault("BLOCKED_HOST", keyed_url)` |
| 54 | redirect_request | 22 | `                raise TransportFault("credential_missing_or_not_accepted", newurl)` | `                raise TransportFault("XXcredential_missing_or_not_acceptedXX", newurl)` |
| 55 | redirect_request | 25 | `                or (strict and not _stream_allowed(newurl))` | `                or (strict or not _stream_allowed(newurl))` |
| 56 | redirect_request | 25 | `                or (strict and not _stream_allowed(newurl))` | `                or (strict and _stream_allowed(newurl))` |
| 57 | redirect_request | 30 | `                self, req, fp, code, msg, headers, newurl` | `                None, req, fp, code, msg, headers, newurl` |
| 58 | redirect_request | 30 | `                self, req, fp, code, msg, headers, newurl` | `                self, req, None, code, msg, headers, newurl` |
| 59 | redirect_request | 30 | `                self, req, fp, code, msg, headers, newurl` | `                self, req, fp, code, None, headers, newurl` |
| 60 | redirect_request | 30 | `                self, req, fp, code, msg, headers, newurl` | `                self, req, fp, code, msg, None, newurl` |
| 61 | redirect_request | 37 | `                for name, value in authorization_header(newurl, token).items():` | `                for name, value in authorization_header(None, token).items():` |
| 62 | redirect_request | 37 | `                for name, value in authorization_header(newurl, token).items():` | `                for name, value in authorization_header(newurl, None).items():` |
| 63 | redirect_request | 38 | `                    redirected.add_header(name, value)` | `                    redirected.add_header(None, value)` |
| 64 | redirect_request | 38 | `                    redirected.add_header(name, value)` | `                    redirected.add_header(name, None)` |
| 65 | redirect_request | 38 | `                    redirected.add_header(name, value)` | `                    redirected.add_header(value)` |
| 66 | redirect_request | 38 | `                    redirected.add_header(name, value)` | `                    redirected.add_header(name, )` |

#### R105 — _stream_allowed

`_stream_allowed` accepts only approved credential-free HTTPS stream addresses. Item 67 replaces the permitted explicit port; an otherwise admitted address using port 443 must return true and port 444 false. Items 68–69 move the control-character cutoff: compare a literal space, an exclamation mark in an admitted path and a neighbouring control character without involving a live request. Item 70 turns malformed-port parsing into acceptance; an address whose port cannot be parsed must return false. Validate the hostname against an invented allow-list fixture so the port and character cases actually reach this predicate.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 67 | _stream_allowed | 7 | `            and parts.port in (None, 443)` | `            and parts.port in (None, 444)` |
| 68 | _stream_allowed | 8 | `            and not any(ord(char) <= 32 for char in url)` | `            and not any(ord(char) < 32 for char in url)` |
| 69 | _stream_allowed | 8 | `            and not any(ord(char) <= 32 for char in url)` | `            and not any(ord(char) <= 33 for char in url)` |
| 70 | _stream_allowed | 11 | `        return False` | `        return True` |

#### R105 — open_attempt

`open_attempt` sends one checked GET request and refuses redirects rather than following them. Items 71–91 alter the request object, method, optional header, timeout, read result or exception classification. An invented accepted address with a fixed response body must produce `AttemptResult` category `ok` with exactly those bytes; inspect the outgoing method `GET`, the declared timeout and the header's presence only when both name and value are nonempty. An HTTP failure must raise `OpenerFault` with `http`, and a connection failure `unreachable`, while the redirect fixture must terminate with `redirect` and no second send. These cases exercise the actual request construction so an invalid method cannot be hidden behind a preconstructed response.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 71 | open_attempt | 17 | `    call = urllib.request.Request(request.url, method="GET")` | `    call = None` |
| 72 | open_attempt | 17 | `    call = urllib.request.Request(request.url, method="GET")` | `    call = urllib.request.Request(request.url, method=None)` |
| 73 | open_attempt | 17 | `    call = urllib.request.Request(request.url, method="GET")` | `    call = urllib.request.Request(request.url, )` |
| 74 | open_attempt | 17 | `    call = urllib.request.Request(request.url, method="GET")` | `    call = urllib.request.Request(request.url, method="XXGETXX")` |
| 75 | open_attempt | 17 | `    call = urllib.request.Request(request.url, method="GET")` | `    call = urllib.request.Request(request.url, method="get")` |
| 76 | open_attempt | 18 | `    if request.header_name and request.header_value:` | `    if request.header_name or request.header_value:` |
| 77 | open_attempt | 19 | `        call.add_header(request.header_name, request.header_value)` | `        call.add_header(None, request.header_value)` |
| 78 | open_attempt | 19 | `        call.add_header(request.header_name, request.header_value)` | `        call.add_header(request.header_name, None)` |
| 79 | open_attempt | 19 | `        call.add_header(request.header_name, request.header_value)` | `        call.add_header(request.header_value)` |
| 80 | open_attempt | 19 | `        call.add_header(request.header_name, request.header_value)` | `        call.add_header(request.header_name, )` |
| 81 | open_attempt | 22 | `        with opener.open(call, timeout=HTTP_TIMEOUT_S) as response:` | `        with opener.open(None, timeout=HTTP_TIMEOUT_S) as response:` |
| 82 | open_attempt | 22 | `        with opener.open(call, timeout=HTTP_TIMEOUT_S) as response:` | `        with opener.open(call, timeout=None) as response:` |
| 83 | open_attempt | 22 | `        with opener.open(call, timeout=HTTP_TIMEOUT_S) as response:` | `        with opener.open(timeout=HTTP_TIMEOUT_S) as response:` |
| 84 | open_attempt | 22 | `        with opener.open(call, timeout=HTTP_TIMEOUT_S) as response:` | `        with opener.open(call, ) as response:` |
| 85 | open_attempt | 23 | `            body = response.read()` | `            body = None` |
| 86 | open_attempt | 30 | `    return AttemptResult("ok", body)` | `    return AttemptResult(None, body)` |
| 87 | open_attempt | 30 | `    return AttemptResult("ok", body)` | `    return AttemptResult("ok", None)` |
| 88 | open_attempt | 30 | `    return AttemptResult("ok", body)` | `    return AttemptResult(body)` |
| 89 | open_attempt | 30 | `    return AttemptResult("ok", body)` | `    return AttemptResult("ok", )` |
| 90 | open_attempt | 30 | `    return AttemptResult("ok", body)` | `    return AttemptResult("XXokXX", body)` |
| 91 | open_attempt | 30 | `    return AttemptResult("ok", body)` | `    return AttemptResult("OK", body)` |

#### R105 — __repr__

The text representations of `SlotSecrets` and `PreparedRequest` deliberately hide their fields. Items 92–94 change the first representation and items 97–99 the second; construct both with invented sensitive values and require exactly `SlotSecrets(redacted)` and `PreparedRequest(redacted)`, respectively. Check absence of the invented values separately: a harmless change of case may preserve secrecy but is not automatically equivalent to a contract that also fixes the diagnostic spelling.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 92 | __repr__ | 1 | `    return "SlotSecrets(redacted)"` | `    return "XXSlotSecrets(redacted)XX"` |
| 93 | __repr__ | 1 | `    return "SlotSecrets(redacted)"` | `    return "slotsecrets(redacted)"` |
| 94 | __repr__ | 1 | `    return "SlotSecrets(redacted)"` | `    return "SLOTSECRETS(REDACTED)"` |
| 97 | __repr__ | 1 | `    return "PreparedRequest(redacted)"` | `    return "XXPreparedRequest(redacted)XX"` |
| 98 | __repr__ | 1 | `    return "PreparedRequest(redacted)"` | `    return "preparedrequest(redacted)"` |
| 99 | __repr__ | 1 | `    return "PreparedRequest(redacted)"` | `    return "PREPAREDREQUEST(REDACTED)"` |

#### R105 — for_slot

`SlotSecrets.for_slot` delegates slot selection to `read_slot`. Item 95 discards the requested slot. Give the two slots distinct invented values and require each named lookup to return its own value, while an unknown slot returns the empty string; this detects a null forwarded slot without needing any real credential.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 95 | for_slot | 1 | `    return self.read_slot(slot)` | `    return self.read_slot(None)` |

#### R105 — read_slot

`SlotSecrets.read_slot` returns the selected field or an empty value for an unknown name. Item 96 changes only that unknown-name result to `XXXX`. Supply an invented unrecognised slot and require exactly the empty string, then confirm the two recognised names still select their distinct fields; caller restrictions could explain the change only if they prove an unknown name cannot reach this public method.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 96 | read_slot | 4 | `    return ""` | `    return "XXXX"` |

#### R105 — perform

`perform` checks a trade descriptor before constructing the request passed to its opener. Items 100–101 change the empty sensitive-value fallback or forbidden-family predicate: compare an allowed family, an exact forbidden family and a family containing a forbidden token, requiring `forbidden_endpoint` without an opener call for the latter cases. Items 102–105 damage the `query_key` refusal; put an invented sensitive value into a prohibited request-address position and require that reason with the value absent from diagnostics. Items 106–118 change the prepared request or handling of a returned location; require its exact endpoint identity and empty header when no value was selected, and make an unapproved redirected location refuse before any follow-up call. A benign successful descriptor must still return the opener's original result.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 100 | perform | 17 | `    secret = header_value or ""` | `    secret = header_value or "XXXX"` |
| 101 | perform | 21 | `    forbidden = family in FORBIDDEN_FAMILIES or any(` | `    forbidden = family in FORBIDDEN_FAMILIES and any(` |
| 102 | perform | 30 | `        raise refusal_hiding(policy, descriptor, "query_key", header_value) from None` | `        raise refusal_hiding(None, descriptor, "query_key", header_value) from None` |
| 103 | perform | 30 | `        raise refusal_hiding(policy, descriptor, "query_key", header_value) from None` | `        raise refusal_hiding(policy, descriptor, None, header_value) from None` |
| 104 | perform | 30 | `        raise refusal_hiding(policy, descriptor, "query_key", header_value) from None` | `        raise refusal_hiding(policy, descriptor, "XXquery_keyXX", header_value) from None` |
| 105 | perform | 30 | `        raise refusal_hiding(policy, descriptor, "query_key", header_value) from None` | `        raise refusal_hiding(policy, descriptor, "QUERY_KEY", header_value) from None` |
| 106 | perform | 35 | `        endpoint_id=descriptor.endpoint_id(),` | `        endpoint_id=None,` |
| 107 | perform | 34 | `        header_value=header_value or "",` | `        header_value=header_value or "XXXX",` |
| 108 | perform | 40 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(policy, descriptor, "provider_error", ) from None` |
| 109 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(None, descriptor, "provider_error", secret) from None` |
| 110 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(policy, None, "provider_error", secret) from None` |
| 111 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(policy, descriptor, None, secret) from None` |
| 112 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(policy, descriptor, "provider_error", None) from None` |
| 113 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(descriptor, "provider_error", secret) from None` |
| 114 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(policy, "provider_error", secret) from None` |
| 115 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(policy, descriptor, secret) from None` |
| 116 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(policy, descriptor, "provider_error", ) from None` |
| 117 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(policy, descriptor, "XXprovider_errorXX", secret) from None` |
| 118 | perform | 42 | `        raise refusal(policy, descriptor, "provider_error", secret) from None` | `        raise refusal(policy, descriptor, "PROVIDER_ERROR", secret) from None` |

#### R105 — _url_has_secret

`_url_has_secret` detects either a credential-shaped address field or the selected sensitive value after percent decoding. Item 119 makes the first positive branch return false. An invented address containing a recognised credential-query name but a value different from the selected test token must still return true; add a normal public path returning false so merely finding the selected token does not mask this branch.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 119 | _url_has_secret | 2 | `        return True` | `        return False` |

#### R105 — _checked_url

`_checked_url` requires both a typed policy and a typed descriptor before producing the policy-approved address. Items 120–123 weaken that paired type check or change its `descriptor` diagnostic. Pass an invalid policy with a valid descriptor and then the reverse, requiring `OpenerFault` with exactly `descriptor` in both cases; the valid pair must return the expected safe public address. Checking only a pair of invalid values would miss the change from either-invalid to both-invalid.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 120 | _checked_url | 1 | `    if not isinstance(policy, Policy) or not isinstance(descriptor, Descriptor):` | `    if not isinstance(policy, Policy) and not isinstance(descriptor, Descriptor):` |
| 121 | _checked_url | 2 | `        raise OpenerFault("descriptor")` | `        raise OpenerFault(None)` |
| 122 | _checked_url | 2 | `        raise OpenerFault("descriptor")` | `        raise OpenerFault("XXdescriptorXX")` |
| 123 | _checked_url | 2 | `        raise OpenerFault("descriptor")` | `        raise OpenerFault("DESCRIPTOR")` |

#### R105 — _refuse_redirect

`_refuse_redirect` examines a reported trade redirect against the request host, configured redirect hosts and credential restrictions. Items 124–129 change type validation or the empty header; reject each singly invalid typed argument with `descriptor`, and inspect an empty-header control without filler text in its refusal. Items 130–173 alter forbidden-family refusal fields, address parsing, admitted-host construction or cross-origin credential refusal. Use an invented policy with different request and permitted redirect hosts: key-free same-host and configured-host HTTPS locations pass, whereas an unlisted host, non-HTTPS scheme, user information, fragment or credential-query name must yield `redirect_host`. A header-bearing cross-host redirect must yield `cross_origin_credential`, and a forbidden endpoint token must yield `forbidden_endpoint`; compare the refusal's endpoint identity and safe address as well as its reason, with no sensitive value in any field.

Changes in R105:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 124 | _refuse_redirect | 11 | `    if not isinstance(policy, Policy) or not isinstance(descriptor, Descriptor):` | `    if not isinstance(policy, Policy) and not isinstance(descriptor, Descriptor):` |
| 125 | _refuse_redirect | 12 | `        raise OpenerFault("descriptor")` | `        raise OpenerFault(None)` |
| 126 | _refuse_redirect | 12 | `        raise OpenerFault("descriptor")` | `        raise OpenerFault("XXdescriptorXX")` |
| 127 | _refuse_redirect | 12 | `        raise OpenerFault("descriptor")` | `        raise OpenerFault("DESCRIPTOR")` |
| 128 | _refuse_redirect | 14 | `    header = header_value or ""` | `    header = header_value and ""` |
| 129 | _refuse_redirect | 14 | `    header = header_value or ""` | `    header = header_value or "XXXX"` |
| 130 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(None, descriptor, "forbidden_endpoint", header) from None` |
| 131 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(policy, None, "forbidden_endpoint", header) from None` |
| 132 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(policy, descriptor, None, header) from None` |
| 133 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(policy, descriptor, "forbidden_endpoint", None) from None` |
| 134 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(descriptor, "forbidden_endpoint", header) from None` |
| 135 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(policy, "forbidden_endpoint", header) from None` |
| 136 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(policy, descriptor, header) from None` |
| 137 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(policy, descriptor, "forbidden_endpoint", ) from None` |
| 138 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(policy, descriptor, "XXforbidden_endpointXX", header) from None` |
| 139 | _refuse_redirect | 16 | `        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None` | `        raise refusal(policy, descriptor, "FORBIDDEN_ENDPOINT", header) from None` |
| 140 | _refuse_redirect | 18 | `    template = policy.template(descriptor.api_class, descriptor.endpoint_family)` | `    template = None` |
| 141 | _refuse_redirect | 18 | `    template = policy.template(descriptor.api_class, descriptor.endpoint_family)` | `    template = policy.template(None, descriptor.endpoint_family)` |
| 142 | _refuse_redirect | 18 | `    template = policy.template(descriptor.api_class, descriptor.endpoint_family)` | `    template = policy.template(descriptor.api_class, None)` |
| 143 | _refuse_redirect | 19 | `    request_host = template.host if template is not None else ""` | `    request_host = None` |
| 144 | _refuse_redirect | 19 | `    request_host = template.host if template is not None else ""` | `    request_host = template.host if (template is not None) and False else ""` |
| 145 | _refuse_redirect | 19 | `    request_host = template.host if template is not None else ""` | `    request_host = template.host if (template is not None) or True else ""` |
| 146 | _refuse_redirect | 19 | `    request_host = template.host if template is not None else ""` | `    request_host = template.host if template is None else ""` |
| 147 | _refuse_redirect | 19 | `    request_host = template.host if template is not None else ""` | `    request_host = template.host if template is not None else "XXXX"` |
| 148 | _refuse_redirect | 20 | `    redirect_host = (parts.hostname or "").casefold()` | `    redirect_host = (parts.hostname or "XXXX").casefold()` |
| 149 | _refuse_redirect | 23 | `        for name, _value in parse_qsl(parts.query, keep_blank_values=True)` | `        for name, _value in parse_qsl(None, keep_blank_values=True)` |
| 150 | _refuse_redirect | 23 | `        for name, _value in parse_qsl(parts.query, keep_blank_values=True)` | `        for name, _value in parse_qsl(parts.query, keep_blank_values=None)` |
| 151 | _refuse_redirect | 23 | `        for name, _value in parse_qsl(parts.query, keep_blank_values=True)` | `        for name, _value in parse_qsl(parts.query, )` |
| 152 | _refuse_redirect | 23 | `        for name, _value in parse_qsl(parts.query, keep_blank_values=True)` | `        for name, _value in parse_qsl(parts.query, keep_blank_values=False)` |
| 153 | _refuse_redirect | 25 | `    secret = bool(parts.username or parts.password or parts.fragment)` | `    secret = None` |
| 154 | _refuse_redirect | 25 | `    secret = bool(parts.username or parts.password or parts.fragment)` | `    secret = bool(None)` |
| 155 | _refuse_redirect | 25 | `    secret = bool(parts.username or parts.password or parts.fragment)` | `    secret = bool(parts.username or parts.password and parts.fragment)` |
| 156 | _refuse_redirect | 25 | `    secret = bool(parts.username or parts.password or parts.fragment)` | `    secret = bool(parts.username and parts.password or parts.fragment)` |
| 157 | _refuse_redirect | 26 | `    keyed_query = bool(names & CREDENTIAL_QUERY_NAMES)` | `    keyed_query = None` |
| 158 | _refuse_redirect | 26 | `    keyed_query = bool(names & CREDENTIAL_QUERY_NAMES)` | `    keyed_query = bool(None)` |
| 159 | _refuse_redirect | 29 | `    if parts.scheme.casefold() != "https" or secret or keyed_query:` | `    if parts.scheme.casefold() != "https" or secret and keyed_query:` |
| 160 | _refuse_redirect | 29 | `    if parts.scheme.casefold() != "https" or secret or keyed_query:` | `    if parts.scheme.casefold() != "https" and secret or keyed_query:` |
| 161 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(None, descriptor, "redirect_host", header) from None` |
| 162 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(policy, None, "redirect_host", header) from None` |
| 163 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(policy, descriptor, None, header) from None` |
| 164 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(policy, descriptor, "redirect_host", None) from None` |
| 165 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(descriptor, "redirect_host", header) from None` |
| 166 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(policy, "redirect_host", header) from None` |
| 167 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(policy, descriptor, header) from None` |
| 168 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(policy, descriptor, "redirect_host", ) from None` |
| 169 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(policy, descriptor, "XXredirect_hostXX", header) from None` |
| 170 | _refuse_redirect | 30 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(policy, descriptor, "REDIRECT_HOST", header) from None` |
| 171 | _refuse_redirect | 32 | `        raise refusal(policy, descriptor, "redirect_host", header) from None` | `        raise refusal(policy, descriptor, "redirect_host", ) from None` |
| 172 | _refuse_redirect | 33 | `    if header_value and redirect_host != request_host:` | `    if header_value or redirect_host != request_host:` |
| 173 | _refuse_redirect | 34 | `        raise refusal(policy, descriptor, "cross_origin_credential", header) from None` | `        raise refusal(policy, descriptor, "cross_origin_credential", ) from None` |

### R107 — custodian/src/eii_custodian/publicdata/fetch/checks.py

Task coverage for `custodian/src/eii_custodian/publicdata/fetch/checks.py`: background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30; latest measurement R107.

`custodian/src/eii_custodian/publicdata/fetch/checks.py` was read at the measured commit `2ae1299` for R107.

#### R107 — count_failure

`count_failure` enforces the entry's declared row-count interval and reports an unreadable or out-of-range body. Items 1–9 corrupt the unreadable failure: for a declared interval and null rows require code 1, the original public URL, check `row_count`, the exact interval text and observed `unreadable`. Items 10–15 lose fields for a measured count outside that interval; use a nonempty list below the lower bound and require its decimal length as observed, while an in-range control returns null. Testing only whether a failure object exists misses every altered field here.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 1 | count_failure | 6 | `        return AttemptFailure(1, url, "row_count", span, "unreadable")` | `        return AttemptFailure(None, url, "row_count", span, "unreadable")` |
| 2 | count_failure | 6 | `        return AttemptFailure(1, url, "row_count", span, "unreadable")` | `        return AttemptFailure(1, url, None, span, "unreadable")` |
| 3 | count_failure | 6 | `        return AttemptFailure(1, url, "row_count", span, "unreadable")` | `        return AttemptFailure(1, url, "row_count", None, "unreadable")` |
| 4 | count_failure | 6 | `        return AttemptFailure(1, url, "row_count", span, "unreadable")` | `        return AttemptFailure(1, url, "row_count", span, None)` |
| 5 | count_failure | 6 | `        return AttemptFailure(1, url, "row_count", span, "unreadable")` | `        return AttemptFailure(2, url, "row_count", span, "unreadable")` |
| 6 | count_failure | 6 | `        return AttemptFailure(1, url, "row_count", span, "unreadable")` | `        return AttemptFailure(1, url, "XXrow_countXX", span, "unreadable")` |
| 7 | count_failure | 6 | `        return AttemptFailure(1, url, "row_count", span, "unreadable")` | `        return AttemptFailure(1, url, "ROW_COUNT", span, "unreadable")` |
| 8 | count_failure | 6 | `        return AttemptFailure(1, url, "row_count", span, "unreadable")` | `        return AttemptFailure(1, url, "row_count", span, "XXunreadableXX")` |
| 9 | count_failure | 6 | `        return AttemptFailure(1, url, "row_count", span, "unreadable")` | `        return AttemptFailure(1, url, "row_count", span, "UNREADABLE")` |
| 10 | count_failure | 11 | `        return AttemptFailure(1, url, "row_count", span, str(count))` | `        return AttemptFailure(None, url, "row_count", span, str(count))` |
| 11 | count_failure | 11 | `        return AttemptFailure(1, url, "row_count", span, str(count))` | `        return AttemptFailure(1, None, "row_count", span, str(count))` |
| 12 | count_failure | 11 | `        return AttemptFailure(1, url, "row_count", span, str(count))` | `        return AttemptFailure(1, url, "row_count", None, str(count))` |
| 13 | count_failure | 11 | `        return AttemptFailure(1, url, "row_count", span, str(count))` | `        return AttemptFailure(1, url, "row_count", span, None)` |
| 14 | count_failure | 11 | `        return AttemptFailure(1, url, "row_count", span, str(count))` | `        return AttemptFailure(2, url, "row_count", span, str(count))` |
| 15 | count_failure | 11 | `        return AttemptFailure(1, url, "row_count", span, str(count))` | `        return AttemptFailure(1, url, "row_count", span, str(None))` |

#### R107 — schema_failure

`schema_failure` requires each declared column in every record and checks its declared type. Items 16–21 change the empty-input failure and items 22–27 change the non-record failure. With the first declared column named `amount`, test an empty row list and a list containing a non-mapping value separately, requiring `(1, original URL, schema_missing, amount, missing)` in each case. A record with a valid `amount` field must pass so the negative cases cannot be satisfied by rejecting every schema.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 16 | schema_failure | 5 | `        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "missing")` | `        return AttemptFailure(None, url, "schema_missing", entry.columns[0][0], "missing")` |
| 17 | schema_failure | 5 | `        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "missing")` | `        return AttemptFailure(1, None, "schema_missing", entry.columns[0][0], "missing")` |
| 18 | schema_failure | 5 | `        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "missing")` | `        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], None)` |
| 19 | schema_failure | 5 | `        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "missing")` | `        return AttemptFailure(2, url, "schema_missing", entry.columns[0][0], "missing")` |
| 20 | schema_failure | 5 | `        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "missing")` | `        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "XXmissingXX")` |
| 21 | schema_failure | 5 | `        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "missing")` | `        return AttemptFailure(1, url, "schema_missing", entry.columns[0][0], "MISSING")` |
| 22 | schema_failure | 9 | `                1, url, "schema_missing", entry.columns[0][0], "missing"` | `                None, url, "schema_missing", entry.columns[0][0], "missing"` |
| 23 | schema_failure | 9 | `                1, url, "schema_missing", entry.columns[0][0], "missing"` | `                1, None, "schema_missing", entry.columns[0][0], "missing"` |
| 24 | schema_failure | 9 | `                1, url, "schema_missing", entry.columns[0][0], "missing"` | `                1, url, "schema_missing", entry.columns[0][0], None` |
| 25 | schema_failure | 9 | `                1, url, "schema_missing", entry.columns[0][0], "missing"` | `                2, url, "schema_missing", entry.columns[0][0], "missing"` |
| 26 | schema_failure | 9 | `                1, url, "schema_missing", entry.columns[0][0], "missing"` | `                1, url, "schema_missing", entry.columns[0][0], "XXmissingXX"` |
| 27 | schema_failure | 9 | `                1, url, "schema_missing", entry.columns[0][0], "missing"` | `                1, url, "schema_missing", entry.columns[0][0], "MISSING"` |

#### R107 — period_failure

`period_failure` dispatches structured period rules or compares the latest plain period with the entry's minimum last period. Item 28 loses the address passed to the structured-rule path; a stale structured fixture must preserve the original URL in its failure. Items 29–43 damage the missing-row report and items 44–73 damage reports for a non-record row or non-string period: exercise null rows, a scalar row and a mapping with a numeric period separately, requiring `(1, original URL, period_last, declared last period, unreadable)`. Item 74 refuses equality; a row exactly equal to the declared last period must return null, while an earlier string period returns the exact earlier value. Do not replace those plain-period comparisons with arithmetic on dates.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 28 | period_failure | 9 | `        return _ruled_period_failure(entry, rows, url)` | `        return _ruled_period_failure(entry, rows, None)` |
| 29 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(None, url, "period_last", entry.period_last, "unreadable")` |
| 30 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, None, "period_last", entry.period_last, "unreadable")` |
| 31 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, None, entry.period_last, "unreadable")` |
| 32 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, "period_last", None, "unreadable")` |
| 33 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, "period_last", entry.period_last, None)` |
| 34 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(url, "period_last", entry.period_last, "unreadable")` |
| 35 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, "period_last", entry.period_last, "unreadable")` |
| 36 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, entry.period_last, "unreadable")` |
| 37 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, "period_last", "unreadable")` |
| 38 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, "period_last", entry.period_last, )` |
| 39 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(2, url, "period_last", entry.period_last, "unreadable")` |
| 40 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, "XXperiod_lastXX", entry.period_last, "unreadable")` |
| 41 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, "PERIOD_LAST", entry.period_last, "unreadable")` |
| 42 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, "period_last", entry.period_last, "XXunreadableXX")` |
| 43 | period_failure | 11 | `        return AttemptFailure(1, url, "period_last", entry.period_last, "unreadable")` | `        return AttemptFailure(1, url, "period_last", entry.period_last, "UNREADABLE")` |
| 44 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                None, url, "period_last", entry.period_last, "unreadable"` |
| 45 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, None, "period_last", entry.period_last, "unreadable"` |
| 46 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, None, entry.period_last, "unreadable"` |
| 47 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", None, "unreadable"` |
| 48 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", entry.period_last, None` |
| 49 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                url, "period_last", entry.period_last, "unreadable"` |
| 50 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, "period_last", entry.period_last, "unreadable"` |
| 51 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, entry.period_last, "unreadable"` |
| 52 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", "unreadable"` |
| 53 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"<br>            )` | `                1, url, "period_last", entry.period_last, )` |
| 54 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                2, url, "period_last", entry.period_last, "unreadable"` |
| 55 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "XXperiod_lastXX", entry.period_last, "unreadable"` |
| 56 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "PERIOD_LAST", entry.period_last, "unreadable"` |
| 57 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", entry.period_last, "XXunreadableXX"` |
| 58 | period_failure | 16 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", entry.period_last, "UNREADABLE"` |
| 59 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                None, url, "period_last", entry.period_last, "unreadable"` |
| 60 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, None, "period_last", entry.period_last, "unreadable"` |
| 61 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, None, entry.period_last, "unreadable"` |
| 62 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", None, "unreadable"` |
| 63 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", entry.period_last, None` |
| 64 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                url, "period_last", entry.period_last, "unreadable"` |
| 65 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, "period_last", entry.period_last, "unreadable"` |
| 66 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, entry.period_last, "unreadable"` |
| 67 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", "unreadable"` |
| 68 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"<br>            )` | `                1, url, "period_last", entry.period_last, )` |
| 69 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                2, url, "period_last", entry.period_last, "unreadable"` |
| 70 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "XXperiod_lastXX", entry.period_last, "unreadable"` |
| 71 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "PERIOD_LAST", entry.period_last, "unreadable"` |
| 72 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", entry.period_last, "XXunreadableXX"` |
| 73 | period_failure | 21 | `                1, url, "period_last", entry.period_last, "unreadable"` | `                1, url, "period_last", entry.period_last, "UNREADABLE"` |
| 74 | period_failure | 25 | `    if latest < entry.period_last:` | `    if latest <= entry.period_last:` |

#### R107 — _ruled_period_failure

`_ruled_period_failure` parses the declared rule and compares the observed canonical last period, except that published labels use exact presence. Item 75 loses the address on that label path; an absent label must preserve the URL. Items 76–86 corrupt a rule-parser refusal: choose a malformed rule and require code 1, its original error name in check and observed, and the declared last period as expected. Items 87–90 alter stale-period failure fields; provide a valid structured rule with observations ending before the required last period and compare its exact URL, expected period and observed canonical period, then require null at equality.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 75 | _ruled_period_failure | 12 | `            return _published_label_failure(entry, rows, url, rule.field)` | `            return _published_label_failure(entry, rows, None, rule.field)` |
| 76 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(None, url, error.name, entry.period_last, error.name)` |
| 77 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(1, None, error.name, entry.period_last, error.name)` |
| 78 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(1, url, None, entry.period_last, error.name)` |
| 79 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(1, url, error.name, None, error.name)` |
| 80 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(1, url, error.name, entry.period_last, None)` |
| 81 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(url, error.name, entry.period_last, error.name)` |
| 82 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(1, error.name, entry.period_last, error.name)` |
| 83 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(1, url, entry.period_last, error.name)` |
| 84 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(1, url, error.name, error.name)` |
| 85 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(1, url, error.name, entry.period_last, )` |
| 86 | _ruled_period_failure | 17 | `        return AttemptFailure(1, url, error.name, entry.period_last, error.name)` | `        return AttemptFailure(2, url, error.name, entry.period_last, error.name)` |
| 87 | _ruled_period_failure | 19 | `        return AttemptFailure(1, url, "period_last", entry.period_last, last)` | `        return AttemptFailure(None, url, "period_last", entry.period_last, last)` |
| 88 | _ruled_period_failure | 19 | `        return AttemptFailure(1, url, "period_last", entry.period_last, last)` | `        return AttemptFailure(1, None, "period_last", entry.period_last, last)` |
| 89 | _ruled_period_failure | 19 | `        return AttemptFailure(1, url, "period_last", entry.period_last, last)` | `        return AttemptFailure(1, url, "period_last", None, last)` |
| 90 | _ruled_period_failure | 19 | `        return AttemptFailure(1, url, "period_last", entry.period_last, last)` | `        return AttemptFailure(2, url, "period_last", entry.period_last, last)` |

#### R107 — _published_label_failure

`_published_label_failure` searches for the exact published last label and leaves missing-label cases to a different refusal. Items 91–105 alter the null-body failure; require `(1, original URL, period_label, recorded label, absent)`. Items 106–115 change gap detection or terminate the search early; place a malformed row or empty label before a matching row, requiring null without an exception, and contrast an all-well-formed list of different nonempty labels, which must refuse. Items 116–118 corrupt that final absence report; compare its code, URL and `period_label` fields exactly. Empty, absent and nonmatching labels are deliberately distinct cases in this function.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 91 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(None, url, "period_label", entry.period_last, "absent")` |
| 92 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, None, "period_label", entry.period_last, "absent")` |
| 93 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, None, entry.period_last, "absent")` |
| 94 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, "period_label", None, "absent")` |
| 95 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, "period_label", entry.period_last, None)` |
| 96 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(url, "period_label", entry.period_last, "absent")` |
| 97 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, "period_label", entry.period_last, "absent")` |
| 98 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, entry.period_last, "absent")` |
| 99 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, "period_label", "absent")` |
| 100 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, "period_label", entry.period_last, )` |
| 101 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(2, url, "period_label", entry.period_last, "absent")` |
| 102 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, "XXperiod_labelXX", entry.period_last, "absent")` |
| 103 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, "PERIOD_LABEL", entry.period_last, "absent")` |
| 104 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, "period_label", entry.period_last, "XXabsentXX")` |
| 105 | _published_label_failure | 8 | `        return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `        return AttemptFailure(1, url, "period_label", entry.period_last, "ABSENT")` |
| 106 | _published_label_failure | 9 | `    gap = False` | `    gap = None` |
| 107 | _published_label_failure | 11 | `        if not isinstance(row, dict) or field not in row:` | `        if not isinstance(row, dict) and field not in row:` |
| 108 | _published_label_failure | 12 | `            gap = True` | `            gap = None` |
| 109 | _published_label_failure | 12 | `            gap = True` | `            gap = False` |
| 110 | _published_label_failure | 13 | `            continue` | `            break` |
| 111 | _published_label_failure | 15 | `        if value is None or value == "":` | `        if value is None and value == "":` |
| 112 | _published_label_failure | 15 | `        if value is None or value == "":` | `        if value is None or value == "XXXX":` |
| 113 | _published_label_failure | 16 | `            gap = True` | `            gap = None` |
| 114 | _published_label_failure | 16 | `            gap = True` | `            gap = False` |
| 115 | _published_label_failure | 17 | `            continue` | `            break` |
| 116 | _published_label_failure | 22 | `    return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `    return AttemptFailure(None, url, "period_label", entry.period_last, "absent")` |
| 117 | _published_label_failure | 22 | `    return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `    return AttemptFailure(1, None, "period_label", entry.period_last, "absent")` |
| 118 | _published_label_failure | 22 | `    return AttemptFailure(1, url, "period_label", entry.period_last, "absent")` | `    return AttemptFailure(2, url, "period_label", entry.period_last, "absent")` |

#### R107 — _count_span

`_count_span` renders the entry's optional lower and upper counts as a literal range. Items 119–120 replace the empty lower-bound representation or bypass its null check. An entry with no lower bound and an upper bound of two must return exactly `..2`; a finite lower-bound control verifies that an omitted bound remains different from a measured count.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 119 | _count_span | 1 | `    low = "" if entry.row_count_min is None else str(entry.row_count_min)` | `    low = "" if (entry.row_count_min is None) and False else str(entry.row_count_min)` |
| 120 | _count_span | 1 | `    low = "" if entry.row_count_min is None else str(entry.row_count_min)` | `    low = "XXXX" if entry.row_count_min is None else str(entry.row_count_min)` |

#### R107 — _seen_type

`_seen_type` names the observed type without exposing a cell's content. Items 121–122 change the boolean name, items 123–124 the floating-number name and items 125–126 the fallback name. Require exactly `boolean` for a boolean value, `number` for a floating value and `other` for a list or null, checking these literal names independently of the production constants and confirming no cell value appears in the result.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 121 | _seen_type | 1 | `        return "boolean"` | `        return "XXbooleanXX"` |
| 122 | _seen_type | 1 | `        return "boolean"` | `        return "BOOLEAN"` |
| 123 | _seen_type | 5 | `        return "number"` | `        return "XXnumberXX"` |
| 124 | _seen_type | 5 | `        return "number"` | `        return "NUMBER"` |
| 125 | _seen_type | 8 | `    return "other"` | `    return "XXotherXX"` |
| 126 | _seen_type | 8 | `    return "other"` | `    return "OTHER"` |

#### R107 — _type_ok

`_type_ok` admits null cells or values of a closed declared type, including a two-coordinate point. Items 127–128 change the latitude key: use a point with valid longitude and an invalid string latitude, requiring false, since an absent renamed key would otherwise be treated as an admissible null. Item 129 admits an unknown declared type; a non-null value with an invented unrecognised kind must return false, alongside a valid numeric point returning true. The test must therefore exercise type failure inside the point, rather than merely its outer mapping shape.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 127 | _type_ok | 11 | `            _type_ok(value.get(axis), "number") for axis in ("lon", "lat")` | `            _type_ok(value.get(axis), "number") for axis in ("lon", "XXlatXX")` |
| 128 | _type_ok | 11 | `            _type_ok(value.get(axis), "number") for axis in ("lon", "lat")` | `            _type_ok(value.get(axis), "number") for axis in ("lon", "LAT")` |
| 129 | _type_ok | 19 | `    return False` | `    return True` |

### R107 — custodian/src/eii_custodian/publicdata/fetch/kinds.py

Task coverage for `custodian/src/eii_custodian/publicdata/fetch/kinds.py`: background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30; latest measurement R107.

R025: 282 earlier unmatched occurrences; see this file’s R107 work list; its overlapping row list is omitted.

`custodian/src/eii_custodian/publicdata/fetch/kinds.py` was read at the measured commit `2ae1299` for R107.

#### R107 — prepare

`prepare` dispatches by entry kind, then retains auxiliary trade responses separately from the final data body. Items 1–11 alter the special kind's missing-build-context refusal; call that branch outside its required build context and require code 1, `build_context_required`, expected `build-public context` and observed `absent`, with the unchanged public endpoint and no request. Items 12–18 lose or invert auxiliary-body selection: make an admitted trade fetch return metadata bytes different from its data bytes and require only the metadata response in `auxiliary`, with the final prepared data unchanged. A second response with identical data bytes must be excluded by the recorded body-equality rule.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 1 | prepare | 10 | `                1,` | `                None,` |
| 2 | prepare | 11 | `                "https://besttime.app/api/v1/forecasts",` | `                None,` |
| 3 | prepare | 13 | `                "build-public context",` | `                None,` |
| 4 | prepare | 14 | `                "absent",` | `                None,` |
| 5 | prepare | 10 | `                1,` | `                2,` |
| 6 | prepare | 11 | `                "https://besttime.app/api/v1/forecasts",` | `                "XXhttps://besttime.app/api/v1/forecastsXX",` |
| 7 | prepare | 11 | `                "https://besttime.app/api/v1/forecasts",` | `                "HTTPS://BESTTIME.APP/API/V1/FORECASTS",` |
| 8 | prepare | 13 | `                "build-public context",` | `                "XXbuild-public contextXX",` |
| 9 | prepare | 13 | `                "build-public context",` | `                "BUILD-PUBLIC CONTEXT",` |
| 10 | prepare | 14 | `                "absent",` | `                "XXabsentXX",` |
| 11 | prepare | 14 | `                "absent",` | `                "ABSENT",` |
| 12 | prepare | 22 | `        responses.append(response)` | `        responses.append(None)` |
| 13 | prepare | 42 | `        result, auxiliary=tuple(r for r in responses if r.body != result.body)` | `        None, auxiliary=tuple(r for r in responses if r.body != result.body)` |
| 14 | prepare | 42 | `        result, auxiliary=tuple(r for r in responses if r.body != result.body)` | `        result, auxiliary=None` |
| 15 | prepare | 42 | `        result, auxiliary=tuple(r for r in responses if r.body != result.body)` | `        auxiliary=tuple(r for r in responses if r.body != result.body)` |
| 16 | prepare | 42 | `        result, auxiliary=tuple(r for r in responses if r.body != result.body)<br>    )` | `        result, )` |
| 17 | prepare | 42 | `        result, auxiliary=tuple(r for r in responses if r.body != result.body)` | `        result, auxiliary=tuple(None)` |
| 18 | prepare | 42 | `        result, auxiliary=tuple(r for r in responses if r.body != result.body)` | `        result, auxiliary=tuple(r for r in responses if r.body == result.body)` |

#### R107 — _portal

`_portal` reads portal metadata and the export, then validates publisher and licence information before preparing the body. Items 19, 21 replace the entry passed to `_call`; the measured `_call` immediately discards that parameter, so these may be equivalent if every reachable use retains that implementation and the other arguments are unchanged. Item 20 changes the initial export sentinel; trace both the accident-workbook branch and ordinary export branch to prove assignment before use. Items 22–23 alter the constructed workbook response's final address or hops; use the accident fixture and require its original public export URL and empty redirect tuple, including their use by receipt generation. Confirm the exceptional branch's downstream consumers before accepting a sentinel-only explanation.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 19 | _portal | 1 | `    meta, failure = _call(entry, meta_url, reader)` | `    meta, failure = _call(None, meta_url, reader)` |
| 20 | _portal | 4 | `    export: Response &#124; None = None` | `    export: Response &#124; None = ""` |
| 21 | _portal | 6 | `        export, failure = _call(entry, entry.url, reader)` | `        export, failure = _call(None, entry.url, reader)` |
| 22 | _portal | 77 | `        export = Response(entry.url, body, ())` | `        export = Response(None, body, ())` |
| 23 | _portal | 77 | `        export = Response(entry.url, body, ())` | `        export = Response(entry.url, body, None)` |

#### R107 — _file

`_file` accepts one HTTPS body, checks a workbook container when declared, then applies row-count validation. Items 24–33 change fields of the invalid-workbook refusal. Give an `xlsx` entry ordinary text bytes and require `(1, final public URL, workbook_content, OOXML workbook, invalid body)`, with no prepared successful body; contrast an invented valid workbook container that reaches row-count checking. Looking only for any refusal would miss the changed expected-format label and observed explanation.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 24 | _file | 14 | `                1,` | `                None,` |
| 25 | _file | 15 | `                response.final_url,` | `                None,` |
| 26 | _file | 17 | `                "OOXML workbook",` | `                None,` |
| 27 | _file | 18 | `                "invalid body",` | `                None,` |
| 28 | _file | 14 | `                1,` | `                2,` |
| 29 | _file | 17 | `                "OOXML workbook",` | `                "XXOOXML workbookXX",` |
| 30 | _file | 17 | `                "OOXML workbook",` | `                "ooxml workbook",` |
| 31 | _file | 17 | `                "OOXML workbook",` | `                "OOXML WORKBOOK",` |
| 32 | _file | 18 | `                "invalid body",` | `                "XXinvalid bodyXX",` |
| 33 | _file | 18 | `                "invalid body",` | `                "INVALID BODY",` |

#### R107 — read_terms_page

`read_terms_page` returns the terms body's visible-text fingerprint and original bytes while leaving the data address untouched. Item 34 substitutes a null entry for `_call`; because that function discards the entry, equivalence depends on that implementation remaining unchanged across all callers. Item 35 omits the returned bytes and falls back to an empty body; a terms fixture with visible nonempty text must return those exact bytes as well as its correct fingerprint and null failure, otherwise later archiving would silently retain an empty page.

Changes in R107:

| Item | Function | Diff-relative line / recorded span | Original | Changed to |
|---|---|---|---|---|
| 34 | read_terms_page | 6 | `    terms, failure = _call(entry, entry.terms_url, reader)` | `    terms, failure = _call(None, entry.terms_url, reader)` |
| 35 | read_terms_page | 9 | `    return TermsPage(terms_text_sha256(terms.body), None, terms.body)` | `    return TermsPage(terms_text_sha256(terms.body), None, )` |

### R108 — custodian/src/eii_custodian/publicdata/fetch/registry.py

Task coverage for `custodian/src/eii_custodian/publicdata/fetch/registry.py`: background campaign covering S2-T01, S2-T21, S2-T27, S2-T28, S2-T29, S2-T30; latest measurement R108.

R025: 119 earlier unmatched occurrences; see this file’s R108 work list; R108 is incomplete, so overlap and closure remain unproved.

R108 retains no comparable original and changed lines for this file. Its outcome counts and named partial variants remain in section 9; recover each original span and enclosing function at the measured commit before choosing a test. Earlier text cannot establish the missing alteration identities.


## Sources

Each status, count, cost and change row names its R-numbered original record; section 9 gives the fingerprints. The explanation comparison column identifies the commits read and the commit whose exact file-and-change entry matched. Unknown revisions and missing change text remain unresolved.

Repository context: [Testing and Quality](12_TESTING_AND_QUALITY.md), [Task ledger](../TASKS.md), [Open items](../OPEN_ITEMS.md), [background-campaign decision](decisions/0052-mutation-campaigns-run-in-a-background-lane.md), and [decision 0055](decisions/0055-mutation-testing-moves-to-after-go-live.md), which defers mutation work until after go live while preserving ordinary checks; the owner accepted its written record on 2026-11-18.
