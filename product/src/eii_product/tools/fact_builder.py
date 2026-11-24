"""Build validated facts without arithmetic or rounding.

BE-23's single display rounding is already performed by eii_core.calc.emit.
The builder retains that value exactly; DAT-94 failures drop the fact.
Arabic labels are application-owned and pending native review.
"""

from collections.abc import Mapping, Sequence

from eii_core.calc import reliability
from eii_core.calc.facts import CalculationFact
from eii_core.facts import Fact, fact_id, validate_chain

LABELS = {
    "night_lights_radiance": ("Night-time radiance", "الإشعاع الضوئي الليلي"),
    "venue_busyness_index": (
        "BestTime relative busyness",
        "مؤشر الانشغال النسبي من BestTime",
    ),
    "population_grid_people": ("Population by age and sex", "السكان حسب العمر والجنس"),
    "active_count": ("Active licence count", "عدد التراخيص النشطة"),
    "including_ratio": ("Cancellation to stock ratio", "نسبة الإلغاءات إلى الرصيد"),
    "including_percent": (
        "Churn including flagged months",
        "الدوران شاملا الأشهر المحددة",
    ),
    "excluding_percent": (
        "Churn excluding flagged months",
        "الدوران باستثناء الأشهر المحددة",
    ),
    "churn_low": ("Churn lower bound", "الحد الأدنى للدوران"),
    "churn_high": ("Churn upper bound", "الحد الأعلى للدوران"),
    "undated_count": ("Undated cancellations", "الإلغاءات غير المؤرخة"),
    "bulk_share": ("Flagged cancellation share", "حصة الإلغاءات المحددة"),
    "bulk_month": ("Flagged cancellation month", "شهر الإلغاءات المحدد"),
    "licence_density": ("Licence density", "كثافة التراخيص"),
    "location_quotient": ("Location quotient", "معامل التوطن"),
    "lq_low": ("Quotient lower bound", "الحد الأدنى لمعامل التوطن"),
    "lq_high": ("Quotient upper bound", "الحد الأعلى لمعامل التوطن"),
    "local_count": ("Local licence count", "عدد التراخيص المحلية"),
}
LABELS.update(
    {
        "employees": ("Employees", "الموظفون"),
        "establishments": ("Establishments", "المنشآت"),
        "compensation": ("Compensation", "التعويضات"),
        "purchases": ("Purchases", "المشتريات"),
        "sales": ("Sales", "المبيعات"),
        "stocks": ("Stocks", "المخزون"),
        "guests": ("Guests", "النزلاء"),
        "arrivals": ("Arrivals", "الوافدون"),
        "facilities": ("Facilities", "المرافق"),
        "size_class": ("Size class", "فئة الحجم"),
        "mean_before": ("Earlier mean pay", "متوسط الأجر السابق"),
        "mean_after": ("Later mean pay", "متوسط الأجر اللاحق"),
        "change": ("Pay change", "تغير الأجر"),
        "within": ("Within groups", "داخل المجموعات"),
        "mix": ("Composition change", "تغير التركيبة"),
        "mix_share": ("Composition share", "حصة التركيبة"),
        "fixed_composition_change": (
            "Fixed composition change",
            "التغير بتركيبة ثابتة",
        ),
        "fixed_composition_percent": (
            "Fixed composition percentage",
            "نسبة التغير بتركيبة ثابتة",
        ),
        "change_percent": ("Change percentage", "نسبة التغير"),
        "populated_groups": ("Populated groups", "المجموعات المشغولة"),
        "national_ratio": ("National multiple", "المضاعف الوطني"),
        "zone_ratio": ("Zone multiple", "مضاعف المنطقة"),
        "ranked_ratio": ("Ranked multiple", "المضاعف المرتب"),
        "relative": ("Relative multiple", "المضاعف النسبي"),
        "compensation_percent": ("Compensation share", "حصة التعويضات"),
        "surplus_percent": ("Surplus share", "حصة الفائض"),
        "goods_percent": ("Goods share", "حصة السلع"),
        "services_percent": ("Services share", "حصة الخدمات"),
        "food": ("Food share", "حصة الغذاء"),
        "beverages": ("Beverages share", "حصة المشروبات"),
        "building_rent": ("Building rent share", "حصة إيجار المبنى"),
    }
)
STORED_UNITS = {
    "persons": "count",
    "establishments": "count",
    "count": "count",
    "percent": "percent",
    "ratio": "ratio",
    "QAR": "qar",
    "QAR_thousand": "qar_thousand",
    "qar": "qar",
    "qar_thousand": "qar_thousand",
}


def build_published(
    *,
    value: object,
    unit: str,
    metric_key: str,
    period: str,
    geography: Mapping[str, str],
    release_id: str,
    lineage_ref: str,
    lineage_rows: Sequence[Mapping[str, object]],
    source_rows: Sequence[Mapping[str, object]],
    qualifiers: Mapping[str, str],
    caveat_keys: Sequence[str] = (),
    count: int | None = None,
) -> Fact | None:
    """Fixed read: the stored value is never rounded, converted or repaired."""
    if validate_chain(lineage_ref, lineage_rows, source_rows) is not None:
        return None
    labels = LABELS.get(metric_key)
    if labels is None:
        return None
    try:
        return Fact.model_validate(
            dict(
                fact_id=fact_id(
                    release_id=release_id,
                    metric_key=metric_key,
                    geography=geography,
                    period=period,
                    qualifiers=qualifiers,
                ),
                value=value,
                unit=unit,
                period=period,
                geography=dict(geography),
                provenance="public",
                input_classes=["public"],
                evidence_status="observed",
                reliability=reliability(count),
                coverage_keys=[],
                caveat_keys=list(caveat_keys),
                label_en=labels[0],
                label_ar=labels[1],
                lineage_ref=lineage_ref,
                release_id=release_id,
            )
        )
    except ValueError:
        return None


def build_calculated(
    result: CalculationFact,
    *,
    release_id: str,
    lineage_ref: str,
    lineage_rows: Sequence[Mapping[str, object]],
    source_rows: Sequence[Mapping[str, object]],
    qualifiers: Mapping[str, str],
    caveat_keys: Sequence[str] = (),
    count: int | None = None,
    numerator_table: str | None = None,
) -> Fact | None:
    """Use the store identity, and the numerator's lineage covering all inputs."""
    if result.provenance != "public" or result.evidence_status != "observed":
        return None
    if (
        validate_chain(
            lineage_ref,
            lineage_rows,
            source_rows,
            required_sources=result.sources,
            numerator_table=result.sources[0].table
            if numerator_table is None
            else numerator_table,
        )
        is not None
    ):
        return None
    qualified = dict(qualifiers)
    for key, text in (
        ("base_period", result.base_period),
        ("base_geography", result.base_geography),
        ("base_geography_kind", result.base_geography_kind),
    ):
        if text:
            if key in qualified and qualified[key] != text:
                return None
            qualified[key] = text
    geography = {"kind": result.geography_kind}
    if result.geography_kind == "public":
        geography["public_code"] = result.geography
    return build_published(
        value=result.value,
        unit=result.unit,
        metric_key=result.metric_key,
        period=result.period,
        geography=geography,
        release_id=release_id,
        lineage_ref=lineage_ref,
        lineage_rows=lineage_rows,
        source_rows=source_rows,
        qualifiers=qualified,
        caveat_keys=tuple(dict.fromkeys(("calculated", *caveat_keys))),
        count=count,
    )
