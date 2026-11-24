"""Bundle and evidence types; complete lineage travels beside each fact."""

from dataclasses import dataclass, field
from typing import Any

from eii_core.facts import Fact, validate_chain
from eii_product.assistant.catalogue.schema import ReturnedFact


@dataclass
class Evidence:
    fact: Fact
    metric_key: str
    lineage: list[dict[str, Any]]
    sources: list[dict[str, Any]]

    def valid(self, release_id: str) -> bool:
        try:
            Fact.model_validate(self.fact.model_dump())
        except ValueError:
            return False
        return (
            self.fact.release_id == release_id
            and validate_chain(self.fact.lineage_ref, self.lineage, self.sources)
            is None
        )

    def returned(self) -> ReturnedFact:
        fact = self.fact
        return ReturnedFact(
            fact.fact_id,
            self.metric_key,
            fact.unit,
            fact.period,
            fact.geography["kind"],
            fact.provenance,
            fact.evidence_status,
            fact.lineage_ref,
        )

    def wire(self) -> dict[str, Any]:
        return {
            **self.fact.model_dump(mode="json"),
            "source_chain": {"lineage": self.lineage, "sources": self.sources},
        }


@dataclass
class Bundle:
    release_id: str
    inputs: dict[str, Any]
    playbook: str = "site_check"
    steps: list[dict[str, Any]] = field(default_factory=list)
    stage: list[dict[str, Any]] = field(default_factory=list)
    cards: list[dict[str, Any]] = field(default_factory=list)
    facts: dict[str, Evidence] = field(default_factory=dict)
    area_roles: dict[str, str | None] = field(default_factory=dict)

    def wire(self) -> dict[str, Any]:
        return dict(
            release_id=self.release_id,
            playbook=self.playbook,
            inputs=self.inputs,
            steps=self.steps,
            stage=self.stage,
            area_roles=self.area_roles,
            cards=self.cards,
            facts=[item.wire() for item in self.facts.values()],
        )
