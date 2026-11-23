"""Give scripts tests the custodian test fixtures under the runner's ``-P``.

``./eii test`` runs pytest with ``python -P``, so the repository root is not
on the import path and ``custodian.tests`` cannot be found from a scripts
test unless the root is added first. Import the fixtures from here.
"""

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from custodian.tests.method_pin_config_fixture import (  # noqa: E402 (after the root)
    stage_tracked_configuration,
)

__all__ = ["stage_tracked_configuration"]
