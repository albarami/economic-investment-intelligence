# Public additions

`build.py` dispatches the closed family parsers and validates typed rows before
publishing the selected set. Source snapshots and receipts supply lineage;
fixtures in `custodian/tests/test_additions_*.py` are invented.

`industry.py` reads establishment-size, manufacturing, trade and logistics
bulletins through `custodian/publicdata/review/additions_industry.yaml`.
Activity-name columns are declared source-only because the establishment
release contract has no name columns. Undeclared columns remain errors.
Manufacturing values alone use decimal(18,6), with no rounding of finer values.
Certificates use exact country dispositions and closed type aliases;
thirteen withheld country labels and four regions produce counted coverage
and no output row. Bosnia maps exactly to BIH (Bosnia and Herzegovina in the
committed country reference).

See [decision 0122](../../../../../docs/decisions/0122-additions-read-the-published-shapes.md)
items 1 to 3 and [document 03](../../../../../docs/03_DATA_CONTRACTS.md)
section 7.3 for the contracts and their limits.
