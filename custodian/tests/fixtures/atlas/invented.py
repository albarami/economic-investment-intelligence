"""Entirely invented Atlas archives. Finished files only; values are not a publisher's."""

from contextlib import contextmanager
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo

from eii_custodian.publicdata.fetch.cadence import Cadence
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response

CPY_URL = "https://www.data.gov.qa/invented-atlas-cpy.zip"
CPP_URL = "https://www.data.gov.qa/invented-atlas-cpp.zip"
PAGE = "https://www.data.gov.qa/invented-atlas-page"
CPY_MEMBERS = {
    "invented-cpy-country.csv": "code,name\n00Q,Invented target\n00A,Invented partner\n",
    "invented-cpy-product.csv": "code,description,revision\n000001,Invented product,invented-HS-A\n",
    "invented-cpy.csv": (
        "year,country,product,revision,measure\n"
        "2091,00Q,000001,invented-HS-A,-123456.654321\n"
        "2091,00A,000001,invented-HS-A,NA\n"
    ),
}
CPP_MEMBERS = {
    "invented-cpp-country.csv": (
        "code,name\n00Q,Invented target\n00A,Invented partner\n00B,Invented other\n"
    ),
    "invented-cpp-product.csv": "code,description,revision\n000001,Invented product,invented-HS-A\n",
    "invented-cpp.csv": (
        "year,reporter,partner,product,revision,measure\n"
        "2091,00Q,00A,000001,invented-HS-A,0\n"
        "2091,00A,00Q,000001,invented-HS-A,1.000000\n"
        "2091,00A,00B,000001,invented-HS-A,0.000000\n"
    ),
}


def _zip(members: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as zipped:
        for name, text in members.items():
            zipped.writestr(ZipInfo(name), text)
    return buffer.getvalue()


def cpy_archive(members: dict[str, str] | None = None) -> bytes:
    return _zip(CPY_MEMBERS if members is None else members)


def cpp_archive(members: dict[str, str] | None = None) -> bytes:
    return _zip(CPP_MEMBERS if members is None else members)


def entry():
    return replace(
        load_registry()[0],
        refetch=Cadence("none", "frequency_unconfirmed", ""),
        key="atlas_complexity",
        source_id="atlas_complexity",
        slug="",
        kind="https_file",
        title_en="Invented Atlas",
        publisher="Invented publisher",
        url=CPY_URL,
        landing_url=PAGE,
        fetch_host="www.data.gov.qa",
        terms_url="",
        licence_id="unconfirmed",
        licence_basis="owner_decision",
        decision_record="0026",
        terms_words="terms to be read",
        terms_read_on="2026-11-16",
        commit_allowed=False,
        nightly_live_fetch=True,
        skip_reason="",
        extension="zip",
        columns=(("year", "integer"),),
        row_count_min=5,
        row_count_max=5,
        period_first="2091",
        period_last="2091",
        period_field="year",
        release_tables=(
            "pub_atlas_country_product_year",
            "pub_atlas_cpy_country",
            "pub_atlas_cpy_product",
            "pub_atlas_country_partner_product_year",
            "pub_atlas_cppy_country",
            "pub_atlas_cppy_product",
        ),
        reconciliation="open",
        caveat_keys=("atlas_finished_only",),
        public_splits=(),
    )


def metadata(url: str) -> Response:
    return Response(url, b"Invented publisher page", ())


@contextmanager
def stream(url: str):
    body = cpy_archive() if url == CPY_URL else cpp_archive()
    yield SimpleNamespace(
        final_url=url, hops=(), declared_length=len(body), chunks=iter([body])
    )


def _member(
    name: str, kind: str, rows: list[int], header: str, mapped: list[str]
) -> dict[str, object]:
    return {
        "name": name,
        "kind": kind,
        "year": None,
        "bytes": [1, 4096],
        "rows": rows,
        "sha256": "",
        "header": header.split(","),
        "columns": dict(zip(header.split(","), mapped, strict=True)),
    }


def configuration() -> dict[str, object]:
    from hashlib import sha256

    return {
        "config_version": "atlas-v1",
        "method_version": "v1",
        "source_version": "invented-atlas-release",
        "access": "visitor",
        "confirmed": True,
        "bound_origin": "assumption",
        "finished_only": True,
        "reviewed_urls": [CPY_URL, CPP_URL, PAGE],
        "publisher": "Invented publisher",
        "page": PAGE,
        "page_sha256": sha256(b"Invented publisher page").hexdigest(),
        "attribution": "Invented publisher, invented release",
        "evidence": "invented fixture only",
        "licence_words": "invented licence words",
        "hs_revision": "invented-HS-A",
        "publisher_mapping": "pending",
        "qatar_key": "00Q",
        "country_width": 3,
        "product_width": 6,
        "period_first": 2091,
        "period_last": 2091,
        "year_selection": "native",
        "raw_rows": [5, 5],
        "measures": [
            {
                "name": "finished_measure",
                "total_digits": 12,
                "fractional_digits": 6,
                "signed": True,
                "missing": ["NA"],
                "unit": "invented-finished-unit",
            }
        ],
        "downloads": [
            {
                "grain": "country_product_year",
                "url": CPY_URL,
                "archive_bytes": [1, 8192],
                "raw_rows": [2, 2],
                "member_count": [3, 3],
                "publisher_sha256": "",
                "members": [
                    _member(
                        "invented-cpy-country.csv",
                        "country",
                        [2, 2],
                        "code,name",
                        ["country_code", "source_name"],
                    ),
                    _member(
                        "invented-cpy-product.csv",
                        "product",
                        [1, 1],
                        "code,description,revision",
                        ["product_code", "source_description", "hs_revision"],
                    ),
                    _member(
                        "invented-cpy.csv",
                        "country_product_year",
                        [2, 2],
                        "year,country,product,revision,measure",
                        [
                            "year",
                            "country_code",
                            "product_code",
                            "hs_revision",
                            "finished_measure",
                        ],
                    ),
                ],
            },
            {
                "grain": "country_partner_product_year",
                "url": CPP_URL,
                "archive_bytes": [1, 8192],
                "raw_rows": [3, 3],
                "member_count": [3, 3],
                "publisher_sha256": "",
                "members": [
                    _member(
                        "invented-cpp-country.csv",
                        "country",
                        [3, 3],
                        "code,name",
                        ["country_code", "source_name"],
                    ),
                    _member(
                        "invented-cpp-product.csv",
                        "product",
                        [1, 1],
                        "code,description,revision",
                        ["product_code", "source_description", "hs_revision"],
                    ),
                    _member(
                        "invented-cpp.csv",
                        "country_partner_product_year",
                        [3, 3],
                        "year,reporter,partner,product,revision,measure",
                        [
                            "year",
                            "reporter_code",
                            "partner_code",
                            "product_code",
                            "hs_revision",
                            "finished_measure",
                        ],
                    ),
                ],
            },
        ],
    }
