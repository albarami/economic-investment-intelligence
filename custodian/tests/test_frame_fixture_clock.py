"""Invented archive bytes must not depend on the ZIP writer's clock."""

from unittest.mock import patch

from custodian.tests.fixtures.frame.invented import invented_archive


def test_invented_archive_is_clock_independent() -> None:
    with patch("zipfile.time.localtime", return_value=(2020, 1, 2, 3, 4, 6, 0, 2, 0)):
        early = invented_archive()
    with patch("zipfile.time.localtime", return_value=(2024, 5, 6, 7, 8, 10, 0, 2, 0)):
        late = invented_archive()
    assert early == late
