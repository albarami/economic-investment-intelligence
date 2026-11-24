"""The health count reads the persistent journal and preserves idempotency."""

from eii_product.ledger.local import LocalLedger, tool_entry


def test_operational_count_survives_reopen_and_duplicate(tmp_path):
    path = tmp_path / "INVENTED-ledger.sqlite"
    ledger = LocalLedger(path)
    assert ledger.row_count() == 0
    row = tool_entry(
        answer_id="INVENTED-answer",
        tool="INVENTED-tool",
        arguments={},
        release_id="ab" * 32,
        engine="embedded",
        status="OK",
        fact_ids=[],
    )
    ledger.write(row)
    ledger.write(row)
    assert ledger.row_count() == 1
    ledger.close()
    reopened = LocalLedger(path)
    assert reopened.row_count() == 1
    reopened.close()
