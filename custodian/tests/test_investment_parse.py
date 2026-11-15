"""Framed dashboard reader. Each refusal names its own reason."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.allowlist import HostDecision, approve
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.investment_build import load_source_spec
from eii_custodian.publicdata.investment_contracts import (
    InvestmentFailure,
    SourceEnvelope,
    parse_decimal,
)
from eii_custodian.publicdata.investment_parse import dashboard_envelope, parse_fdi

_FIXTURE_PATH = Path(__file__).with_name("investment_fixtures.py")
_FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "investment_fixtures", _FIXTURE_PATH
)
assert _FIXTURE_SPEC is not None and _FIXTURE_SPEC.loader is not None
_fixtures = importlib.util.module_from_spec(_FIXTURE_SPEC)
_FIXTURE_SPEC.loader.exec_module(_fixtures)
DASHBOARD = _fixtures.DASHBOARD_URL
PHRASES = _fixtures.PHRASES
TERMS = _fixtures.TERMS_URL
TERMS_BODY = _fixtures.TERMS_BODY
invented_record = _fixtures.invented_record
made_dashboard = _fixtures.made_dashboard
page_from_script = _fixtures.page_from_script

RETRIEVED = "2026-11-14T08:00:00Z"


def _with(name: str, value: object) -> dict[str, object]:
    record = invented_record()
    record[name] = value
    return record


def _without(name: str) -> dict[str, object]:
    record = invented_record()
    del record[name]
    return record


def test_decimal_integer_capacity_and_scale() -> None:
    """A decimal fits precision minus scale integer digits and scale fractional digits."""
    shape = _shape()
    envelope = _envelope()
    too_wide = "1" * 17
    largest = ("9" * 16) + ".99"
    too_fine = "1.234"
    for field in ("capex", "jobs"):
        refused = parse_fdi(
            made_dashboard((invented_record(**{field: ("n", too_wide)}),)).body,
            shape,
            envelope,
        )
        assert getattr(refused, "check", "") == "unrepresentable"
        fitted = parse_fdi(
            made_dashboard((invented_record(**{field: ("n", largest)}),)).body,
            shape,
            envelope,
        )
        assert not isinstance(fitted, InvestmentFailure), getattr(fitted, "check", "")
        rows, _empty = fitted
        stored = "capex_value" if field == "capex" else "jobs"
        assert rows[0][stored] == largest
        fine = parse_fdi(
            made_dashboard((invented_record(**{field: ("n", too_fine)}),)).body,
            shape,
            envelope,
        )
        assert getattr(fine, "check", "") == "unrepresentable"


def test_leading_zeros_are_not_integer_digits() -> None:
    """A leading zero is not an integer digit of a decimal(18,2) value."""
    padded = "0" + ("9" * 16)
    assert parse_decimal(padded, precision=18, scale=2) == padded


def test_one_chunk_list_and_text_row_identity() -> None:
    """Two chunk lists, or a repeated or shared text-row id, fail; other-row ids may repeat."""
    shape = _shape()
    envelope = _envelope()
    nested = parse_fdi(made_dashboard(inner_chunks=2).body, shape, envelope)
    assert getattr(nested, "check", "") == "chunk_list"
    assert getattr(nested, "observed", "") == "2"
    garbled = parse_fdi(
        made_dashboard(payload=b'c:{"serializedDatasetChunks":\n').body,
        shape,
        envelope,
    )
    assert getattr(garbled, "check", "") == "chunk_list"
    assert getattr(garbled, "observed", "") == "unreadable"
    quoted = parse_fdi(
        made_dashboard(payload=b'c:"serializedDatasetChunks"\n').body,
        shape,
        envelope,
    )
    assert getattr(quoted, "check", "") == "chunk_list"
    assert getattr(quoted, "observed", "") == "unreadable"
    repeated = parse_fdi(made_dashboard(duplicate_text=True).body, shape, envelope)
    assert getattr(repeated, "check", "") == "row_framing"
    shared = parse_fdi(made_dashboard(shared_row_id=True).body, shape, envelope)
    assert getattr(shared, "check", "") == "row_framing"
    loaded = parse_fdi(made_dashboard().body, shape, envelope)
    assert not isinstance(loaded, InvestmentFailure), getattr(loaded, "check", "")
    payload = _fixtures._payload(
        (invented_record(),),
        currency_text="USD",
        raw_count=None,
        record_count=None,
        extra_key="",
        omit_key="",
        projects_value=None,
        omit_last_reference=False,
        extra_chunk=False,
        bad_reference="",
        document_override=None,
        count_place="metrics",
        inner_chunks=1,
        duplicate_text=False,
        shared_row_id=False,
    )
    assert payload.startswith(b":")
    assert payload.count(b"b:") >= 2


def test_record_counts_come_from_the_metrics_object() -> None:
    """The two counts sit under diagnostics.metrics and equal the records."""
    page = made_dashboard()
    payload = _payload_bytes(page.body)
    assert b'"diagnostics"' in payload
    assert b'"metrics"' in payload
    assert b'"serializedDatasetChunks"' in payload
    parsed = parse_fdi(page.body, _shape(), _envelope())
    assert not isinstance(parsed, InvestmentFailure), getattr(parsed, "check", "")
    assert len(parsed[0]) == 1


def test_number_literals_keep_long_digit_runs() -> None:
    """A coordinate, an amount, a count and an identifier given as numbers load."""
    lat = "25." + ("1" * 8)
    lng = "51." + ("2" * 11)
    amount = ("3" * 8) + ".25"
    counted = ("4" * 11) + ".5"
    identifier = int("5" * 8)
    wide = invented_record(lat=("n", lat), capex=("n", amount))
    far = invented_record(lng=("n", lng), jobs=("n", counted), project_id=identifier)
    page = made_dashboard((wide, far))
    parsed = parse_fdi(page.body, _shape(), _envelope())
    assert not isinstance(parsed, InvestmentFailure), getattr(parsed, "check", "")
    rows = {row["project_id"]: row for row in parsed[0]}
    assert rows[1001]["lat"] == lat
    assert rows[1001]["capex_value"] == amount
    assert rows[identifier]["lng"] == lng
    assert rows[identifier]["jobs"] == counted
    assert rows[identifier]["project_id"] == identifier


def test_text_field_digit_run_names_the_field() -> None:
    """A text field with a bare digit run fails identifier_shape and names the field."""
    eight = invented_record(description="Invented " + ("6" * 8))
    refused = parse_fdi(made_dashboard((eight,)).body, _shape(), _envelope())
    assert isinstance(refused, InvestmentFailure)
    assert refused.check == "identifier_shape"
    assert refused.observed == "description"
    eleven = invented_record(city_name="Invented " + ("7" * 11))
    refused_eleven = parse_fdi(made_dashboard((eleven,)).body, _shape(), _envelope())
    assert isinstance(refused_eleven, InvestmentFailure)
    assert refused_eleven.check == "identifier_shape"
    assert refused_eleven.observed == "city_name"


def test_other_inline_scripts_are_not_payloads() -> None:
    """Noise scripts around one or two payloads do not become push arguments."""
    around = made_dashboard(noise_order=(0, 1, 2, 3), payload_at=2, pushes=2)
    text = around.body.decode("utf-8")
    assert "dataLayer.push(arguments)" in text
    assert "$RB.push(a)" in text
    assert "requestAnimationFrame(function()" in text
    parsed = parse_fdi(around.body, _shape(), _envelope())
    assert not isinstance(parsed, InvestmentFailure), getattr(parsed, "check", "")
    assert parsed[0][0]["company"] == "Invented Loom Works"
    other = made_dashboard(noise_order=(2, 0, 3, 1), payload_at=1, pushes=1)
    again = parse_fdi(other.body, _shape(), _envelope())
    assert not isinstance(again, InvestmentFailure), getattr(again, "check", "")
    assert again[0][0]["company"] == "Invented Loom Works"


def test_builder_cuts_text_rows_inside_a_multibyte_character() -> None:
    """One push and two pushes use both row kinds and rejoin a split character."""
    once = made_dashboard(pushes=1)
    twice = made_dashboard(pushes=2)
    assert twice.body.count(b".push(") == 3
    payload = _payload_bytes(twice.body)
    assert b":[]\n" in payload
    assert payload.count(b"\nb:") >= 1
    assert b'"serializedDatasetChunks"' in payload
    assert b":T" in payload
    assert b"\xc3\xa9" not in payload
    assert b"\xc3" in payload
    shape = _shape()
    envelope = _envelope()
    first = parse_fdi(once.body, shape, envelope)
    second = parse_fdi(twice.body, shape, envelope)
    assert not isinstance(first, InvestmentFailure)
    assert not isinstance(second, InvestmentFailure)
    assert first[0][0]["project_key"] == second[0][0]["project_key"]
    assert first[0][0]["description"] == "Invented caf\u00e9 note"
    assert first[0][0]["tags"] is None
    assert first[0][0]["project_key"] == _independent_key(once.tokens[0])


def test_jobs_fraction_and_three_project_identifiers() -> None:
    """A fraction digit is kept, and three identifiers are three keys."""
    fraction = made_dashboard((invented_record(jobs=("n", "4.5")),))
    parsed = parse_fdi(fraction.body, _shape(), _envelope())
    assert not isinstance(parsed, InvestmentFailure)
    assert parsed[0][0]["jobs"] == "4.5"
    records = tuple(invented_record(project_id=1000 + index) for index in (1, 2, 3))
    page = made_dashboard(records)
    loaded = parse_fdi(page.body, _shape(), _envelope())
    assert not isinstance(loaded, InvestmentFailure)
    keys = [row["project_key"] for row in loaded[0]]
    assert len(set(keys)) == 3
    assert keys == [_independent_key(tokens) for tokens in page.tokens]


def test_empty_text_on_every_text_field_loads_as_null() -> None:
    """An empty text is nothing on every text field, and a number there is refused."""
    blank = made_dashboard((invented_record(city_name="", sector_name=""),))
    parsed = parse_fdi(blank.body, _shape(), _envelope())
    assert not isinstance(parsed, InvestmentFailure), getattr(parsed, "check", "")
    assert parsed[0][0]["city_name"] is None
    assert parsed[0][0]["sector"] is None
    numbered = made_dashboard((invented_record(city_name=("n", "4")),))
    refused = parse_fdi(numbered.body, _shape(), _envelope())
    assert isinstance(refused, InvestmentFailure)
    assert refused.check == "field_type"
    assert refused.expected == "city_name:text"
    assert refused.observed == "number"
    listed = made_dashboard((invented_record(province=["Invented"]),))
    refused_list = parse_fdi(listed.body, _shape(), _envelope())
    assert isinstance(refused_list, InvestmentFailure)
    assert refused_list.check == "field_type"
    assert refused_list.observed == "list"
    nulled = made_dashboard((invented_record(description=None),))
    refused_null = parse_fdi(nulled.body, _shape(), _envelope())
    assert isinstance(refused_null, InvestmentFailure)
    assert refused_null.check == "field_type"
    assert refused_null.observed == "null"
    text_on_number = made_dashboard((invented_record(tech_level_id="one"),))
    refused_text = parse_fdi(text_on_number.body, _shape(), _envelope())
    assert isinstance(refused_text, InvestmentFailure)
    assert refused_text.check == "field_type"
    assert refused_text.observed == "string"


def test_published_text_and_empty_forms_load_as_specified() -> None:
    """Trailing space stays, and the page's empty forms load as null."""
    spaced = made_dashboard((invented_record(sector_name="Invented textiles "),))
    parsed = parse_fdi(spaced.body, _shape(), _envelope())
    assert not isinstance(parsed, InvestmentFailure)
    assert parsed[0][0]["sector"] == "Invented textiles "
    zeros = made_dashboard((invented_record(lat=("n", "0"), lng=("n", "0")),))
    emptied = parse_fdi(zeros.body, _shape(), _envelope())
    assert not isinstance(emptied, InvestmentFailure)
    assert emptied[0][0]["lat"] is None
    assert emptied[0][0]["lng"] is None
    assert emptied[1] == 1
    undated = made_dashboard(
        (invented_record(project_date="", project_year="", project_month=None),)
    )
    blank = parse_fdi(undated.body, _shape(), _envelope())
    assert not isinstance(blank, InvestmentFailure)
    assert blank[0][0]["announced"] is None
    assert blank[0][0]["project_year"] is None
    assert blank[0][0]["project_month"] is None
    quiet = made_dashboard((invented_record(capex=("n", "0"), capex_currency=""),))
    money = parse_fdi(quiet.body, _shape(), _envelope())
    assert not isinstance(money, InvestmentFailure)
    assert money[0][0]["capex_value"] is None
    assert money[0][0]["capex_unit"] is None
    zero = made_dashboard((invented_record(capex=("n", "0")),))
    stated = parse_fdi(zero.body, _shape(), _envelope())
    assert not isinstance(stated, InvestmentFailure)
    assert stated[0][0]["capex_value"] == "0"
    assert stated[0][0]["capex_unit"] == "Mn USD"
    south = made_dashboard((invented_record(lat=("n", "-90"), lng=("n", "180")),))
    south_row = parse_fdi(south.body, _shape(), _envelope())
    assert not isinstance(south_row, InvestmentFailure)
    assert south_row[0][0]["lat"] == "-90"
    assert south_row[0][0]["lng"] == "180"
    north = made_dashboard((invented_record(lat=("n", "90"), lng=("n", "-180")),))
    north_row = parse_fdi(north.body, _shape(), _envelope())
    assert not isinstance(north_row, InvestmentFailure)
    assert north_row[0][0]["lat"] == "90"
    assert north_row[0][0]["lng"] == "-180"
    signed = made_dashboard((invented_record(lat=("n", "-10.5")),))
    signed_row = parse_fdi(signed.body, _shape(), _envelope())
    assert not isinstance(signed_row, InvestmentFailure)
    assert signed_row[0][0]["lat"] == "-10.5"
    labelled = made_dashboard((invented_record(tags=["invented", "loom"]),))
    labelled_row = parse_fdi(labelled.body, _shape(), _envelope())
    assert not isinstance(labelled_row, InvestmentFailure)
    assert labelled_row[0][0]["tags"] == '["invented","loom"]'


@pytest.mark.parametrize(
    ("name", "page", "check", "expected", "observed"),
    [
        (
            "no_push_payload",
            page_from_script("(self.__next_f=self.__next_f||[]).push([0])"),
            "no_push_payload",
            "push payload",
            "absent",
        ),
        (
            "push_argument",
            page_from_script('self.__next_f.push([1,"x",true])'),
            "push_argument",
            "two-element array",
            "refused",
        ),
        (
            "push_argument_zero",
            page_from_script("self.__next_f.push([0])"),
            "push_argument",
            "two-element array",
            "refused",
        ),
        (
            "row_framing",
            made_dashboard(payload=b"not-a-row").body,
            "row_framing",
            "id and colon",
            "absent",
        ),
        (
            "text_row_length",
            made_dashboard(payload=b"1:T10,abc").body,
            "text_row_length",
            "bytes that remain",
            "longer",
        ),
        (
            "text_row_exact",
            made_dashboard(payload=b"1:T3,abc").body,
            "chunk_list",
            "one",
            "none",
        ),
        (
            "chunk_list_none",
            made_dashboard(payload=b"1:[]\n").body,
            "chunk_list",
            "one",
            "none",
        ),
        (
            "chunk_list_two",
            made_dashboard(extra_chunk=True).body,
            "chunk_list",
            "one",
            "2",
        ),
        (
            "chunk_reference",
            made_dashboard(bad_reference="$ffff").body,
            "chunk_reference",
            "text row",
            "$ffff",
        ),
        (
            "chunk_encoding",
            made_dashboard(omit_last_reference=True).body,
            "chunk_encoding",
            "utf-8",
            "not utf-8",
        ),
        (
            "chunk_json",
            made_dashboard(document_override=b"{").body,
            "chunk_json",
            "one json document",
            "refused",
        ),
        (
            "top_level_keys",
            made_dashboard(extra_key="invented_extra").body,
            "top_level_keys",
            "clientProjects,indexBaseMetrics,currencyText,latestDate",
            "clientProjects,currencyText,indexBaseMetrics,invented_extra,latestDate",
        ),
        (
            "client_projects",
            made_dashboard(projects_value=[1]).body,
            "client_projects",
            "list of objects",
            "refused",
        ),
        (
            "client_projects_object",
            made_dashboard(projects_value={}).body,
            "client_projects",
            "list of objects",
            "refused",
        ),
        (
            "record_count",
            made_dashboard(raw_count=99).body,
            "record_count",
            "1",
            "99",
        ),
        (
            "record_count_recorded",
            made_dashboard(record_count=99).body,
            "record_count",
            "1",
            "99",
        ),
        (
            "record_count_no_diagnostics",
            made_dashboard(count_place="no_diagnostics").body,
            "record_count",
            "record count",
            "not an integer",
        ),
        (
            "record_count_no_metrics",
            made_dashboard(count_place="no_metrics").body,
            "record_count",
            "record count",
            "not an integer",
        ),
        (
            "record_count_no_raw",
            made_dashboard(count_place="no_raw").body,
            "record_count",
            "record count",
            "not an integer",
        ),
        (
            "record_count_no_record",
            made_dashboard(count_place="no_record").body,
            "record_count",
            "record count",
            "not an integer",
        ),
        (
            "record_count_beside",
            made_dashboard(count_place="beside").body,
            "record_count",
            "record count",
            "not an integer",
        ),
        (
            "record_count_fraction",
            made_dashboard(count_place="raw_fraction").body,
            "record_count",
            "record count",
            "not an integer",
        ),
        (
            "unknown_field",
            made_dashboard((_with("firm_name", "Invented"),)).body,
            "unknown_field",
            "declared field",
            "firm_name",
        ),
        (
            "missing_field",
            made_dashboard((_without("province"),)).body,
            "missing_field",
            "province",
            "missing",
        ),
        (
            "field_type",
            made_dashboard((invented_record(jobs="many"),)).body,
            "field_type",
            "jobs:decimal(18,2)",
            "string",
        ),
        (
            "missing_caveat",
            made_dashboard(drop_phrase=PHRASES[0]).body,
            "missing_caveat",
            PHRASES[0],
            "absent",
        ),
        (
            "capex_label",
            made_dashboard(drop_label="Mn").body,
            "capex_label",
            "Mn",
            "absent",
        ),
        (
            "currency_text",
            made_dashboard(currency_text="EUR").body,
            "currency_text",
            "USD",
            "EUR",
        ),
        (
            "unrepresentable_integer",
            made_dashboard((invented_record(tech_level_id=("n", "1.5")),)).body,
            "unrepresentable",
            "integer",
            "refused",
        ),
        (
            "unrepresentable_decimal",
            made_dashboard((invented_record(capex=("n", "1.234")),)).body,
            "unrepresentable",
            "decimal(18,2)",
            "refused",
        ),
        (
            "coordinate_one_zero",
            made_dashboard((invented_record(lat=("n", "0"), lng=("n", "20.5")),)).body,
            "coordinate",
            "both empty or neither",
            "one zero",
        ),
        (
            "coordinate_latitude",
            made_dashboard((invented_record(lat=("n", "91")),)).body,
            "coordinate",
            "latitude -90 to 90",
            "outside",
        ),
        (
            "coordinate_longitude",
            made_dashboard((invented_record(lng=("n", "181")),)).body,
            "coordinate",
            "longitude -180 to 180",
            "outside",
        ),
        (
            "capex_currency_empty",
            made_dashboard(
                (invented_record(capex=("n", "1"), capex_currency=""),)
            ).body,
            "capex_currency",
            "USD or empty with zero",
            "empty currency",
        ),
        (
            "capex_currency_other",
            made_dashboard((invented_record(capex_currency="EUR"),)).body,
            "capex_currency",
            "USD",
            "EUR",
        ),
        (
            "announced_calendar",
            made_dashboard((invented_record(project_date="2023-02-29"),)).body,
            "announced",
            "calendar date",
            "refused",
        ),
        (
            "announced_month",
            made_dashboard((invented_record(project_year=2023),)).body,
            "announced",
            "year and zero-based month",
            "mismatch",
        ),
        (
            "announced_undated",
            made_dashboard(
                (
                    invented_record(
                        project_date="", project_year=2024, project_month=None
                    ),
                )
            ).body,
            "announced",
            "empty year and month",
            "dated parts",
        ),
        (
            "duplicate_project",
            made_dashboard((invented_record(), invented_record())).body,
            "duplicate_project",
            "unique published fields",
            "fdi_",
        ),
    ],
)
def test_each_planted_refusal_names_its_reason(
    name: str, page: bytes, check: str, expected: str, observed: str
) -> None:
    """One planted page fails by its own reason and publishes nothing from the parser."""
    del name
    result = parse_fdi(page, _shape(), _envelope())
    assert isinstance(result, InvestmentFailure)
    assert result.check == check
    assert result.expected == expected
    if check != "duplicate_project":
        assert result.observed == observed
    else:
        assert result.observed.startswith("fdi_")


def test_renamed_required_field_fails_the_build_and_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown dashboard field fails the build by source and publishes no rows."""
    import commands.build_public as build_public

    record = invented_record()
    record["firm_name"] = "Invented"
    page = made_dashboard((record,)).body
    _allow_reserved(monkeypatch)

    def transport(url: str) -> object:
        from eii_custodian.publicdata.fetch.transport import Response

        if url == DASHBOARD:
            return Response(final_url=url, body=page, hops=())
        if url == TERMS:
            return Response(final_url=url, body=TERMS_BODY, hops=())
        raise AssertionError(url)

    monkeypatch.setattr(build_public, "load_registry", lambda: (_fdi_entry(),))
    monkeypatch.setattr(build_public, "utc_now", lambda: RETRIEVED)
    code = build_public.run(
        tmp_path, {}, (), transport=transport, sleep=lambda _seconds: None
    )
    captured = capsys.readouterr()
    assert code != 0
    assert "fdi_projects" in captured.out
    assert "unknown_field" in captured.out
    assert "firm_name" in captured.out
    loadable = tmp_path / "data" / "public_cache" / "fdi_projects" / "loadable.json"
    assert not loadable.exists()
    staged = list((tmp_path / "data" / "public_cache").rglob("staging/**/*.json"))
    assert staged == []


def _payload_bytes(page: bytes) -> bytes:
    text = page.decode("utf-8")
    decoder = json.JSONDecoder()
    parts: list[str] = []
    cursor = 0
    while True:
        found = text.find(".push(", cursor)
        if found < 0:
            break
        value, offset = decoder.raw_decode(text[found + 6 :])
        cursor = found + 6 + offset
        if isinstance(value, list) and len(value) == 2 and value[0] == 1:
            parts.append(value[1])
    return "".join(parts).encode("utf-8", "surrogateescape")


def _independent_key(tokens: dict[str, str]) -> str:
    parts = [
        json.dumps(name, ensure_ascii=True) + ":" + tokens[name]
        for name in sorted(tokens)
    ]
    encoded = "{" + ",".join(parts) + "}"
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return "fdi_" + digest[:16]


def _shape() -> object:
    spec = load_source_spec("fdi_projects", url=DASHBOARD)
    assert not isinstance(spec, InvestmentFailure)
    assert spec.dashboard is not None
    return spec.dashboard


def _envelope() -> SourceEnvelope:
    return dashboard_envelope(
        SourceEnvelope(
            source_id="fdi_projects",
            publisher="National investment promotion agency",
            page_url=DASHBOARD,
            licence_id="publisher-terms",
            licence_basis="owner_decision",
            decision_record="0017",
            terms_sha256="ab" * 32,
            terms_url=TERMS,
            retrieved_utc=RETRIEVED,
            page_sha256="cd" * 32,
            method="",
            method_version="",
        )
    )


def _allow_reserved(monkeypatch: pytest.MonkeyPatch) -> None:
    def allow(url: str) -> HostDecision:
        decision = approve(url)
        if decision.ok or decision.host.endswith(".invalid"):
            return HostDecision(True, decision.host, "https", "")
        return decision

    monkeypatch.setattr("eii_custodian.publicdata.fetch.build.approve", allow)
    monkeypatch.setattr("eii_custodian.publicdata.fetch.kinds.approve", allow)


def _fdi_entry() -> Entry:
    return Entry(
        key="fdi_projects",
        source_id="fdi_projects",
        slug="",
        kind="terms_page",
        title_en="FDI projects dashboard",
        publisher="National investment promotion agency",
        licence_id="publisher-terms",
        licence_basis="owner_decision",
        decision_record="0017",
        fetch_host="dashboard.invalid",
        url=DASHBOARD,
        terms_url=TERMS,
        nightly_live_fetch=True,
        public_splits=(),
        commit_allowed=False,
        release_tables=("fdi_projects",),
        caveat_keys=("fdi_estimates",),
        columns=(),
        row_count_min=1,
        row_count_max=5000,
        period_first="2000",
        period_last="2000",
        period_field="announced",
        reconciliation="none",
        skip_reason="",
        extension="html",
        landing_url=DASHBOARD,
        terms_watch=True,
        basis_note="Owner decision recorded for this planted row.",
    )
