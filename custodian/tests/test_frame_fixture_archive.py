"""The invented boundary archive is the same bytes whatever the clock says."""

from __future__ import annotations

import hashlib
import time

import pytest
from custodian.tests.fixtures.frame.invented import invented_archive


def test_invented_archive_bytes_do_not_follow_the_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two builds an hour apart give one hash, so a test may build it twice."""
    real = time.time()
    monkeypatch.setattr(time, "time", lambda: real)
    first = hashlib.sha256(invented_archive()).hexdigest()
    monkeypatch.setattr(time, "time", lambda: real + 3600)
    second = hashlib.sha256(invented_archive()).hexdigest()
    assert first == second
