"""Closed offline decision vocabulary, from decision 0014 item 4."""

from dataclasses import dataclass
from typing import Literal

DecisionClass = Literal[
    "spine_match",
    "router_miss_finder",
    "brief_second_reader",
    "question_route",
    "string_parity",
]
Kind = Literal["yes_no", "choice", "ordinal"]
Outcome = Literal[
    "DECIDED",
    "BELOW_THRESHOLD",
    "UNAVAILABLE",
    "DISABLED",
    "ERROR",
    "BLOCKED_BY_DATA_POLICY",
]
CLASS_RULES = {
    "spine_match": ("admitted", "order_human_review"),
    "router_miss_finder": ("admitted", "flag_router_disagreement"),
    "brief_second_reader": ("admitted", "add_to_human_sample"),
    "question_route": ("shadow", "record_shadow_route"),
    "string_parity": ("experiment_first", "record_experiment"),
}
KINDS = ("yes_no", "choice", "ordinal")
OUTCOMES = (
    "DECIDED",
    "BELOW_THRESHOLD",
    "UNAVAILABLE",
    "DISABLED",
    "ERROR",
    "BLOCKED_BY_DATA_POLICY",
)


@dataclass(frozen=True)
class Request:
    """Tooling-owned inputs only. Labels are supplied by code, never invented by a model."""

    decision_class: str
    kind: str
    input_class: str
    input_text: str
    language: str
    rubric_id: str
    rubric_text: str
    route: str
    options: tuple[str, ...] = ()
    case_id: str = "synthetic-case"

    def __post_init__(self) -> None:
        if self.decision_class not in CLASS_RULES or self.kind not in KINDS:
            raise ValueError("unknown decision class or kind")
        if self.kind == "yes_no":
            if self.options:
                raise ValueError("yes_no has fixed labels")
        elif len(self.options) < 2 or len(set(self.options)) != len(self.options):
            raise ValueError("supply distinct closed labels")
        if any(not label or label.isnumeric() for label in self.options):
            raise ValueError("labels must be nonnumeric names")

    @property
    def labels(self) -> tuple[str, ...]:
        return ("no", "yes") if self.kind == "yes_no" else self.options
