"""Fixed layer facts retain the source unit and exact public geography."""

import pytest

from eii_core.facts import Fact, fact_id


@pytest.mark.parametrize(
    "metric,unit,code,value",
    [
        ("guide_price_class", "qar_per_ft2", "district:INVENTED-district", 3),
        ("parcel_area", "square_metre", "feature:INVENTED-parcel", 3),
        ("radiance_class", "radiance_nw_cm2_sr", "cell:INVENTED-frame", 3),
        ("place_listing", "published_text", "place:INVENTED-place", "INVENTED-place 2"),
    ],
)
def test_public_layer_fact(metric, unit, code, value):
    geo = {"kind": "public", "public_code": code}
    identifier = fact_id(
        release_id="ab" * 32,
        metric_key=metric,
        geography=geo,
        period="2025",
        qualifiers={},
    )
    f = Fact.model_validate(
        dict(
            fact_id=identifier,
            value=value,
            unit=unit,
            period="2025",
            geography=geo,
            provenance="public",
            input_classes=["public"],
            evidence_status="observed",
            reliability="not_applicable",
            coverage_keys=[],
            caveat_keys=[],
            label_en="Published value",
            label_ar="قيمة منشورة",
            lineage_ref="lin_fixture",
            release_id="ab" * 32,
        )
    )
    assert f.unit == unit and f.geography == geo


def test_fixed_layer_extensions_remain_public_only():
    geo = {"kind": "public", "public_code": "cell:INVENTED-frame"}
    body = dict(
        fact_id="f_" + "ab" * 16,
        value=3,
        unit="count",
        period="2025",
        geography=geo,
        provenance="synthetic",
        input_classes=["synthetic"],
        evidence_status="observed",
        reliability="not_applicable",
        coverage_keys=[],
        caveat_keys=[],
        label_en="Invented value",
        label_ar="قيمة مخترعة",
        lineage_ref="lin_fixture",
        release_id="ab" * 32,
    )
    with pytest.raises(ValueError):
        Fact.model_validate(body)
    body.update(
        geography={"kind": "public", "public_code": "district:INVENTED-district"},
        unit="qar_per_ft2",
    )
    with pytest.raises(ValueError):
        Fact.model_validate(body)
