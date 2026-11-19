"""Command seed validation happens before inputs, credentials or connections."""

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from commands import build_public
from eii_custodian.publicdata.fetch.build import BuildOutcome, run_build


@pytest.mark.parametrize(
    "args",
    [
        ["--seed"],
        ["--seed", "oops"],
        ["--seed", "-1"],
        ["--seed", "1", "extra"],
        ["--seed", "1", "--seed", "2"],
        ["--seed", "\u0661"],
        ["--other"],
        ["--seed", "1", "--cdse-backup"],
        ["--cdse-backup", "--seed", "1"],
        ["--cdse-backup", "x"],
    ],
)
def test_invalid_seed_has_no_reads_or_connections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    def forbidden(*a: Any, **k: Any) -> Any:
        pytest.fail("input read before seed validation")

    monkeypatch.setattr(build_public, "load_registry", forbidden)
    monkeypatch.setattr(build_public, "earthdata_token", forbidden)
    monkeypatch.setattr(build_public, "cdse_credentials", forbidden)
    assert build_public.run(tmp_path, {}, args, transport=forbidden) == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("args,seed", [([], 0), (["--seed", "17"], 17)])
def test_valid_seed_reaches_the_real_build_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], seed: int
) -> None:
    monkeypatch.setattr(build_public, "load_registry", lambda: ())
    runner = Mock(return_value=BuildOutcome((), None))
    monkeypatch.setattr(build_public, "run_build", runner)
    assert (
        build_public.run(
            tmp_path, {}, args, transport=lambda url: pytest.fail("network")
        )
        == 0
    )
    assert runner.call_args.kwargs["seed"] == seed


def test_run_build_calls_ordered_production_assembly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata import assembly_adapters

    seen = []

    def run(self: Any) -> tuple[str, ...]:
        seen.append(self.seed)
        return ()

    monkeypatch.setattr(assembly_adapters.Production, "run", run)
    outcome = run_build(
        (),
        lambda url: pytest.fail("network"),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda seconds: None,
        seed=17,
    )
    assert outcome.failure is None
    assert seen == [17]


@pytest.mark.parametrize(
    "message,expected",
    [
        ("snapshot_selection_invalid", "snapshot_selection_invalid"),
        ("SYN-sensitive-path", "assembly_build_refused"),
    ],
)
def test_only_closed_assembly_refusals_reach_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message: str, expected: str
) -> None:
    from eii_custodian.publicdata.assembly import AssemblyError
    from eii_custodian.publicdata.assembly_adapters import Production

    def refuse(self: Any) -> tuple[str, ...]:
        raise AssemblyError(message)

    monkeypatch.setattr(Production, "run", refuse)
    outcome = run_build(
        (),
        lambda url: pytest.fail("network"),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda seconds: None,
        seed=17,
    )
    assert outcome.failure is not None
    assert outcome.failure.check == expected
    assert "SYN-sensitive-path" not in str(outcome)


def test_usage_shows_effective_public_draw_seed() -> None:
    from commands.table import by_word

    assert by_word("build-public").form == "build-public [--seed N]"


@pytest.mark.parametrize(
    "word",
    [
        "municipality_frame_not_supplied",
        "unmapped_municipality_spelling",
        "municipality_names_refused",
        "selected_input_refused",
    ],
)
def test_typed_series_refusals_preserve_only_closed_word(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, word: str
) -> None:
    from eii_custodian.publicdata.assembly_adapters import Production
    from eii_custodian.publicdata.series.parse import SeriesRefused

    def refused(self: Any) -> tuple[str, ...]:
        raise SeriesRefused(word, "SYN-sensitive-input-text")

    monkeypatch.setattr(Production, "run", refused)
    result = run_build(
        (),
        lambda url: pytest.fail("network"),
        tmp_path,
        lambda: "2026-11-18T00:00:00Z",
        lambda seconds: None,
        seed=17,
    )
    assert result.failure is not None
    assert result.failure.check == word
    assert "SYN-sensitive-input-text" not in str(result)
