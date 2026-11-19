"""Let pytest import the derivation module that sits beside its tests.

The repository runs pytest with ``--import-mode=importlib``, which does not put
a test file's own folder on the import path. The tests of decision record 0062
import ``derive_tolerances`` from this folder, as the unittest command in the
record does when it runs here, so this folder is added to the path for them.
"""

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
