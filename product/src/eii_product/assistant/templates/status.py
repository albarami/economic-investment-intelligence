"""Application-owned step labels and closed Public status template keys."""

from typing import Any

STEP_LABELS = {
    "resolve": ("Read the activity", "قراءة النشاط"),
    "make_area": ("Read the area", "قراءة المنطقة"),
    "stage": ("Show the area", "عرض المنطقة"),
    "sector_facts": ("Read the public context", "قراءة السياق العام"),
    "night_lights": ("Read night-time radiance", "قراءة الإشعاع الليلي"),
    "population_age_sex": ("Read the population context", "قراءة السياق السكاني"),
}
STATUS_KEYS = {
    "OK": "public_evidence",
    "NO_DATA": "no_data",
    "OUT_OF_SCOPE": "out_of_scope",
    "SUPPRESSED": "suppressed",
}


def status_key(status: str) -> str:
    if status not in STATUS_KEYS:
        raise ValueError("status_invalid")
    return STATUS_KEYS[status]


def plan_step(step: dict[str, Any]) -> dict[str, Any]:
    labels = STEP_LABELS[step["tool"]]
    return dict(
        step_id=step["key"],
        tool=step["tool"],
        label_en=labels[0],
        label_ar=labels[1],
        state="done",
    )
