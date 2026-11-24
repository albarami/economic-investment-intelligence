"""Inventory-derived refusal plants over invented outputs, with no acquisition.

The fixture traces each distinct named refusal (and opaque exception family) to
its row in the supplied S2-P56 study. These tests exercise log delivery, not the
correctness of the pre-existing producer's refusal conditions.
"""

import importlib
import json
import re
from hashlib import sha256

import pytest
from custodian.tests.fixtures.assembly_refusals import (
    INVENTORY_CASES,
    REVIEW_DATA_GUARD_CASES,
)
from custodian.tests.test_production_adapters import context
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly import PHASES, AssemblyError, Step, run_steps
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.assembly_inventory import INVENTORY
from eii_custodian.publicdata.assembly_io import write_record
from eii_custodian.publicdata.assembly_refusal_policy import TEXT_REASONS
from eii_custodian.publicdata.fetch.build import run_build

CASES = [
    {
        "row": row["row"],
        "stage": row["stage"],
        "anchor": row["anchor"],
        "exception": kind,
        "message": message,
        "expected": expected,
        "plant": f"syn_{index}",
    }
    for row in (*INVENTORY_CASES, *REVIEW_DATA_GUARD_CASES)
    for index, (kind, message, expected) in enumerate(row["plants"])
]
MODULES = {
    "AdditionError": "additions.common",
    "AwardError": "fetch.award_checks",
    "ParseError": "comtrade.parse",
    "PageShapeError": "singles.tenders_html",
    "YAMLError": "yaml",
    "ParserError": "yaml.parser",
    "CsvError": "csv",
    "DuckDBError": "duckdb",
    "AreaError": "places.areas",
    "AssemblyError": "assembly",
    "BaciError": "baci.config",
    "BuildingError": "building_inputs",
    "BuildInputError": "busyness.build",
    "CacheError": "review.cache_fixture",
    "CoolingError": "singles.dcool",
    "CreditError": "singles.bank_credit",
    "DecimalRefusal": "fetch.decimals",
    "FamilyError": "singles.families",
    "FrameError": "frame.checks",
    "GraphError": "review.graph",
    "HeightError": "heights.model",
    "LayerError": "gis.layers",
    "MunicipalityFrameRefused": "series.frame",
    "PageError": "fetch.page_records",
    "PlacesError": "places",
    "PlacesFsqError": "places_fsq.errors",
    "RegistryError": "fetch.registry",
    "ReviewError": "busyness.review",
    "SafeRefusal": "comtrade.policy",
    "SeriesRefused": "series.parse",
    "ShapeError": "busyness.parse",
    "SnapshotError": "fetch.snapshots",
    "SpineError": "review.activity",
    "TenderError": "singles.tenders",
    "JSONDecodeError": "json",
    "PackageNotFoundError": "importlib.metadata",
    "InvalidOperation": "decimal",
}


def test_refusal_inventory_matches_approved_payload():
    payload = json.dumps(INVENTORY_CASES, sort_keys=True, separators=(",", ":"))
    assert sha256(payload.encode()).hexdigest() == (
        "e2f363e027c8c828e6b7fa5dc8ec23cd802dc086b4a36472d59cbcb602a64dc5"
    )


def planted_error(name, message):
    if name == "UnicodeDecodeError":
        return UnicodeDecodeError("utf-8", b"\xff", 0, 1, message)
    if name in MODULES:
        module = MODULES[name]
        if module not in {
            "json",
            "importlib.metadata",
            "decimal",
            "yaml",
            "yaml.parser",
            "csv",
            "duckdb",
        }:
            module = "eii_custodian.publicdata." + module
    else:
        module = "builtins"
    cls = getattr(
        importlib.import_module(module),
        "Error" if name in {"CsvError", "DuckDBError"} else name,
    )
    if name == "JSONDecodeError":
        return cls(message, "", 0)
    if name == "SafeRefusal":
        return cls(message, "SYN", "SYN")
    if name == "SeriesRefused":
        return cls(message, "SYN opaque detail")
    return cls(message)


def invented_adapters(build, stage, fault, calls):
    def producer(item):
        def run():
            calls.append(item.name)
            if item.name == stage:
                raise fault
            output = {}
            # Main's S2-P56 stub combines with S2-P63's pending pin phase:
            # without bound inputs, that phase's expected output set is empty.
            outputs = () if item.name == "method_pins" else item.outputs
            for path in outputs:
                output.update(write_record(build.cache, path, {"syn": True}))
            return output

        return run

    return {item.name: producer(item) for item in INVENTORY}


def bind_fault(monkeypatch, stage, fault, calls):
    monkeypatch.setattr(
        Production,
        "adapters",
        lambda build: invented_adapters(build, stage, fault, calls),
    )
    if stage == "require_complete":

        def refused(_audit):
            raise fault

        monkeypatch.setattr(
            "eii_custodian.publicdata.assembly_reports.require_complete", refused
        )


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=lambda c: (
        c["row"] + ":" + c["exception"] + ":" + c["expected"] + ":" + c["plant"]
    ),
)
def test_inventory_refusal_reaches_build_log(tmp_path, monkeypatch, case):
    fault = planted_error(case["exception"], case["message"])
    calls = []
    bind_fault(monkeypatch, case["stage"], fault, calls)
    result = run_build(
        (),
        lambda _url: pytest.fail("network called"),
        tmp_path,
        lambda: "2026-11-22T00:00:00Z",
        lambda _delay: None,
        seed=17,
    )
    expected = f"REFUSED {case['stage']} {case['expected']}"
    assert expected in result.lines
    assert expected in json.loads((tmp_path / "build-log.json").read_text())["lines"]
    assert result.failure.code == 1
    if case["stage"] in PHASES:
        assert calls == list(PHASES[: PHASES.index(case["stage"]) + 1])


@pytest.mark.parametrize("stage", (*PHASES, "require_complete"))
def test_exception_identity_and_existing_fail_word_are_unchanged(
    tmp_path, monkeypatch, stage
):
    fault = AssemblyError("assembly_input_refused")
    calls = []
    bind_fault(monkeypatch, stage, fault, calls)
    build = context(tmp_path / "direct")
    with pytest.raises(AssemblyError, match=r"^assembly_input_refused$") as raised:
        build.run()
    assert raised.value is fault
    assert build.lines == [f"REFUSED {stage} assembly_input_refused"]
    result = run_build(
        (),
        lambda _url: pytest.fail("network called"),
        tmp_path / "outer",
        lambda: "2026-11-22T00:00:00Z",
        lambda _delay: None,
        seed=17,
    )
    assert result.failure.code == 1
    assert result.failure.check == "assembly_build_refused"
    assert result.lines[-1] == (
        "FAIL assembly assembly_build_refused expected=verified ordered outputs "
        "observed=NO_DATA"
    )


def test_logging_never_echoes_exception_text(tmp_path, monkeypatch):
    message = "/syn/forbidden-output " + "9" * 9
    fault = ValueError(message)
    bind_fault(monkeypatch, "heights", fault, [])
    build = context(tmp_path)
    with pytest.raises(ValueError, match=re.escape(message)) as raised:
        build.run()
    assert raised.value is fault
    assert build.lines == ["REFUSED heights heights_unexpected_valueerror"]
    assert message not in "\n".join(build.lines)
    assert "/syn/forbidden-output" not in "\n".join(build.lines)
    assert "9" * 9 not in "\n".join(build.lines)


def test_all_policy_words_are_closed_and_known():
    from eii_custodian.publicdata.assembly_refusals import (
        STAGE_WORDS,
        closed_reason,
    )

    for case in CASES:
        reason = closed_reason(
            case["stage"], planted_error(case["exception"], case["message"])
        )
        assert reason == case["expected"]
        assert reason in STAGE_WORDS[case["stage"]]
    for stage, words in STAGE_WORDS.items():
        assert re.fullmatch("[a-z0-9_]+", stage)
        for word in words:
            assert re.fullmatch("[a-z0-9_]+", word)
            assert not re.search(r"(?<![0-9])(?:[0-9]{8}|[0-9]{11})(?![0-9])", word)


@pytest.mark.parametrize(
    "kind,index,pattern,word",
    [
        (kind, index, pattern, word)
        for kind, rows in TEXT_REASONS.items()
        for index, (pattern, word) in enumerate(rows)
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else str(value),
)
def test_all_policy_words_rows_are_reachable(kind, index, pattern, word):
    from eii_custodian.publicdata.assembly_refusals import closed_reason

    # Current policy patterns contain literal text and .* wildcards only.
    witness = re.sub(r"\\(.)", r"\1", pattern.pattern.replace(".*", "SYN"))
    assert pattern.fullmatch(witness) is not None, "extend the witness generator"
    first = next(
        (position, reason)
        for position, (candidate, reason) in enumerate(TEXT_REASONS[kind])
        if candidate.fullmatch(witness) is not None
    )
    # Row identity also rejects dead duplicates that return the same word.
    assert first == (index, word), f"shadowed {kind.__name__} row: {pattern.pattern}"
    assert (
        closed_reason("gis_property_singles", planted_error(kind.__name__, witness))
        == word
    )


@given(
    st.text(),
    st.text(
        alphabet=st.characters(exclude_characters="\x00", exclude_categories=("Cs",))
    ),
)
def test_arbitrary_messages_and_class_names_cannot_escape_closed_table(message, name):
    from eii_custodian.publicdata.assembly_refusals import (
        STAGE_WORDS,
        closed_reason,
    )

    for stage in STAGE_WORDS:
        word = closed_reason(stage, ValueError(message))
        assert word in STAGE_WORDS[stage]
        assert re.fullmatch("[a-z0-9_]+", word)
        unknown = type(name, (Exception,), {})(message)
        assert closed_reason(stage, unknown) == stage + "_unexpected"


@pytest.mark.parametrize("bad_output", [None, [], {"syn-extra": "syn"}])
def test_output_validation_refusals_name_the_responsible_stage(tmp_path, bad_output):
    lines = []

    def producer(name):
        return lambda: bad_output if name == "heights" else {}

    steps = tuple(Step(name, producer(name), ()) for name in PHASES)
    with pytest.raises(AssemblyError, match=r"^assembly_output_invalid$"):
        run_steps(tmp_path, steps, lines=lines)
    assert lines == ["REFUSED heights assembly_output_invalid"]


@pytest.mark.parametrize("reason", ["road_file_missing", "road_file_unreceipted"])
def test_silent_road_refusals_are_observed_without_changing_return(
    tmp_path, monkeypatch, reason
):
    from eii_custodian.publicdata.places import integrate
    from eii_custodian.publicdata.places.areas import AreaError

    def refused(_cache):
        raise AreaError(reason)

    monkeypatch.setattr(integrate, "road_receipt", refused)
    lines = []
    from eii_custodian.publicdata.assembly_refusals import stage_refusals

    with stage_refusals(lines, "frame"):
        assert integrate.areas_before_stage(tmp_path, lines, tmp_path) is None
    assert lines == [f"REFUSED frame {reason}"]


@pytest.mark.parametrize("reader", ["read_place_file", "read_building_file"])
def test_swallowed_places_reader_error_is_observed_without_changing_points(
    tmp_path, monkeypatch, reader
):
    from eii_custodian.publicdata.places import PlacesError, integrate

    monkeypatch.setattr(integrate, "_tag", lambda _review: "ar")
    monkeypatch.setattr(
        integrate,
        "_opened_place",
        lambda _cache, key: (
            (tmp_path / "syn.parquet", None) if key.startswith("places_ovt") else None
        ),
    )

    monkeypatch.setattr(
        integrate,
        "_buildings_from_registry",
        lambda _cache, _registry: ([tmp_path / "syn.parquet"], ()),
    )
    monkeypatch.setattr(integrate, "read_place_file", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(integrate, "read_building_file", lambda *_args, **_kwargs: ())

    def refused(*_args, **_kwargs):
        raise PlacesError("missing_column")

    monkeypatch.setattr(integrate, reader, refused)
    lines = []
    from eii_custodian.publicdata.assembly_refusals import stage_refusals

    with stage_refusals(lines, "frame"):
        assert integrate._cache_points(tmp_path, tmp_path) == {}
    assert lines == ["REFUSED frame missing_column"]


def test_review_wrapper_keeps_the_underlying_closed_error(tmp_path, monkeypatch):
    from eii_custodian.publicdata.places import integrate

    monkeypatch.setattr(integrate, "road_receipt", lambda _cache: "a" * 64)

    def refused(_cache, _review):
        raise OSError("/syn/unreadable " + "9" * 9)

    monkeypatch.setattr(integrate, "_cache_points", refused)
    lines = []
    from eii_custodian.publicdata.assembly_refusals import stage_refusals

    with stage_refusals(lines, "frame"):
        assert integrate.areas_before_stage(tmp_path, lines, tmp_path) is None
    assert lines == [
        "REFUSED review_unreadable",
        "REFUSED frame frame_unexpected_oserror",
    ]


@pytest.mark.parametrize(
    "reason", ["", "/syn/leak " + "9" * 9, "\u03b1", "syn_unknown"]
)
def test_unknown_nested_note_uses_closed_fallback(reason):
    from eii_custodian.publicdata.places import integrate

    lines = []
    from eii_custodian.publicdata.assembly_refusals import stage_refusals

    with stage_refusals(lines, "frame"):
        integrate._note(lines, "places", reason)
    assert lines == ["REFUSED frame frame_unexpected_placeserror"]


def test_unknown_stage_and_absent_log_write_nothing():
    from eii_custodian.publicdata.assembly_refusals import note_refusal, stage_refusals

    lines = []
    fault = ValueError("/syn/no-output " + "9" * 9)
    note_refusal(lines, "/syn/unknown-stage", fault)
    assert lines == []
    with pytest.raises(ValueError, match=re.escape(str(fault))) as raised:
        with stage_refusals(None, "frame"):
            raise fault
    assert raised.value is fault


@pytest.mark.parametrize("kind", ["OSError", "ValueError", "KeyError", "SpineError"])
def test_caught_series_regression_keeps_closed_reason_and_blocked_result(
    tmp_path, monkeypatch, kind
):
    from custodian.tests.test_public_series import series_cache
    from custodian.tests.test_series_figures_survivors import _shapes

    from eii_custodian.publicdata.assembly_refusals import stage_refusals
    from eii_custodian.publicdata.series import figures

    entry, digest = series_cache(tmp_path, "util_elec", [_shapes()["util_elec"][0]])
    fault = planted_error(kind, "figure_invalid" if kind == "ValueError" else "SYN")

    def refused(*_args, **_kwargs):
        raise fault

    monkeypatch.setattr(figures, "compute_checks", refused)
    original = figures.build_series(tmp_path, [entry], {entry.key: digest})
    lines = []
    with stage_refusals(lines, "series_stage"):
        observed = figures.build_series(tmp_path, [entry], {entry.key: digest})
    assert observed == original
    expected = (
        "figure_invalid"
        if kind == "ValueError"
        else "series_stage_unexpected_" + kind.lower()
    )
    assert lines == ["REFUSED series_stage " + expected]


def test_wrapped_refusal_names_both_closed_causes_without_changing_exception():
    from eii_custodian.publicdata.assembly_refusals import stage_refusals
    from eii_custodian.publicdata.building_inputs import BuildingError
    from eii_custodian.publicdata.heights.model import HeightError

    inner = BuildingError("building_part_unregistered")
    outer = HeightError("building_manifest_inputs")
    lines = []
    with pytest.raises(HeightError, match=r"^building_manifest_inputs$") as raised:
        with stage_refusals(lines, "heights"):
            try:
                raise inner
            except BuildingError:
                raise outer from None
    assert raised.value is outer
    assert lines == [
        "REFUSED heights building_manifest_inputs",
        "REFUSED heights building_part_unregistered",
    ]


@pytest.mark.parametrize(
    "chain,outer_kind,inner_kind,reasons",
    [
        (
            "explicit",
            "AssemblyError",
            "ValueError",
            ["assembly_input_refused", "heights_unexpected_valueerror"],
        ),
        (
            "implicit",
            "PlacesError",
            "ValueError",
            ["heights_unexpected_placeserror", "heights_unexpected_valueerror"],
        ),
        (
            "suppressed",
            "OSError",
            "KeyError",
            ["heights_unexpected_oserror", "heights_unexpected_keyerror"],
        ),
        (
            "cycle",
            "OSError",
            "KeyError",
            ["heights_unexpected_oserror", "heights_unexpected_keyerror"],
        ),
    ],
)
def test_exception_chains_keep_closed_lines_and_exception_identity(
    chain, outer_kind, inner_kind, reasons
):
    from eii_custodian.publicdata.assembly_refusals import stage_refusals

    message = "/syn/leak/path 1234567890 https://syn.invalid/x"
    outer = planted_error(
        outer_kind, "assembly_input_refused" if chain == "explicit" else message
    )
    inner = planted_error(inner_kind, message)
    if chain == "cycle":
        outer.__cause__ = inner
        inner.__cause__ = outer
    lines = []
    with pytest.raises(type(outer), match=re.escape(str(outer))) as raised:
        with stage_refusals(lines, "heights"):
            if chain == "explicit":
                raise outer from inner
            if chain == "cycle":
                raise outer
            try:
                raise inner
            except type(inner):
                if chain == "suppressed":
                    raise outer from None
                raise outer  # noqa: B904 -- exercise implicit exception context
    assert raised.value is outer
    assert lines == ["REFUSED heights " + reason for reason in reasons]
    assert not any(re.search(r"/syn|[0-9]{10}|https?:", line) for line in lines)


def test_exception_context_cycle_is_finite_and_deduplicated(monkeypatch):
    from eii_custodian.publicdata import assembly_refusals
    from eii_custodian.publicdata.assembly_refusals import note_refusal

    original = assembly_refusals.closed_reason
    calls = []

    def bounded_visit(stage, error):
        calls.append(error)
        assert len(calls) <= 2, (
            "a context cycle must stop after the distinct exceptions"
        )
        return original(stage, error)

    monkeypatch.setattr(assembly_refusals, "closed_reason", bounded_visit)
    first = ValueError("figure_invalid")
    second = ValueError("figure_invalid")
    first.__context__ = second
    second.__context__ = first
    lines = []
    note_refusal(lines, "draw", first)
    assert lines == ["REFUSED draw figure_invalid"]


def test_unknown_nested_stage_and_missing_sink_are_withheld():
    from eii_custodian.publicdata.places.integrate import _note

    lines = []
    _note(lines, "/syn/unknown-stage", "arabic_tag_missing")
    assert lines == []
    assert _note(None, "places", "arabic_tag_missing") is None


def test_named_word_is_canonical_even_when_message_formatting_would_leak():
    from eii_custodian.publicdata.assembly_refusals import note_refusal

    class UnsafeWord(str):
        def __format__(self, _spec):
            return "/syn/never-log " + "9" * 9

    lines = []
    note_refusal(lines, "draw", ValueError(UnsafeWord("figure_invalid")))
    assert lines == ["REFUSED draw figure_invalid"]


def test_nontext_error_argument_is_never_stringified():
    from eii_custodian.publicdata.assembly_refusals import note_refusal

    class UnsafeValue:
        def __str__(self):
            pytest.fail("exception argument was stringified")

    lines = []
    note_refusal(lines, "draw", ValueError(UnsafeValue()))
    assert lines == ["REFUSED draw draw_unexpected_valueerror"]


def test_fetch_network_exit_and_original_failure_survive_the_logged_refusal(
    tmp_path, monkeypatch
):
    from eii_custodian.publicdata.fetch.build import BuildOutcome, FetchFailure

    failure = FetchFailure(6, "syn_source", "", "unreachable", "available", "NO_DATA")
    fetched = BuildOutcome(("FAIL syn_source unreachable",), failure)

    def adapters(build):
        build.fetcher = lambda: fetched
        result = invented_adapters(build, "syn_never", None, [])
        result["fetch_archive"] = build.fetch_archive
        return result

    monkeypatch.setattr(Production, "adapters", adapters)
    result = run_build(
        (),
        lambda _url: pytest.fail("network called"),
        tmp_path,
        lambda: "2026-11-22T00:00:00Z",
        lambda _delay: None,
        seed=17,
    )
    assert result.failure is failure
    assert result.failure.code == 6
    assert result.lines == (
        "FAIL syn_source unreachable",
        "REFUSED fetch_archive assembly_fetch_refused",
    )
    assert json.loads((tmp_path / "build-log.json").read_text())["lines"] == list(
        result.lines
    )


def test_nested_legacy_binding_inherits_and_restores_the_observer():
    from eii_custodian.publicdata.assembly_log import build_lines, observe
    from eii_custodian.publicdata.assembly_refusals import stage_refusals

    outer, inner, explicit = [], [], []
    fault = ValueError("figure_invalid")
    assert observe("draw", fault) is False
    with stage_refusals(outer, "draw"):
        with build_lines(inner):
            assert observe("draw", fault) is True
        assert observe("draw", fault, lines=explicit) is True
        assert outer == []
        assert observe("draw", fault) is True
    assert observe("draw", fault) is False
    assert outer == inner == explicit == ["REFUSED draw figure_invalid"]


def test_observer_binding_is_restored_after_exception():
    from eii_custodian.publicdata.assembly_log import build_lines, observe
    from eii_custodian.publicdata.assembly_refusals import note_refusal, stage_refusals

    lines = []
    fault = ValueError("figure_invalid")
    with stage_refusals(lines, "draw"):
        with pytest.raises(ValueError, match=r"^figure_invalid$"):
            with build_lines([], observer=lambda *_args: None):
                raise fault
        assert observe("draw", fault) is True
    assert lines == ["REFUSED draw figure_invalid"]
    assert observe("draw", fault) is False
    # An absent observer cannot accidentally route a previous build's sink.
    note_refusal(None, "draw", fault)


def test_swallowed_snapshot_refusal_keeps_its_closed_name(tmp_path, monkeypatch):
    from custodian.tests.test_places_partb_survivors_c import _row

    from eii_custodian.publicdata.assembly_refusals import stage_refusals
    from eii_custodian.publicdata.fetch.snapshots import SnapshotError
    from eii_custodian.publicdata.places import integrate

    row = _row("places_ovt/part-00014", "places_ovt")
    monkeypatch.setattr(
        integrate, "reviewed_selections", lambda _cache: {row.key: "a" * 64}
    )

    def refused(_cache, _digest):
        raise SnapshotError("snapshot_hash_mismatch")

    monkeypatch.setattr(integrate, "read_snapshot", refused)
    lines = []
    with stage_refusals(lines, "frame"):
        assert integrate._receipt_of(tmp_path, row) is None
    assert lines == ["REFUSED frame snapshot_hash_mismatch"]


def test_nested_area_refusal_uses_closed_assembly_words_and_keeps_legacy_notes():
    from eii_custodian.publicdata.assembly_refusals import stage_refusals
    from eii_custodian.publicdata.places.areas import AreaError
    from eii_custodian.publicdata.places.integrate import _area_refusal

    lines = []
    with stage_refusals(lines, "frame"):
        _area_refusal(lines, AreaError("/syn/never-log " + "9" * 9))
    assert lines == ["REFUSED frame frame_unexpected_areaerror"]
    legacy = []
    _area_refusal(legacy, AreaError("road_file_missing"))
    assert legacy == ["REFUSED road_file_missing"]


def test_fixed_message_patterns_match_the_whole_diagnostic():
    from eii_custodian.publicdata.assembly_refusals import closed_reason

    known = "selected sources must exactly match owned entries"
    assert (
        closed_reason("series_stage", ValueError(known))
        == "selected_sources_must_exactly_match_owned_entries"
    )
    assert (
        closed_reason("series_stage", ValueError(known + " SYN"))
        == "series_stage_unexpected_valueerror"
    )
    assert (
        closed_reason("series_stage", ValueError())
        == "series_stage_unexpected_valueerror"
    )
