"""Cleanup races, exact JSON bytes and locale-independent file operations."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

import eii_custodian.publicdata.investment_build as build


def test_discard_candidate_handles_missing_pointer_and_marker_names(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "SYN-source"
    directory.mkdir()
    table = directory / "XXXX.json"
    manifest = directory / "SYN-manifest.json"
    table.write_bytes(b"SYN-candidate")
    manifest.write_bytes(b"SYN-candidate")
    build._discard_candidate(tmp_path, "SYN-source", table, manifest)
    assert not table.exists()
    assert not manifest.exists()
    # A missing candidate is harmless, including on the second cleanup attempt.
    build._discard_candidate(tmp_path, "SYN-source", table, manifest)
    table = directory / "SYN-table.json"
    manifest = directory / "XXXX.json"
    table.write_bytes(b"SYN-candidate")
    manifest.write_bytes(b"SYN-candidate")
    build._discard_candidate(tmp_path, "SYN-source", table, manifest)
    assert not table.exists()
    assert not manifest.exists()


@pytest.mark.parametrize(
    "pointer", ["{}", '{"manifest_sha256": 3}', '{"manifest_sha256": "SYN-kept"}']
)
def test_discard_candidate_handles_incomplete_current_manifest(
    tmp_path: Path, pointer: str
) -> None:
    source = tmp_path / "SYN-source"
    (source / "manifests").mkdir(parents=True)
    (source / "loadable.json").write_text(pointer, encoding="utf-8")
    (source / "manifests/SYN-kept.json").write_text("{}", encoding="utf-8")
    build._discard_candidate(
        tmp_path, "SYN-source", source / "SYN-table.json", source / "SYN-new.json"
    )
    assert (source / "loadable.json").read_text(encoding="utf-8") == pointer
    assert (source / "manifests/SYN-kept.json").read_text(encoding="utf-8") == "{}"


def test_clear_partials_tolerates_a_disappearing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "SYN-cache"
    build._clear_partials(directory)
    directory.mkdir()
    vanished = directory / ".SYN.partial"
    vanished.write_bytes(b"SYN")

    def racing_scan(path: Path, pattern: str):
        assert path == directory
        assert pattern == "*.partial"
        vanished.unlink()
        return iter((vanished,))

    monkeypatch.setattr(Path, "rglob", racing_scan)
    build._clear_partials(directory)
    assert list(directory.iterdir()) == []


def test_read_json_returns_only_decoded_document(tmp_path: Path) -> None:
    source = tmp_path / "SYN-document.json"
    assert build._read_json(source) is None
    for body in ("[", "{", "SYN-bad"):
        source.write_text(body, encoding="utf-8")
        assert build._read_json(source) is None
    source.write_text('{"SYN-text": "café"}', encoding="utf-8")
    assert build._read_json(source) == {"SYN-text": "café"}


def test_text_io_is_utf8_even_with_ascii_process_locale(tmp_path: Path) -> None:
    module_path = Path(build.__file__).resolve()
    source_root = module_path.parents[2]
    source = tmp_path / "SYN-input.json"
    source.write_bytes(b'{"SYN-text": "caf\xc3\xa9"}')
    destination = tmp_path / "SYN-output.txt"
    program = (
        "import sys\n"
        "from pathlib import Path\n"
        "from eii_custodian.publicdata import investment_build\n"
        "assert Path(investment_build.__file__).resolve() == Path(sys.argv[3])\n"
        "assert investment_build._read_json(Path(sys.argv[1])) == {'SYN-text': 'caf\\u00e9'}\n"
        "investment_build._atomic_write(Path(sys.argv[2]), 'caf\\u00e9')\n"
        "assert Path(sys.argv[2]).read_bytes() == b'caf\\xc3\\xa9'\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8=0",
            "-c",
            program,
            str(source),
            str(destination),
            str(module_path),
        ],
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                (str(source_root), os.environ.get("PYTHONPATH", ""))
            ),
            "LC_ALL": "C",
            "PYTHONCOERCECLOCALE": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert destination.read_bytes() == b"caf\xc3\xa9"


def test_dump_sorts_and_escapes_with_exact_newline() -> None:
    assert build._dump({"z": "café", "a": 2}) == '{"a": 2, "z": "caf\\u00e9"}\n'


def test_atomic_json_digest_matches_exact_bytes(tmp_path: Path) -> None:
    destination = tmp_path / "SYN-cache/nested/SYN-document.json"
    expected = b'{"a": 2, "z": "caf\\u00e9"}\n'
    assert (
        build._atomic_json(destination, {"z": "café", "a": 2})
        == hashlib.sha256(expected).hexdigest()
    )
    assert destination.read_bytes() == expected
    assert [p.name for p in destination.parent.iterdir()] == ["SYN-document.json"]


def test_atomic_write_creates_parents_and_exact_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "SYN-cache/nested/SYN-text.json"
    calls: list[tuple[Path, Path]] = []

    def replacing(source: Path, target: Path) -> None:
        assert source == destination.with_name(".SYN-text.json.partial")
        assert target == destination
        assert source.read_bytes() == b"SYN-caf\xc3\xa9\n"
        calls.append((source, target))
        source.replace(target)

    monkeypatch.setattr(build, "_replace", replacing)
    build._atomic_write(destination, "SYN-café\n")
    assert len(calls) == 1
    assert destination.read_bytes() == b"SYN-caf\xc3\xa9\n"
