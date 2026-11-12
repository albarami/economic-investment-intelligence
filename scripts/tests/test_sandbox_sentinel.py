"""Sentinel reads and network attempts inside both profiles."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sandbox_support as support

import sandbox_check
import sandbox_launch as launch

pytestmark = pytest.mark.sandbox


class SentinelRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        support.require_environment(cls)

    def test_both_profiles_block_read_and_network(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            config = support.probe_config(fx, port, abstract, hidden=[])
            outside = support.run_outside(
                fx, config, ["read_outside", "tcp_loopback", "unix_abstract"]
            )
            self.assertEqual(
                outside, ["read_outside ok", "tcp_loopback ok", "unix_abstract ok"]
            )
            for profile in ("build-world", "build-release"):
                support.assert_inside(
                    self, support.run_inside(profile, fx, config, support.ATTEMPTS)
                )
            self.assertEqual(
                sorted(path.name for path in fx.outside.iterdir()), ["sentinel.txt"]
            )
            self.assertEqual(
                (fx.outside / "sentinel.txt").read_text(encoding="utf-8"), "sentinel\n"
            )

    def test_repository_secrets_are_not_mounted(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            link = fx.root / "data" / "public_cache" / "outside-link"
            link.symlink_to(fx.outside / "sentinel.txt")
            hidden = [str(path) for path in fx.hidden] + [str(link)]
            config = support.probe_config(fx, port, abstract, hidden=hidden)
            outside = support.run_outside(fx, config, ["hidden"])
            self.assertEqual(outside, [f"hidden {index} ok" for index in range(5)])
            expected = [
                f"hidden {index} error FileNotFoundError ENOENT" for index in range(5)
            ]
            for profile in ("build-world", "build-release"):
                self.assertEqual(
                    support.run_inside(profile, fx, config, ["hidden"]), expected
                )

    def test_planted_leaks_are_seen(self) -> None:
        plants = [
            (
                "no-unshare-net",
                ["tcp_loopback", "unix_abstract"],
                ["tcp_loopback ok", "unix_abstract ok"],
            ),
            ("share-net", ["tcp_loopback"], ["tcp_loopback ok"]),
            ("bind-outside", ["read_outside"], ["read_outside ok"]),
            ("cache-writable", ["write_cache"], ["write_cache ok"]),
            ("no-remount-ro", ["write_root"], ["write_root ok"]),
            (
                "no-extension-remount-ro",
                ["write_extensions"],
                ["write_extensions ok"],
            ),
            ("no-clearenv", ["env"], None),
            ("bind-repo", ["hidden"], ["hidden 0 ok"]),
        ]
        labels = []
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            config = support.probe_config(
                fx, port, abstract, hidden=[str(fx.hidden[0])]
            )
            for kind, attempts, expected in plants:
                labels.append(kind)
                env = (
                    {"EII_PLANTED_SECRET": "planted-value-1234"}
                    if kind == "no-clearenv"
                    else {}
                )
                command = launch.python_command(
                    str(fx.root / support.PROBE_REL), config, *attempts
                )
                with support.sandbox_argv(fx, "build-world", command) as (
                    argv,
                    descriptors,
                ):
                    lines = support.run_argv(
                        support.mutate(argv, kind, fx), descriptors, env
                    )
                if kind == "no-clearenv":
                    self.assertEqual(len(lines), 1)
                    self.assertIn("EII_PLANTED_SECRET", lines[0])
                else:
                    self.assertEqual(lines, expected)
                if kind == "cache-writable":
                    self.assertTrue(
                        (fx.root / "data" / "public_cache" / "new.txt").is_file()
                    )
        self.assertEqual(len(labels), 8)

    def test_network_attempts_table(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            self.assertNotIn(port, sandbox_check.BANNED_PORTS)
            fx = support.make_fixture(tmp)
            config = support.probe_config(fx, port, abstract, hidden=[])
            for profile in ("build-world", "build-release"):
                lines = support.run_inside(
                    profile, fx, config, ["tcp_unrouted", "dns_lookup"]
                )
                self.assertEqual(lines[0], "tcp_unrouted error OSError ENETUNREACH")
                self.assertRegex(lines[1], r"dns_lookup error gaierror -[23]")
            command = launch.python_command(
                str(fx.root / support.PROBE_REL), config, "dns_lookup", "tcp_loopback"
            )
            with support.sandbox_argv(fx, "build-world", command) as (
                argv,
                descriptors,
            ):
                lines = support.run_argv(
                    support.mutate(argv, "share-net", fx), descriptors, {}
                )
            self.assertRegex(lines[0], r"dns_lookup error gaierror -[23]")
            self.assertEqual(lines[1], "tcp_loopback ok")

    def test_scenario_and_staging_mounts(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            sandbox_check.listeners() as (port, abstract),
        ):
            fx = support.make_fixture(tmp)
            hidden = [str(fx.root / "data" / "releases" / "r1" / "manifest.txt")]
            config = support.probe_config(fx, port, abstract, hidden=hidden)
            attempts = ["read_scenario", "write_scenario", "write_staging", "hidden"]
            world = support.run_inside("build-world", fx, config, attempts)
            self.assertEqual(
                world,
                [
                    "read_scenario ok",
                    "write_scenario error OSError EROFS",
                    "write_staging error FileNotFoundError ENOENT",
                    "hidden 0 error FileNotFoundError ENOENT",
                ],
            )
            release = support.run_inside("build-release", fx, config, attempts)
            self.assertEqual(
                release,
                [
                    "read_scenario error FileNotFoundError ENOENT",
                    "write_scenario error FileNotFoundError ENOENT",
                    "write_staging ok",
                    "hidden 0 error FileNotFoundError ENOENT",
                ],
            )
            staging = fx.root / "data" / "releases" / ".staging" / "b1" / "s.txt"
            self.assertEqual(staging.read_bytes(), b"x")
