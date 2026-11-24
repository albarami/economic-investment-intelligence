"""Keep the native map-proof entry point in the test tooling plane."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/tests"))

from map_assets_server import main

if __name__ == "__main__":
    sys.exit(main())
