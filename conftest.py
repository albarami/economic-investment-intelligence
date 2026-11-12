"""pytest bootstrap: one Hypothesis profile and one printed seed (TST-07)."""

import random
import time
from datetime import timedelta

import pytest
from hypothesis import settings

settings.register_profile(
    "eii",
    settings.get_profile("default"),
    max_examples=100,
    deadline=timedelta(milliseconds=200),
    derandomize=False,
    database=None,
    print_blob=True,
)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("hypothesis_seed") is None:
        config.option.hypothesis_seed = str(int(time.time()))
    random.seed(int(config.getoption("hypothesis_seed")))


def pytest_report_header(config: pytest.Config) -> str:
    return f"eii seed={config.getoption('hypothesis_seed')}"
