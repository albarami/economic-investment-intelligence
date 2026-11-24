"""Typed serving policy. No gateway configuration is read by the product."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from eii_product.store.protocol import ReleaseStore
from eii_product.store.startup import StartupRefusal, verify_startup


@dataclass(frozen=True)
class ServingPolicy:
    environment: Literal["development", "staging", "live"]
    release_id: str
    verify: Callable[[], None]
    traffic: Literal["simulated"] = "simulated"
    presenter: Literal[False] = False

    def require(self, store: ReleaseStore, folder: Path) -> None:
        del folder
        if self.traffic != "simulated":
            raise StartupRefusal("traffic_mode_refused")
        if self.presenter is not False:
            raise StartupRefusal("presenter_mode_refused")
        if self.environment not in {"development", "staging", "live"}:
            raise StartupRefusal("environment_invalid")
        if self.environment in {"live", "staging"} and store.engine != "postgres":
            raise StartupRefusal("postgres_required")
        if store.release_id != self.release_id:
            raise StartupRefusal("startup_identity_mismatch")
        self.verify()


def developer_policy(folder: Path) -> ServingPolicy:
    """Explicit embedded development verification, with no PostgreSQL contact."""
    from eii_product.store.release_check import check_release

    identity = str(check_release(folder).document["release_id"])

    def verify() -> None:
        verify_startup(folder, environment="development", embedded=True)

    return ServingPolicy("development", identity, verify)
