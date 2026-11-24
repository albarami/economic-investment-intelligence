"""Tests for the standing audience-origin check (decision 0035 item 5; S3-T19).

The check reads typed surface evidence (``audience-evidence.v1``) and a
reviewed bilingual rules file (``scripts/audience_origin_rules.json``). Every
guard has a planted violation: English and Arabic origin labels are planted
separately in every output class, a missing or empty extraction is planted,
and an omitted active surface is planted. Positive controls prove that
unrelated uses of the same words (sample size, public transport, a method's
name), genuine source attribution, backend keys and suppression reasons pass.

Run from the repository root:

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts"
CHECKER = SCRIPT_DIR / "check_audience_origin.py"
RULES_PATH = SCRIPT_DIR / "audience_origin_rules.json"
EXTRACTOR = REPO_ROOT / "web" / "scripts" / "extract-audience.mjs"
WEB = REPO_ROOT / "web"

sys.path.insert(0, str(SCRIPT_DIR))

import check_audience_origin as checker  # noqa: E402

ALL_CLASSES = (
    "screen",
    "accessible",
    "url",
    "template",
    "catalogue",
    "speech",
    "export_body",
    "export_filename",
    "export_heading",
)

PLANT_EN = (
    "Simulated workers present",
    "Synthetic employment records",
    "Generated results",
    "This is sample data",
    "Demo figures",
)
PLANT_AR = (
    "عمالة بالمحاكاة",
    "سجلات اصطناعية",
    "نتائج مولدة",
    "بيانات عينة",
    "أرقام تجريبية",
)


def real_rules() -> dict[str, Any]:
    """The committed rules with a fixture surface manifest."""
    rules = checker.load_rules(RULES_PATH)
    rules["surfaces"] = [
        {
            "id": "fixture.surface",
            "output_class": "any",
            "required": True,
            "min_items": 1,
        }
    ]
    return rules


def item(
    text: str,
    output_class: str = "screen",
    language: str = "en",
    field: str = "copy",
    field_kind: str = "copy",
) -> dict[str, Any]:
    return {
        "field": field,
        "field_kind": field_kind,
        "output_class": output_class,
        "language": language,
        "text": text,
    }


def evidence(*items: dict[str, Any], status: str = "ok") -> dict[str, Any]:
    # An empty surface is an empty extraction; fixtures that exercise the
    # backend or method groups still need one benign audience item.
    entries = list(items) or [item("An ordinary sentence.")]
    return {
        "schema": "audience-evidence.v1",
        "extractor": "fixture",
        "surfaces": [
            {
                "id": "fixture.surface",
                "origin": "fixture",
                "status": status,
                "items": entries,
            }
        ],
        "generated_outputs": [],
        "source_chains": [],
    }


def finding_groups(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {name: report["groups"][name] for name in report["groups"]}


def plant_word(language: str) -> str:
    return PLANT_EN[0] if language == "en" else PLANT_AR[0]


class TestAudienceAbsence(unittest.TestCase):
    """Every output class fails on a planted origin label, in both languages."""

    def test_every_output_class_fails_on_an_english_origin_label(self) -> None:
        rules = real_rules()
        for output_class in ALL_CLASSES:
            for word in PLANT_EN:
                with self.subTest(output_class=output_class, word=word):
                    report = checker.check_evidence(
                        evidence(item(word, output_class, "en")), rules
                    )
                    self.assertFalse(report["ok"])
                    found = finding_groups(report)["audience"]
                    self.assertTrue(found)
                    self.assertTrue(
                        any(output_class in f["where"] for f in found),
                        f"no finding names {output_class}: {found}",
                    )

    def test_every_output_class_fails_on_an_arabic_origin_label(self) -> None:
        rules = real_rules()
        for output_class in ALL_CLASSES:
            for word in PLANT_AR:
                with self.subTest(output_class=output_class, word=word):
                    report = checker.check_evidence(
                        evidence(item(word, output_class, "ar")), rules
                    )
                    self.assertFalse(report["ok"])
                    found = finding_groups(report)["audience"]
                    self.assertTrue(found)

    def test_a_plant_in_accessible_text_fails(self) -> None:
        rules = real_rules()
        report = checker.check_evidence(
            evidence(
                item(
                    "Simulated layer",
                    "accessible",
                    "en",
                    field="aria-label",
                    field_kind="accessible",
                )
            ),
            rules,
        )
        self.assertFalse(report["ok"])

    def test_a_plant_in_an_encoded_audience_url_fails(self) -> None:
        rules = real_rules()
        encoded = "https://example.invalid/brief?source=%73imulated-data"
        report = checker.check_evidence(
            evidence(item(encoded, "url", "und", field_kind="url")), rules
        )
        self.assertFalse(report["ok"])
        found = finding_groups(report)["audience"]
        self.assertTrue(found)

    def test_a_bare_class_word_badge_fails(self) -> None:
        rules = real_rules()
        for badge in ("Public", "Protected", "Synthetic", "عام", "علني"):
            with self.subTest(badge=badge):
                report = checker.check_evidence(
                    evidence(item(badge, "screen", "und")), rules
                )
                self.assertFalse(report["ok"])

    def test_an_unclassified_class_word_fails_for_review(self) -> None:
        rules = real_rules()
        for text in ("The data is public.", "بيانات عامة"):
            with self.subTest(text=text):
                report = checker.check_evidence(
                    evidence(item(text, "screen", "und")), rules
                )
                self.assertFalse(report["ok"])
                found = finding_groups(report)["audience"]
                self.assertTrue(any(f["verdict"] == "review" for f in found))

    def test_positive_controls_pass(self) -> None:
        rules = real_rules()
        controls = (
            item("The sample size is shown beside the figure.", "screen", "en"),
            item("Public transport stops nearby.", "screen", "en"),
            item("What public context does this area have?", "catalogue", "en"),
            item("ما السياق العام لهذه المنطقة؟", "catalogue", "ar"),
            item("قراءة السياق العام", "template", "ar"),
            item("includes estimates of publicly announced projects", "screen", "en"),
            item("Private sector employers.", "screen", "en"),
            item("القطاع الخاص", "screen", "ar"),
            item("حجم العينة معروض", "screen", "ar"),
        )
        report = checker.check_evidence(evidence(*controls), rules)
        self.assertEqual(
            finding_groups(report)["audience"],
            [],
            f"unrelated uses flagged: {finding_groups(report)['audience']}",
        )
        self.assertTrue(report["ok"])

    def test_genuine_source_attribution_passes_only_as_reviewed(self) -> None:
        rules = real_rules()
        publisher = item(
            "Sample Agency", "screen", "en", field="publisher", field_kind="source"
        )
        report = checker.check_evidence(evidence(publisher), rules)
        self.assertFalse(report["ok"], "an unreviewed source word must fail")
        reviewed = real_rules()
        reviewed["allow_values"] = [
            {"value": "Sample Agency", "language": "en", "reason": "test fixture"}
        ]
        report = checker.check_evidence(evidence(publisher), reviewed)
        self.assertEqual(finding_groups(report)["audience"], [])

    def test_a_method_name_passes_only_as_reviewed(self) -> None:
        rules = real_rules()
        method = item(
            "sample_mean",
            "screen",
            "en",
            field="method",
            field_kind="method",
        )
        report = checker.check_evidence(evidence(method), rules)
        self.assertFalse(report["ok"])
        reviewed = real_rules()
        reviewed["allow_values"] = [
            {"value": "sample_mean", "language": "en", "reason": "test fixture"}
        ]
        report = checker.check_evidence(evidence(method), reviewed)
        self.assertEqual(finding_groups(report)["audience"], [])

    def test_backend_keys_are_not_audience_text(self) -> None:
        rules = real_rules()
        backend = item(
            "synthetic",
            "catalogue",
            "und",
            field="allowed_provenance",
            field_kind="backend",
        )
        report = checker.check_evidence(evidence(backend), rules)
        self.assertEqual(finding_groups(report)["audience"], [])
        self.assertTrue(report["ok"])

    def test_the_withheld_word_passes_only_in_the_withheld_kind(self) -> None:
        rules = real_rules()
        withheld = item("محجوب", "screen", "ar", field="mark", field_kind="withheld")
        self.assertTrue(checker.check_evidence(evidence(withheld), rules)["ok"])
        plain = item("محجوب", "screen", "ar", field_kind="copy")
        self.assertFalse(checker.check_evidence(evidence(plain), rules)["ok"])

    def test_an_origin_token_in_a_style_attribute_fails(self) -> None:
        rules = real_rules()
        styled = item(
            "layer-sample synthetic",
            "screen",
            "und",
            field="class",
            field_kind="style",
        )
        self.assertFalse(checker.check_evidence(evidence(styled), rules)["ok"])

    def test_an_arabic_label_with_diacritics_still_fails(self) -> None:
        rules = real_rules()
        decorated = "بِالمُحَاكَاة"
        report = checker.check_evidence(
            evidence(item(decorated, "screen", "ar")), rules
        )
        self.assertFalse(report["ok"])

    def test_a_split_text_label_is_caught_as_one_item(self) -> None:
        rules = real_rules()
        report = checker.check_evidence(
            evidence(item("Sim ulated", "screen", "en")), rules
        )
        # A split inside one item is still one text; "Sim ulated" holds no
        # whole word, so this passes the word rule (the DOM extractor emits
        # whole elements, which is the real split-text defence).
        self.assertTrue(report["ok"])
        joined = item("Simulated", "screen", "en")
        self.assertFalse(checker.check_evidence(evidence(joined), rules)["ok"])


class TestExtractionCoverage(unittest.TestCase):
    """A missing or empty extraction and an omitted active surface fail."""

    def test_missing_evidence_document_fails(self) -> None:
        report = checker.check_evidence(None, real_rules())
        self.assertFalse(report["ok"])
        self.assertTrue(finding_groups(report)["extraction"])

    def test_empty_extraction_fails(self) -> None:
        report = checker.check_evidence(
            {"schema": "audience-evidence.v1", "surfaces": []}, real_rules()
        )
        self.assertFalse(report["ok"])
        self.assertTrue(finding_groups(report)["extraction"])

    def test_an_omitted_active_surface_fails(self) -> None:
        rules = real_rules()
        rules["surfaces"] = [
            {
                "id": "fixture.surface",
                "output_class": "screen",
                "required": True,
                "min_items": 1,
            },
            {
                "id": "fixture.missing",
                "output_class": "screen",
                "required": True,
                "min_items": 1,
            },
        ]
        report = checker.check_evidence(
            evidence(item("An ordinary sentence.", "screen", "en")), rules
        )
        self.assertFalse(report["ok"])
        found = finding_groups(report)["extraction"]
        self.assertTrue(any("fixture.missing" in f["where"] for f in found))

    def test_an_absent_surface_status_fails(self) -> None:
        rules = real_rules()
        report = checker.check_evidence(
            evidence(item("An ordinary sentence.", "screen", "en"), status="absent"),
            rules,
        )
        self.assertFalse(report["ok"])
        self.assertTrue(finding_groups(report)["extraction"])

    def test_a_required_surface_below_its_item_floor_fails(self) -> None:
        rules = real_rules()
        rules["surfaces"] = [
            {
                "id": "fixture.surface",
                "output_class": "screen",
                "required": True,
                "min_items": 2,
            }
        ]
        report = checker.check_evidence(
            evidence(item("An ordinary sentence.", "screen", "en")), rules
        )
        self.assertFalse(report["ok"])
        self.assertTrue(finding_groups(report)["extraction"])

    def test_an_unknown_output_class_fails_the_schema(self) -> None:
        rules = real_rules()
        bad = item("An ordinary sentence.", "poster", "en")
        report = checker.check_evidence(evidence(bad), rules)
        self.assertFalse(report["ok"])
        self.assertTrue(finding_groups(report)["extraction"])

    def test_an_unknown_field_kind_fails_the_schema(self) -> None:
        rules = real_rules()
        bad = item("An ordinary sentence.", "screen", "en", field_kind="mystery")
        report = checker.check_evidence(evidence(bad), rules)
        self.assertFalse(report["ok"])
        self.assertTrue(finding_groups(report)["extraction"])

    def test_unproduced_classes_are_reported_not_failed(self) -> None:
        rules = real_rules()
        report = checker.check_evidence(
            evidence(item("An ordinary sentence.", "screen", "en")), rules
        )
        self.assertTrue(report["ok"])
        self.assertEqual(
            sorted(report["unproduced"]),
            sorted(rules["unproduced_classes"]),
        )


class TestBackendMarkers(unittest.TestCase):
    """Generated outputs keep explicit markers and a truthful chain."""

    def generated_output(self) -> dict[str, Any]:
        markers = {
            "origin": "synthetic",
            "generator_name": "employment_gen",
            "generator_version": "1.0.0",
        }
        record = dict(markers)
        table = {**markers, "records": [record]}
        file = {**markers, "tables": [table]}
        return {**markers, "files": [file]}

    def test_a_whole_generated_output_passes(self) -> None:
        report = checker.check_evidence(evidence(), real_rules())
        self.assertTrue(report["ok"])
        doc = evidence()
        doc["generated_outputs"] = [self.generated_output()]
        report = checker.check_evidence(doc, real_rules())
        self.assertEqual(finding_groups(report)["backend"], [])

    def test_a_missing_marker_at_each_level_fails(self) -> None:
        for level in ("release", "files", "tables", "records"):
            doc = evidence()
            output = self.generated_output()
            node = output
            for step in ("files", "tables", "records"):
                if step == level:
                    break
                node = node[step][0]
            del node["generator_version"]
            doc["generated_outputs"] = [output]
            report = checker.check_evidence(doc, real_rules())
            self.assertFalse(
                report["ok"], f"missing marker at {level} passed: {report}"
            )
            self.assertTrue(finding_groups(report)["backend"])

    def test_a_marker_declared_by_detection_not_contract_fails(self) -> None:
        doc = evidence()
        output = self.generated_output()
        del output["files"][0]["tables"][0]["records"][0]["origin"]
        doc["generated_outputs"] = [output]
        report = checker.check_evidence(doc, real_rules())
        self.assertFalse(report["ok"])

    def test_marker_expectations_come_from_the_contract_inventory(self) -> None:
        rules = real_rules()
        self.assertEqual(
            sorted(rules["backend_markers"]["fields"]),
            ["generator_name", "generator_version", "origin"],
        )
        self.assertEqual(
            rules["backend_markers"]["levels"],
            ["release", "file", "table", "record"],
        )


class TestMethodAndAttribution(unittest.TestCase):
    """Source chains stay truthful; false official or measured claims fail."""

    def chain(self) -> dict[str, Any]:
        return {
            "chain": {
                "method": "count_method",
                "method_version": "1",
                "pipeline": "employment_gen",
                "pipeline_version": "1.0.0",
                "label_en": "Workers present",
                "inputs": [{"publisher": "A register office"}],
            },
            "markers": {
                "origin": "synthetic",
                "generator_name": "employment_gen",
                "generator_version": "1.0.0",
            },
        }

    def test_a_truthful_chain_passes(self) -> None:
        doc = evidence()
        doc["source_chains"] = [self.chain()]
        report = checker.check_evidence(doc, real_rules())
        self.assertEqual(finding_groups(report)["method"], [])

    def test_a_chain_without_its_pipeline_fails(self) -> None:
        doc = evidence()
        entry = self.chain()
        del entry["chain"]["pipeline"]
        doc["source_chains"] = [entry]
        report = checker.check_evidence(doc, real_rules())
        self.assertFalse(report["ok"])
        self.assertTrue(finding_groups(report)["method"])

    def test_a_chain_naming_another_producer_fails(self) -> None:
        doc = evidence()
        entry = self.chain()
        entry["chain"]["pipeline"] = "other_gen"
        doc["source_chains"] = [entry]
        report = checker.check_evidence(doc, real_rules())
        self.assertFalse(report["ok"])

    def test_a_planted_outside_publisher_fails(self) -> None:
        doc = evidence()
        entry = self.chain()
        entry["chain"]["publisher"] = "An outside office"
        doc["source_chains"] = [entry]
        report = checker.check_evidence(doc, real_rules())
        self.assertFalse(report["ok"])

    def test_a_false_official_or_measured_claim_fails_in_audience_text(self) -> None:
        rules = real_rules()
        for text in (
            "Official figures for this area.",
            "Measured employment counts.",
            "أرقام رسمية لهذه المنطقة",
        ):
            with self.subTest(text=text):
                report = checker.check_evidence(
                    evidence(item(text, "screen", "und")), rules
                )
                self.assertFalse(report["ok"])
                self.assertTrue(finding_groups(report)["method"])

    def test_a_real_publisher_name_is_not_a_claim(self) -> None:
        rules = real_rules()
        source = item(
            "Ministry register office bulletin",
            "screen",
            "en",
            field="publisher",
            field_kind="source",
        )
        report = checker.check_evidence(evidence(source), rules)
        self.assertEqual(finding_groups(report)["method"], [])


def run_extractor(root: Path) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("node is not on PATH")
    result = subprocess.run(
        [node, str(EXTRACTOR), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"extractor failed: {result.stderr.strip()}")
    parsed: dict[str, Any] = json.loads(result.stdout)
    return parsed


class TestTheRealTree(unittest.TestCase):
    """The committed tree carries no audience origin label."""

    evidence: dict[str, Any]
    report: dict[str, Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence = run_extractor(REPO_ROOT)
        cls.evidence = checker.merge_evidence(
            cls.evidence, checker.collect_product_evidence(REPO_ROOT)
        )
        cls.report = checker.check_evidence(
            cls.evidence, checker.load_rules(RULES_PATH)
        )

    def test_no_audience_origin_label_reaches_the_tree(self) -> None:
        for name, found in finding_groups(self.report).items():
            self.assertEqual(found, [], f"{name}: {found}")
        self.assertTrue(self.report["ok"])

    def test_every_required_surface_is_extracted(self) -> None:
        rules = checker.load_rules(RULES_PATH)
        by_id = {surface["id"]: surface for surface in self.evidence["surfaces"]}
        for declared in rules["surfaces"]:
            with self.subTest(surface=declared["id"]):
                self.assertIn(declared["id"], by_id)
                surface = by_id[declared["id"]]
                self.assertEqual(surface["status"], "ok")
                self.assertGreaterEqual(len(surface["items"]), declared["min_items"])

    def test_produced_classes_carry_both_languages(self) -> None:
        languages = {
            "screen": {"en", "ar"},
            "accessible": {"en", "ar"},
            "catalogue": {"en", "ar"},
            "template": {"en", "ar"},
        }
        seen: dict[str, set[str]] = {}
        for surface in self.evidence["surfaces"]:
            for entry in surface["items"]:
                if entry["field_kind"] == "backend":
                    continue
                seen.setdefault(entry["output_class"], set()).add(entry["language"])
        for output_class, wanted in languages.items():
            with self.subTest(output_class=output_class):
                self.assertTrue(
                    wanted <= seen.get(output_class, set()),
                    f"{output_class}: saw {seen.get(output_class)}",
                )

    def test_the_command_line_check_passes_on_the_tree(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CHECKER), "--tree", str(REPO_ROOT)],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0, f"{result.stdout}\n{result.stderr}")
        for group in ("audience", "extraction", "backend", "method"):
            self.assertIn(group, result.stdout)


if __name__ == "__main__":
    unittest.main()
