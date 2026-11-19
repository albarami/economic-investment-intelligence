"""Optional CDSE command wiring; invented credentials and no public connections."""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cdse_key
import commands.build_public as command
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
        for env in (
            {},
            {"CDSE_CLIENT_ID": "FAKE-CDSE-ID"},
            {"CDSE_CLIENT_SECRET": "FAKE-CDSE-SECRET"},
            {
                "CDSE_CLIENT_ID": "FAKE-CDSE-ID",
                "CDSE_CLIENT_SECRET": "FAKE-CDSE-SECRET",
            },
        ):
            with (
                tempfile.TemporaryDirectory() as folder,
                patch("socket.socket", side_effect=AssertionError("network")),
                patch("subprocess.Popen", side_effect=AssertionError("child")),
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                self.assertEqual(command.run(Path(folder), env, ("--cdse-backup",)), 0)
                self.assertIn("omitted", out.getvalue())
                self.assertNotIn("FAKE-CDSE", out.getvalue())
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_default_never_selects_backup(self) -> None:
        entries = load_registry()
        self.assertTrue(any(e.source_id == "satellite_cdse_backup" for e in entries))
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(command, "run_build") as build,
            contextlib.redirect_stdout(io.StringIO()),
        ):
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

    def test_unknown_extra_flags_refused_before_reader(self) -> None:
        with (
            patch.object(
                command, "cdse_credentials", side_effect=AssertionError("reader")
            ),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            for args in (("--cdse-backup", "extra"), ("--url",), ("--proof",)):
                self.assertEqual(command.run(Path("."), {}, args), 2)
