"""Invented assembly roots that run gather_audit for S2-T09 acceptance plants."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from custodian.tests.method_card_pin_fixtures import (
    case,
    lineage_context,
    write_json,
    write_yaml,
)
from custodian.tests.repository_root import repository_root
from custodian.tests.test_production_adapters import context

from eii_custodian.publicdata.assembly_io import write_record
from eii_custodian.publicdata.assembly_reports import gather_audit
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.gate_report import CONFIRMATION_TASKS

REPO = repository_root(Path(__file__))
_S2_T09_RECORD = "s2_t09_source_checks.yaml"
_GATHER_ROOT_FILES = (
    "docs/04_PUBLIC_DATA_PACK.md",
    "docs/03_DATA_CONTRACTS.md",
    "custodian/publicdata/investment_pages.yaml",
    "OPEN_ITEMS.md",
    "docs/decisions/0025-reconciliation-of-restaurant-and-wage-figures.md",
)


def stage_method_pin_gather_build(
    tmp_path: Path,
    *,
    mutate: Callable[..., None] | None = None,
    stage_outputs: bool = True,
    stage_record: bool = True,
) -> tuple[Any, dict[str, object], dict[str, object], dict[str, object]]:
    """Return a Production build whose gather_audit path can collect S2-T09 evidence.

    The returned configuration is the same recorded generation configuration
    the staged (or phase-written) outputs were built from, so a test can bind
    it straight to the production ``method_pins`` phase inputs.
    """
    root = tmp_path / "gather-root"
    for relative in _GATHER_ROOT_FILES:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / relative, destination)
    # The committed S2-T09 record is never copied: a staged record is written
    # below, and with stage_record=False the record must be truly absent.
    shutil.copytree(
        REPO / "custodian/publicdata/review",
        root / "custodian/publicdata/review",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(_S2_T09_RECORD),
    )
    work = tmp_path / "pin-work"
    work.mkdir()
    paths, record, artifact, config = case(work)
    if mutate is not None:
        mutate(paths, record, artifact, config)
    ctx = lineage_context(record)
    cache = tmp_path / "cache"
    (cache / "assembly").mkdir(parents=True, exist_ok=True)
    if stage_record:
        write_yaml(root / "custodian/publicdata/review" / _S2_T09_RECORD, record)
    if stage_outputs:
        write_json(cache / "assembly/s2_t09_pin_artifact.json", artifact)
        write_record(cache, "assembly/s2_t09_pin_generation_config.json", config)
    shutil.copy(paths[3], root / "docs/07_ECONOMIC_METHODS.md")
    entries = (*load_registry(), *ctx["registry"])
    build = replace(
        context(cache, entries),
        root=root,
        review=root / "custodian/publicdata/review",
    )
    build.receipts.update(ctx["receipts"])
    return build, record, artifact, config


def gathered_s2_t09_confirmation(build) -> dict[str, object]:
    """The S2-T09 row produced by the production gather_audit evidence path."""
    audit = gather_audit(build)
    return next(row for row in audit["confirmations"] if row["task"] == "S2-T09")


def otherwise_complete_audit_with_s2_t09(
    s2_t09_row: dict[str, object],
) -> dict[str, object]:
    """An audit that passes every gate except S2-T09, which comes from gather_audit."""
    return {
        "completeness": [{"state": "in use"}],
        "terms": [{"own_words_state": "recorded"}],
        "oi03": {"state": "recorded"},
        "regressions": {"missing": [], "mismatch": ""},
        "confirmations": [
            s2_t09_row if task == "S2-T09" else {"task": task, "state": "recorded"}
            for task in CONFIRMATION_TASKS
        ],
    }
