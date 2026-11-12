"""Tests for the twelve ./eii commands and the launcher dispatch."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

import commands_support as support

ROOT = support.ROOT
UP_TAIL = ("up", "-d", "--wait", "--wait-timeout", "60", "db")
DOWN_TAIL = ("stop", "db")
PLACEHOLDER_DETAIL = {
    "down": "not_built (not built yet)",
    "build-public": "not_built (built by task S2-T01)",
    "build-world": "not_built (not built yet)",
    "build-release": "not_built (not built yet)",
    "load-release": "not_built (built by task S3-T02)",
    "freeze": "not_built (built by task S11-T01 and S11-T06)",
}
UP_DETAIL = "not_built (not built yet)"


class Commands(unittest.TestCase):
    def test_usage_lists_every_command(self) -> None:
        expected = support.expected_usage(ROOT)
        rows = support.architecture_table(ROOT)
        self.assertEqual(len(rows), 12)
        for args in ((), ("bogus",)):
            with self.subTest(args=args):
                proc = support.run_launcher(args, {"PATH": ""}, ROOT)
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertEqual(proc.stdout, "")
                self.assertEqual(proc.stderr, expected)
                self.assertTrue(proc.stderr.startswith("eii: usage error:"))
        self.assertEqual(
            set(support.shell_words(ROOT)), set(support.pinned_words(ROOT))
        )
        import commands.table as table

        self.assertEqual(table.usage_text(), expected)
        specs = table.COMMANDS
        self.assertEqual(len(specs), 12)
        for spec, (command, plane) in zip(specs, rows, strict=True):
            self.assertEqual(spec.form, support.usage_form(command))
            self.assertEqual(spec.plane, plane)
            self.assertEqual(spec.word, command.split()[0])
        for argv in (("preflight", "x"), ("up", "--bogus")):
            with self.subTest(argv=argv):
                code, stdout, stderr = support.run_main(argv, {"PATH": ""}, ROOT)
                self.assertEqual(code, 2, stderr)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, expected)
        planted = "\n".join(line for line in expected.splitlines() if line != "db-down")
        missing = _missing_forms(planted, expected)
        self.assertEqual(missing, ["db-down"])

    def test_preflight_only_probes(self) -> None:
        folder = support.stub_folder(self)
        root = support.make_temp(self, "eii-cmd-root-")
        before = support.snapshot(root)
        code, _stdout, _stderr = support.run_main(
            ("preflight",),
            {"PATH": str(folder)},
            root,
        )
        self.assertIn(code, (0, 1))
        records = support.calls(folder)
        self.assertEqual(support.probe_problems(records), [])
        self.assertEqual(support.tree_problems(before, support.snapshot(root)), [])
        self.assertTrue(records)
        planted_record = support.probe_problems(
            [{"program": "docker", "argv": ["docker", "compose", "up"]}]
        )
        self.assertTrue(any("compose up" in item for item in planted_record))
        planted_tree = dict(before)
        planted_tree["planted-extra"] = b"x"
        planted_files = support.tree_problems(before, planted_tree)
        self.assertTrue(any("planted-extra" in item for item in planted_files))

    def test_db_up_and_db_down_alone(self) -> None:
        project = support.compose_project(ROOT)
        import commands.database as database

        self.assertEqual(database.COMPOSE_PROJECT, project)
        self.assertEqual(database.UP_LIMIT_S, 90)
        self.assertEqual(database.DOWN_LIMIT_S, 60)
        for form in database.FORMS:
            for arg in form.args:
                self.assertNotIn(arg, support.BANNED_COMPOSE, form.name)
        banned = support.one_compose_problems(
            [
                {
                    "program": "docker",
                    "argv": ["docker", "compose", "down"],
                    "env": {},
                }
            ],
            tail=("down",),
            root=ROOT,
            project=project,
        )
        self.assertTrue(any("banned argument down" in item for item in banned))
        for word, tail, pass_line in (
            ("db-up", UP_TAIL, "PASS db-up: database service started"),
            ("db-down", DOWN_TAIL, "PASS db-down: database service stopped"),
        ):
            with self.subTest(word=word):
                folder = support.stub_folder(self)
                root = support.make_temp(self, "eii-cmd-db-")
                support.write_secret(root)
                before = support.snapshot(root)
                code, stdout, stderr = support.run_main(
                    (word,),
                    {"PATH": str(folder), "EII_DATABASE_URL": support.command_url()},
                    root,
                )
                self.assertEqual(code, 0, stderr)
                self.assertIn(pass_line, stdout)
                self.assertEqual(stderr, "")
                problems = support.one_compose_problems(
                    support.calls(folder),
                    tail=tail,
                    root=root,
                    project=project,
                )
                self.assertEqual(problems, [], problems)
                self.assertEqual(
                    support.tree_problems(before, support.snapshot(root)), []
                )
        bare = support.make_temp(self, "eii-cmd-db-")
        folder = support.stub_folder(self)
        code, _stdout, stderr = support.run_main(
            ("db-up",),
            {"PATH": str(folder), "EII_DATABASE_URL": support.command_url()},
            bare,
        )
        self.assertEqual(code, 1, stderr)
        self.assertIn("data/compose/postgres_superuser_password", stderr)
        self.assertEqual(support.calls(folder), [])
        sources = support.command_sources(ROOT)
        self.assertEqual(support.source_problems(sources), [])
        planted = dict(sources)
        planted["up_cmd.py"] = planted["up_cmd.py"] + "\nfrom . import database\n"
        wiring = support.source_problems(planted)
        self.assertTrue(any("up_cmd.py" in item for item in wiring))

    def test_up_never_starts_a_database(self) -> None:
        for args in ((), ("--embedded",)):
            with self.subTest(args=args):
                folder = support.stub_folder(self)
                root = support.make_temp(self, "eii-cmd-up-")
                support.write_secret(root)
                code, _stdout, stderr = support.run_main(
                    ("up", *args),
                    {
                        "PATH": str(folder),
                        "EII_DATABASE_URL": support.command_url(),
                    },
                    root,
                )
                self.assertEqual(code, 4, stderr)
                self.assertIn("EII_RELEASE_DIR", stderr)
                self.assertEqual(
                    support.failure_problems(code, stderr, _meaning(4)),
                    [],
                )
                records = support.calls(folder)
                self.assertEqual(support.database_start_problems(records), [])
                if args == ("--embedded",):
                    names = {str(rec["program"]) for rec in records}
                    self.assertTrue(names.isdisjoint({"pg_isready", "psql", "docker"}))
        planted = support.database_start_problems(
            [{"program": "docker", "argv": ["docker", "compose", "up", "-d"]}]
        )
        self.assertTrue(any("docker" in item for item in planted))
        import commands.table as table

        self.assertEqual(table.by_word("up").detail, UP_DETAIL)
        # A set release directory still fails the release rows, so this run
        # never reaches the branch where up_decision returns 0. source_problems
        # reports an import of the database module placed on that branch.
        with self.subTest(label="uncaught-break-up-success-path"):
            folder = support.stub_folder(self)
            root = support.make_temp(self, "eii-cmd-up-")
            release = root / "data" / "releases" / "sample-release"
            release.mkdir(parents=True)
            code, _stdout, stderr = support.run_main(
                ("up",),
                {"PATH": str(folder), "EII_RELEASE_DIR": str(release)},
                root,
            )
            self.assertEqual(code, 4, stderr)
            self.assertNotIn("not_built", stderr)

    def test_exit_codes_are_in_the_table(self) -> None:
        meanings = support.exit_meanings(ROOT)
        self.assertEqual(set(meanings), set(range(8)))
        import commands.exits as exits

        self.assertEqual(exits.MEANINGS, meanings)
        folder = support.stub_folder(self)
        root = support.make_temp(self, "eii-cmd-exit-")
        cases: tuple[tuple[tuple[str, ...], int, str], ...] = (
            (("preflight",), 1, "preflight"),
            (("db-up",), 1, "db-up"),
            (("db-down",), 1, "db-down"),
            (("up",), 4, "up"),
            (("up", "--embedded"), 4, "up"),
            (("down",), 1, "down"),
            (("build-public",), 1, "build-public"),
            (("build-world",), 1, "build-world"),
            (("build-release",), 1, "build-release"),
            (("load-release",), 1, "load-release"),
            (("freeze",), 1, "freeze"),
        )
        for argv, expect, command in cases:
            with self.subTest(argv=argv):
                code, _stdout, stderr = support.run_main(
                    argv,
                    {"PATH": str(folder)},
                    root,
                )
                self.assertEqual(code, expect, stderr)
                self.assertEqual(
                    support.failure_problems(code, stderr, meanings[expect]),
                    [],
                    stderr,
                )
                self.assertTrue(stderr.startswith(f"FAIL {command}: "), stderr)
                if command in PLACEHOLDER_DETAIL:
                    self.assertIn(PLACEHOLDER_DETAIL[command], stderr)
                if command in {"db-up", "db-down"}:
                    self.assertIn("EII_DATABASE_URL", stderr)
        with self.subTest(command="test"):
            proc = support.run_launcher(("test", "--bogus"), os.environ, ROOT)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertTrue(proc.stderr.startswith("eii: usage error:"), proc.stderr)
            self.assertNotIn("eii: exit 2:", proc.stderr)
        planted_code, planted_err = support.run_finish(9, "planted", "ignored")
        self.assertEqual(planted_code, 1)
        self.assertIn("internal fault", planted_err)
        self.assertEqual(support.failure_problems(1, planted_err, meanings[1]), [])
        self.assertNotIn("eii: exit 9:", planted_err)

    def test_down_deletes_nothing(self) -> None:
        folder = support.stub_folder(self)
        root = support.make_temp(self, "eii-cmd-down-")
        _write_kept_tree(root)
        support.write_secret(root)
        before = support.snapshot(root)
        code, stdout, stderr = support.run_main(
            ("down",),
            {"PATH": str(folder), "EII_DATABASE_URL": support.command_url()},
            root,
        )
        self.assertEqual(code, 1, stderr)
        self.assertEqual(stdout, "")
        self.assertIn(PLACEHOLDER_DETAIL["down"], stderr)
        self.assertEqual(support.failure_problems(code, stderr, _meaning(1)), [])
        self.assertEqual(support.calls(folder), [])
        self.assertEqual(support.tree_problems(before, support.snapshot(root)), [])
        planted = dict(before)
        del planted["data/ledger/local-ledger.jsonl"]
        removed = support.tree_problems(before, planted)
        self.assertTrue(any("local-ledger.jsonl" in item for item in removed))

    def test_launcher_dispatch(self) -> None:
        folder = support.make_temp(self, "eii-cmd-uv-")
        support.write_fake_uv(folder)
        env = {"PATH": str(folder)}
        for word in support.pinned_words(ROOT):
            with self.subTest(word=word):
                extra = "--embedded" if word == "up" else "marker"
                proc = support.run_launcher((word, extra), env, ROOT)
                self.assertEqual(proc.returncode, 7, proc.stdout + proc.stderr)
                lines = proc.stdout.splitlines()
                self.assertIn(extra, lines)
                self.assertIn("--locked", lines)
                if word == "test":
                    self.assertIn("scripts/run_tests.py", lines)
                    self.assertNotIn("scripts/commands/main.py", lines)
                    self.assertNotIn("test", lines)
                else:
                    self.assertIn("scripts/commands/main.py", lines)
                    self.assertIn(word, lines)
                    self.assertNotIn("scripts/run_tests.py", lines)
        with self.subTest(word="bogus"):
            proc = support.run_launcher(("bogus",), env, ROOT)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(proc.stderr, support.expected_usage(ROOT))
        empty = support.make_temp(self, "eii-cmd-empty-")
        for word in support.pinned_words(ROOT):
            with self.subTest(missing=word):
                proc = support.run_launcher((word,), {"PATH": str(empty)}, ROOT)
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertEqual(proc.stdout, "")
                self.assertEqual(
                    proc.stderr,
                    "FAIL tools: uv: not found on PATH; install uv, then run "
                    f"./eii {word} again\n",
                )


def _meaning(code: int) -> str:
    return support.exit_meanings(ROOT)[code]


def _missing_forms(planted: str, expected: str) -> list[str]:
    expected_forms = expected.splitlines()[1:]
    present = set(planted.splitlines()[1:])
    return [form for form in expected_forms if form not in present]


def _write_kept_tree(root: Path) -> None:
    release = root / "data" / "releases" / "sample-release"
    release.mkdir(parents=True)
    (release / "marker.txt").write_text("synthetic release marker\n", encoding="utf-8")
    ledger = root / "data" / "ledger"
    ledger.mkdir(parents=True)
    (ledger / "local-ledger.jsonl").write_text(
        "synthetic ledger row\n",
        encoding="utf-8",
    )
    freeze = root / "data" / "freeze" / "sample-freeze"
    freeze.mkdir(parents=True)
    (freeze / "freeze.json").write_text("{}\n", encoding="utf-8")
