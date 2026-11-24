"""The web catalogue export writes one file and refuses a broken folder."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import export_web_catalogue

ROOT = Path(__file__).resolve().parents[2]


class ExportWebCatalogue(unittest.TestCase):
    def test_check_matches_the_committed_file(self) -> None:
        """The documented --check command writes nothing and exits 0."""
        before = (
            ROOT / "web" / "src" / "brief" / "catalogue.generated.json"
        ).read_bytes()
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "export_web_catalogue.py"),
                "--check",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        after = (
            ROOT / "web" / "src" / "brief" / "catalogue.generated.json"
        ).read_bytes()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, after)

    def test_refusal_writes_nothing(self) -> None:
        """An unknown catalogue key exits non-zero and leaves no file."""
        source = ROOT / "product/src/eii_product/assistant/catalogue/assets"
        with tempfile.TemporaryDirectory(prefix="eii-catalogue-") as tmp:
            folder = Path(tmp) / "catalogue"
            shutil.copytree(source, folder)
            claims = folder / "claims.yaml"
            claims.write_text(
                claims.read_text(encoding="utf-8") + "unknown_key: true\n",
                encoding="utf-8",
            )
            target = Path(tmp) / "out.json"
            self.assertIsNone(export_web_catalogue.render_catalogue(folder))
            code = export_web_catalogue.run(folder, target, check=False)
            self.assertEqual(code, 1)
            self.assertFalse(target.exists())

    def _exported(self, tmp: str) -> tuple[Path, Path, str]:
        source = ROOT / "product/src/eii_product/assistant/catalogue/assets"
        folder = Path(tmp) / "catalogue"
        shutil.copytree(source, folder)
        target = Path(tmp) / "out.json"
        code = export_web_catalogue.run(folder, target, check=False)
        self.assertEqual(code, 0)
        return folder, target, target.read_text(encoding="utf-8")

    def _check(self, folder: Path, target: Path) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            code = export_web_catalogue.run(folder, target, check=True)
        return code, buffer.getvalue().strip()

    def test_stale_file_fails_by_name(self) -> None:
        """A fresh export with one key changed is refused as stale."""
        with tempfile.TemporaryDirectory(prefix="eii-catalogue-") as tmp:
            folder, target, fresh = self._exported(tmp)
            planted = fresh.replace("foundation_note", "foundation_leaf", 1)
            self.assertNotEqual(planted, fresh)
            target.write_text(planted, encoding="utf-8")
            code, fault = self._check(folder, target)
            self.assertEqual(code, 1)
            self.assertEqual(fault, "stale")

    def test_changed_catalogue_version_fails(self) -> None:
        """A well-formed file with another version is refused by that name."""
        with tempfile.TemporaryDirectory(prefix="eii-catalogue-") as tmp:
            folder, target, fresh = self._exported(tmp)
            parsed = json.loads(fresh)
            parsed["version"] = "a" * 64
            target.write_text(json.dumps(parsed), encoding="utf-8")
            code, fault = self._check(folder, target)
            self.assertEqual(code, 1)
            self.assertEqual(fault, "changed-version")

    def test_malformed_export_fails(self) -> None:
        """A file that is not the export's JSON is refused as malformed."""
        with tempfile.TemporaryDirectory(prefix="eii-catalogue-") as tmp:
            folder, target, _fresh = self._exported(tmp)
            target.write_text("{", encoding="utf-8")
            code, fault = self._check(folder, target)
            self.assertEqual(code, 1)
            self.assertEqual(fault, "malformed")
