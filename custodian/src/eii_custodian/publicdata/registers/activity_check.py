"""No register activity is inferred; reuse the spine's signed-code checks."""

from collections.abc import Mapping

from eii_custodian.publicdata.review.activity import (
    ActivityRow,
    IsicClass,
    ReviewRow,
    SpineError,
    _derive,
)

from .contracts import refuse


def register_activity_check(
    activity: ActivityRow | None,
    classes: Mapping[str, IsicClass],
    review: ReviewRow | None,
) -> dict[str, str]:
    """A stand-in can exercise a code; today's register has no code column."""
    if activity is None:
        return {"status": "not_proved", "reason": "register_publishes_no_code"}
    if (
        review is not None
        and review.status == "mapped"
        and review.isic_class != activity.code[:4]
    ):
        refuse("activity_code_mismatch")
    try:
        status, reason, _ = _derive(activity, classes, review, True)
    except SpineError:
        refuse("activity_review_invalid")
    return {"status": status, "reason": reason}
