"""Production public builders, each invoked through one named phase.

The independent inventory lives in assembly_inventory, never in this map. No
fixture graph mode, invented producer or source discovery is used here.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from .assembly import AssemblyError, Step, run_steps
from .assembly_intake import write_intake_evidence
from .assembly_inventory import INVENTORY, validate_inventory
from .assembly_io import bound_files, local, read_object, write_record
from .fetch.bounded import file_hash
from .fetch.registry import Entry, RegistryError, parse_yaml, read_yaml
from .fetch.snapshots import Snapshot, read_snapshot, reviewed_selections
from .fetch.transport import Transport
from .frame.build import FrameResult, build_public_frame, read_cached
from .trade_reconciliation import Selection


def _fsq_manifest(cache: Path, key: str, identity: str) -> tuple[Snapshot, str]:
    """Resolve one reviewed digest inside exactly one dated release namespace."""
    from .places_fsq.errors import PlacesFsqError
    from .places_fsq.releases import validate_release

    matches = sorted(local(cache, key).glob(f"*/manifests/index/{identity}.json"))
    if len(matches) != 1:
        raise AssemblyError("assembly_lineage_missing")
    directory = matches[0].parent.parent
    release = directory.parent.name
    try:
        validate_release(release)
    except PlacesFsqError:
        raise AssemblyError("assembly_lineage_missing") from None
    return read_snapshot(directory, identity), release


@dataclass
class Production:
    entries: tuple[Entry, ...]
    cache: Path
    review: Path
    root: Path
    transport: Transport
    clock: Callable[[], str]
    sleep: Callable[[float], None]
    seed: int
    environ: Mapping[str, str]
    fetcher: Callable[[], Any] | None = None
    reconciliation_selection: Selection | None = None
    selected: dict[str, str] = field(default_factory=dict)
    receipts: dict[str, dict[str, Any]] = field(default_factory=dict)
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    table_sources: dict[str, set[str]] = field(default_factory=dict)
    source_tables: dict[str, list[str]] = field(default_factory=dict)
    frame_result: FrameResult | None = None
    lines: list[str] = field(default_factory=list)
    fetched: Any = None
    files: dict[str, str] = field(default_factory=dict)
    data_files: dict[str, str] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)
    stamp: str = ""
    draw_exclusions: list[dict[str, Any]] = field(default_factory=list)
    intake_refusal: str = ""

    def adapters(self) -> dict[str, Callable[[], Mapping[str, str]]]:
        return {
            "intake_evidence": self.intake_evidence,
            "fetch_archive": self.fetch_archive,
            "investment_capture": self.investment_capture,
            "reviewed_selections": self.reviewed_selections,
            "frame": self.frame,
            "spine_graph": self.spine_graph,
            "additions": self.additions,
            "gis_property_singles": self.gis_property_singles,
            "fsq": self.fsq,
            "series_stage": self.series_stage,
            "heights": self.heights,
            "trade_reconciliation": self.trade_reconciliation,
            "busyness": self.busyness,
            "final_audit": self.final_audit,
            "draw": self.draw,
            "reports": self.reports,
        }

    def run(self) -> tuple[str, ...]:
        if type(self.seed) is not int:
            raise AssemblyError("figure_seed_invalid")
        adapters = self.adapters()
        validate_inventory(adapters)
        paths = [local(self.cache, path) for item in INVENTORY for path in item.outputs]
        graph = local(self.cache, "assembly/graph")
        for path in paths:
            path.unlink(missing_ok=True)
        if graph.exists():
            graph.rmdir()
        self.fetched = None
        self.lines.clear()
        self.files.clear()
        self.data_files.clear()
        self.tables.clear()
        self.source_tables.clear()
        self.table_sources.clear()
        self.receipts.clear()
        self.selected.clear()
        self.audit.clear()
        self.frame_result = None
        self.intake_refusal = ""
        # Persist the seed before the clock, review, cache or source reader.
        write_record(self.cache, "assembly/build.json", {"figure_seed": self.seed})
        self.stamp = self.clock()
        steps = tuple(
            Step(item.name, adapters[item.name], item.outputs) for item in INVENTORY
        )
        completed = run_steps(self.cache, steps)
        from .assembly_reports import require_complete

        require_complete(self.audit)
        return completed

    def record(self, phase: str, value: object) -> dict[str, str]:
        if not isinstance(value, dict):
            raise AssemblyError("assembly_output_invalid")
        fields = (
            "source_id",
            "publisher",
            "licence_id",
            "licence_basis",
            "retrieved_utc",
            "sha256",
            "fetch_url",
        )
        chain = {
            key: {field: receipt.get(field, "") for field in fields}
            for key, receipt in self.receipts.items()
        }
        result = write_record(
            self.cache,
            "assembly/" + phase + ".json",
            {
                "method": "public-assembly." + phase,
                "method_version": "1",
                "source_chain": chain,
                **value,
            },
        )
        self.files.update(result)
        return result

    def table(
        self, name: str, rows: Sequence[Mapping[str, Any]], sources: Sequence[str]
    ) -> None:
        if name in self.tables:
            raise AssemblyError("assembly_table_duplicate")
        if not sources or any(key not in self.receipts for key in sources):
            raise AssemblyError("assembly_lineage_missing")
        self.tables[name] = [dict(row) for row in rows]
        self.table_sources[name] = set(sources)
        for key in sources:
            self.source_tables.setdefault(key, []).append(name)

    def raw(
        self, entry: Entry, *, standard_json: bool = False, family_archive: bool = False
    ) -> Any:
        digest = self.selected.get(entry.key, "")
        decode = None
        if family_archive:
            from .singles.families import decode_family_archive

            decode = decode_family_archive
        from .fetch.own_run import is_own_run_entry, is_tender_entry, own_run_cache

        if is_tender_entry(entry) and not is_own_run_entry(entry):
            raise AssemblyError("snapshot_selection_invalid")

        source_cache = (
            own_run_cache(self.cache) if is_own_run_entry(entry) else self.cache
        )
        payload, receipt = read_cached(
            source_cache, entry, digest=digest, decode=decode
        )
        self.receipts[entry.key] = receipt
        if standard_json:
            return json.loads(
                read_snapshot(local(source_cache, entry.key), digest).body
            )
        return payload

    def needed_frame(self) -> FrameResult:
        if self.frame_result is None:
            raise AssemblyError("assembly_frame_incomplete")
        return self.frame_result

    def intake_evidence(self) -> dict[str, str]:
        document = read_yaml(self.review / "s2_t29_sources.yaml")
        if not isinstance(document, dict):
            raise AssemblyError("assembly_intake_invalid")
        try:
            return write_intake_evidence(
                self.cache,
                document,
                self.seed,
                self.stamp or self.clock(),
                awards_selected=any(
                    entry.source_id == "awards_owner_scrape" and not entry.skip_reason
                    for entry in self.entries
                ),
            )
        except AssemblyError as exc:
            if str(exc) not in {
                "assembly_input_refused",
                "assembly_intake_invalid",
                "assembly_intake_bound",
                "assembly_seed_mismatch",
            }:
                raise
            # Preserve the refusal; an independent portal read can still run
            # in full. The refused workbook never enters a successful assembly.
            self.intake_refusal = str(exc)
            return write_record(
                self.cache,
                "assembly/intake_evidence.json",
                {
                    "method": "assembly-intake.v1",
                    "awards": {"state": "refused", "reason": self.intake_refusal},
                },
            )

    def fetch_archive(self) -> dict[str, str]:
        if self.fetcher is None:
            raise AssemblyError("assembly_fetch_unbound")
        self.fetched = self.fetcher()
        self.lines.extend(self.fetched.lines)
        if self.fetched.failure is not None:
            raise AssemblyError("assembly_fetch_refused")
        if self.intake_refusal:
            raise AssemblyError(self.intake_refusal)
        from .fetch.own_run import is_own_run_entry

        if any(
            entry.kind == "paged_cards"
            and not entry.skip_reason
            and not is_own_run_entry(entry)
            for entry in self.entries
        ):
            raise AssemblyError("assembly_tender_pages_incomplete")
        return self.record(
            "fetch_archive",
            {
                "lines": self.fetched.lines,
                "manifests": self.fetched.manifests,
                "tender_archives": {},
            },
        )

    def investment_capture(self) -> dict[str, str]:
        from .fetch.build import _archive_investment_attempts
        from .investment_contracts import EvidenceAuditEntry

        if self.fetched is None:
            raise AssemblyError("assembly_fetch_unbound")
        from .assembly_milestones import load_milestones

        milestones = load_milestones(self.cache, self.entries)
        audits: list[EvidenceAuditEntry] = []
        failure = _archive_investment_attempts(
            self.entries,
            list(self.fetched.investment_attempts),
            self.cache,
            self.clock,
            self.lines,
            audit_history=True,
            audit_entries=audits,
            milestones=milestones,
        )
        if failure is not None:
            raise AssemblyError("assembly_investment_refused")
        return self.record(
            "investment_capture",
            {"attempts": self.fetched.investment_attempts, "audit": audits},
        )

    def reviewed_selections(self) -> dict[str, str]:
        selected = reviewed_selections(self.cache)
        from .confirm_s2_t13 import (
            completion_evidence,
            load_confirmation,
            own_run_pending,
        )
        from .fetch.own_run import is_own_run_entry, is_tender_entry, own_run_cache

        if any(
            is_tender_entry(entry) and not is_own_run_entry(entry)
            for entry in self.entries
        ):
            raise AssemblyError("snapshot_selection_invalid")

        confirmation = (
            load_confirmation(self.review / "s2_t13_confirmation.yaml")
            if any(is_own_run_entry(entry) for entry in self.entries)
            else None
        )
        if not selected and (
            not self.entries
            or not all(
                confirmation is not None and own_run_pending(confirmation, entry, None)
                for entry in self.entries
            )
        ):
            raise AssemblyError("snapshot_selection_invalid")
        keys = {entry.key for entry in self.entries}
        investment_keys = {
            entry.key + "/evidence"
            for entry in self.entries
            if entry.source_id in {"fdi_projects", "investqa_pages"}
        }
        keys |= investment_keys
        if set(selected) - keys:
            raise AssemblyError("snapshot_selection_invalid")
        from .assembly_native import NATIVE_SOURCES, read_native

        for entry in self.entries:
            if entry.source_id in NATIVE_SOURCES and entry.key in selected:
                read_native(self, entry, selected[entry.key])
                continue
            if entry.skip_reason or entry.kind in {"citation_only", "besttime"}:
                continue
            if entry.key not in selected:
                if confirmation is not None and own_run_pending(
                    confirmation, entry, None
                ):
                    continue
                raise AssemblyError("snapshot_selection_invalid")
            source_cache = (
                own_run_cache(self.cache) if is_own_run_entry(entry) else self.cache
            )
            directory = local(source_cache, entry.key)
            stored_key = entry.key
            if entry.key in {"places_ovt", "bldg_ovt"}:
                stored_key = entry.key + "/listing"
                directory = local(self.cache, stored_key)
            if entry.key == "places_fsq/copy":
                snapshot, _ = _fsq_manifest(self.cache, entry.key, selected[entry.key])
            else:
                snapshot = read_snapshot(directory, selected[entry.key])
            if (
                snapshot.sidecar.get("key") != stored_key
                or snapshot.sidecar.get("source_id") != entry.source_id
            ):
                raise AssemblyError("assembly_lineage_missing")
            self.receipts[entry.key] = snapshot.sidecar
            if is_own_run_entry(entry):
                assert confirmation is not None
                completion_evidence(confirmation, entry, snapshot.sidecar)
                from .assembly_tenders import verify_archive_terms, verify_intake_match

                verify_archive_terms(snapshot.body, snapshot.sidecar)
                verify_intake_match(
                    self.cache, snapshot.body, self.stamp or self.clock()
                )
            if entry.source_id in {"fdi_projects", "investqa_pages"}:
                from .assembly_native import read_investment

                evidence_identity = selected.get(entry.key + "/evidence")
                if evidence_identity is None:
                    raise AssemblyError("assembly_investment_review_missing")
                read_investment(self, entry, selected[entry.key], evidence_identity)
        self.selected = selected
        from .investment_build import page_public_totals

        return self.record(
            "reviewed_selections",
            {
                "selected": self.selected,
                "tables": self.tables.copy(),
                "page_public_totals": page_public_totals(
                    self.tables.get("pub_investqa_page", [])
                ),
            },
        )

    def frame(self) -> dict[str, str]:
        from .building_inputs import (
            BUILDING_MANIFEST_RELATIVE,
            BuildingError,
            invalidate_buildings,
            verify_building_manifest,
        )
        from .frame.municipality_output import (
            MUNICIPALITY_OUTPUT,
            write_municipality_output,
        )
        from .heights.model import BUILDINGS_RELATIVE
        from .places.integrate import areas_before_stage

        invalidate_buildings(self.cache)
        areas_before_stage(self.cache, self.lines, self.review)
        try:
            result = build_public_frame(
                self.cache,
                self.entries,
                self.review,
                selections=self.selected,
                build_date=datetime.fromisoformat(
                    self.stamp or self.clock().replace("Z", "+00:00")
                ).date(),
            )
        except BuildingError as exc:
            self.lines.append(f"FAIL buildings check={exc.name}")
            if exc.name == "building_frame_absent":
                raise AssemblyError("assembly_frame_incomplete") from None
            raise
        if any(
            not result.tables.get(name)
            for name in ("municipality", "zone", "district", "grid_cell")
        ):
            raise AssemblyError("assembly_frame_incomplete")
        self.frame_result = result
        building = local(self.cache.parent, BUILDINGS_RELATIVE)
        if not building.is_file():
            raise AssemblyError("assembly_buildings_incomplete")
        verify_building_manifest(self.cache, self.entries, self.selected, building)
        building_paths = {
            name: file_hash(local(self.cache.parent, name))
            for name in (BUILDINGS_RELATIVE, BUILDING_MANIFEST_RELATIVE)
        }
        self.data_files.update(building_paths)
        write_municipality_output(
            self.cache, result.tables["municipality"], result.sources
        )
        paths = {
            MUNICIPALITY_OUTPUT.as_posix(): file_hash(self.cache / MUNICIPALITY_OUTPUT)
        }
        for filename in (
            "pub_place.jsonl",
            "pub_place_verification.jsonl",
            "place_points.json",
            "build_report.json",
            "flagship_check.json",
        ):
            name = "places_s2_t06/" + filename
            path = local(self.cache, name)
            if not path.is_file():
                raise AssemblyError("assembly_places_incomplete")
            paths[name] = file_hash(path)
        self.files.update(paths)
        # Only frame-returned tables are credited; registry declarations alone
        # cannot supply a released table or a source-to-table edge.
        for name, rows in result.tables.items():
            sources = [
                e.key
                for e in self.entries
                if e.source_id in result.sources and name in e.release_tables
            ]
            if sources:
                self.table(name, rows, sources)
        place_keys = tuple(
            e.key
            for e in self.entries
            if e.source_id == "places_ovt" and e.key in self.receipts
        )
        if place_keys:
            self.table("pub_place", self.read_places(), place_keys)
            verification = [
                json.loads(line)
                for line in local(
                    self.cache, "places_s2_t06/pub_place_verification.jsonl"
                )
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.table("pub_place_verification", verification, place_keys)
        building_keys = [
            e.key
            for e in self.entries
            if e.source_id == "bldg_ovt"
            and e.key in self.receipts
            and "gazetteer" in e.release_tables
        ]
        if "gazetteer" in self.tables:
            for key in building_keys:
                self.table_sources["gazetteer"].add(key)
                self.source_tables.setdefault(key, []).append("gazetteer")
        return self.record(
            "frame",
            {
                "tables": {
                    **result.tables,
                    **{
                        name: self.tables[name]
                        for name in ("pub_place", "pub_place_verification")
                        if name in self.tables
                    },
                },
                "sources": result.sources,
                "report": result.report,
                "files": paths,
                "data_files": building_paths,
            },
        )

    def spine_graph(self) -> dict[str, str]:
        from .review.activity import (
            SpineError,
            basket_membership,
            load_activity_inputs,
            read_activity_rows,
        )
        from .review.graph import build_graph, read_allowlist, write_graph

        activities, _, _ = read_activity_rows(self.cache, self.entries, self.selected)
        try:
            baskets_bytes = (self.review / "baskets.yaml").read_bytes()
            baskets = parse_yaml(baskets_bytes)
            playbook, suppliers = basket_membership(baskets, activities)
        except (SpineError, OSError, RegistryError, KeyError, TypeError) as error:
            raise AssemblyError("assembly_membership_invalid") from error
        inputs = load_activity_inputs(
            self.cache,
            playbook,
            supplier_membership=suppliers,
            registry=self.entries,
            review_path=self.review / "activity_spine.csv",
            selections=self.selected,
        )
        places = self.read_places()
        categories = tuple(
            sorted({str(row["category"]) for row in places if row.get("category")})
        )
        graph = build_graph(
            inputs.spine,
            inputs.activities,
            inputs.classes,
            read_allowlist(self.review / "category_allowlist.csv"),
            categories,
            self.entries,
            mode="release",
        )
        directory = local(self.cache, "assembly/graph")
        # The graph writer refuses replacement; a rebuild uses its own staged
        # output and the existing complete directory is never taken as evidence.
        if directory.exists():
            raise AssemblyError("assembly_graph_exists")
        node, edge = write_graph(
            graph, directory, registry=self.entries, mode="release"
        )
        result = self.record(
            "spine_graph",
            {
                "spine": inputs.spine,
                "membership": {
                    "playbook_codes": playbook,
                    "supplier_codes": suppliers.codes,
                    "supplier_classes": sorted({code[:4] for code in suppliers.codes}),
                    "baskets_sha256": sha256(baskets_bytes).hexdigest(),
                },
                "manifest": inputs.manifest,
                "left_out": inputs.left_out,
            },
        )
        result.update(
            {p.relative_to(self.cache).as_posix(): file_hash(p) for p in (node, edge)}
        )
        self.files.update(result)
        return result

    def read_places(self) -> list[dict[str, Any]]:
        name = "places_s2_t06/pub_place.jsonl"
        if name not in self.files:
            raise AssemblyError("assembly_places_incomplete")
        bound_files(self.cache, {name: self.files[name]})
        rows = [
            json.loads(line)
            for line in local(self.cache, name).read_text(encoding="utf-8").splitlines()
        ]
        if any(not isinstance(row, dict) for row in rows):
            raise AssemblyError("assembly_places_incomplete")
        return rows

    def additions(self) -> dict[str, str]:
        from .additions.build import build_additions
        from .additions.common import ADDITION_FAMILIES

        selected = {
            e.key: self.selected[e.key]
            for e in self.entries
            if e.source_id in ADDITION_FAMILIES and not e.skip_reason
        }
        output = build_additions(
            self.cache,
            self.entries,
            selected,
            self.review,
            self.review,
            local(self.cache, "additions"),
        )
        manifest = read_object(output, "manifest.json")
        files = {}
        for item in manifest["tables"]:
            name = "additions/current/tables/" + item["name"] + ".parquet"
            files[name] = item["sha256"]
        bound_files(self.cache, files)
        if manifest["pending_slugs"]:
            raise AssemblyError("assembly_additions_pending")
        from .review.cache_fixture import read_parquet

        names = []
        for item in manifest["tables"]:
            name = item["name"]
            rows = read_parquet(
                local(
                    self.cache, "additions/current/tables/" + name + ".parquet"
                ).read_bytes()
            )
            sources = tuple(sorted({str(row["source_key"]) for row in rows}))
            if not sources:
                sources = tuple(sorted(selected))
            self.table(name, rows, sources)
            names.append(name)
        self.files.update(files)
        return self.record(
            "additions",
            {
                "manifest": manifest,
                "files": files,
                "tables": {name: self.tables[name] for name in names},
            },
        )

    def gis_property_singles(self) -> dict[str, str]:
        from .assembly_layers import build_layers

        before = dict(self.tables)
        build_layers(self)
        names = {
            name for name, rows in self.tables.items() if before.get(name) is not rows
        }
        return self.record(
            "gis_property_singles",
            {
                "tables": {name: self.tables[name] for name in sorted(names)},
                "source_tables": self.source_tables,
            },
        )

    def fsq(self) -> dict[str, str]:
        from .places_fsq.assemble import build_places
        from .places_fsq.constants import ATTRIBUTION, RELEASE_KEY
        from .places_fsq.policy import PlaceStandIn, assert_policy, load_mapping
        from .places_fsq.select import FRAME_BOX

        row = next((e for e in self.entries if e.key == RELEASE_KEY), None)
        if row is None or row.key not in self.selected:
            raise AssemblyError("assembly_fsq_missing")
        snapshot, release = _fsq_manifest(self.cache, row.key, self.selected[row.key])
        manifest = json.loads(snapshot.body)
        if manifest.get("release") != release:
            raise AssemblyError("assembly_fsq_missing")
        assert_policy(self.review / "places_fsq_policy.yaml")
        paths = {}
        hashes = {}
        for item in manifest["files"]:
            name, digest = item["name"], item["sha256"]
            if name in paths:
                raise AssemblyError("assembly_output_invalid")
            paths[name] = read_snapshot(
                local(self.cache, f"{row.key}/{release}/files"), digest
            ).path
            hashes[name] = digest
        places = self.read_places()
        standins = tuple(
            PlaceStandIn(
                str(r["place_id"]),
                str(r["name"]),
                r["name_ar"],
                float(r["lon"]),
                float(r["lat"]),
                False,
            )
            for r in places
        )
        categories = frozenset(str(r["category"]) for r in places if r.get("category"))
        result = build_places(
            files=paths,
            expected_sha256=hashes,
            frame=FRAME_BOX,
            grid=self.needed_frame().tables["grid_cell"],
            places=standins,
            mapping=load_mapping(self.review / "places_fsq_categories.csv", categories),
            labels=(),
            min_edit_distance=1,
            release=release,
            attribution=manifest["attribution"],
            receipt_sha256=snapshot.sha256,
        )
        self.table("pub_place_fsq", [asdict(r) for r in result.rows], (row.key,))
        if result.release != release or manifest["attribution"] != ATTRIBUTION:
            raise AssemblyError("assembly_fsq_missing")
        return self.record(
            "fsq",
            {
                "tables": {"pub_place_fsq": self.tables["pub_place_fsq"]},
                "coverage": result.coverage,
                "release": result.release,
                "receipt_sha256": snapshot.sha256,
            },
        )

    def series_stage(self) -> dict[str, str]:
        from .series.figures import build_series
        from .series.frame import frame_municipalities
        from .series.parse import FIELD_MAP
        from .series.support import SUPPORT_KEYS

        selected = {
            e.source_id: self.selected[e.key]
            for e in self.entries
            if e.source_id in FIELD_MAP and not e.skip_reason
        }
        result = build_series(
            self.cache,
            self.entries,
            selected,
            municipalities=frame_municipalities(self.cache)
            if any(source.startswith("lic_") for source in selected)
            else (),
            supporting_selected={
                key: self.selected[key] for key in SUPPORT_KEYS if key in self.selected
            },
        )
        from .series.figures import validate_figure

        names = sorted(
            {table for source in selected for table, _ in FIELD_MAP[source].values()}
        )
        produced = {}
        row_sources = {}
        by_source = {entry.source_id: entry for entry in self.entries}
        for name in names:
            relative = "series/internal/" + name + ".json"
            path = local(self.cache, relative)
            if not path.is_file():
                continue
            envelope = read_object(self.cache, relative)
            validate_figure(envelope)
            keys = []
            for source in envelope["source_chain"]:
                entry = by_source[source["source_id"]]
                snapshot = read_snapshot(
                    local(self.cache, entry.key), self.selected[entry.key]
                )
                if source["sha256"] != snapshot.sha256:
                    raise AssemblyError("assembly_lineage_missing")
                self.receipts[entry.key] = snapshot.sidecar
                keys.append(entry.key)
            self.table(name, envelope["rows"], tuple(keys))
            self.files[relative] = file_hash(path)
            produced[name] = self.tables[name]
            row_sources[name] = envelope["row_sources"]
        output = self.record(
            "series_stage", {**result, "tables": produced, "row_sources": row_sources}
        )
        if result["mismatch"] or result["missing"]:
            raise AssemblyError("assembly_regression_refused")
        return output

    def heights(self) -> dict[str, str]:
        from .building_inputs import BUILDING_MANIFEST_RELATIVE
        from .heights.model import (
            BUILDINGS_RELATIVE,
            HEIGHTS_FILE,
            HEIGHTS_RELATIVE,
            MANIFEST_FILE,
        )
        from .heights.step import build_heights

        # The existing asset convention is relative to the data directory.
        building = local(self.cache.parent, BUILDINGS_RELATIVE)
        output = local(self.cache.parent, HEIGHTS_RELATIVE)
        # Earlier outputs are removed here, outside the producer, so only files
        # this invocation wrote can be hashed and recorded as built.
        for name in (HEIGHTS_FILE, MANIFEST_FILE):
            (output / name).unlink(missing_ok=True)
        build_heights(
            self.cache,
            self.entries,
            building,
            output,
            self.lines,
            terms_attempts=tuple(self.fetched.terms_attempts) if self.fetched else (),
            selections=self.selected,
        )
        if not all((output / name).is_file() for name in (HEIGHTS_FILE, MANIFEST_FILE)):
            raise AssemblyError("assembly_heights_incomplete")
        paths = {
            name: file_hash(output / name) for name in (HEIGHTS_FILE, MANIFEST_FILE)
        }
        self.data_files.update(
            {HEIGHTS_RELATIVE + "/" + name: digest for name, digest in paths.items()}
        )
        building_paths = {
            name: file_hash(local(self.cache.parent, name))
            for name in (BUILDINGS_RELATIVE, BUILDING_MANIFEST_RELATIVE)
        }
        self.data_files.update(building_paths)
        return self.record(
            "heights",
            {"state": "built", "files": paths, "building_files": building_paths},
        )

    def trade_reconciliation(self) -> dict[str, str]:
        from .trade_reconciliation import build_reconciliation, load_selection

        selection = self.reconciliation_selection
        if selection is None:
            selection = load_selection()
        if selection is None:
            return self.record(
                "trade_reconciliation",
                {"state": "NO_DATA", "reason": "comparison_selection_absent"},
            )
        reason = selection.comparison_block_reason()
        if reason is not None:
            return self.record(
                "trade_reconciliation", {"state": "NO_DATA", "reason": reason}
            )
        from .comtrade.policy import Policy

        policy = next(
            (
                e.comtrade_policy
                for e in self.entries
                if isinstance(e.comtrade_policy, Policy)
            ),
            None,
        )
        digest = build_reconciliation(self.cache, selection, comtrade_policy=policy)
        manifest_name = "trade_reconciliation/" + digest + ".manifest.json"
        manifest = read_object(self.cache, manifest_name)
        self.files[manifest_name] = digest
        self.files["trade_reconciliation/" + manifest["output_sha256"] + ".json"] = (
            manifest["output_sha256"]
        )
        bound_files(self.cache, self.files)
        return self.record("trade_reconciliation", {"state": "built", "sha256": digest})

    def busyness(self) -> dict[str, str]:
        from .busyness.build import build_busyness
        from .busyness.security import assert_clean

        results = {}
        for entry in self.entries:
            if entry.kind == "besttime" and not entry.skip_reason:
                results[entry.key] = build_busyness(
                    entry,
                    self.transport,
                    self.cache,
                    self.clock,
                    self.environ,
                    self.review,
                )
        tables = {}
        from .fetch.receipts import sha256_hex

        for entry in self.entries:
            if entry.key not in results:
                continue
            name = entry.key + "/manifest.json"
            manifest_body = local(self.cache, name).read_bytes()
            if sha256_hex(manifest_body.removesuffix(b"\n")) != results[entry.key]:
                raise AssemblyError("assembly_output_invalid")
            manifest = read_object(self.cache, name)
            snapshot = read_snapshot(
                local(self.cache, entry.key), manifest["table_sha256"]
            )
            self.receipts[entry.key] = snapshot.sidecar
            rows = [
                json.loads(line) for line in snapshot.body.decode("utf-8").splitlines()
            ]
            self.table("pub_venue_busyness", rows, (entry.key,))
            tables["pub_venue_busyness"] = self.tables["pub_venue_busyness"]
            self.files[name] = file_hash(local(self.cache, name))
            self.files[snapshot.path.relative_to(self.cache).as_posix()] = (
                snapshot.sha256
            )
        assert_clean(self.environ, self.lines)
        return self.record("busyness", {"manifests": results, "tables": tables})

    def final_audit(self) -> dict[str, str]:
        from .assembly_reports import gather_audit

        bound_files(self.cache, self.files)
        bound_files(self.cache.parent, self.data_files)
        self.audit = gather_audit(self)
        return self.record("final_audit", self.audit)

    def draw(self) -> dict[str, str]:
        from .assembly_reports import draw_tables
        from .draw import draw

        figures = draw(
            draw_tables(self), self.seed, local(self.cache, "assembly/build.json")
        )
        output = self.record(
            "draw",
            {
                "figure_ids": [f.figure_id for f in figures],
                "figure_seed": self.seed,
                "excluded_tables": self.draw_exclusions,
            },
        )
        output.update(
            self.record(
                "draw_values",
                {"seed": self.seed, "figures": [asdict(f) for f in figures]},
            )
        )
        output.update(
            write_record(
                self.cache,
                "assembly/draw_review_values.json",
                [asdict(f) for f in figures],
            )
        )
        output["assembly/build.json"] = file_hash(
            local(self.cache, "assembly/build.json")
        )
        self.files.update(output)
        return output

    def reports(self) -> dict[str, str]:
        from .assembly_reports import write_reports

        return write_reports(self)
