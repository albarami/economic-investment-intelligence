"""Closed lead-shell commands: replay cannot touch the live transport."""

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import awards_proofs
from eii_custodian.publicdata.fetch.registry import Entry


class AwardProofCommandTests(unittest.TestCase):
    def test_replay_and_exit_status(self) -> None:
        for incomplete in (False, True):
            with self.subTest(incomplete=incomplete):
                report: dict[str, object] = {
                    "award_links": {"incomplete": incomplete, "results": []}
                }
                entry = object.__new__(Entry)
                object.__setattr__(entry, "source_id", "awards_owner_scrape")
                with (
                    patch.object(awards_proofs, "load_registry", return_value=(entry,)),
                    patch.object(
                        awards_proofs, "replay_awards", return_value=report
                    ) as replay,
                    patch.object(awards_proofs, "fetch_awards") as live,
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(
                        awards_proofs.main(["replay", "--cache", "SYN-cache"]),
                        int(incomplete),
                    )
                    self.assertEqual(
                        replay.call_args.args[:2], (entry, Path("SYN-cache"))
                    )
                    live.assert_not_called()

    def test_mode_is_closed(self) -> None:
        with (
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            with patch.object(
                awards_proofs,
                "load_registry",
                side_effect=AssertionError("unknown mode reached registry"),
            ):
                awards_proofs.main(["SYN-unknown", "--cache", "SYN-cache"])
        self.assertEqual(raised.exception.code, 2)

    def test_live_prints_counts_and_classes_without_intake_values(self) -> None:
        from types import SimpleNamespace

        entry = object.__new__(Entry)
        object.__setattr__(entry, "source_id", "awards_owner_scrape")
        check: dict[str, object] = {"incomplete": False, "results": []}
        side = {
            "award_links": check,
            "award_readers": {},
            "registration_match": "SYN confidential marker",
        }
        output = io.StringIO()
        with (
            patch.object(awards_proofs, "load_registry", return_value=(entry,)),
            patch.object(
                awards_proofs,
                "fetch_awards",
                return_value=SimpleNamespace(sidecar=side),
            ) as live,
            patch.object(awards_proofs, "replay_awards") as replay,
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(awards_proofs.main(["live", "--cache", "SYN-cache"]), 0)
            live.assert_called_once()
            replay.assert_not_called()
        self.assertNotIn("SYN confidential marker", output.getvalue())
        self.assertIn('"refused_count": 0', output.getvalue())

    def test_cache_argument_is_required(self) -> None:
        errors = io.StringIO()
        with (
            contextlib.redirect_stderr(errors),
            patch.object(
                awards_proofs,
                "load_registry",
                side_effect=AssertionError("missing cache reached registry"),
            ),
            self.assertRaises(SystemExit) as raised,
        ):
            awards_proofs.main(["replay"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn(
            "the following arguments are required: --cache", errors.getvalue()
        )
