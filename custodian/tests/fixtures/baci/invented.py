"""Entirely invented archive, codes, units and publisher; no source values."""

from contextlib import contextmanager
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response

URL = "https://www.data.gov.qa/invented-baci.zip"
PAGE = "https://www.data.gov.qa/invented-baci-page"
TRADE = "year,exporter,importer,product,value,quantity,revision\n2091,00Q,00A,000001,123456789012.345600,0,invented-HS-A\n2091,00A,00Q,000001,1.00,NA,invented-HS-A\n2091,00Q,00Q,000001,0,2.00,invented-HS-A\n2091,00A,00A,000001,3,4,invented-HS-A\n"
MEMBERS = {
    "invented-country.csv": "code,name,iso3\n00Q,Invented target,\n00A,Invented partner,\n",
    "invented-product.csv": "code,description,revision\n000001,Invented product,invented-HS-A\n",
    "invented-year.csv": TRADE,
}


def archive(members=None):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as zipped:
        for name, text in (MEMBERS if members is None else members).items():
            zipped.writestr(ZipInfo(name), text)
    return buffer.getvalue()


def entry():
    return replace(
        load_registry()[0],
        key="cepii_baci",
        source_id="cepii_baci",
        slug="",
        kind="https_file",
        title_en="Invented BACI",
        publisher="Invented publisher",
        url=URL,
        landing_url=PAGE,
        fetch_host="www.data.gov.qa",
        terms_url="",
        licence_id="unconfirmed",
        licence_basis="owner_decision",
        decision_record="0026",
        terms_words="terms to be read",
        terms_read_on="2026-11-16",
        commit_allowed=False,
        skip_reason="",
        extension="zip",
        columns=(("year", "integer"),),
        row_count_min=4,
        row_count_max=4,
        period_first="2091",
        period_last="2091",
        release_tables=("pub_baci_trade", "pub_baci_country", "pub_baci_product"),
    )


def metadata(url):
    return Response(url, b"Invented publisher page", ())


@contextmanager
def stream(url):
    body = archive()
    yield SimpleNamespace(
        final_url=url, hops=(), declared_length=len(body), chunks=iter([body])
    )


def configuration():
    from hashlib import sha256

    return {
        "config_version": "baci-v1",
        "method_version": "v1",
        "source_version": "invented-release",
        "hs_revision": "invented-HS-A",
        "access": "visitor",
        "confirmed": True,
        "reviewed_urls": [URL, PAGE],
        "publisher": "Invented publisher",
        "page": PAGE,
        "page_sha256": sha256(b"Invented publisher page").hexdigest(),
        "attribution": "Invented publisher, invented release",
        "evidence": "invented fixture only",
        "qatar_key": "00Q",
        "country_width": 3,
        "product_width": 6,
        "value_unit": "invented-value-unit",
        "quantity_unit": "invented-quantity-unit",
        "currency": "invented-currency",
        "valuation_basis": "unknown",
        "reconciliation": "unknown",
        "missing_quantity": ["NA"],
        "period_first": 2091,
        "period_last": 2091,
        "archive_bytes": [1, 4096],
        "raw_rows": [4, 4],
        "total_digits": 18,
        "fractional_digits": 6,
        "publisher_sha256": "",
        "members": [
            {
                "name": name,
                "kind": kind,
                "year": year,
                "bytes": [1, 2048],
                "rows": counts,
                "sha256": "",
                "header": header.split(","),
                "columns": dict(zip(header.split(","), mapped, strict=True)),
            }
            for name, kind, year, counts, header, mapped in [
                (
                    "invented-country.csv",
                    "country",
                    None,
                    [2, 2],
                    "code,name,iso3",
                    ["country_code", "source_name", "iso3"],
                ),
                (
                    "invented-product.csv",
                    "product",
                    None,
                    [1, 1],
                    "code,description,revision",
                    ["hs_code", "source_description", "hs_revision"],
                ),
                (
                    "invented-year.csv",
                    "trade",
                    2091,
                    [4, 4],
                    "year,exporter,importer,product,value,quantity,revision",
                    [
                        "year",
                        "exporter_code",
                        "importer_code",
                        "hs_code",
                        "value",
                        "quantity",
                        "hs_revision",
                    ],
                ),
            ]
        ],
    }
