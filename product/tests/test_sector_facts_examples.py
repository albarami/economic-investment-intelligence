"""Tool regressions on invented stand-ins for document 07 card inputs."""

from decimal import Decimal


def test_licences_reproduces_card_c1():
    from product.tests.sector_fixture import licence_store

    from eii_product.tools.sector_facts import sector_facts

    with licence_store() as store:
        result = sector_facts(
            store,
            {
                "activity": "SYN-restaurant",
                "topic": "licences",
                "geography": "municipality:SYN-local",
            },
        )
    by_label = {fact.label_en: fact for fact in result["facts"]}
    assert by_label["Licence density"].value == Decimal(32)
    assert by_label["Location quotient"].value == Decimal("1.39")
    assert "Quotient lower bound" in by_label
    assert "Quotient upper bound" in by_label


def test_licences_interval_uses_the_card_scale_through_store():
    """The independent 10/100 versus 10/1000 S2-T07 fixture, at the tool boundary."""
    from product.tests.sector_fixture import licence_rows, release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    data = licence_rows()
    for row, count in zip(data["pub_licence_active"], (10, 90, 0, 900), strict=True):
        row["active_count"] = count
    with release_store(with_lineage(data)) as store:
        result = sector_facts(
            store,
            dict(
                activity="SYN-restaurant",
                topic="licences",
                geography="municipality:SYN-local",
            ),
        )
    values = {f.label_en: f.value for f in result["facts"]}
    assert values["Quotient lower bound"] == Decimal("5.52")
    assert values["Quotient upper bound"] == Decimal("17.44")


def test_pay_decomposition_reproduces_card_c3():
    from product.tests.sector_fixture import pay_rows, release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    with release_store(with_lineage(pay_rows())) as store:
        result = sector_facts(
            store,
            dict(activity="SYN-a", topic="pay_decomposition", geography="national"),
        )
    facts = {f.label_en: f.value for f in result["facts"]}
    assert facts["Earlier mean pay"] == Decimal(10084)
    assert facts["Later mean pay"] == Decimal(11855)
    assert facts["Within groups"] == Decimal(38)
    assert facts["Composition change"] == Decimal(1733)
    assert facts["Composition share"] == Decimal("97.8")


def test_zone_momentum_reproduces_card_c9():
    from product.tests.sector_fixture import release_store, utility_rows, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    with release_store(with_lineage(utility_rows())) as store:
        result = sector_facts(
            store, dict(activity="SYN-a", topic="zone_momentum", geography="national")
        )
    assert next(
        f.value for f in result["facts"] if f.label_en == "National multiple"
    ) == Decimal("1.34")
    assert next(
        f.value
        for f in result["facts"]
        if f.label_en == "Zone multiple" and f.geography["public_code"] == "zone:SYN-d"
    ) == Decimal("3.34")
    assert result["payload"]["zone_order"][:4] == ["SYN-a", "SYN-b", "SYN-c", "SYN-d"]


def test_churn_reproduces_card_c2():
    """Both published municipal examples through the served tool and named sums."""
    from product.tests.sector_fixture import churn_rows, release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    for area, expected in [("SYN-local", "15.1"), ("SYN-second", "13.6")]:
        with release_store(with_lineage(churn_rows())) as store:
            result = sector_facts(
                store,
                dict(
                    activity="SYN-restaurant",
                    topic="churn",
                    geography="municipality:" + area,
                ),
            )
        assert next(
            f.value
            for f in result["facts"]
            if f.period == "2024" and f.label_en == "Churn including flagged months"
        ) == Decimal(expected)
        assert next(
            f.value for f in result["facts"] if f.label_en == "Undated cancellations"
        ) == Decimal(7386)


def test_unit_economics_reproduces_card_c4_norms():
    from product.tests.sector_fixture import release_store, with_lineage

    from eii_product.tools.sector_facts import sector_facts

    rows = [
        dict(
            activity_code="SYN-a",
            period="2022",
            indicator=indicator,
            value=value,
            unit=unit,
            source_id="SYN-pub_sector_accounts",
        )
        for indicator, value, unit in [
            ("employees:SYN-size", 41458, "count"),
            ("productivity_of_employee", 152875, "QAR"),
            ("compensation", 1308140, "QAR_thousand"),
            ("operating_surplus", 1247422, "QAR_thousand"),
            ("goods_share", "40.6", "percent"),
            ("services_share", "16.5", "percent"),
        ]
    ]
    with release_store(with_lineage({"pub_sector_accounts": rows})) as store:
        result = sector_facts(
            store, dict(activity="SYN-a", topic="unit_economics", geography="national")
        )
    assert {f.label_en: f.value for f in result["facts"]} == {
        "Compensation share": Decimal("20.6"),
        "Surplus share": Decimal("19.7"),
        "Goods share": Decimal("40.6"),
        "Services share": Decimal("16.5"),
    }
