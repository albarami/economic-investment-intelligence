"""S3-C34 plants over produced output; extend rather than rewrite pinned tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_audience_origin import REPO_ROOT, RULES_PATH, run_extractor

import check_audience_origin as checker

PRODUCED = ("screen", "accessible", "url", "template", "catalogue")
LABELS = {
    "en": ("Simulated workers present", "en.simulated"),
    "ar": ("عمالة بالمحاكاة", "ar.simulated.with"),
}


@pytest.fixture(scope="module")
def produced() -> dict[str, Any]:
    return checker.merge_evidence(
        run_extractor(REPO_ROOT), checker.collect_product_evidence(REPO_ROOT)
    )


@pytest.mark.parametrize("output_class", PRODUCED)
@pytest.mark.parametrize("language", ("en", "ar"))
def test_s3_produced_output_plant_has_exact_reason(
    produced: dict[str, Any],
    output_class: str,
    language: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rules = checker.load_rules(RULES_PATH)
    assert checker.check_evidence(produced, rules)["ok"]
    planted = copy.deepcopy(produced)
    # URLs are language-neutral paths in this tree. Plant each language in an
    # actual URL item rather than inventing a language-specific URL producer.
    surface, entry = next(
        (surface, entry)
        for surface in planted["surfaces"]
        for entry in surface["items"]
        if entry["output_class"] == output_class
        and entry["field_kind"] != "backend"
        and (output_class == "url" or entry["language"] == language)
    )
    label, reason = LABELS[language]
    entry["text"] = (
        f"/evidence?label={quote(label)}" if output_class == "url" else label
    )
    report = checker.check_evidence(planted, rules)
    assert not report["ok"]
    assert [
        (f["where"], f["verdict"], f["detail"]) for f in report["groups"]["audience"]
    ] == [(f"{surface['id']}:{output_class}:{entry['field']}", "violation", reason)]
    assert all(
        not report["groups"][group] for group in ("extraction", "backend", "method")
    )
    evidence_file = tmp_path / "audience.json"
    evidence_file.write_text(json.dumps(planted), encoding="utf-8")
    assert checker.main(["--evidence", str(evidence_file)]) == 1
    assert f": {reason} " in capsys.readouterr().out


@given(
    output_class=st.sampled_from(PRODUCED),
    language=st.sampled_from(("en", "ar")),
    boundary=st.text(alphabet=" -_:;()[]\n", max_size=20),
    repetitions=st.integers(min_value=1, max_value=4),
)
def test_s3_origin_detection_survives_boundaries_and_duplicates(
    output_class: str, language: str, boundary: str, repetitions: int
) -> None:
    from test_audience_origin import evidence, item, real_rules

    label, reason = LABELS[language]
    text = boundary + label + boundary
    kind = "accessible" if output_class == "accessible" else "copy"
    if output_class == "url":
        kind, text = "url", f"/evidence?label={quote(text)}"
    entries = [item(text, output_class, language, field_kind=kind)] * repetitions
    report = checker.check_evidence(evidence(*entries), real_rules())
    assert not report["ok"]
    assert [finding["detail"] for finding in report["groups"]["audience"]] == [
        reason
    ] * repetitions


@pytest.mark.parametrize("language", ("en", "ar"))
@pytest.mark.parametrize(
    "output_class", ("screen", "split-screen", "accessible", "url")
)
def test_s3_built_output_extraction_plant(
    tmp_path: Path, language: str, output_class: str
) -> None:
    label, reason = LABELS[language]
    document = (REPO_ROOT / "web/dist/index.html").read_text(encoding="utf-8")
    payload = {
        "screen": f"<p>{label}</p>",
        "split-screen": f"<p>{label[:2]}<b>{label[2:]}</b></p>",
        "accessible": f'<span aria-label="{label}"></span>',
        "url": f'<a href="/evidence?label={quote(label)}"></a>',
    }[output_class]
    document = document.replace("</body>", f"{payload}</body>")
    built = tmp_path / "web/dist/index.html"
    built.parent.mkdir(parents=True)
    built.write_text(document, encoding="utf-8")
    extracted = run_extractor(tmp_path)
    # Other producers remain the real extraction; replace only the three
    # built-document surfaces with the extractor's planted document results.
    merged = checker.merge_evidence(
        run_extractor(REPO_ROOT), checker.collect_product_evidence(REPO_ROOT)
    )
    for surface in merged["surfaces"]:
        if surface["id"] in ("web.dist.document", "web.dist.accessible", "web.urls"):
            replacement = next(
                s for s in extracted["surfaces"] if s["id"] == surface["id"]
            )
            surface["items"] = replacement["items"]
    report = checker.check_evidence(merged, checker.load_rules(RULES_PATH))
    assert not report["ok"]
    assert report["groups"]["audience"]
    assert {finding["detail"] for finding in report["groups"]["audience"]} == {reason}
    assert all(
        not report["groups"][group] for group in ("extraction", "backend", "method")
    )


def test_s3_produced_outputs_absence(produced: dict[str, Any]) -> None:
    assert checker.check_evidence(produced, checker.load_rules(RULES_PATH))["ok"]
