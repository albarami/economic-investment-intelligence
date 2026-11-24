"""Start the pinned browser runner of ``./eii remote-check``: bounded, silent.

The command module names the fixed argument list; nothing of the child's own
output is printed or kept, and a child that outlives its bound is stopped
with every process it started.
"""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path


def launch(
    argv: Sequence[str], cwd: Path, env: Mapping[str, str], seconds: float
) -> int | None:
    """The child's exit code, or ``None`` when it was stopped at its bound."""
    child = subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        return child.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        return None
    finally:
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
