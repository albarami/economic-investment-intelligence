# Decision 0074: Company-level fields of the owner's company workbook

| | |
|---|---|
| Status | Accepted, 2026-11-20; the owner's decisions of 2026-11-20 |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner's decisions of 2026-11-20, relayed in package P27 |
| Amends | AGENTS.md and CLAUDE.md rule 3; [docs/README.md](../README.md), decision index; [OPEN_ITEMS.md](../../OPEN_ITEMS.md), OI-186, OI-187 and OI-190; [TASKS.md](../../TASKS.md), S2-T48; [docs/14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md) |
| Purpose | Admit a bounded read of company-level columns from the owner's company workbook for register keying and size band, settle three register open items, and approve company web pages as a later task, without person-level or salary data entering the repository |
| Read first | [decision 0022](0022-real-register-companies-with-a-synthetic-world.md) items 1, 2 and 8; [decision 0033](0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 1; AGENTS.md rules 3 and 8; document 03 DAT-02 and DAT-12 |

## Context

Rule 3 forbids reading real custodian records except the owner's aggregate calibration tables
on decision 0022's terms, as amended by decision 0036. The public register companies are real;
their synthetic labour and residence records stay synthetic. The owner's company workbook sits
outside the repository. Earlier decisions left several register open items (rows without a
registration number, activity codes and financial-centre feed treatment) for later owner
choices. On 2026-11-20 the owner narrowed what may be read from the workbook for the world
build, then decided the three open items and approved company web pages for a later task.

The owner's words of 2026-11-20 (typing kept):

> the first exersize we did is the companies since its pulbic we use them . what we dont use from
> [the owner's company workbook] is the people working there and their job titles and salaires .
> the company name the cr nubmer the eid their adress we can use . the mapping of qfc companeis to
> eid or cr we can use . the company size we can use .

Further owner words of 2026-11-20 (typing kept), with "the financial centre" written for any
financial-centre name in the quotation:

> for qfc its ok if he doesnt find a cr or eid number . the name and adress and wesbsite he can
> fetch the web and find their adress im sure we dicussed this before and even if not let him do it

> for nubmer 1 yes, for number 2 alow , for website he should make clis to do the search by
> company name qatar and will prbably find their adress . for number 4i confirm.

(In the second quotation: number 1 is OI-186, number 2 is OI-187, number 3 is the company web
pages task, number 4 is the trade selection and is not part of package P27.)

In every repository file this record writes "the owner's company workbook" for the workbook;
never its file or folder name, never "mol" or any ministry or organisation name, and never a path.
The financial centre is written as "the financial centre", as the documents already do.

## Decision

1. **The exception.** The world build, and the lead's own shell for counting, may read ONLY these
   company-level columns of the owner's company workbook: company name, commercial registration
   number, establishment identity number (EID), address, the mapping of financial-centre companies
   to EID or registration number, and company size band. Never a person-level row, a job title, a
   salary or salary-threshold column, an employee or nationality count, or any other column. Read on
   the terms of decision 0022 and decision 0033 item 1: values are written only to the vault feed,
   never to a report, log, message, coverage file, brief, worker, reviewer or repository file; only
   counts reach the owner, outside the repository.

2. **Use.** Key register companies: the identity numbers join a company exactly as the registration
   number does under DAT-12, normalised under DAT-02. Give a company its size band. No value is shown
   for a named company beyond what rule 8 already allows.

3. **Not decided by this record (left open, cited).** The key of the rows without a registration
   number (OI-186), the financial centre's feed treatment (OI-190), and activity (OI-187); the owner
   has been given the counts. Match counts were relayed to the owner outside the repository; no count
   is stated here.

4. **Rule 3 amendment.** After the calibration-table exception of rule 3, the world build and the
   lead's own shell for counting may read only the company-level columns named in item 1 of this
   record from the owner's company workbook, on the terms of item 1; the lead's own shell may also
   read the company activity, activity group and sector columns named in item 6 on the terms of that
   item; no value of those columns is described in the repository.

5. **OI-186 decided — register rows without a registration number.** A register row without a
   registration number is keyed by its licence number in a separate key namespace (a visible prefix)
   because some licence numbers equal other companies' registration numbers; the workbook's
   establishment or registration number is added only where it gives exactly one. This replaces the
   default of [decision 0033](0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 1
   for these rows; decision 0033 itself is not edited.

6. **OI-187 decided — activity columns for counting only.** The lead's own shell may also read the
   workbook's company activity, activity group and sector columns, company-level only, on the same
   terms as the other fields of item 1: nothing committed, briefed or given to a worker; values written
   only to the vault feed; only counts reach the owner outside the repository. The world build does not
   read these columns unless a later decision says otherwise.

7. **OI-190 decided — the financial centre without registration or establishment numbers.** A
   financial-centre company needs no registration or establishment number; an absent number stays
   empty and is never guessed; existing exact-name matches stay.

8. **Company web pages (step 2).** Approved for financial-centre and register companies: a command-line
   web search per company (company name plus "Qatar"), then the pages found are fetched; name, address,
   website and activity are taken, each with source address, retrieval date and hash; reviewed by another
   maker before use; company-level public information only (never a person, job title or salary). The
   work is task S2-T48 in TASKS.md and the slice S2 list of document 14.

## Consequences and change triggers

OI-186, OI-187 and OI-190 close with dated 2026-11-20 CLOSED lines under decision 0074 items 5, 6
and 7, citing the owner's words above. TASKS.md boxes that depend on register snapshot restoration or
DAT-24 proof are unchanged until their owning tasks prove them; this record does not tick them.
S2-T48 is not started by this record.

Any read outside the listed columns, any person-level row, any salary column, any value copied into
a repository file, or any displayed attribute for a named company beyond rule 8 requires a new
decision under rule 46. Reading job titles, salaries or employee counts from the workbook remains
forbidden.

## Sources

- The owner's decisions of 2026-11-20, relayed in package P27, with the verbatim quotations above.
- [decision 0022](0022-real-register-companies-with-a-synthetic-world.md); [decision 0033](0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 1;
  [decision 0036](0036-generated-data-stands-for-the-future-real-data.md) item 6; AGENTS.md rules 3 and 8;
  [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), DAT-02 and DAT-12;
  [OPEN_ITEMS.md](../../OPEN_ITEMS.md), OI-186, OI-187 and OI-190.