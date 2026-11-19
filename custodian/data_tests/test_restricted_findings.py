"""PYTEST_DONT_REWRITE — lead-shell-only pinned restricted-source findings."""

import pytest

from .cache import CACHE
from .local_expectations import check_case
from .restricted_cases import CASES


@pytest.mark.parametrize("case", CASES, ids=[case.case_id for case in CASES])
def test_restricted_finding(case):
    check_case(CACHE, case)
