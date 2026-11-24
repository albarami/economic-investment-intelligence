"""Internal outcomes become exact governed envelopes or sanitized errors."""

import json
from decimal import Decimal

import pytest

from eii_product.api.results import respond
from eii_product.ledger.local import LocalLedger
from eii_product.store.protocol import StoreRefusal
from eii_product.tools.area_outline import OutlineError
from eii_product.tools.areas import AreaIdError
from eii_product.tools.make_area import ArgumentError, MakeAreaResult
from eii_product.tools.routing import RoutingTilesUnavailable

RELEASE = "ab" * 32


def result(status="OK", reason=None):
    return MakeAreaResult(
        "make_area", status, reason, RELEASE, {"area_id": "INVENTED-area"}
    )


@pytest.fixture
def ledger(tmp_path):
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    yield ledger
    ledger.close()


@pytest.mark.parametrize("status", ["OK", "NO_DATA", "OUT_OF_SCOPE", "SUPPRESSED"])
def test_envelope_exact_and_transactional(ledger, status):
    responses = [
        respond(
            lambda: result(status, "point_without_base_cell"),
            ledger=ledger,
            engine="embedded",
            arguments={},
        )
        for _ in range(2)
    ]
    bodies = [json.loads(response.body) for response in responses]
    for body in bodies:
        assert set(body) == {
            "tool",
            "call_id",
            "release_id",
            "engine",
            "status",
            "blocks",
            "facts",
            "payload",
            "caveat_keys",
        }
        assert body["status"] == status
        assert body["caveat_keys"] == ["point_without_base_cell"]
    rows = ledger.rows()
    assert len(rows) == 2
    assert rows[0]["answer_id"] != rows[1]["answer_id"]
    assert [row["answer_id"] for row in rows] == [body["call_id"] for body in bodies]
    assert all(row["seat_key"] == "" for row in rows)


@pytest.mark.parametrize(
    "error,status,code",
    [
        (ArgumentError("SELECT /tmp/ 25.1234"), 422, "INVALID_ARGUMENT"),
        (AreaIdError("INVALID_ARGUMENT"), 422, "INVALID_ARGUMENT"),
        (StoreRefusal("STORE_UNAVAILABLE"), 503, "STORE_UNAVAILABLE"),
        (StoreRefusal("engine operation failed"), 500, "INTERNAL"),
        (TimeoutError("SELECT /tmp/ 25.1234"), 504, "QUERY_TIMEOUT"),
        (RuntimeError("SELECT /tmp/ 25.1234"), 500, "INTERNAL"),
        (OutlineError(), 500, "INTERNAL"),
        (RoutingTilesUnavailable("SELECT /tmp/ 25.1234"), 500, "INTERNAL"),
    ],
)
def test_errors_no_ledger_or_disclosure(ledger, capsys, error, status, code):
    def run():
        raise error

    response = respond(run, ledger=ledger, engine="embedded", arguments={})
    assert response.status_code == status
    body = json.loads(response.body)
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message_key", "error_id"}
    assert body["error"]["code"] == code
    assert ledger.rows() == []
    text = response.body.decode() + capsys.readouterr().out
    assert all(sentinel not in text for sentinel in ("SELECT", "/tmp/", "25.1234"))


@pytest.mark.parametrize(
    "status,expected",
    [("INVALID_ARGUMENT", 422), ("RELEASE_MODE", 500), ("UNKNOWN", 500)],
)
def test_internal_status_is_never_an_envelope(ledger, status, expected):
    response = respond(
        lambda: result(status), ledger=ledger, engine="embedded", arguments={}
    )
    assert response.status_code == expected
    assert "error" in json.loads(response.body)
    assert ledger.rows() == []


def test_missing_write_and_write_then_fail_roll_back(ledger, monkeypatch):
    original = ledger.write

    def broken(entry):
        original(entry)
        raise RuntimeError("SELECT /tmp/ 25.1234")

    monkeypatch.setattr(ledger, "write", broken)
    assert (
        respond(result, ledger=ledger, engine="embedded", arguments={}).status_code
        == 500
    )
    assert ledger.rows() == []
    monkeypatch.setattr(ledger, "write", lambda entry: None)
    assert (
        respond(result, ledger=ledger, engine="embedded", arguments={}).status_code
        == 500
    )
    assert ledger.rows() == []


def test_validation_failure_value_error_is_internal(ledger):
    def broken():
        raise ValueError("reader failed")

    assert (
        respond(broken, ledger=ledger, engine="embedded", arguments={}).status_code
        == 500
    )
    assert ledger.rows() == []


@pytest.mark.parametrize("value", [Decimal("3.25"), Decimal("10000000000000001.00")])
def test_fact_projection_is_numeric_and_lossless(value):
    from decimal import Decimal

    from eii_core.facts import Fact
    from eii_product.api.results import wire_fact

    fact = Fact.model_validate(
        dict(
            fact_id="f_" + "ab" * 16,
            value=value,
            unit="qar",
            period="2025",
            geography={"kind": "public", "public_code": "district:INVENTED"},
            provenance="public",
            input_classes=["public"],
            evidence_status="observed",
            reliability="not_applicable",
            coverage_keys=[],
            caveat_keys=[],
            label_en="Published value",
            label_ar="قيمة منشورة",
            lineage_ref="lin_fixture",
            release_id=RELEASE,
        )
    )
    if value == Decimal("3.25"):
        wire = wire_fact(fact)
        assert isinstance(wire["value"], (int, float))
        assert Decimal(str(wire["value"])) == value
    else:
        with pytest.raises(ValueError, match="numeric_wire_invalid"):
            wire_fact(fact)
