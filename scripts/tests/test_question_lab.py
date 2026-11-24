"""S3-T21: independent oracle controls and planted corruptions, offline only."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import socket
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Match the offline eval tests under the runner's safe-path Python.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evals.question_lab.cases import coverage, load_cases, select_cases
from evals.question_lab.oracles import (
    accuracy,
    disclosure,
    map_behaviour,
    parity,
    percentile,
    seal,
    smoothness,
    value,
    visual,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("case", load_cases(ROOT), ids=lambda case: case.identity)
def test_arabic_questions_use_isolated_identifiers_and_reviewed_family_forms(
    case: Any,
) -> None:
    question = case.questions["ar"]
    outside = re.sub("\u2066[^\u2069]*\u2069", "", question)
    assert not re.search("[A-Za-z]", outside), "Latin runs require LTR isolates"
    assert "مرساة" not in question
    starts = {
        "flagship": "عرض الأدلة العامة المدققة",
        "map": "إبقاء الشكل المحدد على الخريطة وأدلته",
        "chip": "فتح مصدر المعلومة المعروضة",
        "refusal": "عرض سبب تعذر توفر المدخلات",
    }
    modes = {
        "polygon": "اختيار مضلع",
        "distance": "اختيار مسافة",
        "walk": "اختيار نطاق المشي",
        "drive": "اختيار نطاق القيادة",
    }
    token = case.identity.removeprefix("INVENTED-question-").replace("-", " ")
    assert question == (
        f"{starts[case.family]} للسيناريو المخترع \u2066{token}\u2069 مع "
        f"{modes[case.mode]} عند نقطة الارتكاز المخترعة {case.pin:.6f}."
    )


@pytest.mark.parametrize("metric", ["map", "chip", "evidence_bundle"])
@pytest.mark.parametrize("limit", [None, 10, "INVENTED-invalid", []])
def test_non_dict_budget_limit_is_a_named_refusal(metric: str, limit: Any) -> None:
    from evals.question_lab.locks import budget_problems

    budget = json.loads((ROOT / "evals/question_lab/budgets.v1.json").read_bytes())
    budget["limits_ms"][metric] = limit
    raw = json.dumps(budget).encode()
    assert "budget:raised_or_invalid_limit" in budget_problems(raw, committed=raw)


def test_distinct_identities_have_both_languages_and_closed_angles() -> None:
    cases = load_cases(ROOT)
    assert len(cases) == 100
    assert len({case.identity for case in cases}) == 100
    assert len({case.questions["en"] for case in cases}) == 100
    assert len({case.questions["ar"] for case in cases}) == 100
    assert {case.family for case in cases} == {"flagship", "map", "chip", "refusal"}
    assert all(set(case.questions) == {"en", "ar"} for case in cases)
    selected = select_cases(cases, 100, 17)
    assert selected == select_cases(tuple(reversed(cases)), 100, 17)
    assert selected != select_cases(cases, 100, 18)
    assert [case.identity for case in selected[:3]] == [
        "INVENTED-question-refusal-ae",
        "INVENTED-question-refusal-ac",
        "INVENTED-question-map-ax",
    ]
    for n in (0, 50, 101):
        with pytest.raises(ValueError, match="question_capacity"):
            select_cases(cases, n, 17)
    with pytest.raises(ValueError, match="question_identity"):
        select_cases((*cases[:-1], cases[0]), 100, 17)
    grid = coverage(selected)
    assert grid["planned_distinct_questions"] == 100
    assert grid["planned_language_executions"] == 200
    assert grid["language_executions"] == 0
    assert any(row["owner"] == "S8-T03" for row in grid["empty_cells"])
    assert all(row["count"] == 0 for row in grid["empty_cells"])


def test_accuracy_independent_expected_value_identity_and_chain_plants() -> None:
    expected = {
        "fact_id": "INVENTED-fact-a",
        "value": 4,
        "unit": "radiance_nw_cm2_sr",
        "period": "2026-03",
        "area": "INVENTED-area-a",
        "status": "OK",
    }
    observed: dict[str, Any] = {
        **expected,
        "chain": {
            key: "INVENTED"
            for key in (
                "table",
                "method",
                "version",
                "publisher",
                "dataset",
                "licence",
                "retrieved",
                "hash",
            )
        },
    }
    observed["chain"]["hash"] = "ab" * 32
    assert accuracy(observed, expected) == []
    for key, planted in (
        ("value", 7),
        ("fact_id", "INVENTED-fact-b"),
        ("unit", "count"),
        ("period", "2025"),
        ("area", "INVENTED-area-b"),
        ("status", "SUPPRESSED"),
    ):
        assert f"accuracy:{key}" in accuracy({**observed, key: planted}, expected)
    for key in observed["chain"]:
        broken = copy.deepcopy(observed)
        del broken["chain"][key]
        assert "accuracy:chain" in accuracy(broken, expected)
    assert "accuracy:property" in accuracy(
        {**observed, "prose": "invented prose"}, expected
    )


def test_wrong_target_and_applied_camera_plants() -> None:
    expected = {
        "target": "INVENTED-place-a",
        "outline": [[1, 1], [2, 2]],
        "camera": [1, 1],
        "pins": ["INVENTED-pin-a"],
        "layer": "night_lights",
    }
    assert map_behaviour(expected, expected) == []
    for key, planted in (
        ("target", "INVENTED-place-b"),
        ("camera", [2, 2]),
        ("outline", [[2, 2], [1, 1]]),
        ("pins", []),
        ("layer", "wages"),
    ):
        assert f"map:{key}" in map_behaviour({**expected, key: planted}, expected)


def test_hidden_count_json_dom_attribute_and_differencing_plants() -> None:
    assert disclosure({"status": "SUPPRESSED", "value": None}, 37) == []
    for observed in (
        {"value": 37},
        {"aria-label": "INVENTED 37"},
        {"text": "37"},
        {"total": 50, "published": 13},
        {"status": "SUPPRESSED", "value": 0},
    ):
        assert disclosure(observed, 37)


def test_monotonic_accounted_map_first_and_reset_plants() -> None:
    events = [
        ("submit", 0.0),
        ("map", 100.0),
        ("chip", 200.0),
        ("accounted", 210.0),
        ("brief", 220.0),
        ("reset", 230.0),
    ]
    assert smoothness(events) == []
    assert "smoothness:late_repaint" in smoothness([*events, ("brief", 240.0)])
    assert "smoothness:clock" in smoothness([*events, ("map", 1.0)])
    assert "smoothness:accounting" in smoothness(
        [e for e in events if e[0] != "accounted"]
    )
    swapped = [events[0], ("chip", 100.0), ("map", 200.0), *events[3:]]
    assert "smoothness:map_first" in smoothness(swapped)
    assert smoothness([])


def test_value_presence_and_interaction_budget_plants() -> None:
    checklist = {"evidence", "date", "limitation", "next_test", "source"}
    assert value(checklist, 6) == []
    assert value(checklist, 7) == ["value:actions"]
    for item in checklist:
        assert f"value:{item}" in value(checklist - {item}, 6)


def test_visual_fixture_every_proxy_has_a_plant() -> None:
    clean = {
        key: True
        for key in (
            "map_visible",
            "answer_visible",
            "no_overflow",
            "no_clipping",
            "contrast",
            "targets",
            "fonts",
            "focus",
            "legend",
            "land",
            "bottom_sheet",
            "safe_margins",
            "presenter_type",
            "pixel_baseline",
            "pixel_match",
            "unmirrored_map",
            "numeric_isolates",
            "reading_order",
        )
    }
    assert visual(clean) == []
    for key in clean:
        assert f"visual:{key}" in visual({**clean, key: False})
    assert visual({})


def test_card_parity_exact_catalogue_and_identity_plants() -> None:
    common = {
        "fact_ids": ["INVENTED-fact-a"],
        "digits": ["4"],
        "unit": "count",
        "period": "2025",
        "status": "OK",
        "coverage": "complete",
        "depth": "evidence",
    }
    en = {**common, "text": "INVENTED approved caveat", "language": "en"}
    ar = {**common, "text": "قيد مخترع", "language": "ar"}
    assert parity(en, ar, {"en": en["text"], "ar": ar["text"]}) == []
    assert "parity:ar_text" in parity(
        en, {**ar, "text": en["text"]}, {"en": en["text"], "ar": ar["text"]}
    )
    for key in common:
        assert f"parity:{key}" in parity(
            en, {**ar, key: None}, {"en": en["text"], "ar": ar["text"]}
        )


def test_seal_is_actual_denied_author_read_not_a_label(tmp_path: Path) -> None:
    author = tmp_path / "author"
    author.mkdir()
    # A real separate identity/volume is an external prerequisite; this only
    # tests the protocol. The current author can read this plant, so it fails.
    readable = author / "case"
    readable.write_text("INVENTED-seal-canary")
    assert "seal:author_readable" in seal(readable, author, "INVENTED-seal-canary")
    assert "seal:missing" in seal(author / "absent", author, "INVENTED-seal-canary")


def test_nearest_rank_percentiles_never_drop_bad_samples() -> None:
    assert percentile([5, 1, 4, 2, 3]) == {"count": 5, "p50": 3, "p95": 5, "worst": 5}
    for samples in ([], [-1], [float("nan")], [float("inf")], [True]):
        with pytest.raises(ValueError, match="timing_samples"):
            percentile(samples)


def test_command_registration_and_generated_artifact_split() -> None:
    import commands.table as table

    assert "question-lab" in table.WORDS
    assert "evals/question_lab/runs/" in (ROOT / ".gitignore").read_text()
    assert (ROOT / "AGENTS.md").read_bytes() == (ROOT / "CLAUDE.md").read_bytes()
    budgets = json.loads((ROOT / "evals/question_lab/budgets.v1.json").read_text())
    assert budgets["ratification"] == "waiting"


def test_closed_parser_does_not_start_for_malformed_or_duplicate_flags() -> None:
    from commands.question_lab import parse

    assert parse(("run", "--n", "100", "--seed", "17")) == (100, 17)
    assert parse(("run", "--seed", "17", "--n", "100")) == (100, 17)
    for args in (
        (),
        ("run",),
        ("run", "--n", "100", "--n", "100"),
        ("run", "--n", "50", "--seed", "17"),
        ("run", "--n", "100", "--seed", "-1"),
        ("run", "--n", "\u0661\u0660\u0660", "--seed", "17"),
        ("run", "--n", "100", "--seed", "17", "--skip"),
    ):
        assert parse(args) is None


def test_pre_run_budget_commit_and_unchanged_bytes_plants() -> None:
    from evals.question_lab.locks import budget_problems, compare_limits

    raw = (ROOT / "evals/question_lab/budgets.v1.json").read_bytes()
    assert "budget:uncommitted" in budget_problems(raw, committed=None)
    assert "budget:ratification_waiting" in budget_problems(raw, committed=raw)
    ratified = json.loads(raw)
    ratified.update(
        ratification="ratified",
        native_stage="INVENTED-stage",
        native_phone="INVENTED-phone",
    )
    approved = json.dumps(ratified).encode()
    assert budget_problems(approved, committed=approved) == []
    ratified["limits_ms"]["map"]["p95"] = 501
    assert "budget:changed_since_commit" in budget_problems(
        json.dumps(ratified).encode(), committed=approved
    )
    samples = {key: [1.0] * 200 for key in ratified["limits_ms"]}
    assert compare_limits(samples, approved)[1] == []
    samples["map"] = [500.0] * 200
    assert "timing:map_p95" in compare_limits(samples, approved)[1]
    samples["map"] = [1.0] * 199 + [1001.0]
    assert "timing:map_worst" in compare_limits(samples, approved)[1]
    del samples["chip"]
    assert "timing:missing_chip" in compare_limits(samples, approved)[1]
    samples["evidence_bundle"] = [1.0] * 199
    assert "timing:evidence_sample_count" in compare_limits(samples, approved)[1]


def test_loopback_denies_caught_egress_and_strips_credentials() -> None:
    from evals.question_lab.safety import child_environment, loopback_only

    env = child_environment(
        {
            "PATH": "INVENTED",
            "JEV_PRO_API_KEY": "INVENTED",
            "ANTHROPIC_API_KEY": "INVENTED",
            "EII_DECISION_PROVIDER": "jev",
        }
    )
    assert env["EII_DECISION_PROVIDER"] == "none"
    assert env["UV_OFFLINE"] == "1"
    assert not any("KEY" in key for key in env)
    attempts: list[str] = []
    with loopback_only(attempts), socket.socket() as sock:
        for method in (sock.connect, sock.connect_ex):
            with pytest.raises(PermissionError, match="non_loopback_attempt"):
                method(("192.0.2.1", 1))
        with pytest.raises(PermissionError, match="dns_attempt"):
            socket.getaddrinfo("invented.invalid", 1)
    assert attempts == ["non_loopback_attempt", "non_loopback_attempt", "dns_attempt"]


def test_packet_missing_capture_and_result_fail_closed(tmp_path: Path) -> None:
    from evals.question_lab.packet import packet_problems, write_gallery

    assert "packet:results_missing" in packet_problems(
        tmp_path, ["INVENTED-question-a"]
    )
    (tmp_path / "results.jsonl").write_text(
        json.dumps({"question_id": "INVENTED-question-a", "language": "en"}) + "\n"
    )
    assert "packet:bilingual_results" in packet_problems(
        tmp_path, ["INVENTED-question-a"]
    )
    assert "packet:captures_missing" in packet_problems(
        tmp_path, ["INVENTED-question-a"]
    )
    write_gallery(tmp_path, [])
    assert "waiting" in (tmp_path / "gallery.html").read_text()
    # A sealed capture must never enter the author gallery.
    with pytest.raises(ValueError, match="gallery_sealed"):
        write_gallery(tmp_path, [{"sealed": True, "path": "INVENTED.png"}])


def test_receipt_checks_are_five_booleans_with_separate_metadata() -> None:
    from evals.question_lab.api import receipt_problems

    checks = {
        key: True
        for key in (
            "Sources",
            "Assumptions",
            "Nothing invented",
            "Scope",
            "Limits stated",
        )
    }
    data: dict[str, Any] = {
        "Checked before display": {
            **checks,
            "assumptions": ["activity"],
            "caveat_keys": [],
            "coverage_keys": [],
        },
        "egress": [],
    }
    assert receipt_problems(data) == []
    for key in checks:
        broken = copy.deepcopy(data)
        broken["Checked before display"][key] = False
        assert receipt_problems(broken) == ["accuracy:accounting"]
    assert receipt_problems({**data, "egress": ["INVENTED"]}) == ["accuracy:accounting"]


def test_capture_prerequisites_never_download_refresh_or_start_a_browser(
    tmp_path: Path,
) -> None:
    from evals.question_lab.capture import capture_prerequisites

    assert capture_prerequisites(tmp_path, ["budget:uncommitted"]) == [
        "browser:assets_missing",
        "pixel:approved_CI_baselines_required",
        "budget:uncommitted",
    ]


def test_no_later_commit_or_ledger_rewrite_cures_a_failed_run() -> None:
    from evals.question_lab.locks import no_loosening
    from evals.question_lab.packet import ledger_problems

    raw = (ROOT / "evals/question_lab/budgets.v1.json").read_bytes()
    stricter = json.loads(raw)
    stricter["limits_ms"]["map"]["p95"] = 400
    prior = json.dumps(stricter).encode()
    assert no_loosening(prior, raw) == []
    assert no_loosening(raw, prior) == ["budget:loosened_after_run"]
    line = (
        json.dumps(
            {
                "run": "INVENTED-a",
                "status": "incomplete",
                "exit": 1,
                "previous_sha256": hashlib.sha256(b"").hexdigest(),
            }
        ).encode()
        + b"\n"
    )
    assert ledger_problems(line, committed=line) == []
    assert ledger_problems(b"", committed=line) == ["ledger:committed_prefix_changed"]
    assert ledger_problems(line.replace(b"incomplete", b"passed"), committed=line)
    assert "ledger:chain" in ledger_problems(line + line, committed=line)


@pytest.mark.parametrize(
    "name",
    [
        "../INVENTED.png",
        "/INVENTED.png",
        "https://invented.invalid/INVENTED.png",
        "%2e%2e/INVENTED.png",
        "INVENTED\\file.png",
    ],
)
def test_capture_path_cannot_become_a_gallery_egress_or_escape(
    tmp_path: Path, name: str
) -> None:
    from evals.question_lab.packet import capture_path

    with pytest.raises(ValueError, match="capture_path"):
        capture_path(tmp_path, name)


def test_udp_egress_is_denied_before_the_transport_is_called() -> None:
    from evals.question_lab.safety import loopback_only

    attempts: list[str] = []
    # The stand-in guarantees the red test cannot emit a real datagram.
    with patch.object(socket.socket, "sendto", return_value=1) as transport:
        with loopback_only(attempts), socket.socket(type=socket.SOCK_DGRAM) as sock:
            with pytest.raises(PermissionError, match="non_loopback_attempt"):
                sock.sendto(b"INVENTED", ("192.0.2.1", 1))
        transport.assert_not_called()
    assert attempts == ["non_loopback_attempt"]


def test_vectored_egress_is_denied_before_the_transport_is_called() -> None:
    from evals.question_lab.safety import loopback_only

    attempts: list[str] = []
    with patch.object(socket.socket, "sendmsg", return_value=1) as transport:
        with loopback_only(attempts), socket.socket(type=socket.SOCK_DGRAM) as sock:
            with pytest.raises(PermissionError, match="non_loopback_attempt"):
                sock.sendmsg([b"INVENTED"], [], 0, ("192.0.2.1", 1))
        transport.assert_not_called()
    assert attempts == ["non_loopback_attempt"]


@pytest.mark.parametrize("missing", ["submit", "map", "chip", "accounted", "brief"])
def test_missing_event_is_uncovered_not_a_smoothness_pass(missing: str) -> None:
    events = [
        ("submit", 0.0),
        ("map", 1.0),
        ("chip", 2.0),
        ("accounted", 3.0),
        ("brief", 4.0),
    ]
    assert f"smoothness:missing_{missing}" in smoothness(
        [event for event in events if event[0] != missing]
    )


def test_sealed_canary_in_the_author_gallery_is_a_failed_boundary(
    tmp_path: Path,
) -> None:
    canary = tmp_path / "canary"
    canary.write_text("INVENTED-sealed-marker")
    (tmp_path / "gallery.html").write_text("INVENTED-sealed-marker")
    assert "seal:exposed" in seal(canary, tmp_path, "INVENTED-sealed-marker")


def test_guard_manifest_names_negative_proofs_and_waiting_external_gates() -> None:
    manifest = json.loads((ROOT / "evals/question_lab/guards.v1.json").read_text())
    ids = [row["guard"] for row in manifest["guards"]]
    assert len(ids) == len(set(ids))
    assert {
        "invented_figure",
        "wrong_map_target",
        "hidden_count",
        "model_string",
        "held_out_exposure",
        "english_only_arabic_card",
    } <= set(ids)
    for row in manifest["guards"]:
        assert row["plant"] and row["diagnostic"]
        assert (ROOT / row["test_file"]).is_file()
        assert row["test_name"] in (ROOT / row["test_file"]).read_text()
    assert manifest["external_gates"]["held_out_identity"] == "waiting"


@pytest.mark.parametrize("limit", [True, float("nan"), float("inf")])
def test_budget_cannot_hide_a_limit_with_bool_or_nonfinite_numbers(
    limit: float | bool,
) -> None:
    from evals.question_lab.locks import budget_problems

    document = json.loads((ROOT / "evals/question_lab/budgets.v1.json").read_text())
    document.update(
        ratification="ratified",
        native_stage="INVENTED-stage",
        native_phone="INVENTED-phone",
    )
    document["limits_ms"]["map"]["p95"] = limit
    raw = json.dumps(document).encode()
    assert "budget:raised_or_invalid_limit" in budget_problems(raw, committed=raw)


def test_execution_grid_does_not_credit_a_planned_case_or_an_absent_ui_capture() -> (
    None
):
    from evals.question_lab.cases import execution_coverage

    cases = load_cases(ROOT)
    partial = [
        {
            "question_id": cases[0].identity,
            "language": "en",
            "family": cases[0].family,
            "problems": [],
            "judgements": {"accuracy": "passed:typed_api_only"},
        }
    ]
    grid = execution_coverage(cases, partial, [])
    assert grid["language_executions"] == 1
    assert grid["complete_bilingual_identities"] == 0
    assert len(grid["capture_cells"]) == 48
    assert all(row["count"] == 0 for row in grid["capture_cells"])
    assert all(row["count"] == 0 for row in grid["judgement_cells"])


def test_packet_plant_results_require_intended_failure_and_clean_control() -> None:
    from evals.question_lab.plants import plant_results

    rows = plant_results()
    assert rows
    assert len({row["guard"] for row in rows}) == len(rows)
    for row in rows:
        assert row["control_problems"] == []
        assert row["intended_diagnostic"] in row["plant_problems"]
        assert row["scope"] == "invented_oracle_fixture_not_external_evidence"
