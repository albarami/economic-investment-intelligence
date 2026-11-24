"""Typed serving policy. No gateway configuration is read by the product."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn
from uuid import uuid4

from eii_product.store.protocol import ReleaseStore
from eii_product.store.startup import StartupRefusal, verify_startup

if TYPE_CHECKING:
    from eii_product.assistant.catalogue.schema import Catalogue
    from eii_product.assistant.playbooks.models import Bundle
    from eii_product.assistant.playbooks.registry import Definition
    from eii_product.assistant.templates.writer import Draft

PAID = "remote_paid_assistant_refused"
# A model writer is handed the policy's key reader and provider opener, the
# only ones the answer path has, with the inputs of the template writer.
Writer = Callable[
    [Callable[[], str], Callable[..., object], "Bundle", "Definition", "Catalogue"],
    "Draft | None",
]


@dataclass(frozen=True)
class ServingPolicy:
    environment: Literal["development", "staging", "live"]
    release_id: str
    verify: Callable[[], None]
    traffic: Literal["simulated"] = "simulated"
    presenter: Literal[False] = False
    busyness: Literal["off"] = "off"
    weather: Literal["off"] = "off"
    writer: Writer | None = None

    def require(self, store: ReleaseStore, folder: Path) -> None:
        del folder
        if self.traffic != "simulated":
            raise StartupRefusal("traffic_mode_refused")
        if self.busyness != "off":
            raise StartupRefusal("busyness_mode_refused")
        if self.weather != "off":
            raise StartupRefusal("weather_mode_refused")
        if self.presenter is not False:
            raise StartupRefusal("presenter_mode_refused")
        if self.environment not in {"development", "staging", "live"}:
            raise StartupRefusal("environment_invalid")
        if self.environment in {"live", "staging"} and store.engine != "postgres":
            raise StartupRefusal("postgres_required")
        if store.release_id != self.release_id:
            raise StartupRefusal("startup_identity_mismatch")
        self.verify()

    def hosting_off(self) -> frozenset[str]:
        """The sources a hosted service keeps off; development keeps its own."""
        if self.environment == "development":
            return frozenset()
        return frozenset({"busyness", "weather"})

    def assistant_key(self) -> NoReturn:
        """The only assistant key reader. No key is read (decision 0041 item 3)."""
        raise StartupRefusal(PAID)

    def assistant_open(self, *request: object, **options: object) -> NoReturn:
        """The only provider opener. No paid call is made (decision 0041 item 3)."""
        del request, options
        raise StartupRefusal(PAID)

    def candidate(
        self, bundle: Bundle, definition: Definition, catalogue: Catalogue
    ) -> Draft | None:
        """A model writer's draft, or nothing: the template writer then answers."""
        if self.writer is None:
            return None
        try:
            return self.writer(
                self.assistant_key, self.assistant_open, bundle, definition, catalogue
            )
        except StartupRefusal as refusal:
            if refusal.reason != PAID:
                raise
        row = dict(
            ts=datetime.now(UTC).isoformat(),
            level="error",
            event="assistant_refused",
            answer_id=None,
            seat_key="",
            tool=None,
            engine=None,
            release_id=self.release_id,
            status="fallback",
            duration_ms=None,
            error_code=PAID,
            error_id=str(uuid4()),
        )
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))
        return None


def developer_policy(folder: Path) -> ServingPolicy:
    """Explicit embedded development verification, with no PostgreSQL contact."""
    from eii_product.store.release_check import check_release

    identity = str(check_release(folder).document["release_id"])

    def verify() -> None:
        verify_startup(folder, environment="development", embedded=True)

    return ServingPolicy("development", identity, verify)
