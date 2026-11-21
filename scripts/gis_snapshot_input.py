"""Opt-in release-sandbox input seam; no selected imagery means no root read."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import sandbox_launch
from eii_custodian.publicdata.gis.snapshot_archive import Selection
from eii_custodian.publicdata.gis.snapshot_release import (
    inside_selections,
    reviewed_inputs,
)


def select(
    layout: sandbox_launch.Layout, environ: Mapping[str, str], *, imagery: bool = False
) -> tuple[sandbox_launch.Layout, tuple[Selection, ...]]:
    if not imagery:
        return layout, ()
    root, selections, files = reviewed_inputs(environ)
    return replace(layout, imagery_root=root, imagery=files), inside_selections(
        selections
    )
