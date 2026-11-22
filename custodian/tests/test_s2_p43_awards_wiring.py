"""S2-P43 row S11: the keyed command reaches the awards proof with no archive token, in page scope."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.test_s2_t29_awards import profile
from custodian.tests.test_s2_t29_live_awards import report
from custodian.tests.test_s2_t29_live_shapes import entry

from commands import build_public
from eii_custodian.publicdata import assembly_adapters
from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.page_requests import active
from eii_custodian.publicdata.fetch.transport import Response


def test_keyed_awards_proof_whole_wiring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Row S11: the real run and run_build reach the awards proof with no token, in page scope."""
    declaration, body = report()
    schema = profile()
    schema["proof_columns"] = {
        "company": "SYN company",
        "registration": "SYN registration",
        "value": "SYN amount",
    }
    declaration["profile"] = schema
    declaration["bounds_basis"] = "observed"
    source_entry = replace(
        entry(declaration, "awards_owner_scrape"), kind="awards_intake"
    )
    monkeypatch.setattr(build_public, "load_registry", lambda: (source_entry,))
    monkeypatch.setattr(awards, "load_declaration", lambda source: declaration)
    monkeypatch.setattr(
        assembly_adapters,
        "read_yaml",
        lambda _: {
            "sources": {
                "awards_owner_scrape": {"profile": schema, "max_bytes": len(body)}
            }
        },
    )
    cache = tmp_path / "data/public_cache"
    folder = cache / "intake/awards_owner_scrape"
    folder.mkdir(parents=True)
    values = {
        "syn_company": "SYN first",
        "syn_reg": "SYN-reg",
        "syn_value": "1007.00",
        "syn_date": "03/02/2031",
        "report_url": declaration["url"],
    }
    body_csv = (
        ",".join(schema["columns"])
        + "\n"
        + ",".join(values[column] for column in schema["columns"])
        + "\n"
    ).encode()
    (folder / "syn.csv").write_bytes(body_csv)
    (folder / "intake.json").write_text(
        json.dumps(
            {
                "file": "syn.csv",
                "sha256": hashlib.sha256(body_csv).hexdigest(),
                "seed": 73,
                "register_selections": [],
            }
        )
    )
    seen: list[tuple[str, str, bool]] = []

    def open_stub(
        url: object, token: str = "", headers: object = None, **kwargs: object
    ) -> Response:
        seen.append((str(url), token, active()))
        return Response(str(url), body, ())

    monkeypatch.setattr(build_public, "open_https", open_stub)
    result = build_public.run(
        tmp_path,
        {"EARTHDATA_API_KEY": "SYN-invented-archive-token"},
        [],
        sleep=lambda _: None,
    )
    assert result in {
        0,
        1,
    }  # the invented cache has no assembly inputs; only the request is under test
    proof = [
        (token, scoped) for url, token, scoped in seen if url == declaration["url"]
    ]
    assert proof == [("", True)]
    assert all(token == "" for url, token, scoped in seen)
