"""Declared input classes are checked before provider setup or persistence."""

ALLOWED_INPUTS = ("public", "synthetic", "project_text", "team_question")


class DataPolicyBlocked(ValueError):
    """A refused input is not serialised into the admitted DAT-126 record schema."""


def check_policy(input_class: str, decision_class: str) -> None:
    if input_class not in ALLOWED_INPUTS:
        raise DataPolicyBlocked("BLOCKED_BY_DATA_POLICY")
    if (
        decision_class in ("question_route", "router_miss_finder")
        and input_class != "team_question"
    ):
        raise DataPolicyBlocked("BLOCKED_BY_DATA_POLICY")
    if decision_class == "string_parity" and input_class != "project_text":
        raise DataPolicyBlocked("BLOCKED_BY_DATA_POLICY")
