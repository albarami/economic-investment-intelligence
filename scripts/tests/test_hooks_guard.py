"""Commit guard: staged content is judged against local secret values."""

from __future__ import annotations

import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hooks_support as support

_KEY_NAME = "ANTHROPIC_API_KEY"
_GATEWAY_NAME = "JEV_PRO_API_KEY"
_URL_NAME = "EII_DATABASE_URL"


def _content(path: str, name: str) -> str:
    return (
        f'guard: refused: staged content of "{path}" holds the local value of {name}\n'
    )


def _weak(name: str) -> str:
    return (
        f"guard: refused: the local value of {name} is shorter than 12 characters, "
        "so it cannot be checked; use a longer value or remove it\n"
    )


def _unparseable(name: str) -> str:
    return (
        f"guard: refused: the local value of {name} cannot be parsed as a URL, "
        "so it cannot be checked; use a longer value or remove it\n"
    )


def _unreadable(name: str) -> str:
    return (
        f"guard: refused: the local value of {name} is written in .env in a form "
        "the guard cannot read, so it cannot be checked; fix or remove it\n"
    )


class CommitGuard(unittest.TestCase):
    def _start(
        self, extra: dict[str, str] | None = None
    ) -> tuple[Path, dict[str, str], Path, random.Random]:
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        support.system_bin(home)
        env = support.clean_env(home, [home / "sysbin"], extra)
        repo = support.plain_repo(home, env)
        return home, env, repo, random.Random(support.SEED)

    def _values(self, rng: random.Random) -> tuple[str, str, str]:
        return (
            support.random_value(rng, 30),
            support.random_value(rng, 30),
            support.random_value(rng, 20),
        )

    def _write_env(self, repo: Path, key: str, password: str) -> None:
        url = "postgresql://eii_app:" + password + "@127.0.0.1:55440/eii"
        text = _KEY_NAME + "=" + key + "\n" + _URL_NAME + "=" + url + "\n"
        (repo / ".env").write_text(text, encoding="utf-8")

    def _stage(
        self, repo: Path, env: dict[str, str], name: str, content: bytes
    ) -> None:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        done = support.git(repo, env, "add", "--", name)
        self.assertEqual(done.returncode, 0, done.stderr)

    def _guard(self, env: dict[str, str], cwd: Path) -> tuple[int, str, str]:
        done = support.run(
            [sys.executable, "-I", str(support.ROOT / "scripts" / "commit_guard.py")],
            cwd=cwd,
            env=env,
        )
        return done.returncode, done.stdout, done.stderr

    def _free(self, text: str, *secrets: str) -> None:
        for secret in secrets:
            support.assert_free_of(self, text, secret)

    def test_value_from_env_file_refused(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        self._write_env(repo, key, password)
        self._stage(repo, env, "b.txt", b"x=" + key.encode())
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _content("b.txt", _KEY_NAME))
        self._free(stdout + stderr, key, password)

    def test_value_from_process_environment_refused(self) -> None:
        _home, _env, repo, rng = self._start()
        _key, gateway, _password = self._values(rng)
        env = support.clean_env(_home, [_home / "sysbin"], {_GATEWAY_NAME: gateway})
        self._stage(repo, env, "g.txt", gateway.encode())
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _content("g.txt", _GATEWAY_NAME))
        self._free(stdout + stderr, gateway)

    def test_database_password_refused_when_decoded(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, _password = self._values(rng)
        prefix = support.random_value(rng, 8)
        suffix = support.random_value(rng, 8)
        raw = prefix + "%40" + suffix
        decoded = prefix + "@" + suffix
        url = "postgresql://eii_app:" + raw + "@127.0.0.1:55440/eii"
        text = _KEY_NAME + "=" + key + "\n" + _URL_NAME + "=" + url + "\n"
        (repo / ".env").write_text(text, encoding="utf-8")
        self._stage(repo, env, "n.md", (decoded + "\n").encode())
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _content("n.md", _URL_NAME))
        self._free(stdout + stderr, key, raw, decoded)

    def test_clean_file_passes(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        self._write_env(repo, key, password)
        self._stage(repo, env, "a.txt", b"hello\n")
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 0)
        self.assertEqual(
            stdout, "guard: checked 1 staged file(s) against 2 local secret value(s)\n"
        )
        self.assertEqual(stderr, "")

    def test_empty_value_is_not_guarded(self) -> None:
        _home, env, repo, _rng = self._start()
        (repo / ".env").write_text(_KEY_NAME + "=\n", encoding="utf-8")
        self._stage(repo, env, "a.txt", b"hello\n")
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 0)
        self.assertEqual(
            stdout, "guard: checked 1 staged file(s) against 0 local secret value(s)\n"
        )
        self.assertEqual(stderr, "")

    def test_short_value_fails_closed(self) -> None:
        _home, env, repo, rng = self._start()
        short = support.random_value(rng, 11)
        _key, _gateway, password = self._values(rng)
        self._write_env(repo, short, password)
        self._stage(repo, env, "a.txt", b"hello\n")
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _weak(_KEY_NAME))
        self._free(stdout + stderr, short, password)

    def test_unreadable_url_fails_closed(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        url = (
            "host=127.0.0.1 port=55440 user=eii_app password="
            + password
            + " dbname=eii"
        )
        text = _KEY_NAME + "=" + key + "\n" + _URL_NAME + "=" + url + "\n"
        (repo / ".env").write_text(text, encoding="utf-8")
        self._stage(repo, env, "a.txt", b"hello\n")
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _unparseable(_URL_NAME))
        self._free(stdout + stderr, key, password)

    def test_unreadable_env_line_fails_closed(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        url = "postgresql://eii_app:" + password + "@127.0.0.1:55440/eii"
        text = _KEY_NAME + '="' + key + "\n" + _URL_NAME + "=" + url + "\n"
        (repo / ".env").write_text(text, encoding="utf-8")
        self._stage(repo, env, "a.txt", b"hello\n")
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _unreadable(_KEY_NAME))
        self._free(stdout + stderr, key, password)

    def test_env_file_forms_are_read(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, _password = self._values(rng)
        body = "export " + _KEY_NAME + '="' + key + '"  # my key\n'
        (repo / ".env").write_bytes(b"\xef\xbb\xbf" + body.encode())
        self._stage(repo, env, "b.txt", key.encode())
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _content("b.txt", _KEY_NAME))
        self._free(stdout + stderr, key)

    def test_path_holding_the_value_is_withheld(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        self._write_env(repo, key, password)
        name = "f_" + key + ".txt"
        self._stage(repo, env, name, key.encode())
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "guard: refused: a staged path holds the local value of "
            + _KEY_NAME
            + "\nguard: refused: staged content of <path withheld> holds the "
            "local value of " + _KEY_NAME + "\n",
        )
        self._free(stdout + stderr, key, password)

    def test_binary_file_is_judged(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        self._write_env(repo, key, password)
        self._stage(repo, env, "c.bin", b"\x00" + key.encode() + b"\x00")
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _content("c.bin", _KEY_NAME))
        self._free(stdout + stderr, key, password)

    def test_staged_value_with_work_tree_restored_clean(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        self._write_env(repo, key, password)
        self._stage(repo, env, "b.txt", b"x=" + key.encode())
        (repo / "b.txt").write_text("clean\n", encoding="utf-8")
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _content("b.txt", _KEY_NAME))
        self._free(stdout + stderr, key, password)

    def test_rename_is_judged_at_the_new_path(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        self._write_env(repo, key, password)
        body = "".join(f"filler line {number}\n" for number in range(1, 41))
        (repo / "old.txt").write_text(body, encoding="utf-8")
        self.assertEqual(support.git(repo, env, "add", "--", "old.txt").returncode, 0)
        self.assertEqual(
            support.git(repo, env, "commit", "-q", "-m", "chore: filler").returncode,
            0,
        )
        self.assertEqual(
            support.git(repo, env, "mv", "old.txt", "new.txt").returncode, 0
        )
        with (repo / "new.txt").open("a", encoding="utf-8") as handle:
            handle.write(key + "\n")
        self.assertEqual(support.git(repo, env, "add", "--", "new.txt").returncode, 0)
        plain = support.git(repo, env, "diff", "--cached", "--raw", "-z")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertEqual(_rename_statuses(plain.stdout), ["R"])
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _content("new.txt", _KEY_NAME))
        self._free(stdout + stderr, key, password)

    def test_gitlink_path_is_judged(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        self._write_env(repo, key, password)
        head = support.git(repo, env, "rev-parse", "HEAD")
        self.assertEqual(head.returncode, 0, head.stderr)
        commit = head.stdout.strip()
        secret_path = "g_" + key
        with self.subTest(path="secret"):
            done = support.git(
                repo,
                env,
                "update-index",
                "--add",
                "--cacheinfo",
                "160000," + commit + "," + secret_path,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            status, stdout, stderr = self._guard(env, repo)
            self.assertEqual(status, 1)
            self.assertEqual(stdout, "")
            self.assertEqual(
                stderr,
                "guard: refused: a staged path holds the local value of "
                + _KEY_NAME
                + "\n",
            )
            self._free(stdout + stderr, key, password)
        with self.subTest(path="plain"):
            removed = support.git(
                repo, env, "update-index", "--force-remove", "--", secret_path
            )
            self.assertEqual(removed.returncode, 0, removed.stderr)
            added = support.git(
                repo,
                env,
                "update-index",
                "--add",
                "--cacheinfo",
                "160000," + commit + ",gl",
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            status, stdout, stderr = self._guard(env, repo)
            self.assertEqual(status, 0)
            self.assertEqual(
                stdout,
                "guard: checked 0 staged file(s) against 2 local secret value(s)\n",
            )
            self.assertEqual(stderr, "")

    def test_repository_setting_cannot_shrink_the_listing(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, password = self._values(rng)
        self._write_env(repo, key, password)
        self._stage(repo, env, "a.txt", key.encode())
        configured = support.git(repo, env, "config", "diff.relative", "true")
        self.assertEqual(configured.returncode, 0, configured.stderr)
        (repo / "sub").mkdir()
        plain = support.run(
            ["git", "diff", "--cached", "--raw", "-z"], cwd=repo / "sub", env=env
        )
        self.assertEqual(plain.returncode, 0, plain.stderr)
        parts = [part for part in plain.stdout.split("\0") if part]
        self.assertFalse(
            any(part == "a.txt" or part.endswith("/a.txt") for part in parts)
        )
        status, stdout, stderr = self._guard(env, repo / "sub")
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _content("a.txt", _KEY_NAME))
        self._free(stdout + stderr, key, password)

    def test_cannot_judge_outside_a_repository(self) -> None:
        home, _env, _repo, _rng = self._start()
        plain = home / "plain"
        plain.mkdir()
        env = support.clean_env(
            home, [home / "sysbin"], {"GIT_CEILING_DIRECTORIES": str(home)}
        )
        status, stdout, stderr = self._guard(env, plain)
        self.assertEqual(status, 3)
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "guard: cannot judge: git rev-parse failed (exit 128)\n"
        )

    def test_query_password_parameter_fails_closed(self) -> None:
        _home, env, repo, rng = self._start()
        key, _gateway, _password = self._values(rng)
        secret = support.random_value(rng, 24)
        url = "postgresql://eii_app" + "@" + "127.0.0.1:55440/eii?password=" + secret
        text = _KEY_NAME + "=" + key + "\n" + _URL_NAME + "=" + url + "\n"
        (repo / ".env").write_text(text, encoding="utf-8")
        self._stage(repo, env, "a.txt", b"hello\n")
        status, stdout, stderr = self._guard(env, repo)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, _unparseable(_URL_NAME))
        self._free(stdout + stderr, key, secret)


def _rename_statuses(raw: str) -> list[str]:
    parts = raw.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    found: list[str] = []
    index = 0
    while index < len(parts):
        fields = parts[index].split(" ")
        status = fields[-1] if fields else ""
        found.append(status[:1])
        index += 3 if status[:1] in {"R", "C"} else 2
    return found
