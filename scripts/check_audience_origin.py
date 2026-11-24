#!/usr/bin/env python3
"""Standing audience-origin check (decision 0035 item 5; S3-T19).

Run from the repository root:

    uv run --locked python scripts/check_audience_origin.py --tree .
    uv run --locked python scripts/check_audience_origin.py --evidence FILE ...

The check reads typed surface evidence (``audience-evidence.v1``) and the
reviewed bilingual rules of ``scripts/audience_origin_rules.json``. It reports
four groups separately: audience absence (origin labels in audience text),
extraction coverage (missing, empty or omitted surfaces), backend-marker
validation (explicit synthetic/simulated origin and generator name and
version, from the contract inventory of ``eii_product.backend_origin``) and
the retained method and attribution checks (truthful producing pipeline, no
outside publisher, no official/measured/ministry claim).

``--tree`` collects live evidence: the web extractor
(``web/scripts/extract-audience.mjs``) for the built document, string tables,
accessible text, URLs and the generated catalogue, plus the typed product
loader for the catalogue and the template labels. ``--evidence`` reads
already-collected evidence documents instead (the unit tests). Exit 0 means
every group is clean; exit 1 reports findings; exit 2 is a usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import unquote

from eii_product.backend_origin import (
    GENERATED_ORIGINS,
    LEVELS,
    MARKER_KEYS,
    BackendOriginRefusal,
    require_generated_output,
    require_truthful_chain,
)

EVIDENCE_SCHEMA = "audience-evidence.v1"
RULES_SCHEMA = "audience-origin-rules.v1"
GROUPS = ("audience", "extraction", "backend", "method")

_ARABIC_MARKS = re.compile("[\u064b-\u0652\u0670\u0640]")
_ALEF = re.compile("[\u0622\u0623\u0625]")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = Path(__file__).resolve().parent / "audience_origin_rules.json"
EXTRACTOR = ROOT / "web" / "scripts" / "extract-audience.mjs"


@dataclass(frozen=True)
class Finding:
    """One check finding inside its report group."""

    where: str
    verdict: str
    detail: str
    text: str
    group: str = "audience"

    def as_dict(self) -> dict[str, str]:
        return {
            "where": self.where,
            "verdict": self.verdict,
            "detail": self.detail,
            "text": self.text,
        }


@dataclass(frozen=True)
class _Term:
    rule_id: str
    term: str
    contexts: list[str]
    verdict: str
    exempt_kinds: frozenset[str]
    group: str


@dataclass(frozen=True)
class _Parsed:
    """Derived, normalised form of the raw rules mapping."""

    surfaces: list[dict[str, Any]]
    output_classes: frozenset[str]
    unproduced: list[str]
    field_kinds: frozenset[str]
    scan_kinds: frozenset[str]
    claim_scan_kinds: frozenset[str]
    badge_terms: frozenset[str]
    badge_exempt_kinds: frozenset[str]
    style_rule: re.Pattern[str]
    terms: list[_Term]
    allow_values: frozenset[str]
    backend_fields: tuple[str, ...]
    backend_levels: tuple[str, ...]
    generated_values: frozenset[str]


def normalise(value: str) -> str:
    """Fold case, Arabic diacritics, tatweel and alef variants."""
    text = unicodedata.normalize("NFC", value)
    text = _ARABIC_MARKS.sub("", text)
    text = _ALEF.sub("\u0627", text)
    return text.casefold()


def _is_word_char(char: str) -> bool:
    category = unicodedata.category(char)
    return category.startswith("L") or category.startswith("N")


def _term_hit(term: str, text: str) -> bool:
    """Whole-word match on already-normalised strings."""
    start = 0
    while True:
        index = text.find(term, start)
        if index < 0:
            return False
        end = index + len(term)
        before = index == 0 or not _is_word_char(text[index - 1])
        after = end == len(text) or not _is_word_char(text[end])
        if before and after:
            return True
        start = index + 1


def _masked(normalised: str, phrases: list[str]) -> str:
    masked = normalised
    for phrase in phrases:
        masked = masked.replace(phrase, " " * len(phrase))
    return masked


def _reject(message: str) -> NoReturn:
    raise ValueError(f"rules: {message}")


def _str_set(raw: Any, name: str) -> frozenset[str]:
    if not isinstance(raw, list):
        _reject(f"{name} must be a list")
    values: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            _reject(f"{name} entries must be strings")
        values.append(entry)
    return frozenset(values)


def _parse(raw: dict[str, Any]) -> _Parsed:
    """Validate the raw rules mapping and build its derived form."""
    if raw.get("schema") != RULES_SCHEMA:
        _reject(f"schema must be {RULES_SCHEMA}")
    surfaces_raw = raw.get("surfaces")
    if not isinstance(surfaces_raw, list):
        _reject("surfaces must be a list")
    surfaces: list[dict[str, Any]] = []
    for entry in surfaces_raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            _reject("every surface needs an id")
        surfaces.append(entry)
    terms_raw = raw.get("terms")
    if not isinstance(terms_raw, list):
        _reject("terms must be a list")
    terms: list[_Term] = []
    for entry in terms_raw:
        if not isinstance(entry, dict):
            _reject("terms entries must be objects")
        if not isinstance(entry.get("term"), str) or entry["term"] == "":
            _reject("every term needs a non-empty 'term'")
        if entry.get("verdict") not in ("violation", "review"):
            _reject(f"bad verdict in {entry.get('id')}")
        group = str(entry.get("group", "audience"))
        if group not in ("audience", "method"):
            _reject(f"bad group in {entry.get('id')}")
        contexts = entry.get("allow_contexts", [])
        if not isinstance(contexts, list):
            _reject(f"allow_contexts in {entry.get('id')}")
        exempt = entry.get("exempt_field_kinds", [])
        if not isinstance(exempt, list):
            _reject(f"exempt_field_kinds in {entry.get('id')}")
        terms.append(
            _Term(
                rule_id=str(entry.get("id", "?")),
                term=normalise(str(entry["term"])),
                contexts=[normalise(str(p)) for p in contexts],
                verdict=str(entry["verdict"]),
                exempt_kinds=frozenset(str(k) for k in exempt),
                group=group,
            )
        )
    markers = raw.get("backend_markers")
    if not isinstance(markers, dict):
        _reject("backend_markers must be an object")
    allow_values: set[str] = set()
    for entry in raw.get("allow_values", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("value"), str):
            _reject("allow_values entries need a value")
        allow_values.add(normalise(str(entry["value"])))
    style = raw.get("style_token_rule", "")
    if not isinstance(style, str):
        _reject("style_token_rule must be a string")
    return _Parsed(
        surfaces=surfaces,
        output_classes=_str_set(raw.get("output_classes"), "output_classes"),
        unproduced=[str(c) for c in raw.get("unproduced_classes", [])],
        field_kinds=_str_set(raw.get("field_kinds"), "field_kinds"),
        scan_kinds=_str_set(raw.get("scan_kinds"), "scan_kinds"),
        claim_scan_kinds=_str_set(raw.get("claim_scan_kinds"), "claim_scan_kinds"),
        badge_terms=frozenset(
            normalise(t) for t in _str_set(raw.get("badge_terms"), "badge_terms")
        ),
        badge_exempt_kinds=_str_set(
            raw.get("badge_exempt_kinds"), "badge_exempt_kinds"
        ),
        style_rule=re.compile(style, re.IGNORECASE) if style else re.compile(r"a^"),
        terms=terms,
        allow_values=frozenset(allow_values),
        backend_fields=tuple(str(f) for f in markers.get("fields", ())),
        backend_levels=tuple(str(level) for level in markers.get("levels", ())),
        generated_values=frozenset(str(v) for v in markers.get("generated_values", [])),
    )


def load_rules(path: Path | str) -> dict[str, Any]:
    """Read and validate the rules file; a malformed file is a usage error.

    Returns the raw mapping so a caller (or a test) can inspect or patch it;
    ``check_evidence`` re-derives the working form on every call.
    """
    loaded: object = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        _reject("rules must be an object")
    _parse(loaded)
    return loaded


def _item_finding(
    surface: str, item: dict[str, Any], verdict: str, detail: str
) -> Finding:
    text = str(item.get("text", ""))
    excerpt = text if len(text) <= 80 else text[:77] + "..."
    where = f"{surface}:{item.get('output_class', '?')}:{item.get('field', '?')}"
    return Finding(where=where, verdict=verdict, detail=detail, text=excerpt)


def _scan_item(surface: str, item: dict[str, Any], rules: _Parsed) -> list[Finding]:
    """Scan one evidence item for origin labels and claim words."""
    findings: list[Finding] = []
    kind = str(item.get("field_kind"))
    raw_text = str(item.get("text", ""))
    if kind == "backend":
        return findings
    if kind == "style":
        if rules.style_rule.search(normalise(raw_text)):
            findings.append(_item_finding(surface, item, "violation", "origin-style"))
        return findings
    text = unescape(unquote(raw_text)) if kind == "url" else raw_text
    clean = normalise(text)
    if clean.strip() in rules.allow_values:
        return findings
    downgrade = kind == "source"
    if clean.strip() in rules.badge_terms and kind not in rules.badge_exempt_kinds:
        verdict = "review" if downgrade else "violation"
        findings.append(_item_finding(surface, item, verdict, "class-badge"))
    if kind not in rules.scan_kinds:
        return findings
    for term in rules.terms:
        if kind in term.exempt_kinds:
            continue
        if term.group == "method" and kind not in rules.claim_scan_kinds:
            continue
        if _term_hit(term.term, _masked(clean, term.contexts)):
            verdict = "review" if downgrade else term.verdict
            found = _item_finding(surface, item, verdict, term.rule_id)
            findings.append(
                Finding(
                    where=found.where,
                    verdict=found.verdict,
                    detail=found.detail,
                    text=found.text,
                    group=term.group,
                )
            )
    return findings


def _coverage(evidence: dict[str, Any], rules: _Parsed) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    scanned = 0
    seen = 0
    surfaces = evidence.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        findings.append(Finding("evidence", "coverage", "empty-extraction", ""))
        return findings, scanned
    by_id = {
        str(s["id"]): s
        for s in surfaces
        if isinstance(s, dict) and isinstance(s.get("id"), str)
    }
    for declared in rules.surfaces:
        if not declared.get("required", False):
            continue
        name = str(declared["id"])
        surface = by_id.get(name)
        if surface is None:
            findings.append(Finding(name, "coverage", "surface-missing", ""))
            continue
        if surface.get("status") != "ok":
            findings.append(
                Finding(
                    name,
                    "coverage",
                    f"surface-{surface.get('status', 'invalid')}",
                    "",
                )
            )
            continue
        items = surface.get("items")
        if not isinstance(items, list):
            findings.append(Finding(name, "coverage", "items-invalid", ""))
            continue
        if len(items) < int(declared.get("min_items", 0)):
            findings.append(
                Finding(name, "coverage", f"surface-empty:{len(items)}", "")
            )
    for surface in surfaces:
        if not isinstance(surface, dict):
            findings.append(Finding("?", "coverage", "surface-invalid", ""))
            continue
        items = surface.get("items", [])
        if not isinstance(items, list):
            continue
        for entry in items:
            if not isinstance(entry, dict):
                findings.append(
                    Finding(str(surface.get("id")), "coverage", "item-invalid", "")
                )
                continue
            where = str(surface.get("id"))
            if entry.get("output_class") not in rules.output_classes:
                findings.append(
                    Finding(
                        f"{where}:{entry.get('output_class', '?')}",
                        "coverage",
                        "class-unknown",
                        "",
                    )
                )
            if entry.get("field_kind") not in rules.field_kinds:
                findings.append(
                    Finding(
                        f"{where}:{entry.get('field', '?')}",
                        "coverage",
                        "kind-unknown",
                        "",
                    )
                )
            if not isinstance(entry.get("text"), str):
                findings.append(
                    Finding(
                        f"{where}:{entry.get('field', '?')}",
                        "coverage",
                        "text-invalid",
                        "",
                    )
                )
            else:
                seen += 1
                if entry.get("field_kind") != "backend":
                    scanned += 1
    if seen == 0:
        findings.append(Finding("evidence", "coverage", "empty-extraction", ""))
    return findings, scanned


def check_evidence(
    evidence: dict[str, Any] | None, rules: dict[str, Any]
) -> dict[str, Any]:
    """Check one evidence document; the report groups its findings."""
    parsed = _parse(rules)
    groups: dict[str, list[Finding]] = {name: [] for name in GROUPS}
    if not isinstance(evidence, dict) or evidence.get("schema") != EVIDENCE_SCHEMA:
        groups["extraction"].append(
            Finding("evidence", "coverage", "missing-or-invalid", "")
        )
        return _report(groups, parsed, 0)
    coverage, scanned = _coverage(evidence, parsed)
    groups["extraction"].extend(coverage)
    for surface in evidence.get("surfaces", []):
        if not isinstance(surface, dict):
            continue
        items = surface.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                continue
            for finding in _scan_item(str(surface.get("id")), item, parsed):
                groups[finding.group].append(finding)
    inventory_ok = (
        tuple(MARKER_KEYS) == parsed.backend_fields
        and tuple(LEVELS) == parsed.backend_levels
        and set(GENERATED_ORIGINS) == parsed.generated_values
    )
    if not inventory_ok:
        groups["backend"].append(
            Finding("backend_markers", "marker", "contract-inventory", "")
        )
    outputs = evidence.get("generated_outputs", [])
    if isinstance(outputs, list):
        for index, output in enumerate(outputs):
            try:
                require_generated_output(output)
            except BackendOriginRefusal as refusal:
                groups["backend"].append(
                    Finding(
                        f"generated_outputs[{index}]",
                        "marker",
                        refusal.code,
                        refusal.where,
                    )
                )
            except (TypeError, AttributeError) as error:
                groups["backend"].append(
                    Finding(
                        f"generated_outputs[{index}]",
                        "marker",
                        "invalid",
                        str(error),
                    )
                )
    chains = evidence.get("source_chains", [])
    if isinstance(chains, list):
        for index, entry in enumerate(chains):
            if not isinstance(entry, dict):
                groups["method"].append(
                    Finding(f"source_chains[{index}]", "attribution", "invalid", "")
                )
                continue
            chain = entry.get("chain", {})
            markers = entry.get("markers", {})
            if not isinstance(chain, dict) or not isinstance(markers, dict):
                groups["method"].append(
                    Finding(f"source_chains[{index}]", "attribution", "invalid", "")
                )
                continue
            try:
                require_truthful_chain(chain, markers)
            except BackendOriginRefusal as refusal:
                groups["method"].append(
                    Finding(
                        f"source_chains[{index}]",
                        "attribution",
                        refusal.code,
                        refusal.where,
                    )
                )
    return _report(groups, parsed, scanned)


def _report(
    groups: dict[str, list[Finding]], rules: _Parsed, scanned: int
) -> dict[str, Any]:
    return {
        "ok": all(not found for found in groups.values()),
        "groups": {
            name: [finding.as_dict() for finding in found]
            for name, found in groups.items()
        },
        "unproduced": rules.unproduced,
        "scanned_items": scanned,
    }


def merge_evidence(*documents: dict[str, Any]) -> dict[str, Any]:
    """Merge evidence documents into one."""
    merged: dict[str, Any] = {
        "schema": EVIDENCE_SCHEMA,
        "extractor": "merged",
        "surfaces": [],
        "generated_outputs": [],
        "source_chains": [],
    }
    for document in documents:
        if not isinstance(document, dict):
            continue
        for key in ("surfaces", "generated_outputs", "source_chains"):
            value = document.get(key, [])
            if isinstance(value, list):
                merged[key].extend(value)
    return merged


def _make_item(
    field_name: str,
    field_kind: str,
    output_class: str,
    language: str,
    text: str,
) -> dict[str, Any]:
    return {
        "field": field_name,
        "field_kind": field_kind,
        "output_class": output_class,
        "language": language,
        "text": text,
    }


def _catalogue_items(catalogue: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def add(owner: str, fields: Any) -> None:
        if not isinstance(fields, (list, tuple)):
            return
        for pair in fields:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            name, value = pair
            if not isinstance(value, str):
                continue
            field_name = f"{owner}.{name}"
            if str(name).endswith("_en"):
                items.append(_make_item(field_name, "copy", "catalogue", "en", value))
            elif str(name).endswith("_ar"):
                items.append(_make_item(field_name, "copy", "catalogue", "ar", value))
            else:
                items.append(
                    _make_item(field_name, "backend", "catalogue", "und", value)
                )

    for claim in catalogue.claims:
        add(f"claims.{claim.key}", claim.fields)
        items.append(
            _make_item(
                f"claims.{claim.key}.subject",
                "backend",
                "catalogue",
                "und",
                str(claim.subject),
            )
        )
        for slot in claim.slots:
            for provenance in slot.allowed_provenance:
                items.append(
                    _make_item(
                        f"claims.{claim.key}.slots.{slot.name}.allowed_provenance",
                        "backend",
                        "catalogue",
                        "und",
                        str(provenance),
                    )
                )
    for fragment in catalogue.fragments:
        add(f"fragments.{fragment.key}", fragment.fields)
    for question in catalogue.questions:
        add(f"questions.{question.key}", question.fields)
        for persona in question.personas:
            items.append(
                _make_item(
                    f"questions.{question.key}.personas",
                    "backend",
                    "catalogue",
                    "und",
                    str(persona),
                )
            )
    for component in catalogue.components:
        items.append(
            _make_item(
                f"components.{component.key}",
                "backend",
                "catalogue",
                "und",
                str(component.key),
            )
        )
    for directive in catalogue.directives:
        items.append(
            _make_item(
                f"directives.{directive.name}",
                "backend",
                "catalogue",
                "und",
                str(directive.name),
            )
        )
    return items


def _template_items(root: Path) -> list[dict[str, Any]]:
    """Template labels and rendered fields of the assistant yaml files."""
    import yaml

    from eii_product.assistant.templates.status import STEP_LABELS

    items: list[dict[str, Any]] = []
    for tool, labels in sorted(STEP_LABELS.items()):
        items.append(
            _make_item(f"steps.{tool}.en", "copy", "template", "en", labels[0])
        )
        items.append(
            _make_item(f"steps.{tool}.ar", "copy", "template", "ar", labels[1])
        )
    assistant = root / "product" / "assistant"
    catalogue_dir = assistant / "catalogue"
    if assistant.is_dir():
        for path in sorted(assistant.rglob("*.yaml")):
            if catalogue_dir == path.parent or catalogue_dir in path.parents:
                continue
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            rel = path.relative_to(root)
            for dotted, value in _scalar_fields(document):
                leaf = dotted.rsplit(".", 1)[-1]
                if leaf.endswith("_en") or leaf.endswith("_ar"):
                    kind = "copy"
                    language = "ar" if leaf.endswith("_ar") else "en"
                else:
                    kind = "backend"
                    language = "und"
                items.append(
                    _make_item(f"{rel}:{dotted}", kind, "template", language, value)
                )
    return items


def _scalar_fields(node: Any, prefix: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            found.extend(_scalar_fields(value, dotted))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_scalar_fields(value, f"{prefix}[{index}]"))
    elif isinstance(node, str):
        found.append((prefix, node))
    return found


def collect_product_evidence(root: Path) -> dict[str, Any]:
    """Product-side evidence: the typed catalogue and the template labels."""
    from eii_product.assistant.catalogue.load import (
        catalogue_directory,
        load_catalogue,
    )
    from eii_product.assistant.catalogue.schema import Refusal

    surfaces: list[dict[str, Any]] = []
    folder = catalogue_directory()
    loaded = load_catalogue(folder)
    if isinstance(loaded, Refusal):
        surfaces.append(
            {
                "id": "product.catalogue",
                "origin": "package:eii_product.assistant.catalogue/assets",
                "status": "refused",
                "items": [],
            }
        )
    else:
        surfaces.append(
            {
                "id": "product.catalogue",
                "origin": "package:eii_product.assistant.catalogue/assets",
                "status": "ok",
                "items": _catalogue_items(loaded),
            }
        )
    surfaces.append(
        {
            "id": "product.templates",
            "origin": "product/src/eii_product/assistant + product/assistant",
            "status": "ok",
            "items": _template_items(root),
        }
    )
    return {
        "schema": EVIDENCE_SCHEMA,
        "extractor": "check_audience_origin.collect_product_evidence",
        "surfaces": surfaces,
        "generated_outputs": [],
        "source_chains": [],
    }


def collect_tree(root: Path) -> dict[str, Any]:
    """Run the web extractor and merge it with the product evidence."""
    node = shutil.which("node")
    if node is None:
        raise FileNotFoundError("node is not on PATH")
    result = subprocess.run(
        [node, str(EXTRACTOR), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "extractor failed")
    web = json.loads(result.stdout)
    return merge_evidence(web, collect_product_evidence(root))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tree",
        type=Path,
        default=None,
        help="Collect live evidence from the tree at this root.",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        action="append",
        default=[],
        help="Check an already-collected evidence file (repeatable).",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES,
        help="Rules file (default: scripts/audience_origin_rules.json).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv) if argv is not None else sys.argv[1:])
    try:
        rules = load_rules(args.rules)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"rules error: {error}", file=sys.stderr)
        return 2
    documents: list[dict[str, Any]] = []
    if args.tree is not None:
        try:
            documents.append(collect_tree(args.tree.resolve()))
        except (OSError, RuntimeError, json.JSONDecodeError) as error:
            print(f"extraction error: {error}", file=sys.stderr)
            return 2
    for path in args.evidence:
        try:
            documents.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as error:
            print(f"evidence error: {path}: {error}", file=sys.stderr)
            return 2
    if not documents:
        print("no evidence: pass --tree or --evidence", file=sys.stderr)
        return 2
    report = check_evidence(merge_evidence(*documents), rules)
    for name in GROUPS:
        found = report["groups"][name]
        if not found:
            print(f"{name}: clean")
            continue
        print(f"{name}: {len(found)} finding(s)")
        for finding in found:
            print(
                f"  {finding['verdict']} {finding['where']}: "
                f"{finding['detail']} {finding['text']!r}"
            )
    if report["unproduced"]:
        print("unproduced classes: " + ", ".join(report["unproduced"]))
    print(f"scanned items: {report['scanned_items']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
