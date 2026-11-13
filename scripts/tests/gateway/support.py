"""Small, explicitly synthetic contract inputs."""

from eii_gateway import Request


def request(**changes: str) -> Request:
    values = {
        "decision_class": "spine_match",
        "kind": "yes_no",
        "input_class": "synthetic",
        "input_text": "SYNTHETIC activity example",
        "language": "en",
        "rubric_id": "synthetic-match",
        "rubric_text": "Flag this invented pair for human review.",
        "route": "synthetic-offline",
    }
    values.update(changes)
    return Request(
        decision_class=values["decision_class"],
        kind=values["kind"],
        input_class=values["input_class"],
        input_text=values["input_text"],
        language=values["language"],
        rubric_id=values["rubric_id"],
        rubric_text=values["rubric_text"],
        route=values["route"],
        case_id=values.get("case_id", "synthetic-case"),
    )
