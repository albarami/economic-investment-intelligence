"""Selected native trade inputs. No currency or country binding is inferred."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, NoReturn

from eii_core.calc.trade_reconciliation import (
    METHOD,
    PairResult,
    TradeFigure,
    all_pairs,
    comparison_figures,
)
from eii_custodian.publicdata.baci import contracts as baci_contracts
from eii_custodian.publicdata.benchmarks.config import digest_ok, require
from eii_custodian.publicdata.comtrade.assemble import Assembly, assemble
from eii_custodian.publicdata.comtrade.policy import Policy
from eii_custodian.publicdata.fetch.bounded import file_hash, publish_complete
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.series.figures import contract_rows
from eii_custodian.publicdata.series.parse import confirmed_rows, selected_source


def read_baci(cache: Path, manifest_sha256: str) -> baci_contracts.Release:
    require(digest_ok(manifest_sha256), "selection")
    return baci_contracts.read_selected(cache, manifest_sha256)


def read_comtrade(
    cache: Path,
    policy: Policy,
    *,
    manifest_sha256: str,
    publisher: str,
    licence_basis: str,
    terms_sha256: str,
) -> Assembly:
    require(digest_ok(manifest_sha256), "selection")
    return assemble(
        cache,
        "un_comtrade",
        policy,
        manifest_sha256=manifest_sha256,
        publisher=publisher,
        licence_basis=licence_basis,
        terms_sha256=terms_sha256,
    )


def read_portal(
    cache: Path, source_id: str, selected_hash: str
) -> tuple[list[dict[str, object]], dict[str, object]]:
    require(
        source_id in {"cus_imp_2019", "cus_imp_2025"} and digest_ok(selected_hash),
        "selection",
    )
    entry = next(entry for entry in load_registry() if entry.source_id == source_id)
    rows, receipt = selected_source(cache, entry, selected_hash)
    return contract_rows(source_id, confirmed_rows(entry, rows)), receipt


# Selection is a closed reviewed mapping, not a query or an inferred concordance.

SOURCES = {
    "cus_imp_2019": ("portal",),
    "cus_imp_2025": ("portal",),
    "un_comtrade": ("reporter", "mirror"),
    "cepii_baci": ("baci",),
}


@dataclass(frozen=True)
class SelectedInput:
    source_id: str
    role: str
    selected_hash: str
    publisher: str = ""
    licence_basis: str = ""
    terms_sha256: str = ""


@dataclass(frozen=True)
class Binding:
    source_id: str
    role: str
    row_key: str
    partner: str
    flow: str
    year: int
    product_scope: str
    coverage_key: str
    currency: str
    scale: str
    hs_revision: str
    classification: str
    evidence_sha256: str
    target_code: str = ""
    partner_code: str = ""
    native_flow: str = ""


@dataclass(frozen=True)
class Selection:
    confirmed: bool
    partners: tuple[str, ...]
    years: tuple[int, ...]
    flows: tuple[str, ...]
    scopes: tuple[str, ...]
    inputs: tuple[SelectedInput, ...]
    bindings: tuple[Binding, ...]
    causes: tuple[dict[str, Any], ...]
    obstacles: tuple[dict[str, Any], ...]

    @classmethod
    def from_mapping(cls, data: Any) -> Selection:
        require(
            isinstance(data, dict) and set(data) == {f.name for f in fields(cls)},
            "selection_schema",
        )
        require(data["confirmed"] is True, "selection_pending")
        for key in ("partners", "years", "flows", "scopes"):
            require(
                isinstance(data[key], (list, tuple))
                and bool(data[key])
                and len(set(data[key])) == len(data[key]),
                "selection_scope",
            )
        require(
            all(type(y) is int and 1000 <= y <= 9999 for y in data["years"]),
            "selection_year",
        )
        require(set(data["flows"]) <= {"import", "export"}, "selection_flow")
        try:
            inputs = tuple(SelectedInput(**v) for v in data["inputs"])
            bindings = tuple(Binding(**v) for v in data["bindings"])
        except TypeError:
            raise ValueError("selection_schema") from None
        require(
            len(inputs) >= 2
            and len({(i.source_id, i.role) for i in inputs}) == len(inputs),
            "selection_inputs",
        )
        for item in inputs:
            require(
                item.source_id in SOURCES
                and item.role in SOURCES[item.source_id]
                and (digest_ok(item.selected_hash) or item.selected_hash == ""),
                "selection_inputs",
            )
        require(
            len({(b.source_id, b.role, b.row_key) for b in bindings}) == len(bindings),
            "duplicate_binding",
        )
        for b in bindings:
            require(
                (b.source_id, b.role) in {(i.source_id, i.role) for i in inputs}
                and b.partner in data["partners"]
                and b.year in data["years"]
                and b.flow in data["flows"]
                and b.product_scope in data["scopes"]
                and digest_ok(b.evidence_sha256),
                "binding",
            )
        source_ids = {i.source_id for i in inputs}
        for c in data["causes"]:
            require(
                isinstance(c, dict)
                and set(c)
                == {
                    "left_source",
                    "right_source",
                    "partner",
                    "year",
                    "code",
                    "evidence_sha256",
                },
                "cause_schema",
            )
            require(
                c["left_source"] in source_ids
                and c["right_source"] in source_ids
                and c["left_source"] != c["right_source"]
                and c["partner"] in data["partners"]
                and c["year"] in data["years"]
                and c["code"]
                in {
                    "publication_timing",
                    "valuation",
                    "classification",
                    "coverage",
                    "revision",
                }
                and digest_ok(c["evidence_sha256"]),
                "cause_evidence",
            )
        for o in data["obstacles"]:
            require(
                isinstance(o, dict)
                and set(o)
                == {
                    "source_id",
                    "reason",
                    "evidence_sha256",
                    "price_amount",
                    "price_currency",
                },
                "obstacle_schema",
            )
            require(
                o["source_id"] in source_ids
                and o["reason"]
                in {
                    "registration",
                    "sign_in",
                    "robot_check",
                    "paid_tier",
                    "free_plan_gap",
                    "unavailable",
                }
                and digest_ok(o["evidence_sha256"]),
                "obstacle_evidence",
            )
            require(
                (o["price_amount"] is None) == (o["price_currency"] is None),
                "price_evidence",
            )
            if o["price_amount"] is not None:
                from eii_custodian.publicdata.fetch.decimals import (
                    DecimalRefusal,
                    exact_decimal,
                )

                try:
                    exact_decimal(
                        o["price_amount"],
                        total_digits=12,
                        fractional_digits=4,
                        signed=False,
                    )
                except DecimalRefusal:
                    raise ValueError("price_evidence") from None
                require(
                    isinstance(o["price_currency"], str)
                    and len(o["price_currency"]) == 3
                    and o["price_currency"].isascii()
                    and o["price_currency"].isupper(),
                    "price_evidence",
                )
        for item in inputs:
            if not item.selected_hash:
                require(
                    any(o["source_id"] == item.source_id for o in data["obstacles"]),
                    "missing_input_evidence",
                )
                require(
                    not any(
                        (b.source_id, b.role) == (item.source_id, item.role)
                        for b in bindings
                    ),
                    "unavailable_input_binding",
                )
        return cls(
            True,
            tuple(data["partners"]),
            tuple(data["years"]),
            tuple(data["flows"]),
            tuple(data["scopes"]),
            inputs,
            bindings,
            tuple(data["causes"]),
            tuple(data["obstacles"]),
        )


@dataclass(frozen=True)
class ComparisonInput:
    figure: TradeFigure
    source_table: str
    source_row_key: str
    selected_hash: str
    receipt_sha256: str
    binding_evidence_sha256: str
    native: dict[str, Any]


@dataclass(frozen=True)
class ReconciliationRelease:
    inputs: tuple[ComparisonInput, ...]
    comparisons: tuple[PairResult, ...]
    manifest: dict[str, Any]


def _materialize(
    cache: Path, selection: Selection, comtrade_policy: Policy | None
) -> tuple[ComparisonInput, ...]:
    import json
    from decimal import Decimal

    result = []
    used = set()
    for item in selection.inputs:
        if not item.selected_hash:
            continue
        native_rows: list[dict[str, Any]]
        if item.source_id.startswith("cus_imp_"):
            native_rows, receipt = read_portal(
                cache, item.source_id, item.selected_hash
            )
            source_version = str(receipt.get("source_modified") or "unknown")
            receipt_hash = str(receipt.get("sha256", ""))
            table = "pub_customs_import"
        elif item.source_id == "cepii_baci":
            baci = read_baci(cache, item.selected_hash)
            native_rows = [asdict(r) for r in baci.trade]
            source_version = str(baci.source_registry.get("source_version", "unknown"))
            receipt_hash = item.selected_hash
            table = "pub_baci_trade"
        else:
            require(comtrade_policy is not None, "comtrade_policy_required")
            assert comtrade_policy is not None
            assembled = read_comtrade(
                cache,
                comtrade_policy,
                manifest_sha256=item.selected_hash,
                publisher=item.publisher,
                licence_basis=item.licence_basis,
                terms_sha256=item.terms_sha256,
            )
            native_rows = [
                asdict(r) for r in assembled.rows if r.series_role == item.role
            ]
            source_version = "unknown"
            receipt_hash = item.selected_hash
            table = "pub_comtrade_trade"
        for index, native in enumerate(native_rows):
            key = (item.source_id, item.role, str(index))
            binding = next(
                (
                    b
                    for b in selection.bindings
                    if (b.source_id, b.role, b.row_key) == key
                ),
                None,
            )
            require(binding is not None, "native_row_binding_missing")
            assert binding is not None
            used.add(key)
            if item.role == "baci":
                countries = {c.country_code for c in baci.country}
                require(
                    binding.target_code in countries
                    and binding.partner_code in countries,
                    "binding_country_dictionary",
                )
                exporter, importer = (
                    (binding.partner_code, binding.target_code)
                    if binding.flow == "import"
                    else (binding.target_code, binding.partner_code)
                )
                require(
                    (native["exporter_code"], native["importer_code"])
                    == (exporter, importer),
                    "binding_direction",
                )
            elif item.source_id == "un_comtrade":
                reporter, partner = (
                    (binding.target_code, binding.partner_code)
                    if item.role == "reporter"
                    else (binding.partner_code, binding.target_code)
                )
                require(
                    bool(reporter)
                    and bool(partner)
                    and bool(binding.native_flow)
                    and (
                        native["reporter_code"],
                        native["partner_code"],
                        native["flow_code"],
                    )
                    == (reporter, partner, binding.native_flow),
                    "binding_direction",
                )
            else:
                require(binding.flow == "import", "binding_direction")
            # Reviewed country/direction bindings are retained alongside the complete
            # source-native row; native units and valuation cannot be overwritten.
            period = str(native.get("period", native.get("year", "")))
            require(period[:4] == str(binding.year), "binding_period")
            require(
                str(
                    native.get(
                        "tariff_code",
                        native.get("product_code", native.get("hs_code", "")),
                    )
                )
                == binding.product_scope,
                "binding_product",
            )
            currency = str(
                native.get(
                    "currency", "QAR" if item.role == "portal" else binding.currency
                )
            )
            require(currency == binding.currency, "binding_currency")
            revision = str(
                native.get(
                    "hs_revision", native.get("classification_revision", "unknown")
                )
            )
            require(revision == binding.hs_revision, "binding_revision")
            classification = str(native.get("classification", binding.classification))
            require(classification == binding.classification, "binding_classification")
            value = native.get("value_qar", native.get("value"))
            value_text = str(value) if value is not None else None
            if value_text is not None:
                from eii_custodian.publicdata.fetch.decimals import exact_decimal

                exact_decimal(
                    value_text, total_digits=1000, fractional_digits=1000, signed=False
                )
            native = json.loads(
                json.dumps(
                    native, default=lambda v: str(v) if isinstance(v, Decimal) else v
                )
            )
            identifier = ":".join(key)
            row_receipt = str(
                native.get("receipt_sha256", native.get("member_sha256", receipt_hash))
            )
            require(digest_ok(row_receipt), "input_receipt")
            figure = TradeFigure(
                identifier,
                item.source_id,
                str(native.get("source_version", source_version)),
                item.role,
                binding.partner,
                binding.flow,
                binding.year,
                (period,),
                classification,
                revision,
                binding.product_scope,
                binding.coverage_key,
                currency,
                str(native.get("unit", native.get("value_unit", "QAR"))),
                binding.scale,
                str(native["valuation_basis"]),
                value_text,
                (item.selected_hash, row_receipt, binding.evidence_sha256),
            )
            result.append(
                ComparisonInput(
                    figure,
                    table,
                    str(index),
                    item.selected_hash,
                    row_receipt,
                    binding.evidence_sha256,
                    native,
                )
            )
    require(
        used == {(b.source_id, b.role, b.row_key) for b in selection.bindings},
        "unused_binding",
    )
    return tuple(result)


def _outputs(
    cache: Path, selection: Selection, comtrade_policy: Policy | None
) -> tuple[tuple[ComparisonInput, ...], tuple[PairResult, ...]]:
    inputs = _materialize(cache, selection, comtrade_policy)
    figures = comparison_figures(tuple(i.figure for i in inputs))
    aggregates = tuple(
        ComparisonInput(
            f,
            "pub_trade_comparison_input",
            f.input_id,
            "",
            "",
            "",
            {"input_lineage_refs": list(f.lineage)},
        )
        for f in figures
        if f.figure_kind == "calculated"
    )
    inputs += aggregates
    pairs = all_pairs(
        figures,
        tuple((s.source_id, s.role) for s in selection.inputs),
        selection.partners,
        selection.years,
        selection.flows,
        selection.scopes,
    )
    pairs = tuple(
        replace(
            p,
            known_cause_codes=tuple(
                c["code"]
                for c in selection.causes
                if (c["left_source"], c["right_source"], c["partner"], c["year"])
                == (p.left_source, p.right_source, p.partner, p.year)
            ),
            cause_evidence_refs=tuple(
                c["evidence_sha256"]
                for c in selection.causes
                if (c["left_source"], c["right_source"], c["partner"], c["year"])
                == (p.left_source, p.right_source, p.partner, p.year)
            ),
        )
        for p in pairs
    )
    return inputs, pairs


def _encoded(value: object) -> bytes:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def build_reconciliation(
    cache: Path, selection: Selection, *, comtrade_policy: Policy | None = None
) -> str:
    import hashlib
    import tempfile

    selection = Selection.from_mapping(asdict(selection))
    inputs, pairs = _outputs(cache, selection, comtrade_policy)
    directory = cache / "trade_reconciliation"
    directory.mkdir(parents=True, exist_ok=True)

    def refuse(reason: str) -> NoReturn:
        raise ValueError("trade_reconciliation " + reason)

    with tempfile.TemporaryDirectory(prefix=".stage-", dir=directory) as temporary:
        stage = Path(temporary)
        output = stage / "output.json"
        output.write_bytes(
            _encoded(
                {
                    "inputs": [asdict(i) for i in inputs],
                    "comparisons": [asdict(p) for p in pairs],
                }
            )
        )
        output_hash = file_hash(output)
        manifest = stage / "manifest.json"
        manifest.write_bytes(
            _encoded(
                {
                    "complete": True,
                    "commit_allowed": False,
                    "method": METHOD,
                    "selection": asdict(selection),
                    "selection_sha256": hashlib.sha256(
                        _encoded(asdict(selection))
                    ).hexdigest(),
                    "output_sha256": output_hash,
                    "input_count": len(inputs),
                    "comparison_count": len(pairs),
                    "owner_report": owner_report(selection, pairs),
                }
            )
        )
        selected = file_hash(manifest)
        publish_complete(output, directory / f"{output_hash}.json", refuse)
        publish_complete(manifest, directory / f"{selected}.manifest.json", refuse)
    return selected


def read_reconciliation(
    cache: Path, selected: str, *, comtrade_policy: Policy | None = None
) -> ReconciliationRelease:
    import hashlib
    import json

    require(digest_ok(selected), "selected_manifest")
    directory = cache / "trade_reconciliation"
    try:
        path = directory / f"{selected}.manifest.json"
        require(file_hash(path) == selected, "manifest_hash")
        manifest = json.loads(path.read_bytes())
        require(
            manifest["complete"] is True
            and manifest["commit_allowed"] is False
            and manifest["method"] == METHOD,
            "manifest_contract",
        )
        selection = Selection.from_mapping(manifest["selection"])
        require(
            hashlib.sha256(_encoded(asdict(selection))).hexdigest()
            == manifest["selection_sha256"],
            "selection_hash",
        )
        inputs, pairs = _outputs(cache, selection, comtrade_policy)
        output_hash = manifest["output_sha256"]
        require(digest_ok(output_hash), "output_hash")
        output = directory / f"{output_hash}.json"
        require(file_hash(output) == output_hash, "output_hash")
        expected = {
            "inputs": [asdict(i) for i in inputs],
            "comparisons": [asdict(p) for p in pairs],
        }
        require(output.read_bytes() == _encoded(expected), "recomputed_output")
        require(
            manifest["input_count"] == len(inputs)
            and manifest["comparison_count"] == len(pairs),
            "output_count",
        )
        require(
            manifest["owner_report"] == owner_report(selection, pairs), "owner_report"
        )
        return ReconciliationRelease(inputs, pairs, manifest)
    except (OSError, KeyError, TypeError):
        raise ValueError("trade_reconciliation selected_manifest_invalid") from None


def owner_report(selection: Selection, pairs: tuple[PairResult, ...]) -> dict[str, Any]:
    """Recorded causes describe differences, never explain an entire numeric gap."""
    return {
        "obstacles": list(selection.obstacles),
        "causes": list(selection.causes),
        "unknown_cause": True,
        "coverage_gaps": [
            {
                "partner": p.partner,
                "year": p.year,
                "flow": p.flow,
                "scope": p.scope,
                "left_source": p.left_source,
                "right_source": p.right_source,
                "mismatch_codes": list(p.mismatch_codes),
            }
            for p in pairs
            if p.mismatch_codes
        ],
    }


def load_selection(path: Path | None = None) -> Selection | None:
    import yaml

    target = (
        path
        or Path(__file__).resolve().parents[3] / "publicdata/trade_reconciliation.yaml"
    )
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
        if data == {"confirmed": False}:
            return None
        return Selection.from_mapping(data)
    except (OSError, TypeError, yaml.YAMLError):
        raise ValueError("trade_reconciliation selection_unreadable") from None
