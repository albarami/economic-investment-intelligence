"""S3-T16: ``./eii test`` gives no suite either provider key or service base."""

from __future__ import annotations

import unittest
from pathlib import Path

import run_tests_exec

PROVIDER = {
    "ESRI_API_KEY": "SYN-imagery-key",
    "MAPTILE_API_KEY": "SYN-photoreal-key",
    "EII_IMAGERY_TILE_BASE": "https://imagery.provider.invalid/",
    "EII_PHOTOREAL_TILE_BASE": "https://tiles.provider.invalid/",
}


class RunnerNoProviderKey(unittest.TestCase):
    def test_no_suite_kind_receives_a_provider_setting(self) -> None:
        parent = {"PATH": "/usr/bin", "HOME": "/home/SYN", **PROVIDER}
        for kind in run_tests_exec.KINDS:
            with self.subTest(kind=kind):
                env = run_tests_exec.child_env(kind, parent, 1000000001, Path("t"))
                self.assertEqual(sorted(set(env) & set(PROVIDER)), [])
                self.assertNotIn("SYN-imagery-key", env.values())
                self.assertNotIn("SYN-photoreal-key", env.values())


if __name__ == "__main__":
    unittest.main()
