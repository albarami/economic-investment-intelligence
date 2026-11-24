"""Audience-origin change-set control pin (S3-B1; OPEN_ITEMS.md PO-S3-R5-1).

The closed audience-origin change set is the eight paths of the five S3-T19
commits (PROGRESS.md "S3 closure package R4"). The decision 0035 pin of
`test_decision_0035_controls.py` already stores part of what these paths
declare. This module stores exactly the rest and reuses that pin's walker
helpers and canonical form by import. It adds no threshold: each entry is the
digest of what this checkout declares, at its document anchor.

What each path adds to the existing pin:
- `PROGRESS.md`: the S3-T19 evidence section (AGENTS.md rules 36 and 38).
- document 12: the decision 0035 section, the test map of section 2 (each
  test kind's gate cadence), section 4 (the CI pipeline) and every TST row
  the existing pin does not quote (privacy property tests, attack suite).
- document 15: the decision 0035 section, section 1 (rules of the review),
  every REV row, the "Standing audience-origin check" section and its rule
  lines (below) outside those sections.
- `scripts/audience_origin_rules.json`: every key, term entry, surface entry
  and backend-marker key the existing projection does not read.
- `scripts/check_audience_origin.py`: every top-level declaration except
  `GROUPS`, which the existing pin stores whole (the existing pin stores the
  `ok` expression of `_report`, not the bodies of the enforcing functions).
- `scripts/tests/test_audience_origin.py`: every top-level declaration (the
  planted violations of the check; rules 12 and 37).
- `web/scripts/extract-audience.mjs` and its node test: the code with line
  comments removed and whitespace collapsed.

S3-T18's own change set (ruling L-1518) is the 24 paths of its five commits.
`T18_PATHS` are the twenty that state or invoke a control; `T18_NO_CONTROL`
lists the other four with the reason. Documents 09 and 10 are pinned on their
decision 0035 section and on every table row that cites decision 0035 or says
"origin word or texture" (FE-48, the section 6 layer rows, AI-34 and the
rest). Their rule lines are every other line outside that section, except the
status row, that names decision 0035, an origin word, mark, strip, label,
texture or watermark, or a class word, in any case and number, each with its
own digest (review cf1); a line break inside such a line changes the pin. For
the web sources the `_js` reader splits a file into its top-level declarations
(the walker reads Python only); web tests and the visual harness are digested
whole, as the extractor's node test is.

Python digests drop docstrings and formatting; Markdown digests collapse
whitespace. Retired rule spellings and origin-label wording are stored only as
digests, as in the existing pin.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import test_decision_0035_controls as base
from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = base.ROOT
PIN = Path(__file__).resolve().parent / "fixtures" / "audience_origin_control_pin.json"

PROGRESS = "PROGRESS.md"
DOC12 = base.DOC12
DOC15 = "docs/15_REVIEWER_CHECKLIST.md"
AUDIENCE = base.AUDIENCE
CHECKER = base.CHECKER
AUDIENCE_TEST = "scripts/tests/test_audience_origin.py"
EXTRACTOR = "web/scripts/extract-audience.mjs"
EXTRACTOR_TEST = "web/scripts/tests/extract-audience.node-test.mjs"
T19_PATHS = (
    PROGRESS,
    DOC12,
    DOC15,
    AUDIENCE,
    CHECKER,
    AUDIENCE_TEST,
    EXTRACTOR,
    EXTRACTOR_TEST,
)

OPEN_ITEMS = "OPEN_ITEMS.md"
DOC09 = "docs/09_AI_ASSISTANT.md"
DOC10 = "docs/10_FRONTEND.md"
BACKEND = base.BACKEND
BACKEND_TEST = "product/tests/test_backend_origin.py"
CHECK_ANSWER = "web/scripts/check-answer.mjs"
CHECK_ANSWER_TEST = "web/scripts/tests/check-answer.node-test.mjs"
MARK = "web/src/facts/ProvenanceMark.tsx"
DRAWER = "web/src/facts/SourceChainDrawer.tsx"
PUBLIC_LAYERS = "web/src/stage/layers/PublicLayers.tsx"
LAYER_CHECKS = "web/src/stage/layers/checks.ts"
LEGEND = "web/src/stage/layers/legend.ts"
ANSWER_SPEC = "web/tests/audit/answer.spec.ts"
ORIGIN_TEST = "web/tests/component/audience-origin.test.tsx"
CHAIN_TEST = "web/tests/component/chain.test.tsx"
LAYERS_COMPONENT_TEST = "web/tests/component/layers.test.tsx"
ORIGIN_FIXTURE = "web/tests/fixtures/audience-origin.ts"
LAYERS_UNIT_TEST = "web/tests/unit/layers.test.ts"
VISUAL_HARNESS = "web/tests/visual/harness.tsx"
# `git show --format= --name-only` of the five S3-T18 commits daca0266f3,
# 9669f2f0cf, 7eb51781d4, 232135908a and f127865dcb gives 24 paths.
T18_PATHS = (
    PROGRESS,
    OPEN_ITEMS,
    DOC09,
    DOC10,
    BACKEND,
    BACKEND_TEST,
    CHECK_ANSWER,
    CHECK_ANSWER_TEST,
    MARK,
    DRAWER,
    PUBLIC_LAYERS,
    LAYER_CHECKS,
    LEGEND,
    ANSWER_SPEC,
    ORIGIN_TEST,
    CHAIN_TEST,
    LAYERS_COMPONENT_TEST,
    ORIGIN_FIXTURE,
    LAYERS_UNIT_TEST,
    VISUAL_HARNESS,
)
T18_NO_CONTROL = {
    "web/src/i18n/ar.json": "catalogue text the checks scan; holds no rule",
    "web/src/i18n/en.json": "catalogue text the checks scan; holds no rule",
    "web/src/stage/layers/FdiPanel.tsx": "S3-T18 only removed two marks; "
    "it invokes no privacy rule, gate or guard",
    "web/src/styles/answer.css": "style rules the checks scan; holds no rule",
}
PATHS = tuple(dict.fromkeys(T19_PATHS + T18_PATHS))

D0035 = "## Audience text and backend origin — decision 0035"
IN_BRIEF = "## In brief"
TEST_MAP = "| Test kind | Plane | What it proves | Tool | Runs |"
CI_PIPELINE = "## 4. The CI pipeline"
REVIEW_RULES = "## 1. Rules of the review"
GENERAL_CHECKS = "## 2. General checks"
STANDING = "## Standing audience-origin check — decision 0035"
SOURCES = "## Sources"
T19_SECTION = "## S3-T19 — Script the standing audience-origin check (build)"
T18_SECTIONS = {
    "s3_t18_build": "## S3-T18 — Remove audience origin marks from the map "
    "foundation (build)",
    "s3_t18_oi349_size": "## S3-T18 — the size test waits for the drawer to "
    "come to rest (OI-349), 2026-11-20",
    "s3_t18_oi349_round1": "## S3-T18 — the drawer-rest wait also covers the "
    "two early drawer measurements (OI-349, review round 1), 2026-11-20",
    "s3_t18_oi349_round2": "## S3-T18 — the drawer-rest wait before the planted "
    "wrong-side poll (OI-349, review round 2), 2026-11-20",
}
OI349 = "### OI-349 — S3-T18: the size test measured the answer drawer during its slide"
DOC10_SECTION = "## S3-T18 audience origin removal"
# A table row citing decision 0035 or saying "origin word or texture", keyed by
# its first cell; the status row changes at every amendment and is left out.
_CITED = re.compile(
    r"\| ((?!Status \|)[^|]+?) \|(?=.*(?:decision 0035|origin word or texture))"
)
# A line naming the decision or an origin word, mark, strip, label, texture or
# watermark or a class word, in any case; a search also finds each plural
# (review cf1).
_RULE_WORDS = re.compile(
    r"decision 0035|origin (?:word|mark|strip|label|texture|watermark)|class word",
    re.IGNORECASE,
)
_STATUS_ROW = "| Status |"
_TEXTURES = re.compile(r"\*\*(Provenance textures)\.\*\*")
_STATUS = "- Status:"
_JS_DECL = re.compile(
    r"(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\*?|const|let|var|type|interface|class|enum)\s+([A-Za-z_$][\w$]*)"
)
_REV = re.compile(r"\| (REV-\d+) \|")
# Keys `base._audience_rules` reads whole; every other key is pinned here.
_PROJECTED = frozenset(
    {
        "surfaces",
        "output_classes",
        "unproduced_classes",
        "field_kinds",
        "scan_kinds",
        "claim_scan_kinds",
        "backend_markers",
        "badge_exempt_kinds",
        "allow_values",
        "terms",
    }
)
_MARKERS_PROJECTED = frozenset({"levels", "fields", "generated_values"})
_CHECKER_PINNED = frozenset({"GROUPS"})
# Names whose value or source `base._backend` stores whole; the three marker
# key names reach that pin through the value of `MARKER_KEYS`.
_BACKEND_PINNED = frozenset(
    {
        "LEVELS",
        "MARKER_KEYS",
        "GENERATED_ORIGINS",
        "CHILDREN",
        "DISPLAY_KEYS",
        "REFUSAL_CODES",
        "ORIGIN_KEY",
        "GENERATOR_NAME_KEY",
        "GENERATOR_VERSION_KEY",
        *base.CLAIM_DECLS,
    }
)


def _hash(text: str) -> str:
    # The "sha256:" prefix keeps a stored digest from reading as a credential to the
    # history secret scan (the pin's keys are document labels such as "API").
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _text_hash(text: str) -> str:
    return _hash(base._collapse(text))


def _value_hash(value: object) -> str:
    return _hash(base._canon(value))


def _section(text: str, start: str, end: str) -> str:
    return _text_hash(base._slice(text, start, end))


def _rows(text: str, pattern: re.Pattern[str], what: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        if match.group(1) in found:
            raise base.ExtractionFailure(f"duplicate {what} {match.group(1)}")
        found[match.group(1)] = _text_hash(line)
    if not found:
        raise base.ExtractionFailure(f"no {what} rows")
    return found


def _pinned_tst() -> set[str]:
    """TST labels whose bodies the decision 0035 pin already stores."""
    gates = base._as_dict(base._pin()["gates"])
    return set(base._as_dict(gates["assertions"]))


def _doc12(text: str) -> dict[str, Any]:
    pinned = _pinned_tst()
    tst = {
        label: _hash(body)
        for label, body in base._definitions(text).values()
        if label not in pinned
    }
    return {
        "decision_0035": _section(text, D0035, IN_BRIEF),
        "test_map": {row[0]: _value_hash(row) for row in base._table(text, TEST_MAP)},
        "ci_pipeline": _section(text, CI_PIPELINE, base.SECTION_5),
        "tst_rows": tst,
    }


def _doc15(text: str) -> dict[str, Any]:
    return {
        "decision_0035": _section(text, D0035, IN_BRIEF),
        "review_rules": _section(text, REVIEW_RULES, GENERAL_CHECKS),
        "rev_rows": _rows(text, _REV, "REV"),
        "standing_check": _section(text, STANDING, SOURCES),
        "rule_lines": _rule_lines(
            text,
            ((D0035, IN_BRIEF), (REVIEW_RULES, GENERAL_CHECKS), (STANDING, SOURCES)),
        ),
    }


def _entries(raw: object, what: str) -> dict[str, str]:
    if not isinstance(raw, list):
        raise base.ExtractionFailure(what)
    found: dict[str, str] = {}
    for entry in raw:
        ident = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(ident, str):
            raise base.ExtractionFailure(f"{what} id")
        if ident in found:
            raise base.ExtractionFailure(f"duplicate {what} {ident}")
        found[ident] = _value_hash(entry)
    return found


def _rules(text: str) -> dict[str, Any]:
    base._audience_rules(text)
    raw = json.loads(text)
    markers = raw["backend_markers"]
    return {
        "keys": {
            key: _value_hash(value)
            for key, value in raw.items()
            if key not in _PROJECTED
        },
        "terms": _entries(raw["terms"], "term"),
        "surfaces": _entries(raw["surfaces"], "surface"),
        "backend_markers": {
            key: _value_hash(value)
            for key, value in markers.items()
            if key not in _MARKERS_PROJECTED
        },
    }


def _strip_docstring(node: ast.AST) -> None:
    body = getattr(node, "body", None)
    if not isinstance(body, list):
        return
    first = body[0] if body else None
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        body.pop(0)


def _statement_name(node: ast.stmt, index: int) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    simple = base._simple(node)
    if simple is not None:
        return simple[0]
    return f"statement {index}"


def _python(text: str, skip: frozenset[str] = frozenset()) -> dict[str, str]:
    tree = ast.parse(text)
    for node in ast.walk(tree):
        _strip_docstring(node)
    found: dict[str, str] = {}
    for index, node in enumerate(tree.body):
        name = _statement_name(node, index)
        if name in skip:
            continue
        if name in found:
            raise base.ExtractionFailure(f"duplicate declaration {name}")
        found[name] = _hash(ast.dump(node, include_attributes=False))
    return found


def _script(text: str) -> str:
    code = [line for line in text.splitlines() if not line.lstrip().startswith("//")]
    return _text_hash("\n".join(code))


def _heading_section(text: str, heading: str) -> list[str]:
    """The lines under `heading`, up to the next heading."""
    base._one(text, heading)
    lines = text.split(heading, 1)[1].splitlines()
    end = next(
        (index for index, line in enumerate(lines) if line.startswith("#")),
        len(lines),
    )
    return lines[:end]


def _progress(text: str) -> dict[str, str]:
    """The S3-T19 section and the four S3-T18 sections."""
    found = {
        "s3_t19_evidence": _text_hash("\n".join(_heading_section(text, T19_SECTION)))
    }
    for key, heading in T18_SECTIONS.items():
        found[key] = _text_hash("\n".join(_heading_section(text, heading)))
    return found


def _open_items(text: str) -> dict[str, str]:
    """OI-349 without its status line, which the lead updates."""
    lines = _heading_section(text, OI349)
    kept = [line for line in lines if not line.startswith(_STATUS)]
    return {"oi_349": _text_hash("\n".join(kept))}


def _rule_lines(
    text: str, stored: tuple[tuple[str, str], ...] = ((D0035, IN_BRIEF),)
) -> dict[str, str]:
    """Each `_RULE_WORDS` line outside the sections stored whole (start and
    end heading), the cited rows and the status row, keyed by its heading and
    its place under it."""
    found: dict[str, str] = {}
    heading, end, seen = "preamble", None, dict[str, int]()
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line
            if end is None or line == end:
                end = next((e for s, e in stored if line.startswith(s)), None)
        if end or not _RULE_WORDS.search(line) or line.startswith(_STATUS_ROW):
            continue
        if _CITED.match(line) is None:
            seen[heading] = seen.get(heading, 0) + 1
            found[f"{heading} {seen[heading]}"] = _text_hash(line)
    if not found:
        raise base.ExtractionFailure("no rule lines")
    return found


def _doc09(text: str) -> dict[str, Any]:
    return {
        "decision_0035": _section(text, D0035, IN_BRIEF),
        "cited_rows": _rows(text, _CITED, "decision 0035 row"),
        "rule_lines": _rule_lines(text),
    }


def _doc10(text: str) -> dict[str, Any]:
    return {
        **_doc09(text),
        "provenance_textures": _rows(text, _TEXTURES, "textures"),
        "s3_t18": _text_hash("\n".join(_heading_section(text, DOC10_SECTION))),
    }


def _js(text: str) -> dict[str, str]:
    """Each top-level declaration of a script, cut at the next one.

    A declaration starts at column 0; an indented one stays inside its
    parent. Lines before the first declaration (imports) are `preamble`.
    """
    chunks: dict[str, list[str]] = {}
    name = "preamble"
    for line in text.splitlines():
        match = _JS_DECL.match(line)
        if match is not None:
            name = match.group(1)
            if name in chunks:
                raise base.ExtractionFailure(f"duplicate declaration {name}")
            chunks[name] = []
        chunks.setdefault(name, []).append(line)
    if set(chunks) <= {"preamble"}:
        raise base.ExtractionFailure("no declarations")
    return {key: _script("\n".join(lines)) for key, lines in chunks.items()}


BUILDERS: dict[str, Callable[[str], Any]] = {
    PROGRESS: _progress,
    DOC12: _doc12,
    DOC15: _doc15,
    AUDIENCE: _rules,
    CHECKER: lambda text: _python(text, _CHECKER_PINNED),
    AUDIENCE_TEST: _python,
    EXTRACTOR: _script,
    EXTRACTOR_TEST: _script,
    OPEN_ITEMS: _open_items,
    DOC09: _doc09,
    DOC10: _doc10,
    BACKEND: lambda text: _python(text, _BACKEND_PINNED),
    BACKEND_TEST: _python,
    CHECK_ANSWER: _js,
    CHECK_ANSWER_TEST: _script,
    MARK: _js,
    DRAWER: _js,
    PUBLIC_LAYERS: _js,
    LAYER_CHECKS: _js,
    LEGEND: _js,
    ANSWER_SPEC: _script,
    ORIGIN_TEST: _script,
    CHAIN_TEST: _script,
    LAYERS_COMPONENT_TEST: _script,
    ORIGIN_FIXTURE: _js,
    LAYERS_UNIT_TEST: _script,
    VISUAL_HARNESS: _script,
}


def project(root: Path, overlays: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Read the controls of both change sets that the existing pin misses."""
    out: dict[str, Any] = {}
    for relative in PATHS:
        text = base._read(root, relative, overlays, allow_absent=False)
        assert text is not None  # `_read` refuses an absent path itself
        out[relative] = BUILDERS[relative](text)
    return out


def _pin() -> Any:
    return json.loads(PIN.read_text(encoding="utf-8"))


def _matches(got: object) -> bool:
    return PIN.is_file() and base._canon(got) == base._canon(_pin())


@dataclass(frozen=True)
class Plant:
    name: str
    path: str
    mutate: Callable[[str], str]


def _swap(old: str, new: str) -> Callable[[str], str]:
    return lambda text: base._replace(text, old, new)


PLANTS = (
    Plant(
        "progress_recorded_failure_rewritten",
        PROGRESS,
        _swap("exit 1, 963 tests, 3 failures", "exit 0, 963 tests, 0 failures"),
    ),
    Plant(
        "doc12_audience_gate_nightly",
        DOC12,
        _swap(
            "extract-audience.node-test.mjs` | every pull request |",
            "extract-audience.node-test.mjs` | nightly |",
        ),
    ),
    Plant(
        "doc15_missing_marker_no_longer_fails",
        DOC15,
        _swap("A missing marker must fail; ", ""),
    ),
    Plant("rules_origin_term_deleted", AUDIENCE, base._drop_term("en.synthetic")),
    Plant(
        "checker_surface_missing_not_reported",
        CHECKER,
        _swap(
            'findings.append(Finding(name, "coverage", "surface-missing", ""))',
            "pass",
        ),
    ),
    Plant(
        "test_style_plant_weakened",
        AUDIENCE_TEST,
        _swap(
            'self.assertFalse(checker.check_evidence(evidence(styled), rules)["ok"])',
            "self.assertTrue(True)",
        ),
    ),
    Plant(
        "extractor_aria_label_dropped",
        EXTRACTOR,
        _swap("  'aria-label',\n", ""),
    ),
    Plant(
        "node_test_empty_surface_admitted",
        EXTRACTOR_TEST,
        _swap(
            "assert.ok(items.length > 0, `${id} is empty`);",
            "assert.ok(true, `${id} is empty`);",
        ),
    ),
)

T18_PLANTS = (
    Plant(
        "t18_progress_recorded_failure_rewritten",
        PROGRESS,
        _swap("exit 1: 16171 passed, 1 failed", "exit 0: 16172 passed, 0 failed"),
    ),
    Plant(
        "t18_oi349_tolerance_widened",
        OPEN_ITEMS,
        _swap(
            "No size, selector, tolerance or assertion changed",
            "The size tolerance was widened",
        ),
    ),
    Plant(
        "t18_doc09_ai34_class_word_rendered",
        DOC09,
        _swap("without rendering it as a class word", "and renders it as a class word"),
    ),
    Plant(
        "t18_doc10_refusal_names_origin",
        DOC10,
        _swap("which names no data origin;", "which names its data origin;"),
    ),
    Plant(
        "t18_backend_empty_level_admitted",
        BACKEND,
        _swap(
            "or isinstance(children, str) or not children:",
            "or isinstance(children, str):",
        ),
    ),
    Plant(
        "t18_backend_test_refusal_code_unchecked",
        BACKEND_TEST,
        _swap(
            'assert refusal.value.code == "outside_publisher"',
            "assert refusal.value.code is not None",
        ),
    ),
    Plant(
        "t18_answer_check_any_class_key_allowed",
        CHECK_ANSWER,
        _swap(
            "const withheldKey = key === 'drawer.class.suppressed';",
            "const withheldKey = key.startsWith('drawer.class.');",
        ),
    ),
    Plant(
        "t18_answer_check_test_class_word_unchecked",
        CHECK_ANSWER_TEST,
        _swap(
            "assert.ok(problems.includes('class-word:drawer.class.synthetic'));",
            "assert.ok(Array.isArray(problems));",
        ),
    ),
    Plant(
        "t18_mark_shape_collision_ignored",
        MARK,
        _swap("return new Set(values).size !== values.length;", "return false;"),
    ),
    Plant(
        "t18_drawer_withheld_mark_on_every_generated_fact",
        DRAWER,
        _swap("fact.provenance === 'suppressed' ?", "fact.provenance !== 'public' ?"),
    ),
    Plant(
        "t18_layers_refusal_guard_bypassed",
        PUBLIC_LAYERS,
        _swap(
            "? unimplementedReason(accepted.layerKey)",
            "? ('layers.refused.pending' as const)",
        ),
    ),
    Plant(
        "t18_layer_refusal_by_class",
        LAYER_CHECKS,
        _swap(
            "  if (!entry || !entry.className.includes('Public'))\n"
            "    return 'layers.refused.pending';",
            "  if (!entry || !entry.className.includes('Public'))\n"
            "    return 'layers.refused.writer';",
        ),
    ),
    Plant(
        "t18_legend_origin_sample_admitted",
        LEGEND,
        _swap("  stateKey: 'withheld';", "  stateKey: 'withheld' | 'synthetic';"),
    ),
    Plant(
        "t18_answer_spec_inside_unchecked",
        ANSWER_SPEC,
        _swap("expect(inside).toBe(true);", "expect(inside).toBeDefined();"),
    ),
    Plant(
        "t18_origin_test_hidden_count_unchecked",
        ORIGIN_TEST,
        _swap("expect(described(exposedCounts(root, HIDDEN))).toEqual([]);", ""),
    ),
    Plant(
        "t18_chain_test_collision_unchecked",
        CHAIN_TEST,
        _swap(
            "expect(shapesCollide({ ...STATUS_SHAPE, withheld: 'disc' })).toBe(true);",
            "expect(true).toBe(true);",
        ),
    ),
    Plant(
        "t18_layers_component_test_origin_unchecked",
        LAYERS_COMPONENT_TEST,
        _swap("expect(reason?.textContent).not.toContain('published source');", ""),
    ),
    Plant(
        "t18_origin_fixture_word_dropped",
        ORIGIN_FIXTURE,
        _swap("  'synthetic',\n", ""),
    ),
    Plant(
        "t18_layers_unit_test_extra_samples_admitted",
        LAYERS_UNIT_TEST,
        _swap("expect(samples).toEqual([", "expect(samples.slice(0, 1)).toEqual(["),
    ),
    Plant(
        "t18_harness_suppressed_value_shown",
        VISUAL_HARNESS,
        _swap("value: provenance === 'suppressed' ? null : 3,", "value: 3,"),
    ),
)
# One plant per document block added in round 3, each changing one predicate.
BLOCK_PLANTS = (
    Plant(
        "doc10_fe48_class_word_rendered",
        DOC10,
        _swap(
            "No provenance class word or origin texture is rendered.",
            "A provenance class word is rendered.",
        ),
    ),
    Plant(
        "doc10_layer_row_origin_word_admitted",
        DOC10,
        _swap(
            "flat fill by class | no origin word or texture; Synthetic",
            "flat fill by class | an origin word; Synthetic",
        ),
    ),
    Plant(
        "doc10_decision_0035_sample_label_admitted",
        DOC10,
        _swap(
            "No audience surface labels data as synthetic, simulated, generated, "
            "sample or demo:",
            "No audience surface labels data as synthetic, simulated or generated:",
        ),
    ),
    Plant(
        "doc09_decision_0035_sample_label_admitted",
        DOC09,
        _swap(
            "No audience surface labels data as synthetic, simulated, generated, "
            "sample or demo:",
            "No audience surface labels data as synthetic, simulated or generated:",
        ),
    ),
    Plant(
        "doc09_ai118_origin_label_admitted",
        DOC09,
        _swap(
            "the destination appears only as a public name label, not an origin label",
            "the destination appears as an origin label",
        ),
    ),
)
# One plant per rule line of review cf1 and the one the round 4 sweep found in
# document 15, each outside a table row and outside the decision 0035 section.
RULE_LINE_PLANTS = (
    Plant(
        "doc10_pack_origin_strip_admitted",
        DOC10,
        _swap(
            "no origin strip, watermark, class word or origin texture",
            "an origin strip, watermark, class word and origin texture",
        ),
    ),
    Plant(
        "doc10_gate_asserts_rendered_origin_mark",
        DOC10,
        _swap("asserts no rendered origin mark", "asserts a rendered origin mark"),
    ),
    Plant(
        "doc10_drawer_audience_origin_word_admitted",
        DOC10,
        _swap("no audience origin word or mark", "an audience origin word or mark"),
    ),
    Plant(
        "doc09_origin_words_rendered",
        DOC09,
        _swap("without origin words", "with origin words"),
    ),
    Plant(
        "doc15_example_origin_marks_kept",
        DOC15,
        _swap(
            "origin marks are withdrawn by decision 0035 item 1",
            "origin marks are kept",
        ),
    ),
)
ALL_PLANTS = PLANTS + T18_PLANTS + BLOCK_PLANTS + RULE_LINE_PLANTS


def run_plant(plant: Plant, root: Path) -> tuple[int, bool, int]:
    """Plant in `root`, then restore byte-exact: (red exit, restored, green exit)."""
    target = root / plant.path
    original = target.read_bytes()
    try:
        target.write_text(plant.mutate(original.decode("utf-8")), encoding="utf-8")
        red = 0 if _matches(project(root)) else 1
    finally:
        target.write_bytes(original)
    restored = target.read_bytes() == original
    green = 0 if _matches(project(root)) else 1
    return red, restored, green


def _copy_paths(destination: Path) -> Path:
    for relative in PATHS:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    return destination


def test_eight_closed_paths() -> None:
    assert len(set(T19_PATHS)) == 8
    assert set(BUILDERS) == set(PATHS)
    assert [plant.path for plant in PLANTS] == list(T19_PATHS)


def test_s3_t18_paths_are_its_change_set_with_one_plant_each() -> None:
    assert len(set(T18_PATHS)) == len(T18_PATHS) == 20
    assert not set(T18_PATHS) & set(T18_NO_CONTROL)
    assert len(set(T18_PATHS) | set(T18_NO_CONTROL)) == 24
    assert [plant.path for plant in T18_PLANTS] == list(T18_PATHS)


def test_real_tree_matches_the_stored_pin() -> None:
    assert PIN.is_file(), "pin absent"
    assert base._canon(project(ROOT)) == base._canon(_pin())


@pytest.mark.parametrize("plant", ALL_PLANTS, ids=lambda plant: plant.name)
def test_each_plant_is_red_then_restored_green(plant: Plant, tmp_path: Path) -> None:
    root = _copy_paths(tmp_path)
    assert run_plant(plant, root) == (1, True, 0)
    assert (root / plant.path).read_bytes() == (ROOT / plant.path).read_bytes()


@pytest.mark.parametrize("plant", ALL_PLANTS, ids=lambda plant: plant.name)
def test_the_decision_0035_pin_alone_misses_each_plant(plant: Plant) -> None:
    """Why this module exists: the existing projection is blind to each plant."""
    planted = plant.mutate((ROOT / plant.path).read_text(encoding="utf-8"))
    got = base.project(ROOT, {plant.path: planted})
    assert base._canon(got) == base._canon(base._pin())


def test_missing_anchor_refuses() -> None:
    text = (ROOT / DOC15).read_text(encoding="utf-8").replace(STANDING, "## Moved")
    with pytest.raises(base.ExtractionFailure, match="count 0"):
        project(ROOT, {DOC15: text})


def test_duplicate_rev_row_refuses() -> None:
    text = (ROOT / DOC15).read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| REV-01 |"))
    with pytest.raises(base.ExtractionFailure, match="duplicate REV REV-01"):
        project(ROOT, {DOC15: text + "\n" + row + "\n"})


def test_no_rev_rows_refuses() -> None:
    with pytest.raises(base.ExtractionFailure, match="no REV rows"):
        _rows("| REVIEW | x |\n", _REV, "REV")


def _rules_edit(edit: Callable[[dict[str, Any]], None]) -> str:
    return base._json_edit((ROOT / AUDIENCE).read_text(encoding="utf-8"), edit)


def test_duplicate_term_id_refuses() -> None:
    def edit(data: dict[str, Any]) -> None:
        data["terms"].append(dict(data["terms"][0]))

    with pytest.raises(base.ExtractionFailure, match=r"duplicate term en\.synthetic"):
        project(ROOT, {AUDIENCE: _rules_edit(edit)})


def test_term_without_id_refuses() -> None:
    def edit(data: dict[str, Any]) -> None:
        del data["terms"][0]["id"]

    with pytest.raises(base.ExtractionFailure, match=r"^term$"):
        project(ROOT, {AUDIENCE: _rules_edit(edit)})


def test_entries_need_a_list_and_string_ids() -> None:
    with pytest.raises(base.ExtractionFailure, match=r"^surface$"):
        _entries({"id": "x"}, "surface")
    with pytest.raises(base.ExtractionFailure, match=r"^surface id$"):
        _entries([{"id": 3}], "surface")


def test_duplicate_python_declaration_refuses() -> None:
    text = (ROOT / CHECKER).read_text(encoding="utf-8")
    with pytest.raises(base.ExtractionFailure, match="duplicate declaration ROOT"):
        project(ROOT, {CHECKER: text + "\nROOT = None\n"})


def test_missing_path_refuses(tmp_path: Path) -> None:
    root = _copy_paths(tmp_path)
    (root / EXTRACTOR_TEST).unlink()
    with pytest.raises(base.ExtractionFailure, match=f"missing {EXTRACTOR_TEST}"):
        project(root)


def test_js_duplicate_declaration_refuses() -> None:
    text = (ROOT / LEGEND).read_text(encoding="utf-8")
    planted = text + "\nexport const SAMPLE_COLOUR = 'x';\n"
    with pytest.raises(
        base.ExtractionFailure, match=r"^duplicate declaration SAMPLE_COLOUR$"
    ):
        project(ROOT, {LEGEND: planted})


def test_js_without_declarations_refuses() -> None:
    text = (ROOT / LEGEND).read_text(encoding="utf-8")
    indented = "\n".join(f"  {line}" for line in text.splitlines())
    with pytest.raises(base.ExtractionFailure, match=r"^no declarations$"):
        project(ROOT, {LEGEND: indented})


def test_js_indented_declaration_stays_in_its_parent() -> None:
    text = (ROOT / LEGEND).read_text(encoding="utf-8")
    planted = base._replace(
        text,
        "export function legendLineSamples(): readonly LineSample[] {\n",
        "export function legendLineSamples(): readonly LineSample[] {\n"
        "  const inner = 1;\n",
    )
    real, got = _js(text), _js(planted)
    assert set(got) == set(real)
    assert [key for key in real if real[key] != got[key]] == ["legendLineSamples"]


def test_no_cited_rows_refuses() -> None:
    with pytest.raises(base.ExtractionFailure, match=r"^no decision 0035 row rows$"):
        _rows(
            "| AI-34 | no citation |\n| Status | decision 0035 |\n",
            _CITED,
            "decision 0035 row",
        )


def test_duplicate_fe48_row_refuses() -> None:
    text = (ROOT / DOC10).read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| FE-48 |"))
    with pytest.raises(
        base.ExtractionFailure, match=r"^duplicate decision 0035 row FE-48$"
    ):
        project(ROOT, {DOC10: text + "\n" + row + "\n"})


def test_moved_decision_0035_heading_refuses() -> None:
    text = (ROOT / DOC09).read_text(encoding="utf-8")
    planted = base._replace(text, D0035, "## Moved")
    with pytest.raises(base.ExtractionFailure, match=f"^anchor {D0035} count 0$"):
        project(ROOT, {DOC09: planted})


def test_the_status_row_is_not_a_cited_row() -> None:
    text = (ROOT / DOC10).read_text(encoding="utf-8")
    assert "Status" not in _rows(text, _CITED, "decision 0035 row")
    assert {"FE-48", "Worker density"} <= set(_rows(text, _CITED, "decision 0035 row"))


def test_a_row_saying_origin_word_or_texture_is_cited_without_the_decision() -> None:
    row = "| New layer | `x` | no origin word or texture |\n"
    assert set(_rows(row, _CITED, "decision 0035 row")) == {"New layer"}


# The rule lines review cf1 names and the round 4 sweep's document 15 line,
# found by their text.
CF1_LINES = {
    DOC10: (
        "Forecasts of listed series (Public series",
        "This storyboard extends, never replaces",
        "no audience origin word or mark",
        "no origin strip, watermark, class word or origin texture",
        "absence of visible origin labels (decision 0035)",
        "asserts no rendered origin mark",
        "including the former origin watermark and strip",
    ),
    DOC09: ("without origin words",),
    DOC15: ("origin marks are withdrawn by decision 0035 item 1",),
}


def _line(path: str, fragment: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    (found,) = [line for line in text.splitlines() if fragment in line]
    return found


@pytest.mark.parametrize(
    ("path", "fragment"),
    [
        (path, fragment)
        for path, fragments in CF1_LINES.items()
        for fragment in fragments
    ],
)
def test_the_stored_rule_lines_hold_each_cf1_line(path: str, fragment: str) -> None:
    stored = _pin()[path]["rule_lines"]
    assert _text_hash(_line(path, fragment)) in stored.values()


def test_no_rule_lines_refuses() -> None:
    with pytest.raises(base.ExtractionFailure, match=r"^no rule lines$"):
        _rule_lines("# Title\nA line about origin.\n")


_SECTION_TEXT = (
    f"{D0035}\nA class word here.\n### Inside\nAn origin mark.\n{IN_BRIEF}\n"
)


def test_a_line_inside_the_decision_0035_section_is_not_a_rule_line() -> None:
    assert _rule_lines(_SECTION_TEXT + "No origin label.\n") == {
        f"{IN_BRIEF} 1": _text_hash("No origin label.")
    }


def test_a_line_in_any_section_stored_whole_is_not_a_rule_line() -> None:
    text = "# A\nNo class word.\n# B\nNo origin mark.\n# C\nNo origin label.\n"
    stored = (("# A", "# B"), ("# B", "# C"))
    assert set(_rule_lines(text + "# D\nNo class word.\n", stored)) == {
        "# C 1",
        "# D 1",
    }


def test_the_status_row_is_not_a_rule_line() -> None:
    text = "| Status | amended by decision 0035 |\nNo origin label.\n"
    assert set(_rule_lines(text)) == {"preamble 1"}


def test_a_cited_row_is_not_stored_twice() -> None:
    text = "| FE-1 | decision 0035 |\n| Row | no origin mark |\n"
    assert set(_rule_lines(text)) == {"preamble 1"}
    assert _rule_lines(text)["preamble 1"] == _text_hash("| Row | no origin mark |")


def test_each_rule_line_has_its_own_key_under_its_heading() -> None:
    text = "# A\nNo class word.\nNo class word.\n# B\nNo origin strip.\n"
    assert list(_rule_lines(text)) == ["# A 1", "# A 2", "# B 1"]


_WORDS = (
    "origin word",
    "origin mark",
    "origin strip",
    "origin label",
    "origin texture",
    "origin watermark",
    "class word",
    "decision 0035",
)


@settings(max_examples=80, deadline=None)
@given(
    word=st.sampled_from(_WORDS),
    plural=st.booleans(),
    upper=st.lists(st.booleans(), min_size=16, max_size=16),
)
def test_a_rule_word_in_any_case_and_number_is_stored(
    word: str, plural: bool, upper: list[bool]
) -> None:
    spelled = "".join(
        char.upper() if flag else char for char, flag in zip(word, upper, strict=False)
    ) + ("s" if plural and word != "decision 0035" else "")
    line = f"It shows no {spelled} here."
    assert _rule_lines(f"# H\n{line}\n") == {"# H 1": _text_hash(line)}
    with pytest.raises(base.ExtractionFailure, match=r"^no rule lines$"):
        _rule_lines(f"{D0035}\n{line}\n{IN_BRIEF}\n")


def test_missing_oi349_refuses() -> None:
    text = (ROOT / OPEN_ITEMS).read_text(encoding="utf-8")
    planted = base._replace(text, OI349, "### OI-349 moved")
    with pytest.raises(base.ExtractionFailure, match="count 0"):
        project(ROOT, {OPEN_ITEMS: planted})


def test_the_oi349_status_line_is_not_pinned() -> None:
    text = (ROOT / OPEN_ITEMS).read_text(encoding="utf-8")
    lines = _heading_section(text, OI349)
    status = next(line for line in lines if line.startswith(_STATUS))
    planted = base._replace(text, status, "- Status: closed by the lead.")
    assert base._canon(project(ROOT, {OPEN_ITEMS: planted})) == base._canon(_pin())


_COMMENT = st.text(
    alphabet=st.characters(categories=("L", "N", "Zs")), max_size=40
).map(lambda words: f"// {words}")


@settings(max_examples=40, deadline=None)
@given(line=st.integers(min_value=0), comment=_COMMENT)
def test_a_line_comment_anywhere_keeps_the_script_pin(line: int, comment: str) -> None:
    lines = (ROOT / EXTRACTOR).read_text(encoding="utf-8").splitlines()
    at = line % (len(lines) + 1)
    lines.insert(at, comment)
    assert _script("\n".join(lines)) == _script("\n".join(lines[:at] + lines[at + 1 :]))


_STANDING_TEXT = base._slice(
    (ROOT / DOC15).read_text(encoding="utf-8"), STANDING, SOURCES
)
_VISIBLE = [index for index, char in enumerate(_STANDING_TEXT) if not char.isspace()]


@settings(max_examples=60, deadline=None)
@given(
    position=st.sampled_from(_VISIBLE),
    replacement=st.characters(min_codepoint=0x41, max_codepoint=0x5A),
)
def test_any_visible_change_in_the_standing_section_is_red(
    position: int, replacement: str
) -> None:
    text = (ROOT / DOC15).read_text(encoding="utf-8")
    start = text.index(STANDING) + len(STANDING)
    original = text[start + position]
    if replacement == original:
        replacement = "Z" if original != "Z" else "Y"
    planted = text[: start + position] + replacement + text[start + position + 1 :]
    assert base._canon(project(ROOT, {DOC15: planted})) != base._canon(_pin())


@settings(max_examples=40, deadline=None)
@given(spaces=st.text(alphabet=" \n", min_size=1, max_size=4))
def test_whitespace_alone_keeps_the_markdown_pin(spaces: str) -> None:
    text = (ROOT / DOC15).read_text(encoding="utf-8")
    planted = base._replace(
        text, "A missing marker must fail;", f"A missing{spaces}marker must fail;"
    )
    assert base._canon(project(ROOT, {DOC15: planted})) == base._canon(_pin())


def main(argv: list[str]) -> int:
    """`--in-place`: plant each control in the real file, restore, report.

    `--write`: store the pin when it is absent; never replaces one.
    """
    if argv == ["--write"]:
        if PIN.exists():
            print("pin exists")
            return 1
        PIN.write_text(
            json.dumps(project(ROOT), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return 0
    if argv != ["--in-place"]:
        print("usage: --in-place | --write")
        return 2
    real = 0 if _matches(project(ROOT)) else 1
    print(f"real_tree {real}")
    bad = real
    for plant in ALL_PLANTS:
        red, restored, green = run_plant(plant, ROOT)
        print(f"{plant.name} {plant.path} red {red} restored {restored} green {green}")
        bad += (red, restored, green) != (1, True, 0)
    print(f"plants {len(ALL_PLANTS)} mismatches {bad - real}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
