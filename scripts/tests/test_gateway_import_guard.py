"""Planted forbidden consumers and the actual repository."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gateway_import_guard import check_gateway_imports, check_repository


class GatewayImportGuardTest(unittest.TestCase):
    def test_real_tree(self) -> None:
        self.assertEqual(check_repository(Path(__file__).resolve().parents[2]), [])

    def test_product_import_fails(self) -> None:
        for directory in ("core", "custodian", "product", "web", "infra"):
            for statement in (
                "import eii_gateway\n",
                "from eii_gateway.types import Request\n",
                '__import__("eii_gateway")\n',
            ):
                with (
                    self.subTest(directory=directory, statement=statement),
                    tempfile.TemporaryDirectory() as folder,
                ):
                    root = Path(folder)
                    rel = f"{directory}/synthetic_consumer.py"
                    (root / directory).mkdir()
                    (root / rel).write_text(statement)
                    self.assertEqual(
                        check_gateway_imports(root, [rel]),
                        [
                            f"FAIL gateway-import: {rel}:1: consumer outside scripts or evals"
                        ],
                    )

    def test_tooling_and_internal_imports_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for directory in ("scripts", "evals", "gateway"):
                (root / directory).mkdir()
                (root / directory / "synthetic_consumer.py").write_text(
                    "import eii_gateway\n"
                )
            (root / "synthetic_control.py").write_text(
                "import json\nfrom pathlib import Path\nprint('eii_gatewayish')\n"
            )
            self.assertEqual(
                check_gateway_imports(
                    root,
                    [
                        "synthetic_control.py",
                        "README.md",
                        "scripts/synthetic_consumer.py",
                        "evals/synthetic_consumer.py",
                        "gateway/synthetic_consumer.py",
                    ],
                ),
                [],
            )
