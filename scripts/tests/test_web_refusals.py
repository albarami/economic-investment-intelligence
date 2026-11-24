"""Part C D32 and the browser diagnostic vocabulary, invented health only."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eii_core.reason_codes import CODES
from operations.common import Refusal
from operations.deploy import health_probe

HEALTH = dict(
    status="ok",
    store="embedded",
    postgres="not_used",
    release_id="INVENTED",
    release_hash="INVENTED",
    parity="identical",
    ledger="local",
    local_ledger_rows=0,
    model="template",
    traffic="simulated",
    tiles="ok",
    fonts="ok",
    replays="ok",
)


@pytest.mark.parametrize(
    "row,change,expected",
    [
        ("D32", {"fonts": "missing"}, "fonts_missing"),
        ("D32", {"tiles": "invalid"}, "basemap_invalid"),
        ("D32", {"replays": "missing"}, "replays_missing"),
        ("D32", {"parity": "failed"}, "startup_parity_failed"),
        ("D32", {"traffic": "live"}, "traffic_mode_refused"),
        ("D32", {"model": "live"}, "startup_model_live"),
        ("D32", {"postgres": "up"}, "startup_store_status"),
        ("D32", {"status": "degraded"}, "startup_status_degraded"),
    ],
)
def test_part_c_script_row(row: str, change: dict[str, str], expected: str) -> None:
    with patch(
        "operations.deploy.get", return_value=(503, json.dumps(HEALTH | change))
    ):
        with pytest.raises(Refusal, match="^" + expected + "$") as caught:
            health_probe(8088, 1.0)
    assert caught.value.code == 4


@given(
    st.sampled_from(["tiles", "fonts", "replays"]),
    st.sampled_from(["missing", "invalid"]),
)
def test_health_slot_reason_does_not_depend_on_http_success(
    slot: str, status: str
) -> None:
    expected = ("basemap" if slot == "tiles" else slot) + "_" + status
    for http_status in (200, 503):
        with patch(
            "operations.deploy.get",
            return_value=(http_status, json.dumps(HEALTH | {slot: status})),
        ):
            with pytest.raises(Refusal, match="^" + expected + "$"):
                health_probe(8088, 1.0)


def test_web_vocabulary_is_the_shared_closed_vocabulary() -> None:
    root = Path(__file__).resolve().parents[2]
    assert json.loads(
        (root / "web/src/api/reason-codes.generated.json").read_text()
    ) == sorted(CODES)


def test_health_http_failure_after_valid_body() -> None:
    with patch("operations.deploy.get", return_value=(503, json.dumps(HEALTH))):
        with pytest.raises(Refusal, match=r"^startup_not_ready$"):
            health_probe(8088, 1.0)


def test_health_inner_reason_is_not_masked() -> None:
    with patch("operations.deploy.get", side_effect=Refusal("digest_mismatch")):
        with pytest.raises(Refusal, match=r"^digest_mismatch$"):
            health_probe(8088, 1.0)


@given(st.text().filter(lambda value: value not in {"ok", "missing", "invalid"}))
def test_health_unknown_asset_values_never_reach_the_reason(value: str) -> None:
    with patch(
        "operations.deploy.get",
        return_value=(200, json.dumps(HEALTH | {"fonts": value})),
    ):
        with pytest.raises(Refusal, match=r"^startup_not_ready$"):
            health_probe(8088, 1.0)


@pytest.mark.parametrize("current", [None, "[]"])
def test_web_vocabulary_export_refuses_missing_or_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], current: str | None
) -> None:
    import export_web_catalogue

    target = tmp_path / "web/src/api/reason-codes.generated.json"
    target.parent.mkdir(parents=True)
    if current is not None:
        target.write_text(current)
    with (
        patch.object(export_web_catalogue, "repo_root", return_value=tmp_path),
        patch.object(export_web_catalogue, "run", return_value=0),
        patch.object(
            export_web_catalogue, "_prettier", side_effect=lambda value, root: value
        ),
    ):
        assert export_web_catalogue.main(["--check"]) == 1
    assert capsys.readouterr().err == "reason_catalogue_stale\n"
