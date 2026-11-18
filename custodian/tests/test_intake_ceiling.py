"""S2-T08 part B, mismatch class 8: a bounded refusal for oversize bodies.

The live shape pack's Mismatches item 8 shows one file declaring about two
gigabytes and two portal exports passing the probe's 300 MiB cap with no
Content-Length, all read whole by ``open_https``. The general intake ceiling of
300 MiB is a lead default awaiting the owner's answer. It refuses a declared
size above it before any read and an undeclared body as soon as one byte more
than the ceiling arrives. A lower scoped source cap keeps its own refusal. A
refused body is never published and an earlier snapshot is never touched.
Every body below is invented; the ceiling is lowered in the tests so no test
allocates a large body.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from custodian.tests.test_publicdata_behaviour import FILE_URL, _clock, _entry, _sleep

from eii_custodian.publicdata.fetch import transport
from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.transport import (
    INTAKE_CEILING_BYTES,
    INTAKE_CEILING_STATUS,
    BodyTooLarge,
    TransportFault,
    metadata_limit,
    open_https,
)

SMALL = 16


class _Body:
    def __init__(self, body: bytes, length: str | None) -> None:
        self._body = body
        self.headers = {} if length is None else {"Content-Length": length}
        self.reads: list[int] = []

    def __enter__(self) -> _Body:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def geturl(self) -> str:
        return FILE_URL

    def read(self, size: int = -1) -> bytes:
        self.reads.append(size)
        return self._body if size < 0 else self._body[:size]


def _serve(monkeypatch: pytest.MonkeyPatch, body: bytes, length: str | None) -> _Body:
    answer = _Body(body, length)
    monkeypatch.setattr(
        transport.urllib.request,
        "build_opener",
        lambda *_args: SimpleNamespace(open=lambda *_a, **_k: answer),
    )
    return answer


@pytest.fixture
def small(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(transport, "INTAKE_CEILING_BYTES", SMALL)


def test_the_ceiling_is_300_mib_and_marked_as_the_lead_default() -> None:
    assert INTAKE_CEILING_BYTES == 300 * 1024 * 1024
    assert INTAKE_CEILING_STATUS == "lead default awaiting the owner's answer"
    assert issubclass(BodyTooLarge, TransportFault)


def test_a_declared_size_above_the_real_ceiling_is_refused_before_any_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declared = str(INTAKE_CEILING_BYTES + 1)
    answer = _serve(monkeypatch, b"", declared)
    with pytest.raises(BodyTooLarge) as refused:
        open_https(FILE_URL)
    assert answer.reads == []
    assert (refused.value.kind, refused.value.ceiling, refused.value.observed) == (
        "body_bytes",
        INTAKE_CEILING_BYTES,
        f"declared {declared}",
    )


@pytest.mark.usefixtures("small")
def test_an_undeclared_body_over_the_ceiling_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = _serve(monkeypatch, b"x" * (SMALL + 5), None)
    with pytest.raises(BodyTooLarge) as refused:
        open_https(FILE_URL)
    # One read of at most the ceiling and one byte: nothing larger is asked for.
    assert answer.reads == [SMALL + 1]
    assert refused.value.observed == f"more than {SMALL}"


@pytest.mark.usefixtures("small")
@pytest.mark.parametrize("length", [None, str(SMALL)], ids=["undeclared", "declared"])
def test_a_body_of_exactly_the_ceiling_is_admitted(
    monkeypatch: pytest.MonkeyPatch, length: str | None
) -> None:
    _serve(monkeypatch, b"x" * SMALL, length)
    assert open_https(FILE_URL).body == b"x" * SMALL


@pytest.mark.usefixtures("small")
def test_one_declared_byte_over_the_ceiling_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = _serve(monkeypatch, b"x" * SMALL, str(SMALL + 1))
    with pytest.raises(BodyTooLarge):
        open_https(FILE_URL)
    assert answer.reads == []


@pytest.mark.usefixtures("small")
def test_a_lower_scoped_cap_keeps_its_own_read_and_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = _serve(monkeypatch, b"x" * 10, str(SMALL + 1))
    with metadata_limit(4):
        body = open_https(FILE_URL).body
    # The caller's own bound decides; the general ceiling does not intervene.
    assert answer.reads == [5]
    assert body == b"x" * 5


@pytest.mark.usefixtures("small")
def test_a_higher_scoped_cap_does_not_lift_the_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer = _serve(monkeypatch, b"x" * (SMALL + 1), None)
    with metadata_limit(SMALL * 4), pytest.raises(BodyTooLarge):
        open_https(FILE_URL)
    assert answer.reads == [SMALL + 1]


def _tree(folder: Path) -> dict[str, str]:
    return {
        str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


@pytest.mark.usefixtures("small")
@pytest.mark.parametrize(
    "length", [None, str(SMALL + 1)], ids=["undeclared", "declared"]
)
def test_a_refused_body_is_not_published_and_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, length: str | None
) -> None:
    calls: list[str] = []

    def opener(url: str):
        calls.append(url)
        return open_https(url)

    _serve(monkeypatch, b"x" * (SMALL + 1), length)
    failure = fetch_entry(_entry(), opener, tmp_path, _clock, _sleep)
    assert failure is not None
    assert (failure.check, failure.expected, failure.observed) == (
        "body_bytes",
        f"at most {SMALL} bytes",
        f"declared {SMALL + 1}" if length else f"more than {SMALL}",
    )
    assert calls == [FILE_URL]
    assert _tree(tmp_path) == {}


@pytest.mark.usefixtures("small")
def test_a_refusal_leaves_the_prior_snapshot_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _serve(monkeypatch, b"SYN prior", None)
    assert fetch_entry(_entry(), open_https, tmp_path, _clock, _sleep) is None
    before = _tree(tmp_path)
    assert before
    _serve(monkeypatch, b"x" * (SMALL + 1), None)
    failure = fetch_entry(_entry(), open_https, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "body_bytes"
    assert _tree(tmp_path) == before
