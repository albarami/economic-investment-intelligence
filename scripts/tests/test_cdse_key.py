"""Optional CDSE command wiring; invented credentials and no public connections."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cdse_key
import commands.build_public as command
from eii_custodian.publicdata.fetch.build import BuildOutcome
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.transport import Response


class CdseWiring(unittest.TestCase):
    def test_reader_partial_and_redacted(self) -> None:
        names = ("CDSE_CLIENT_ID", "CDSE_CLIENT_SECRET")
        for values in (
            ("", ""),
            ("FAKE-CDSE-ID", ""),
            ("", "FAKE-CDSE-SECRET"),
            (" ", "\t"),
        ):
            self.assertIsNone(
                cdse_key.cdse_credentials(dict(zip(names, values, strict=True)))
            )
        pair = cdse_key.cdse_credentials(
            dict(zip(names, ("FAKE-CDSE-ID", "FAKE-CDSE-SECRET"), strict=True))
        )
        self.assertIsNotNone(pair)
        self.assertNotIn("FAKE-CDSE", repr(pair))

    def test_optional_mode_never_opens_before_verification(self) -> None:
        complete = {
            "CDSE_CLIENT_ID": "FAKE-CDSE-ID",
            "CDSE_CLIENT_SECRET": "FAKE-CDSE-SECRET",
        }
        for env in (
            {},
            {"CDSE_CLIENT_ID": "FAKE-CDSE-ID"},
            {"CDSE_CLIENT_SECRET": "FAKE-CDSE-SECRET"},
            {"CDSE_CLIENT_ID": "", "CDSE_CLIENT_SECRET": ""},
            {"CDSE_CLIENT_ID": "", "CDSE_CLIENT_SECRET": "FAKE-CDSE-SECRET"},
            {"CDSE_CLIENT_ID": "FAKE-CDSE-ID", "CDSE_CLIENT_SECRET": ""},
            {"CDSE_CLIENT_ID": " \t", "CDSE_CLIENT_SECRET": "FAKE-CDSE-SECRET"},
            {"CDSE_CLIENT_ID": "FAKE-CDSE-ID", "CDSE_CLIENT_SECRET": " \t"},
            complete,
        ):
            with (
                self.subTest(env=env),
                tempfile.TemporaryDirectory() as folder,
                patch("socket.socket", side_effect=AssertionError("network")),
                patch("subprocess.Popen", side_effect=AssertionError("child")),
                patch.object(command, "run_build", side_effect=AssertionError("build")),
                patch("pathlib.Path.open", side_effect=AssertionError("file")),
                patch("pathlib.Path.mkdir", side_effect=AssertionError("directory")),
                contextlib.redirect_stdout(io.StringIO()) as out,
                contextlib.redirect_stderr(io.StringIO()) as err,
            ):
                self.assertEqual(command.run(Path(folder), env, ("--cdse-backup",)), 0)
                self.assertIn("omitted", out.getvalue())
                self.assertNotIn("FAKE-CDSE", out.getvalue())
                self.assertEqual(err.getvalue(), "")
                expected = (
                    "provider_contract_pending"
                    if env == complete
                    else "credentials_absent"
                )
                self.assertEqual(
                    out.getvalue(), f"satellite_cdse_backup omitted: {expected}\n"
                )
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_default_never_selects_backup(self) -> None:
        from custodian.tests.method_pin_config_fixture import (
            stage_tracked_configuration,
        )

        entries = load_registry()
        self.assertTrue(any(e.source_id == "satellite_cdse_backup" for e in entries))
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(command, "run_build") as build,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            stage_tracked_configuration(Path(folder))
            build.return_value.lines = ()
            build.return_value.failure = None
            command.run(
                Path(folder),
                {
                    "CDSE_CLIENT_ID": "FAKE-CDSE-ID",
                    "CDSE_CLIENT_SECRET": "FAKE-CDSE-SECRET",
                },
                (),
                transport=lambda url: Response(url, b"", ()),
            )
            selected = build.call_args.args[0]
            self.assertFalse(
                any(e.source_id == "satellite_cdse_backup" for e in selected)
            )

    def test_default_without_environment_never_reads_backup_credentials(self) -> None:
        def offline(url: str) -> Response:
            return Response(url, b"", ())

        from custodian.tests.method_pin_config_fixture import (
            stage_tracked_configuration,
        )

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(os.environ, {}, clear=True),
            patch("socket.socket", side_effect=AssertionError("network")),
            patch("subprocess.Popen", side_effect=AssertionError("child")),
            patch.object(
                command, "cdse_credentials", side_effect=AssertionError("backup reader")
            ) as reader,
            patch.object(
                command, "run_build", return_value=BuildOutcome((), None)
            ) as build,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            root = Path(folder)
            stage_tracked_configuration(root)
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            self.assertEqual(command.run(root, {}, (), transport=offline), 0)
            reader.assert_not_called()
            build.assert_called_once()
            selected = build.call_args.args[0]
            self.assertTrue(selected)
            self.assertFalse(
                any(e.source_id == "satellite_cdse_backup" for e in selected)
            )
            self.assertIs(build.call_args.args[1], offline)
            self.assertEqual(
                sorted(path.relative_to(root) for path in root.rglob("*")), before
            )

    def test_unknown_extra_flags_refused_before_reader(self) -> None:
        with (
            patch.object(
                command, "cdse_credentials", side_effect=AssertionError("reader")
            ),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            for args in (("--cdse-backup", "extra"), ("--url",), ("--proof",)):
                self.assertEqual(command.run(Path("."), {}, args), 2)
