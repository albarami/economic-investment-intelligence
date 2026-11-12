"""Fetch, verify and staged scan of the pinned secret scanner."""

from __future__ import annotations

import contextlib
import hashlib
import io
import shutil
import sys
import tarfile
import tempfile
import tomllib
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hooks_support as support

import hooks_gitleaks

_PINS = '[[component]]\nname = "gitleaks"\npin = "8.30.1"\n'
_MEMBER = b"#!/bin/sh\necho 8.30.1\n"
_SHAPES = (
    ("cloud_key", "aws-access-token"),
    ("model_key", "anthropic-api-key"),
    ("github_token", "github-pat"),
    ("private_key_block", "private-key"),
)


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> _Body:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _archive(name: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(content)
        info.mode = 0o755
        info.type = tarfile.REGTYPE
        archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def _walk_keys(value: object, found: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            found.append(str(key))
            _walk_keys(item, found)
    elif isinstance(value, list):
        for item in value:
            _walk_keys(item, found)


class HooksGitleaks(unittest.TestCase):
    def _home(self) -> tuple[Path, dict[str, str]]:
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        env = support.clean_env(home, [support.system_bin(home)])
        return home, env

    def _scan_repo(self, home: Path, env: dict[str, str], *, binary: bool) -> Path:
        repo = support.plain_repo(home, env)
        scripts = repo / "scripts"
        scripts.mkdir()
        shutil.copy2(
            support.ROOT / "scripts" / "hooks_gitleaks.py",
            scripts / "hooks_gitleaks.py",
        )
        shutil.copy2(support.ROOT / ".gitleaks.toml", repo / ".gitleaks.toml")
        (repo / "pins.toml").write_text(_PINS, encoding="utf-8")
        if binary:
            support.place_binary(repo)
        return repo

    def _command(
        self, repo: Path, env: dict[str, str], name: str
    ) -> tuple[int, str, str]:
        done = support.run(
            [sys.executable, "-I", "scripts/hooks_gitleaks.py", name],
            cwd=repo,
            env=env,
        )
        return done.returncode, done.stdout, done.stderr

    def test_read_version_needs_one_row(self) -> None:
        home, _env = self._home()
        root = home / "root"
        root.mkdir()
        (root / "pins.toml").write_text("schema = 1\n", encoding="utf-8")
        with self.assertRaises(hooks_gitleaks.Failure) as caught:
            hooks_gitleaks.read_version(root)
        self.assertEqual(
            str(caught.exception), "pins.toml has no single gitleaks row with a pin"
        )
        (root / "pins.toml").write_text(_PINS, encoding="utf-8")
        self.assertEqual(hooks_gitleaks.read_version(root), "8.30.1")

    def test_verify_missing_binary_names_the_remedy(self) -> None:
        home, env = self._home()
        repo = self._scan_repo(home, env, binary=False)
        status, stdout, stderr = self._command(repo, env, "verify")
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "gitleaks: binary not found at data/tools/gitleaks/8.30.1/gitleaks; "
            "run: uv run --locked python scripts/hooks_gitleaks.py fetch\n",
        )

    def test_verify_refuses_another_version(self) -> None:
        home, env = self._home()
        repo = self._scan_repo(home, env, binary=False)
        path = support.place_binary(repo, copy=True)
        path.write_text("#!/bin/sh\necho 9.9.9\n", encoding="utf-8")
        path.chmod(0o755)
        status, stdout, stderr = self._command(repo, env, "verify")
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "gitleaks: binary at data/tools/gitleaks/8.30.1/gitleaks "
            "does not report version 8.30.1\n",
        )

    def test_fetch_refuses_a_wrong_archive_digest(self) -> None:
        home, _env = self._home()
        target = home / "missing" / "gitleaks"
        data = _archive("gitleaks", _MEMBER)
        with self.assertRaises(hooks_gitleaks.Failure) as caught:
            hooks_gitleaks.install_archive(data, "0" * 64, target)
        self.assertEqual(
            str(caught.exception),
            "the archive does not match the pinned checksum; nothing was written",
        )
        self.assertFalse(target.parent.exists())

    def test_fetch_installs_one_exact_member(self) -> None:
        good = _archive("gitleaks", _MEMBER)
        digest = hashlib.sha256(good).hexdigest()
        with self.subTest(member="gitleaks"):
            home, _env = self._home()
            root = home / "root"
            root.mkdir()
            (root / "pins.toml").write_text(_PINS, encoding="utf-8")
            stdout = io.StringIO()
            with (
                patch.dict(hooks_gitleaks.ARCHIVE_SHA256, {"8.30.1": digest}),
                patch.object(
                    urllib.request,
                    "urlopen",
                    return_value=_Body(good),
                ),
                contextlib.redirect_stdout(stdout),
            ):
                status = hooks_gitleaks.fetch(root)
            self.assertEqual(status, 0)
            self.assertIn(
                "gitleaks 8.30.1 installed at data/tools/gitleaks/8.30.1/gitleaks",
                stdout.getvalue(),
            )
            target = root / "data" / "tools" / "gitleaks" / "8.30.1" / "gitleaks"
            self.assertEqual(target.read_bytes(), _MEMBER)
            self.assertEqual(target.stat().st_mode & 0o777, 0o755)
        with self.subTest(member="nested"):
            home, _env = self._home()
            root = home / "root"
            root.mkdir()
            nested = _archive("x/gitleaks", _MEMBER)
            target = root / "data" / "tools" / "gitleaks" / "8.30.1" / "gitleaks"
            with self.assertRaises(hooks_gitleaks.Failure) as caught:
                hooks_gitleaks.install_archive(
                    nested, hashlib.sha256(nested).hexdigest(), target
                )
            self.assertEqual(
                str(caught.exception),
                "the archive does not hold one regular gitleaks file; nothing was written",
            )
            self.assertFalse(target.parent.exists())

    def test_fetch_does_not_use_the_network_when_installed(self) -> None:
        home, _env = self._home()
        root = home / "root"
        root.mkdir()
        (root / "pins.toml").write_text(_PINS, encoding="utf-8")
        good = _archive("gitleaks", _MEMBER)
        digest = hashlib.sha256(good).hexdigest()
        with (
            patch.dict(hooks_gitleaks.ARCHIVE_SHA256, {"8.30.1": digest}),
            patch.object(urllib.request, "urlopen", return_value=_Body(good)),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(hooks_gitleaks.fetch(root), 0)
        stdout = io.StringIO()

        def _forbidden(*_args: Any, **_kwargs: Any) -> _Body:
            raise AssertionError("network")

        with (
            patch.dict(hooks_gitleaks.ARCHIVE_SHA256, {"8.30.1": digest}),
            patch.object(urllib.request, "urlopen", side_effect=_forbidden),
            contextlib.redirect_stdout(stdout),
        ):
            status = hooks_gitleaks.fetch(root)
        self.assertEqual(status, 0)
        self.assertIn(
            "gitleaks 8.30.1 already installed at data/tools/gitleaks/8.30.1/gitleaks",
            stdout.getvalue(),
        )

    def test_platform_refusal(self) -> None:
        with self.assertRaises(hooks_gitleaks.Failure) as caught:
            hooks_gitleaks.check_platform("darwin", "arm64")
        self.assertEqual(
            str(caught.exception),
            "only Linux on x86-64 is supported; the other archives are not pinned",
        )
        hooks_gitleaks.check_platform("linux", "x86_64")

    def test_download_failure_is_one_line(self) -> None:
        home, _env = self._home()
        root = home / "root"
        root.mkdir()
        (root / "pins.toml").write_text(_PINS, encoding="utf-8")
        stderr = io.StringIO()
        with (
            patch.object(hooks_gitleaks, "ROOT", root),
            patch.object(
                urllib.request,
                "urlopen",
                side_effect=urllib.error.URLError("x"),
            ),
            contextlib.redirect_stderr(stderr),
        ):
            status = hooks_gitleaks.main(["fetch"])
        self.assertEqual(status, 1)
        self.assertEqual(stderr.getvalue(), "gitleaks: download failed (URLError)\n")
        self.assertFalse((root / "data").exists())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_staged_clean_passes(self) -> None:
        home, env = self._home()
        repo = self._scan_repo(home, env, binary=True)
        (repo / "a.txt").write_text("hello\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "a.txt").returncode, 0)
        status, stdout, stderr = self._command(repo, env, "staged")
        self.assertEqual(status, 0, stderr)
        self.assertIn("no leaks found", stdout + stderr)

    def test_staged_shapes_are_found_and_redacted(self) -> None:
        rng = __import__("random").Random(support.SEED)
        builders = {
            "cloud_key": support.cloud_key,
            "model_key": support.model_key,
            "github_token": support.github_token,
            "private_key_block": support.private_key_block,
        }
        for name, rule in _SHAPES:
            with self.subTest(shape=name):
                home, env = self._home()
                repo = self._scan_repo(home, env, binary=True)
                token = builders[name](rng)
                (repo / "leak.txt").write_text(token + "\n", encoding="utf-8")
                self.assertEqual(
                    support.git(repo, env, "add", "--", "leak.txt").returncode, 0
                )
                status, stdout, stderr = self._command(repo, env, "staged")
                output = stdout + stderr
                self.assertEqual(status, 1, output)
                self.assertIn("RuleID:      " + rule, output)
                self.assertIn("Secret:      REDACTED", output)
                support.assert_free_of(self, output, token)

    def test_scan_judges_the_index(self) -> None:
        rng = __import__("random").Random(support.SEED)
        token = support.cloud_key(rng)
        with self.subTest(staged=False):
            home, env = self._home()
            repo = self._scan_repo(home, env, binary=True)
            (repo / "leak.txt").write_text(token + "\n", encoding="utf-8")
            status, _stdout, stderr = self._command(repo, env, "staged")
            self.assertEqual(status, 0, stderr)
        with self.subTest(staged=True):
            home, env = self._home()
            repo = self._scan_repo(home, env, binary=True)
            (repo / "leak.txt").write_text(token + "\n", encoding="utf-8")
            self.assertEqual(
                support.git(repo, env, "add", "--", "leak.txt").returncode, 0
            )
            (repo / "leak.txt").write_text("clean\n", encoding="utf-8")
            status, _stdout, _stderr = self._command(repo, env, "staged")
            self.assertEqual(status, 1)

    def test_missing_config_is_fatal(self) -> None:
        home, env = self._home()
        repo = self._scan_repo(home, env, binary=True)
        (repo / ".gitleaks.toml").unlink()
        token = support.cloud_key(__import__("random").Random(support.SEED))
        (repo / "leak.txt").write_text(token + "\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "leak.txt").returncode, 0)
        status, stdout, stderr = self._command(repo, env, "staged")
        output = stdout + stderr
        self.assertEqual(status, 1)
        self.assertIn("unable to load gitleaks config", output)
        self.assertTrue(
            stderr.endswith(
                "gitleaks: exited with status 1, which is not a finding; see above\n"
            )
        )
        support.assert_free_of(self, output, token)

    def test_config_has_no_allow_list_and_extend_has_teeth(self) -> None:
        parsed = tomllib.loads(
            (support.ROOT / ".gitleaks.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(set(parsed), {"title", "extend"})
        self.assertEqual(parsed["extend"], {"useDefault": True})
        keys: list[str] = []
        _walk_keys(parsed, keys)
        for name in ("allowlist", "allowlists", "rules"):
            self.assertNotIn(name, keys)
        home, env = self._home()
        repo = self._scan_repo(home, env, binary=True)
        (repo / ".gitleaks.toml").write_text(
            'title = "eii gitleaks configuration"\n', encoding="utf-8"
        )
        token = support.cloud_key(__import__("random").Random(support.SEED))
        (repo / "leak.txt").write_text(token + "\n", encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "leak.txt").returncode, 0)
        status, _stdout, stderr = self._command(repo, env, "staged")
        self.assertEqual(status, 0, stderr)
        support.assert_free_of(self, stderr, token)
