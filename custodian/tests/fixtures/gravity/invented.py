"""Entirely invented Gravity archive, codes and units; no source values."""

from contextlib import contextmanager
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo

from eii_custodian.publicdata.fetch.cadence import Cadence
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response

URL = "https://www.data.gov.qa/invented-gravity.zip"
PAGE = "https://www.data.gov.qa/invented-gravity-page"
HEADER = "year,origin,destination,distance,contig,language,colony,agreement,gdp_o,gdp_d"
ROWS = "\n".join(
    (
        HEADER,
        "2091,00Q,00A,123456.789,1,0,0,1,123456789012.3456,..",
        "2091,00A,00Q,1.000,0,1,0,0,..,0.0000",
        "2091,00A,00B,0.000,0,0,0,0,0.0000,0.0000",
    )
)
MEMBERS = {
    "invented-country.csv": (
        "code,name\n00Q,Invented target\n00A,Invented partner\n00B,Invented other\n"
    ),
    "invented-bilateral.csv": ROWS + "\n",
}


def archive(members: dict[str, str] | None = None) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as zipped:
        for name, text in (MEMBERS if members is None else members).items():
            zipped.writestr(ZipInfo(name), text)
    return buffer.getvalue()


def entry():
    return replace(
        load_registry()[0],
        refetch=Cadence("none", "frequency_unconfirmed", ""),
        key="cepii_gravity",
        source_id="cepii_gravity",
        slug="",
        kind="https_file",
        title_en="Invented Gravity",
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
        nightly_live_fetch=True,
        skip_reason="",
        extension="zip",
        columns=(("year", "integer"),),
        row_count_min=3,
        row_count_max=3,
        period_first="2091",
        period_last="2091",
        period_field="year",
        release_tables=("pub_gravity_bilateral", "pub_gravity_country"),
        reconciliation="open",
        caveat_keys=("gravity_separate_series",),
        public_splits=(),
    )


def metadata(url: str) -> Response:
    return Response(url, b"Invented publisher page", ())


@contextmanager
def stream(url: str):
    body = archive()
    yield SimpleNamespace(
        final_url=url, hops=(), declared_length=len(body), chunks=iter([body])
    )


def configuration() -> dict[str, object]:
    from hashlib import sha256

    country_header = "code,name"
    bilateral_header = HEADER
    return {
        "config_version": "gravity-v1",
        "method_version": "v1",
        "source_version": "invented-release",
        "access": "visitor",
        "confirmed": True,
        "bound_origin": "assumption",
        "reviewed_urls": [URL, PAGE],
        "publisher": "Invented publisher",
        "page": PAGE,
        "page_sha256": sha256(b"Invented publisher page").hexdigest(),
        "attribution": "Invented publisher, invented release",
        "evidence": "invented fixture only",
        "licence_words": "invented licence words",
        "hs_revision": "absent",
        "publisher_mapping": "pending",
        "qatar_key": "00Q",
        "country_width": 3,
        "period_first": 2091,
        "period_last": 2091,
        "year_selection": "native",
        "archive_bytes": [1, 4096],
        "raw_rows": [3, 3],
        "member_count": [2, 2],
        "publisher_sha256": "",
        "flag_tokens": ["0", "1"],
        "flag_missing": [],
        "measures": [
            {
                "name": "distance",
                "total_digits": 9,
                "fractional_digits": 3,
                "signed": False,
                "missing": ["NA"],
                "unit": "invented-distance-unit",
            },
            {
                "name": "gdp_origin",
                "total_digits": 16,
                "fractional_digits": 4,
                "signed": False,
                "missing": [".."],
                "unit": "invented-gdp-unit",
            },
            {
                "name": "gdp_destination",
                "total_digits": 16,
                "fractional_digits": 4,
                "signed": False,
                "missing": [".."],
                "unit": "invented-gdp-unit",
            },
        ],
        "members": [
            {
                "name": "invented-country.csv",
                "kind": "country",
                "year": None,
                "bytes": [1, 2048],
                "rows": [3, 3],
                "sha256": "",
                "header": country_header.split(","),
                "columns": {"code": "country_code", "name": "source_name"},
            },
            {
                "name": "invented-bilateral.csv",
                "kind": "bilateral",
                "year": None,
                "bytes": [1, 2048],
                "rows": [3, 3],
                "sha256": "",
                "header": bilateral_header.split(","),
                "columns": {
                    "year": "year",
                    "origin": "origin_code",
                    "destination": "destination_code",
                    "distance": "distance",
                    "contig": "contig",
                    "language": "common_language",
                    "colony": "colonial_link",
                    "agreement": "trade_agreement",
                    "gdp_o": "gdp_origin",
                    "gdp_d": "gdp_destination",
                },
            },
        ],
    }
