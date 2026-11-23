# Decision 0102: The lead-shell register projection run in rule 44

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-23 13:48 ("Yes on both", relayed by the advisor; extract owner-relayed-20261123-1348); this record's text is reviewed by another maker before merge |
| Date | 2026-11-23 |
| Scope | AGENTS.md and CLAUDE.md rule 44; [TASKS.md](../../TASKS.md) S2-T49 and S2-T08; the S2 path boxes S2-T49#1 to #3 and S2-T08#14 of decision 0098; `custodian/src/eii_custodian/publicdata/registers/README.md` **Sibling intake protocol**, **Verification boundary** and **Assembly handoff** |
| Amends | AGENTS.md and CLAUDE.md rule 44 and their Status row |
| Purpose | Admit the existing register projection command to rule 44 so the lead may run it; it is permission to run an existing tool, not a new check and not a new data source |
| Read first | [decision 0022](0022-real-register-companies-with-a-synthetic-world.md) item 1; [decision 0033](0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 1; [decision 0074](0074-company-level-fields-of-the-owners-company-workbook.md) items 1 and 6; [decision 0098](0098-s2-sources-follow-their-first-field-reader.md) item 5; AGENTS.md rules 3, 11, 13, 14 and 44 |

## Context and evidence

Four S2 path boxes are BLOCKED because the existing register projection tool is
not a rule-44 command: S2-T49#1 to #3 and S2-T08#14 (the S2 path boxes of
decision 0098). The tool is the package
`custodian/src/eii_custodian/publicdata/registers/`, an offline lead-operated
adapter for [decision 0022](0022-real-register-companies-with-a-synthetic-world.md)
item 1 whose automated tests use invented stand-in bytes only. The S2-P64
`register_tables` assembly phase consumes only its lead-staged, pin-verified
output and never reads a register file or either environment setting. Admitting
the command runs no new check and reads no new source; it lets the lead produce
the staged bundle the already-merged phase verifies.

## Proposed decision

1. **The command.** From the repository root, in the lead's own shell:

   ```
   EII_REGISTER_FILE=BIZ_REGISTER_CSV EII_FC_REGISTER_FILE=FC_REGISTER_CSV \
   uv run --locked python -m eii_custodian.publicdata.registers \
       --frame-cells FRAME_CELLS_JSON \
       --frame-sha256 FRAME_SHA256 \
       --biz-index-sha256 BIZ_INDEX_SHA256 \
       --fc-index-sha256 FC_INDEX_SHA256 \
       --output OUTPUT_DIR \
       --release-kind RELEASE_KIND
   ```

   Every value is a placeholder the lead supplies. `RELEASE_KIND` is
   `public_only` or `protected`. `FRAME_CELLS_JSON` is a lead-prepared JSON
   array of the exact integer `grid_cell.cell` ownership set of the verified S2
   frame, byte-hashed by `FRAME_SHA256`; the two `--*-index-sha256` arguments
   are the lead's reviewed byte-hash pins of each file's `.register.json`
   sibling index. No real value, path or hash is committed here.

2. **Who may run it.** The lead's own shell only; never a worker tool, a test,
   a gate or continuous integration. Automated tests keep their invented UTF-8
   stand-in fixtures and explicit mappings; no test sets the real environment
   settings. Intake writes nothing.

3. **What it reads.** Only the inputs the package README's **Sibling intake
   protocol** names: the two environment-named CSV files under
   `EII_REGISTER_FILE` and `EII_FC_REGISTER_FILE`, each file's sibling index at
   its full filename plus `.register.json`, and the sibling basenames each
   closed index declares for the current capture and for every explicitly
   listed snapshot month. No directory crawl, latest selection, nested path or
   symbolic link; reads are bounded and re-check file identity, size and
   modification metadata. The files stay outside the repository and are read on
   the terms of decision 0022 item 1 and the lead-shell terms of decisions 0074
   item 1 and 0033 item 1: no value is described, printed, committed, briefed or
   given to a worker or reviewer.

4. **What it writes.** To `OUTPUT_DIR` it publishes the validated
   `pub_register_company` and `pub_register_snapshot` projections for the chosen
   release kind — the `current/` output of `manifest.json` and `tables/` — with
   table metadata holding input hashes, key-scoped attribution, method and
   version, and per-source kept months. It prints only the fixed success or a
   fixed refusal reason code; no source row, registration, filename or path
   enters its output. Separately and by hand, under the README's **Assembly
   handoff**, the lead stages that output as `register_bundle/` inside the
   allowed assembly cache and writes `register_bundle_pin.json` holding the
   manifest's byte hash.

5. **Verification boundary.** The run performs the adapter's own checks:
   schema, lexeme type and format, the identifier scans, key ambiguity, sibling
   index pins, receipt digests, snapshot-month and frame-ownership rules, each
   refusing with a named reason. It does not run the receiving release builder's
   full-release schema and privacy checks, and it claims no independent review,
   real geocoding check, retention proof, full application release or store
   load. The S2-P64 `register_tables` phase re-verifies the staged bundle —
   pin, manifest keys and bindings, receipts, table byte hashes, frame
   ownership and released rows — before any use, refusing by name at the first
   mismatch.

6. **What stays forbidden.** Unchanged by this record: no register byte or
   value enters the repository, a fixture, a log, a brief, a model request or a
   worker or reviewer's view (decision 0022 item 8; rules 3, 13, 14 and 15); no
   fetcher for the register site is written; the release assembly never reads a
   register file, its siblings or either environment setting; no other form of
   the command is admitted; no admission policy, test, gate or continuous
   integration changes; no new check or data source is created. A refusal ends
   the run and is never worked around.

7. **Boxes.** This record and its rule-44 amendment clear the records
   precondition of the S2 path boxes S2-T08#14 and S2-T49#1 to
   #3. Those boxes then need the lead's actual run, the staged
   and phase-verified bundle, the registry rows and the normal review and gate
   evidence; they stay unproven until each has its own. Everything else stays
   open: S2-T49's remaining real-file evidence, the S2-P64 different-maker
   review, S2-T36's fetched page-name inventory under decision 0098 item 5, and
   every other blocked or pending row of the path.

## Consequences and limits

On acceptance, the command text of item 1 is appended to rule 44 of AGENTS.md
and CLAUDE.md in one change, the files staying byte-identical and their Status
row noting this decision. A successful run does not tick a box by itself: the
run evidence, the staged and re-verified bundle and the registry rows are
produced and reviewed separately. The receipt list binds to the released tables
only through the lead's manifest pin — pin review is the sole control over that
binding (README **Assembly handoff**). Any change to the command's form, inputs
or outputs requires a new decision under rule 46.

## Sources

- `custodian/src/eii_custodian/publicdata/registers/README.md` (**Sibling
  intake protocol**, **Verification boundary**, **Assembly handoff**) and the
  package's `__main__.py` argument list.
- The S2 path boxes S2-T08#14 and S2-T49#1 to #3 (the blocked boxes).
- [TASKS.md](../../TASKS.md), task S2-T49 (goal, scope and delivery status).
- [decision 0022](0022-real-register-companies-with-a-synthetic-world.md) item 1
  (the two environment settings and the lead's own shell);
  [decision 0033](0033-the-part-a-defaults-of-the-register-and-employment-world.md)
  item 1 and [decision 0074](0074-company-level-fields-of-the-owners-company-workbook.md)
  items 1 and 6 (lead-shell read terms; no value described);
  [decision 0098](0098-s2-sources-follow-their-first-field-reader.md) item 5
  (the S2-T36 page-name inventory carried to its S4 consumer).
