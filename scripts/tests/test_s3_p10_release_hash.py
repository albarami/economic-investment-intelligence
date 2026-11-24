"""S3-P10 round 2 (L-1509): the lead's release build hashes the setting's file.

The hash is computed from the bytes of the file that EII_FC_REGISTER_FILE
names, in the lead's shell, never typed. No second setting carries it.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import s3_t28_support  # noqa: F401  (puts scripts, core and product on the path)

from operations.build import build_release
from operations.common import Refusal
from operations.config import runtime_environment

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "product/tests/fixtures/fc_register/stand_in_register.json"
NAME = "EII_FC_REGISTER_FILE"


class _Stop(Exception):
    pass


class ReleaseHash(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.cache = self.root / "cache"
        (self.cache / "review").mkdir(parents=True)
        (self.cache / "review/release_spec.json").write_text("{}")
        self.secret = self.root / "INVENTED-secret-place"
        self.secret.mkdir()
        self.file = self.secret / "register.json"
        self.file.write_bytes(FIXTURE.read_bytes())

    def _build(self, environ: dict[str, str]) -> Mock:
        produce = Mock(side_effect=_Stop)
        sandbox = Mock()
        with (
            patch.dict(os.environ, environ, clear=True),
            patch("eii_custodian.release.producer.produce", produce),
            self.assertRaises(Refusal) as caught,
        ):
            build_release(self.root, cache=self.cache, sandbox=sandbox, validate=Mock())
        sandbox.assert_not_called()
        self.refusal = caught.exception
        return produce

    def test_the_build_lists_the_sha256_of_the_bytes_it_read(self) -> None:
        produce = self._build({NAME: str(self.file)})
        expected = hashlib.sha256(self.file.read_bytes()).hexdigest()
        produce.assert_called_once_with(self.cache, fc_register_sha256=expected)
        self.assertEqual(self.refusal.reason, "operation_failed")

    def test_an_unset_setting_lists_nothing(self) -> None:
        produce = self._build({})
        produce.assert_called_once_with(self.cache, fc_register_sha256=None)

    def test_an_unreadable_file_refuses_before_the_producer_without_the_path(
        self,
    ) -> None:
        for value in (str(self.secret / "absent.json"), str(self.secret)):
            with self.subTest(kind=Path(value).name):
                produce = self._build({NAME: value})
                produce.assert_not_called()
                self.assertEqual(self.refusal.reason, "fc_register_unreadable")
                for text in (str(self.refusal), repr(self.refusal)):
                    self.assertNotIn("INVENTED-secret-place", text)
                self.assertIsNone(self.refusal.__cause__)

    def test_a_multi_line_setting_refuses_without_the_value(self) -> None:
        produce = self._build({NAME: str(self.file) + "\nINVENTED-secret-place"})
        produce.assert_not_called()
        self.assertEqual(self.refusal.reason, "fc_register_unreadable")
        self.assertNotIn("INVENTED-secret-place", repr(self.refusal))

    def test_a_second_setting_for_the_hash_is_refused_in_every_environment(
        self,
    ) -> None:
        for environment in ("development", "staging", "live"):
            for planted in ("EII_FC_REGISTER_SHA256", "EII_FC_REGISTER_HASH"):
                with (
                    self.subTest(environment=environment, planted=planted),
                    self.assertRaisesRegex(Refusal, "^unwanted_runtime_setting$"),
                ):
                    runtime_environment(
                        {
                            "EII_ENVIRONMENT": environment,
                            planted: "ab" * 32,
                        }
                    )


if __name__ == "__main__":
    unittest.main()
