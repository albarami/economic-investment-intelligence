"""The health count reads the persistent journal and preserves idempotency."""

from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_product.api.health import _font_assets
from eii_product.ledger.local import LocalLedger, tool_entry
from eii_product.store.release_check import CheckedRelease

FONT_REFUSALS = (
    "asset_missing",
    "asset_path_refused",
    "font_stack_refused",
    "font_span_refused",
    "font_range_refused",
)


def _font_release(web: Path) -> CheckedRelease:
    (web / "assets").mkdir()
    (web / "assets/interface.woff2").write_bytes(b"INVENTED-font")
    return CheckedRelease(
        web, {"artefacts": [{"path": "artefacts/fonts/Noto Sans Medium/0-255.pbf"}]}, {}
    )


@settings(deadline=None)
@given(st.sampled_from(FONT_REFUSALS))
def test_font_health_reports_each_closed_path_refusal_as_invalid(
    tmp_path_factory, code
):
    web = tmp_path_factory.mktemp("web")
    checked = _font_release(web)
    with (
        patch("eii_product.api.health._font_path", side_effect=ValueError(code)),
    ):
        assert _font_assets(checked, web) == "invalid"


@pytest.mark.parametrize("code", ["INVENTED-unknown", "operation_failed"])
def test_font_health_does_not_swallow_other_value_errors(tmp_path: Path, code):
    checked = _font_release(tmp_path)
    with (
        patch("eii_product.api.health._font_path", side_effect=ValueError(code)),
        pytest.raises(ValueError, match="^" + code + "$"),
    ):
        _font_assets(checked, tmp_path)


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
