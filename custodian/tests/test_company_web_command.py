"""Opt-in command, safe diagnostics and invented offline multi-stage run."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from custodian.tests.company_web_fixture import (
    NAME,
    STAMP,
    URL,
    body,
    manifest,
    offline_network,  # noqa: F401
)
from scripts.commands import build_public

from eii_custodian.publicdata.company_web.build import run_company_web
from eii_custodian.publicdata.company_web.contracts import Company
from eii_custodian.publicdata.fetch import build
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response


def environment(root: Path, stage: str) -> dict[str, str]:
    folder = root / build.CACHE_RELATIVE / "company_web" / "input"
    folder.mkdir(parents=True, exist_ok=True)
    value = manifest()
    value["companies"] = {"syn-a": [URL]}
    del value["access"]["other.example.test"]
    data = json.dumps(value).encode()
    config = folder / "manifest.json"
    config.write_bytes(data)
    return {
        "EII_COMPANY_WEB_MANIFEST": str(config),
        "EII_COMPANY_WEB_MANIFEST_SHA256": sha256_hex(data),
        "EII_COMPANY_WEB_STAGE": stage,
        "EII_COMPANY_WEB_RUN_ID": "syn-run",
    }


def test_ordinary_command_never_selects_family(tmp_path: Path) -> None:
    with patch.object(
        build_public, "run_build", return_value=build.BuildOutcome((), None)
    ) as run:
        assert build_public.run(tmp_path, {}, (), transport=lambda _: None) == 0
    assert all(e.source_id != "company_web" for e in run.call_args.args[0])


def test_opt_in_does_not_dispatch_other_sources(tmp_path: Path) -> None:
    with (
        patch.object(build_public, "run_company_web", return_value=0) as company,
        patch.object(build_public, "run_build") as ordinary,
    ):
        assert (
            build_public.run(tmp_path, {}, ("--company-web",), transport=lambda _: None)
            == 0
        )
    company.assert_called_once()
    ordinary.assert_not_called()


@pytest.mark.parametrize(
    "args", [("--company-web", "--seed", "1"), ("--company-web-search",)]
)
def test_extra_command_arguments_refused_before_inputs(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    with patch.object(build_public, "run_company_web") as run:
        assert build_public.run(tmp_path, {}, args, transport=lambda _: None) == 2
        run.assert_not_called()


def test_family_registry() -> None:
    entry = next(e for e in load_registry() if e.source_id == "company_web")
    assert entry.licence_basis == "owner_decision" and entry.decision_record == "0026"
    assert not entry.commit_allowed and not entry.release_tables


def test_missing_inputs_no_network_or_private_diagnostics(
    tmp_path: Path, capsys
) -> None:
    sent = []
    assert (
        run_company_web(
            tmp_path, {}, lambda u: sent.append(u), lambda _: None, clock=lambda: STAMP
        )
        == 1
    )
    assert sent == []
    assert NAME not in capsys.readouterr().out


def test_offline_end_to_end_search_fetch_review(tmp_path: Path) -> None:
    tick = [0.0]

    def sleep(seconds: float) -> None:
        tick[0] += seconds

    def transport(url: str) -> Response:
        data = (
            f'<a class="result" href="{URL}">Not retained</a>'.encode()
            if "search.example.test" in url
            else body()
        )
        return Response(url, data, (), body_sha256=sha256_hex(data))

    env = environment(tmp_path, "search")
    with patch(
        "eii_custodian.publicdata.company_web.build.input_companies",
        return_value=(Company("syn-a", NAME, "register", {}),),
    ):
        assert (
            run_company_web(
                tmp_path,
                env,
                transport,
                sleep,
                clock=lambda: STAMP,
                monotonic=lambda: tick[0],
            )
            == 0
        )
        folder = tmp_path / build.CACHE_RELATIVE / "company_web" / "runs" / "syn-run"
        selection = json.loads((folder / "selection.json").read_bytes())
        env.update(
            EII_COMPANY_WEB_STAGE="fetch",
            EII_COMPANY_WEB_SEARCH_SHA256=selection["search"],
        )
        assert (
            run_company_web(
                tmp_path,
                env,
                transport,
                sleep,
                clock=lambda: STAMP,
                monotonic=lambda: tick[0],
            )
            == 0
        )
        selection = json.loads((folder / "selection.json").read_bytes())
        env.update(
            EII_COMPANY_WEB_STAGE="review",
            EII_COMPANY_WEB_FETCH_SHA256=selection["fetch"],
        )
        assert (
            run_company_web(
                tmp_path,
                env,
                transport,
                sleep,
                clock=lambda: STAMP,
                monotonic=lambda: tick[0],
            )
            == 0
        )
        selection = json.loads((folder / "selection.json").read_bytes())
        assert "review" in selection
        # No independent decisions were supplied: all fields remain pending.
        from eii_custodian.publicdata.fetch.snapshots import read_snapshot

        reviewed = json.loads(
            read_snapshot(folder / "review", selection["review"]).body
        )
        assert (
            reviewed["counts"]["retained"] == 0 and reviewed["counts"]["pending"] == 4
        )

        from custodian.tests.company_web_fixture import REVIEWER

        from eii_custodian.publicdata.company_web.contracts import digest

        fetched = json.loads(read_snapshot(folder / "fetch", selection["fetch"]).body)
        page = fetched["outcomes"][0]["pages"][0]
        bundle = json.loads(
            read_snapshot(
                folder / "bundles" / digest(("syn-a", page["identity"])),
                page["reviewer_bundle"],
            ).body
        )
        reviews = {}
        for proposed in bundle["candidates"]:
            signed = {
                key: proposed[key]
                for key in (
                    "candidate_digest",
                    "field",
                    "value_sha256",
                    "page_sha256",
                    "fragment_sha256",
                    "parser",
                    "extractor_sha256",
                )
            }
            signed.update(reviewer=REVIEWER, decision="accepted")
            reviews[proposed["candidate_digest"]] = signed
        review_path = Path(env["EII_COMPANY_WEB_MANIFEST"]).parent / "reviews.json"
        raw = json.dumps(reviews).encode()
        review_path.write_bytes(raw)
        env.update(
            EII_COMPANY_WEB_REVIEWS=str(review_path),
            EII_COMPANY_WEB_REVIEWS_SHA256=sha256_hex(raw),
        )

        def no_open(url):
            raise AssertionError("review_must_be_offline")

        assert (
            run_company_web(
                tmp_path,
                env,
                no_open,
                sleep,
                clock=lambda: STAMP,
                monotonic=lambda: tick[0],
            )
            == 0
        )
        selection = json.loads((folder / "selection.json").read_bytes())
        accepted = json.loads(
            read_snapshot(folder / "review", selection["review"]).body
        )
        assert (
            accepted["counts"]["retained"] == 4 and accepted["counts"]["pending"] == 0
        )
        assert accepted["name_inventory"]["names"] == [NAME]
        assert accepted["fetch_identity"] == selection["fetch"]
        assert accepted["search_identity"] == selection["search"]
        # A changed decision file invalidates its reviewed hash before publication.
        review_path.write_bytes(raw + b" ")
        assert (
            run_company_web(
                tmp_path,
                env,
                no_open,
                sleep,
                clock=lambda: STAMP,
                monotonic=lambda: tick[0],
            )
            == 1
        )


def test_input_adapters_use_both_pinned_sources_once_per_company(
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    from eii_custodian.publicdata.company_web.build import input_companies
    from eii_custodian.publicdata.name_inventory import Contribution

    path = tmp_path / "invented-register.csv"
    path.write_text(
        "company_name,registration_number,licence_number,address\n"
        + NAME
        + ",syn-key,,SYN address\n"
    )
    financial = "Fenzavix Systems"
    selected = SimpleNamespace(
        sha256="a" * 64,
        body=json.dumps(
            {"rows": [{"company_name": financial, "company_name_ar": "SYN alternate"}]}
        ).encode(),
    )
    with (
        patch(
            "eii_custodian.publicdata.company_web.build.financial_contribution",
            return_value=Contribution(
                "fc_register",
                (financial, "SYN alternate"),
                {"snapshot_identity": "a" * 64},
            ),
        ),
        patch(
            "eii_custodian.publicdata.company_web.build.selected_page",
            return_value=selected,
        ),
    ):
        inputs = input_companies(tmp_path, {"EII_REGISTER_FILE": str(path)})
    assert len(inputs) == 2 and {c.source for c in inputs} == {
        "register",
        "fc_register",
    }
    assert inputs[1].name == financial and inputs[1].register_fields == {}


@pytest.mark.parametrize("column", ["person", "job_title", "salary", "workbook"])
def test_register_adapter_refuses_undeclared_columns_before_other_input(
    tmp_path: Path, column: str
) -> None:
    from eii_custodian.publicdata.company_web.build import input_companies
    from eii_custodian.publicdata.company_web.contracts import WebError

    path = tmp_path / "invented-input.csv"
    path.write_text(
        "company_name,registration_number,"
        + column
        + "\n"
        + NAME
        + ",syn-key,Invented\n"
    )
    with patch(
        "eii_custodian.publicdata.company_web.build.financial_contribution"
    ) as financial:
        with pytest.raises(WebError):
            input_companies(tmp_path, {"EII_REGISTER_FILE": str(path)})
        financial.assert_not_called()


def test_manifest_outside_documented_cache_is_not_read(tmp_path: Path) -> None:
    env = environment(tmp_path, "search")
    env["EII_COMPANY_WEB_MANIFEST"] = str(tmp_path / "not-an-input.json")
    with patch(
        "eii_custodian.publicdata.company_web.build.input_companies",
        return_value=(Company("syn-a", NAME, "register", {}),),
    ):
        sent = []
        assert (
            run_company_web(
                tmp_path,
                env,
                lambda u: sent.append(u),
                lambda _: None,
                clock=lambda: STAMP,
            )
            == 1
        )
    assert sent == []
