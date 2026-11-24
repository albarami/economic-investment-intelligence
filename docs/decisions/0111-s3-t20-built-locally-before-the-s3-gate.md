# 0111 — S3-T20 is built and reviewed locally before the slice S3 gate

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-24 |
| Owner | The owner |
| Amends | [Decision 0041](0041-remote-mode-through-the-owners-own-host.md) item 10, placement only |
| Purpose | Remove the serial wait between the slice S3 gate and the first remote opening by building and reviewing S3-T20 beforehand, without opening, merging or exposing anything earlier |
| Read first | Decision 0041 items 1 to 10; TASKS.md "S3-T20 — Remote mode through the owner's own host"; [CLAUDE.md](../../CLAUDE.md) rules 33, 35, 40 and 46 |

## Context

Decision 0041 item 10 says that S3-T20 runs only after the slice S3 gate
approves and is outside that gate. Read literally, its plan, build and
review start only after that approval, so the first remote opening waits for
a whole build and review cycle after the gate. The first go-live is the
opening of the portal after the slice S3 gate. What item 10 protects is that
nothing is opened remotely, and nothing of S3-T20 reaches the base branch,
before the gate approves.

## Decision

1. **Local work may start before the gate.** The S3-T20 plan, its design
   review, its build in its own worktree, its tests with planted violations,
   its whole test and its review by another maker may run before the slice
   S3 gate approves.
2. **Nothing opens or merges earlier.** Its pull request merges only after the
   slice S3 gate record is merged, in slice order. The tunnel command, the
   remote check through the tunnel and the phone evidence of decision 0049
   run only after that merge, by the lead. No remote exposure, public port
   or tunnel run happens before the gate.
3. **The task stays outside the gate.** S3-T10 and S3-T11 still do not depend
   on S3-T20; the gate is judged without it, as item 10 says.
4. **A change after approval is reviewed again.** If the slice S3 gate
   changes code or documents that S3-T20 depends on, its branch is brought
   onto the new base and a code or test move needs a new confirmation by
   another maker (CLAUDE.md rule 33).
5. **Everything else in decision 0041 stands.** No gate, check, privacy rule,
   security control or hard limit is weakened.
