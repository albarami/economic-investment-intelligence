"""Print record counts for saved pages. The command prints no record text.

uv run --locked python -m eii_custodian.publicdata.investment_counts dashboard PAGE
uv run --locked python -m eii_custodian.publicdata.investment_counts agency PAGE URL KIND
uv run --locked python -m eii_custodian.publicdata.investment_counts agency-batch FOLDER

FOLDER holds addresses.txt. Each line is `kind url filename`, with no spaces in the
url or the filename. filename is relative to FOLDER. The command reads every page,
builds one agency batch, and prints the record count and the page count.
"""

from __future__ import annotations

import sys
from pathlib import Path

from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.investment_build import (
    load_source_spec,
    require_page_families,
    validate_investment,
)
from eii_custodian.publicdata.investment_contracts import (
    InvestmentFailure,
    SourceEnvelope,
)
from eii_custodian.publicdata.investment_parse import (
    agency_envelope,
    dashboard_envelope,
    parse_agency,
    parse_fdi,
)


def main(argv: list[str]) -> int:
    """Print counts for a dashboard page or one agency page."""
    if len(argv) == 3 and argv[1] == "dashboard":
        return _dashboard(Path(argv[2]))
    if len(argv) == 5 and argv[1] == "agency":
        return _agency(Path(argv[2]), argv[3], argv[4])
    if len(argv) == 3 and argv[1] == "agency-batch":
        return _agency_batch(Path(argv[2]))
    print("fail usage", file=sys.stderr)
    return 2


def _dashboard(path: Path) -> int:
    spec = load_source_spec("fdi_projects", url="https://fdiprojects.invest.qa/")
    if isinstance(spec, InvestmentFailure) or spec.dashboard is None:
        print("fail unconfirmed")
        return 1
    body = path.read_bytes()
    envelope = dashboard_envelope(
        _envelope("fdi_projects", "https://fdiprojects.invest.qa/", body)
    )
    parsed = parse_fdi(body, spec.dashboard, envelope)
    if isinstance(parsed, InvestmentFailure):
        print(f"fail {parsed.check}")
        return 1
    rows, empty = parsed
    print(f"records {len(rows)}")
    print(f"empty_coordinates {empty}")
    return 0


def _agency(path: Path, url: str, kind: str) -> int:
    spec = load_source_spec("investqa_pages", url=url)
    if isinstance(spec, InvestmentFailure):
        print("fail unconfirmed")
        return 1
    rule = spec.kind_rules.get(kind)
    if rule is None:
        print("fail missing_page")
        return 1
    minimum_blocks = rule.minimum_blocks
    minimum_paragraphs = rule.minimum_paragraphs
    language = ""
    for page in spec.pages:
        if page.url == url and page.kind == kind:
            minimum_blocks = page.minimum_blocks
            minimum_paragraphs = page.minimum_paragraphs
            language = page.language
            break
    body = path.read_bytes()
    parsed = parse_agency(
        body,
        rule=rule,
        furniture=spec.furniture,
        minimum_blocks=minimum_blocks,
        minimum_paragraphs=minimum_paragraphs,
        envelope=agency_envelope(_envelope("investqa_pages", url, body)),
        language=language,
    )
    if isinstance(parsed, InvestmentFailure):
        print(f"fail {parsed.check}")
        return 1
    print(f"records {len(parsed)}")
    return 0


def _agency_batch(folder: Path) -> int:
    """Parse every addressed page in one folder and print the batch counts."""
    listing = folder / "addresses.txt"
    if not listing.is_file():
        print("fail usage", file=sys.stderr)
        return 2
    spec = load_source_spec("investqa_pages", url="https://www.invest.qa/")
    if isinstance(spec, InvestmentFailure):
        print("fail unconfirmed")
        return 1
    rows: list[dict[str, object]] = []
    kinds: list[str] = []
    for raw in listing.read_text(encoding="utf-8").splitlines():
        if raw.strip() == "":
            continue
        parts = raw.split()
        if len(parts) != 3:
            print("fail usage", file=sys.stderr)
            return 2
        kind, url, name = parts
        rule = spec.kind_rules.get(kind)
        if rule is None:
            print("fail missing_page")
            return 1
        minimum_blocks = rule.minimum_blocks
        minimum_paragraphs = rule.minimum_paragraphs
        language = ""
        for page in spec.pages:
            if page.url == url and page.kind == kind:
                minimum_blocks = page.minimum_blocks
                minimum_paragraphs = page.minimum_paragraphs
                language = page.language
                break
        body = (folder / name).read_bytes()
        parsed = parse_agency(
            body,
            rule=rule,
            furniture=spec.furniture,
            minimum_blocks=minimum_blocks,
            minimum_paragraphs=minimum_paragraphs,
            envelope=agency_envelope(_envelope("investqa_pages", url, body)),
            language=language,
        )
        if isinstance(parsed, InvestmentFailure):
            print(f"fail {parsed.check}")
            return 1
        rows.extend(parsed)
        kinds.append(kind)
    entry = next(item for item in load_registry() if item.source_id == "investqa_pages")
    batch = agency_envelope(_envelope("investqa_pages", entry.url, b""))
    missing = require_page_families(tuple(kinds), batch)
    if missing is not None:
        print(f"fail {missing.check}")
        return 1
    validated = validate_investment(tuple(rows), spec.bounds, spec.confirmation, batch)
    if isinstance(validated, InvestmentFailure):
        print(f"fail {validated.check}")
        return 1
    print(f"records {len(validated)}")
    print(f"pages {len(kinds)}")
    return 0


def _envelope(source_id: str, url: str, body: bytes) -> SourceEnvelope:
    entry = next(item for item in load_registry() if item.source_id == source_id)
    return SourceEnvelope(
        source_id=source_id,
        publisher=entry.publisher,
        page_url=url,
        licence_id=entry.licence_id,
        licence_basis=entry.licence_basis,
        decision_record=entry.decision_record,
        terms_sha256="0" * 64,
        terms_url=entry.terms_url,
        retrieved_utc="1970-01-01T00:00:00Z",
        page_sha256=sha256_hex(body),
        method="",
        method_version="",
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
