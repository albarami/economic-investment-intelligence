"""Hash-seed guard for the unstable-key evidence test (S2-T40, ruling L-1050)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEST_NODE = (
    "custodian/tests/test_investment_evidence_survivors_8.py"
    "::test_unstable_caller_key_never_invents_identifier_text"
)
# The whole-test runner passes the run seed as PYTHONHASHSEED, so the guarded
# test must hold for every string hash seed, not for the seeds of one run. The
# first four are the ruling's seeds; the rest spread the row dict's slot
# layouts further, including the two seeds named by earlier runs.
HASH_SEEDS = (
    0,
    1,
    2,
    3764211809,
    3,
    7,
    42,
    1794000022,
    4146161478,
)


@pytest.mark.parametrize("seed", HASH_SEEDS)
def test_unstable_key_evidence_holds_under_hash_seed(seed: int) -> None:
    """The unstable-key evidence test passes in a child under this hash seed."""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    child = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_NODE, "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert child.returncode == 0, (
        f"hash seed {seed}: exit {child.returncode}\n"
        f"{child.stdout[-2000:]}\n{child.stderr[-2000:]}"
    )
