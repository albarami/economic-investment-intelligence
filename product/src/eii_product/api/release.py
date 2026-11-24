"""Verified mounted Public release and emitted-fact source-chain projections.

The index is process-local emission evidence, never a fact table or an ID decoder.
Only the fixed layer/card readers and playbook answers register companions;
an answer's facts resolve only for the admitted session that received it.
GET accepts no inputs.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse

from eii_core.facts import METRIC_KEYS, Fact, validate_chain
from eii_product.api.area_context import trusted_seat, trusted_shapes
from eii_product.api.playbooks import PlaybookRoute, refusal
from eii_product.api.results import PublicResult, error_response
from eii_product.assistant.playbooks.models import Bundle
from eii_product.store.loader import _parquet_rows
from eii_product.store.protocol import ReleaseStore
from eii_product.store.receipt import read_receipt
from eii_product.store.release_check import (
    RELEASE_MANIFEST_COLUMNS,
    check_release,
    digest_rows,
    manifest_rows,
)
from eii_product.tools.public_context_tools import read

FACT_ID = re.compile(r"f_[0-9a-f]{32}\Z")


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Table(Closed):
    releaseId: str
    tableName: str


class Summary(Closed):
    release_id: str
    release_kind: Literal["public_only"]
    rules_version_id: str
    tables: list[Table]
    hour_keys: list[str]
    day_keys: list[str]
    month_keys: list[str]
    basemap_url: Literal["/tiles/basemap.pmtiles"] | None


class Source(Closed):
    sourceId: str
    kind: Literal["public_dataset", "public_document", "reviewed_config"]
    inputClass: Literal["public"]
    publisher: str
    datasetOrPage: str
    licenceOrTerms: str
    retrievalDate: str
    sha256: str


class Lineage(Closed):
    lineageId: str
    releaseId: str
    tableName: str
    method: str
    methodVersion: str
    sourceIds: list[str]
    inputClasses: list[Literal["public"]]


class CitedLineage(Lineage):
    rowRetrievalDate: str
    providerUpdatedOn: str | None


class Binding(Closed):
    metricKey: str
    presentation: Literal["ordinary"] = "ordinary"
    qualifiers: dict[str, str]


class Chain(Closed):
    fact_id: str
    release_id: str
    lineage: Lineage | CitedLineage
    sources: list[Source]
    binding: Binding


def qualifiers(entry: Mapping[str, Any]) -> dict[str, str]:
    """Copy a card entry's selection qualifiers beside its Fact."""
    return {
        k: str(entry[v])
        for k, v in (
            ("day_of_week", "weekday"),
            ("hour", "hour"),
            ("age_band", "age_band"),
            ("sex", "sex"),
        )
        if v in entry
    }


class MountedRelease:
    """Bind checked files, completed loader receipt and actual named store reads."""

    def __init__(
        self,
        store: ReleaseStore,
        folder: Path,
        *,
        basemap_name: Literal["basemap.pmtiles"] | None = None,
    ):
        if basemap_name not in (None, "basemap.pmtiles"):
            raise ValueError("mount_unverified")
        self.store = store
        self.basemap_url: Literal["/tiles/basemap.pmtiles"] | None = (
            "/tiles/basemap.pmtiles" if basemap_name is not None else None
        )
        self.emitted: dict[str, tuple[Fact, Binding]] = {}
        # Playbook answer facts, by the admitted session's seat.
        self.answered: dict[str, dict[str, tuple[Fact, Binding]]] = {}
        self.citations: dict[str, dict[str, Any]] = {}
        try:
            checked = check_release(folder)
            identity = checked.document["release_id"]
            if (
                identity != store.release_id
                or checked.document["release_kind"] != "public_only"
            ):
                raise ValueError("mount_unverified")
            receipt = read_receipt(folder, store.release_id)
            self.manifest = manifest_rows(checked.document)
            if set(cast(list[str], receipt["tables"])) != {
                r["table_name"] for r in self.manifest
            } | {"release_manifest"}:
                raise ValueError("mount_unverified")
            names = {str(r["table_name"]) for r in self.manifest} | {"release_manifest"}
            counts = {r["table_name"]: r["row_count"] for r in self.manifest}
            counts["release_manifest"] = len(self.manifest)
            digests = receipt.get("digests")
            if (
                receipt.get("engines") != ["embedded", "postgres"]
                or receipt.get("row_counts") != counts
                or not isinstance(digests, dict)
                or set(digests) != names
                or any(
                    not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{64}", v) is None
                    for v in digests.values()
                )
            ):
                raise ValueError("mount_unverified")
            self.rows = {
                name: _parquet_rows(
                    folder / ("tables/" + name + ".parquet"), checked.schemas[name]
                )
                for name in ("fact_lineage", "source_registry")
            }
            for name, rows in self.rows.items():
                key = (
                    ("lineage_id", "source_id")
                    if name == "fact_lineage"
                    else ("source_id",)
                )
                if digest_rows(rows, checked.schemas[name], key) != digests[name]:
                    raise ValueError("mount_unverified")
            if (
                digest_rows(self.manifest, RELEASE_MANIFEST_COLUMNS, ("table_name",))
                != digests["release_manifest"]
            ):
                raise ValueError("mount_unverified")
            self.summary()
        except Exception:
            raise ValueError("mount_unverified") from None

    def summary(self) -> dict[str, Any]:
        rows = read(self.store, "public_release_manifest")
        expected = sorted(self.manifest, key=lambda r: str(r["table_name"]))
        if rows != expected or not rows:
            raise ValueError("mount_unverified")
        months = (
            read(self.store, "layer_night_lights_months")
            if any(r["table_name"] == "pub_night_lights" for r in rows)
            else []
        )
        return Summary(
            release_id=self.store.release_id,
            release_kind=rows[0]["release_kind"],
            rules_version_id=rows[0]["rules_version_id"],
            tables=[
                Table(releaseId=r["release_id"], tableName=r["table_name"])
                for r in rows
            ],
            hour_keys=[],
            day_keys=[],
            month_keys=[r["period"] for r in months],
            basemap_url=self.basemap_url,
        ).model_dump()

    def project(self, fact: Fact, binding: Binding) -> dict[str, Any]:
        if (
            fact.release_id != self.store.release_id
            or fact.provenance != "public"
            or fact.input_classes != ["public"]
        ):
            raise ValueError("chain_refused")
        if binding.metricKey not in METRIC_KEYS:
            raise ValueError("metric_unbound")
        summary = self.summary()
        lines = read(self.store, "sector_facts_lineage", lineage=fact.lineage_ref)
        sources = read(
            self.store,
            "sector_facts_sources",
            sources=sorted({r["source_id"] for r in lines}),
        )
        if validate_chain(fact.lineage_ref, lines, sources) is not None or not lines:
            raise ValueError("chain_refused")
        for name, found, key in (
            ("fact_lineage", lines, "lineage_id"),
            ("source_registry", sources, "source_id"),
        ):
            for row in found:
                original = next(
                    (
                        r
                        for r in self.rows[name]
                        if r[key] == row[key]
                        and (
                            name != "fact_lineage" or r["source_id"] == row["source_id"]
                        )
                    ),
                    None,
                )
                if original is None or any(
                    original.get(k) != v for k, v in row.items()
                ):
                    raise ValueError("chain_refused")
        names = {r["table_name"] for r in lines}
        transforms = {r["transform"] for r in lines}
        if (
            len(names) != 1
            or len(transforms) != 1
            or any(r["input_class"] != "public" for r in lines)
        ):
            raise ValueError("chain_refused")
        table = next(iter(names))
        if not any(r["tableName"] == table for r in summary["tables"]):
            raise ValueError("chain_refused")
        method, version = next(iter(transforms)).rsplit("@", 1)
        lineage_fields = dict(
            lineageId=fact.lineage_ref,
            releaseId=fact.release_id,
            tableName=table,
            method=method,
            methodVersion=version,
            sourceIds=sorted({r["source_id"] for r in lines}),
            inputClasses=["public"],
        )
        lineage: Lineage | CitedLineage = Lineage.model_validate(lineage_fields)
        if binding.metricKey == "venue_busyness_index":
            citation = self.citations.get(fact.fact_id)
            if citation is None or citation["rowRetrievalDate"] != fact.period:
                raise ValueError("row_citation_missing")
            lineage = CitedLineage.model_validate({**lineage_fields, **citation})
        return Chain(
            fact_id=fact.fact_id,
            release_id=fact.release_id,
            lineage=lineage,
            sources=[
                Source(
                    sourceId=r["source_id"],
                    kind=r["kind"],
                    inputClass="public",
                    publisher=r["publisher"],
                    datasetOrPage=r["title"],
                    licenceOrTerms=r["licence"],
                    retrievalDate=str(r["retrieved_on"]),
                    sha256=r["sha256"],
                )
                for r in sources
            ],
            binding=binding,
        ).model_dump()

    def checked(
        self, facts: list[tuple[Fact, Binding]]
    ) -> dict[str, tuple[Fact, Binding]]:
        """Validate the whole response before any fact is admitted."""
        for fact, binding in facts:
            self.project(fact, binding)
        return {fact.fact_id: (fact, binding) for fact, binding in facts}

    def prepare(self, facts: list[tuple[Fact, Binding]]) -> Callable[[], None]:
        """Validate the whole response; the returned call admits every fact."""
        prepared = self.checked(facts)
        return lambda: self.emitted.update(prepared)

    def find(self, fact_id: str, seat: str | None) -> tuple[Fact, Binding] | None:
        """A process-wide fact, or one answered to this verified session only."""
        found = self.emitted.get(fact_id)
        if found is None and seat is not None:
            found = self.answered.get(seat, {}).get(fact_id)
        return found

    def register(self, facts: list[tuple[Fact, Binding]]) -> None:
        self.prepare(facts)()

    def layer(self, body: dict[str, Any]) -> dict[str, Any]:
        from eii_product.api.public_layers import METRICS

        companions: dict[str, str] = {}
        for layer in body["payload"]["layers"]:
            for feature in layer["features"]:
                if feature["metric_key"] != METRICS.get(layer["key"]):
                    raise ValueError("metric_unbound")
                companions[feature["fact_id"]] = feature["metric_key"]
                for slot, metric in (
                    ("capex_fact_id", "fdi_capex"),
                    ("jobs_fact_id", "fdi_jobs"),
                    ("lon_fact_id", "fdi_location"),
                    ("lat_fact_id", "fdi_location"),
                ):
                    if feature.get(slot):
                        companions[feature[slot]] = metric
                for segments in feature.get("field_segments", {}).values():
                    for segment in segments:
                        if segment["kind"] == "reference":
                            companions[segment["recordId"]] = "fdi_field"
                if feature.get("announced"):
                    companions[feature["announced"]["recordId"]] = "fdi_field"
            for options in body["payload"].get("filter_options", {}).values():
                for option in options:
                    for segment in option["label"]:
                        if segment["kind"] == "reference":
                            companions[segment["recordId"]] = "fdi_field"
        self.register(
            [
                (
                    Fact.model_validate(f),
                    Binding(metricKey=companions.get(f["fact_id"], ""), qualifiers={}),
                )
                for f in body["facts"]
            ]
        )
        return body

    def prepare_card(self, result: PublicResult) -> Callable[[], None]:
        """Validate before the ledger transaction; admit only after its commit."""
        metrics = {
            "night_lights": "night_lights_radiance",
            "population_age_sex": "population_grid_people",
            "venue_busyness": "venue_busyness_index",
        }
        entries = cast(list[dict[str, Any]], (result.payload or {}).get("entries", []))
        facts = []
        for fact in result.facts:
            entry = next((e for e in entries if e.get("fact_id") == fact.fact_id), {})
            if result.tool == "venue_busyness":
                if "retrieved_on" not in entry or "provider_updated_on" not in entry:
                    raise ValueError("row_citation_missing")
                self.citations[fact.fact_id] = dict(
                    rowRetrievalDate=entry["retrieved_on"],
                    providerUpdatedOn=entry["provider_updated_on"],
                )
            facts.append(
                (
                    fact,
                    Binding(
                        metricKey=metrics[result.tool], qualifiers=qualifiers(entry)
                    ),
                )
            )
        return self.prepare(facts)

    def prepare_answer(self, bundle: Bundle) -> Callable[[str], None]:
        """Bind a playbook answer's facts as its cards' readers bind them; the
        returned call admits them for the admitted session `seat` only."""
        entries = [
            entry
            for step in bundle.steps
            if isinstance(step["payload"], dict)
            for entry in step["payload"].get("entries", [])
        ]
        prepared = self.checked(
            [
                (
                    evidence.fact,
                    Binding(
                        metricKey=evidence.metric_key,
                        qualifiers=qualifiers(
                            next((e for e in entries if e.get("fact_id") == key), {})
                        ),
                    ),
                )
                for key, evidence in bundle.facts.items()
            ]
        )
        return lambda seat: self.answered.setdefault(seat, {}).update(prepared)

    def card(self, result: PublicResult) -> PublicResult:
        """Internal proof reader; HTTP admission goes through respond's commit."""
        self.prepare_card(result)()
        return result


SEAT = Depends(trusted_seat)


def build_release_router(mount: MountedRelease | None) -> APIRouter:
    router = APIRouter(route_class=PlaybookRoute)

    async def invalid(request: Request) -> bool:
        return bool(request.query_params or await request.body())

    def response(body: Mapping[str, Any], model: type[Closed]) -> JSONResponse:
        return JSONResponse(
            content=jsonable_encoder(model.model_validate(body).model_dump()),
            headers={"X-Content-Type-Options": "nosniff"},
        )

    @router.get("/api/release")
    async def release(request: Request) -> JSONResponse:
        if await invalid(request):
            return refusal(422, "INVALID_ARGUMENT")
        if mount is None:
            return refusal(503, "STORE_UNAVAILABLE")
        try:
            return response(mount.summary(), Summary)
        except Exception as error:
            return error_response(error)

    @router.get("/api/facts/{fact_id}/lineage")
    async def lineage(
        fact_id: str, request: Request, seat: str | None = SEAT
    ) -> JSONResponse:
        if await invalid(request) or FACT_ID.fullmatch(fact_id) is None:
            return refusal(422, "INVALID_ARGUMENT")
        if mount is None:
            return refusal(503, "STORE_UNAVAILABLE")
        emitted = mount.find(fact_id, trusted_shapes(request, seat).seat)
        if emitted is None:
            return refusal(404, "NOT_FOUND")
        try:
            return response(mount.project(*emitted), Chain)
        except Exception as error:
            return error_response(error)

    return router
