"""Retain the full existing three-plane guard with the new package present."""

import tempfile
import unittest
from pathlib import Path

import import_boundary_cases as cases
import import_boundary_guard as guard


class GatewayBoundary(unittest.TestCase):
    def test_real_tree_forbids_gateway_in_core(self) -> None:
        root = Path(__file__).resolve().parents[3]
        self.assertEqual(guard.check_imports(root), ([], []))
        with tempfile.TemporaryDirectory() as folder:
            planted = Path(folder)
            cases.make_tree(planted, gateway=True)
            cases.write_planted(planted, "eii_core", "import eii_gateway\n")
            failures, _ = guard.check_imports(planted)
            self.assertEqual(len(failures), 1)
            self.assertIn("eii_core -> eii_gateway", failures[0])
