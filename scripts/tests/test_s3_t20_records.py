"""S3-T20 record checks: boxes B1, B4, B7, B9, B10 and B12.

Each check runs on the repository's own files and on a planted copy in an
invented folder. A check proves that a record has its closed shape; the phone
captures, the boot run and the gate approval themselves are the lead's.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from unittest.mock import patch

from s3_t28_support import ROOT, WorkspaceCase

import check_docs
import remote_records as records

HOST = records.HOST_SETTING
SWITCH = records.SWITCH_SETTING
# Written in parts, so that this file never holds the forms it plants.
FORM = "./" + "eii" + " remote-check"
DECISION_41 = "docs/decisions/0041-remote-mode-through-the-owners-own-host.md"
DECISION_49 = "docs/decisions/0049-one-product-for-every-screen-size.md"
NO_LOGIN_FILES = (records.DOC13, records.DOC17, DECISION_41)
BOX_12 = "[ ] dependency evidence"
APPROVAL = "Slice S3 gate — INVENTED title: final confirmation: APPROVED"


def mentioning(word: str) -> list[str]:
    """Tracked files and new files that hold a word; never an ignored file."""
    done = subprocess.run(
        ["git", "grep", "--untracked", "-l", "-I", "-F", "-e", word],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode not in (0, 1):
        raise AssertionError("the file list cannot be read")
    return done.stdout.splitlines()


def rows() -> list[dict[str, object]]:
    return [
        dict(
            zip(records.CELL_KEYS, cell, strict=True),
            sha256=f"{index:064x}",
        )
        for index, cell in enumerate(records.evidence_cells())
    ]


class RecordCase(WorkspaceCase):
    def plant(self, path: str, text: str) -> str:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return path

    def copies(self, *paths: str) -> None:
        for path in paths:
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, self.root / path)

    def edit(self, path: str, old: str, new: str) -> None:
        text = (self.root / path).read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise AssertionError("a plant must change exactly one place")
        (self.root / path).write_text(text.replace(old, new), encoding="utf-8")


class LeadOnly(RecordCase):
    def test_remote_check_not_in_tests_or_ci(self) -> None:
        self.assertEqual(
            records.invocation_problems(ROOT, mentioning("remote-check")), []
        )
        workflow = self.plant(
            ".github/workflows/invented.yml", f"jobs:\n  steps:\n    - run: {FORM}\n"
        )
        self.assertEqual(
            records.invocation_problems(self.root, [workflow]), [workflow + ":3"]
        )
        listed = self.plant(
            "scripts/tests/test_invented.py",
            'run(["./' + 'eii", "remote' + '-check"])\n',
        )
        self.assertEqual(
            records.invocation_problems(self.root, [listed]), [listed + ":1"]
        )
        # A comment line of the command's own runner names it and is not a run.
        runner = self.plant(
            "web/tests/invented.spec.ts", f"/**\n * The runner of `{FORM}`.\n */\n"
        )
        self.assertEqual(records.invocation_problems(self.root, [runner]), [])
        # The command's own documents and source name it and are not a run.
        named = self.plant("docs/invented.md", FORM + "\n")
        self.assertEqual(records.invocation_problems(self.root, [named]), [])

    def test_rule_files_are_byte_identical(self) -> None:
        failures: list[str] = []
        check_docs.check_agent_files(failures)
        self.assertEqual(failures, [])
        self.assertEqual(
            (ROOT / "AGENTS.md").read_bytes(), (ROOT / "CLAUDE.md").read_bytes()
        )
        for form in (f"`{FORM}`", "`./eii down --previous-boot`"):
            self.assertEqual((ROOT / "AGENTS.md").read_text().count(form), 1)
        self.copies("AGENTS.md", "CLAUDE.md")
        with patch.object(check_docs, "ROOT", self.root):
            check_docs.check_agent_files(failures)
            self.assertEqual(failures, [])
            content = (self.root / "CLAUDE.md").read_bytes()
            (self.root / "CLAUDE.md").write_bytes(content[:-1] + b" ")
            check_docs.check_agent_files(failures)
        self.assertEqual(failures, ["FAIL agent-files: AGENTS.md and CLAUDE.md differ"])

    def test_remote_host_never_committed(self) -> None:
        self.assertEqual(records.host_problems(ROOT, mentioning(HOST)), [])
        name = "maps.owner-" + "host.example"
        planted = [
            self.plant("invented/workflow.yml", f"env:\n  {HOST}: {name}\n"),
            self.plant("invented/start.sh", f"export {HOST}={name}\n"),
            self.plant("invented/settings.json", f'{{"{HOST}": "{name}"}}\n'),
            self.plant("invented/test_case.py", f'run(dict({HOST}="{name}"))\n'),
            self.plant("invented/set.py", f'environ["{HOST}"] = "{name}:8088"\n'),
            self.plant("invented/patch.py", f'setenv("{HOST}", "https://{name}/")\n'),
            self.plant(
                "invented/alias.py", f'KEY = "{HOST}"\nrun({{KEY: "{name}"}})\n'
            ),
        ]
        self.assertEqual(records.host_problems(self.root, planted), sorted(planted))
        invented = [
            self.plant("invented/ok.yml", f"env:\n  {HOST}: entry.s3-t20.invalid\n"),
            self.plant("invented/ok.sh", f'{HOST}="$1"\nunset {HOST}\n'),
            self.plant("invented/ok.py", f'host = environ["{HOST}"]\n{HOST}=name\n'),
            self.plant("invented/ok.md", f"`{HOST}`, read from the environment.\n"),
            self.plant("invented/local.py", f'dict({HOST}="localhost:8088")\n'),
            # In code an unquoted value is an expression, not a host name.
            self.plant("invented/expr.ts", f"{HOST}: process.env.NAME,\n"),
            self.plant("invented/key.py", f'KEY = "{HOST}"\nMY_KEY = "a.example"\n'),
        ]
        self.assertEqual(records.host_problems(self.root, invented), [])

    def test_switch_never_set(self) -> None:
        self.assertEqual(records.switch_problems(ROOT, mentioning(SWITCH)), [])
        case = self.plant(
            "scripts/tests/test_s3_t20_invented.py", f'dict(live, {SWITCH}="1")\n'
        )
        named = self.plant("invented/names.py", f'NAME = "{SWITCH}"\n{SWITCH}=""\n')
        self.assertEqual(records.switch_problems(self.root, [case, named]), [])
        for path, text in (
            (".github/workflows/invented.yml", f"env:\n  {SWITCH}: 1\n"),
            ("scripts/invented.sh", f"export {SWITCH}=yes\n"),
            ("scripts/invented.py", f'environ["{SWITCH}"] = "1"\n'),
            ("scripts/tests/test_other.py", f'setenv("{SWITCH}", "true")\n'),
            ("scripts/test_s3_t20_loose.py", f'dict({SWITCH}="1")\n'),
            ("scripts/invented_alias.py", f'KEY = "{SWITCH}"\nrun({{KEY: "1"}})\n'),
            ("scripts/tests/test_s3_t20_second.py", f'dict({SWITCH}="1")\n'),
        ):
            with self.subTest(path=path):
                planted = self.plant(path, text)
                self.assertEqual(
                    records.switch_problems(self.root, [case, planted]),
                    sorted([case + ": 1", planted + ": 1"]),
                )
                self.assertEqual(
                    records.switch_problems(self.root, [planted]),
                    [] if planted.endswith("second.py") else [planted + ": 1"],
                )
        twice = self.plant(case, f'dict({SWITCH}="1")\ndict({SWITCH}="0")\n')
        self.assertEqual(records.switch_problems(self.root, [twice]), [twice + ": 2"])


class NoLogin(RecordCase):
    def problems(self, path: str = "", old: str = "", new: str = "") -> list[str]:
        self.copies(*NO_LOGIN_FILES)
        if path:
            self.edit(path, old, new)
        return records.no_login_problems(self.root)

    def test_no_login_documented(self) -> None:
        self.assertEqual(records.no_login_problems(ROOT), [])
        self.assertEqual(self.problems(), [])
        self.assertEqual(
            self.problems(records.DOC13, records.NO_LOGIN_MARK, "**The choice.**"),
            [
                "no-login paragraph lacks: " + phrase
                for phrase in (
                    "Anyone who has the address",
                    "DHA-133",
                    "decision 0041 item 8",
                )
            ],
        )
        self.assertEqual(
            self.problems(records.DOC13, "Anyone who has the address", "A visitor"),
            ["no-login paragraph lacks: Anyone who has the address"],
        )
        self.assertEqual(
            self.problems(records.DOC17, "| DHA-148 | Request rate", "| Request rate"),
            ['requirement "DHA-148" found 0 times'],
        )
        self.assertEqual(
            self.problems(
                records.DOC17,
                "| DHA-147 | Connection count on the public entry (origin: S3-T20,",
                "| DHA-147 | Connection count on the public entry (origin: a task,",
            ),
            ["DHA-147 lacks: S3-T20"],
        )

    def test_a_missing_section_or_decision_item_is_named(self) -> None:
        heading = "### " + records.NO_LOGIN_SECTION
        self.assertEqual(
            self.problems(records.DOC13, heading + "\n", "### Start on boot\n"),
            [f'heading "{records.NO_LOGIN_SECTION}" found 0 times'],
        )
        self.copies(*NO_LOGIN_FILES)
        (self.root / DECISION_41).unlink()
        self.assertEqual(
            records.no_login_problems(self.root), [DECISION_41 + " is not a file"]
        )


class Evidence(WorkspaceCase):
    def test_evidence_matrix_complete(self) -> None:
        complete = rows()
        self.assertEqual(len(complete), 80)
        self.assertEqual(records.evidence_problems(complete), [])
        self.assertEqual(
            records.evidence_problems(complete[1:]),
            ["missing cell: first_map/en/light/360/640"],
        )
        self.assertEqual(
            records.evidence_problems([*complete, complete[-1]]),
            ["repeated cell: story/ar/dark/3840/2160"],
        )
        self.assertEqual(len(records.evidence_problems([])), 80)

    def test_one_wrong_leaf_of_one_row_is_named(self) -> None:
        cell = "first_map/en/light/360/640"
        for key, value, wanted in (
            ("sha256", "0" * 63, ["capture hash invalid: " + cell]),
            ("sha256", "G" * 64, ["capture hash invalid: " + cell]),
            ("sha256", None, ["capture hash invalid: " + cell]),
            (
                "width",
                1024,
                ["missing cell: " + cell, "unknown cell: " + cell[:-7] + "1024/640"],
            ),
            (
                "width",
                360.0,
                ["missing cell: " + cell, "unknown cell: " + cell[:-7] + "360.0/640"],
            ),
            (
                "height",
                True,
                ["missing cell: " + cell, "unknown cell: " + cell[:-3] + "True"],
            ),
            (
                "theme",
                "sepia",
                ["missing cell: " + cell, "unknown cell: first_map/en/sepia/360/640"],
            ),
            (
                "language",
                [],
                ["missing cell: " + cell, "unknown cell: first_map/[]/light/360/640"],
            ),
        ):
            with self.subTest(key=key, value=value):
                planted = rows()
                planted[0][key] = value
                self.assertEqual(records.evidence_problems(planted), sorted(wanted))
        extra = rows()
        extra[0]["note"] = "INVENTED"
        self.assertEqual(
            records.evidence_problems(extra), ["malformed row", "missing cell: " + cell]
        )

    def test_sizes_are_the_eight_named_sizes_of_decision_0049(self) -> None:
        text = (ROOT / DECISION_49).read_text(encoding="utf-8")
        item = next(
            line for line in text.splitlines() if line.startswith("2. **Named sizes.**")
        )
        named = [(int(w), int(h)) for w, h in re.findall(r"(\d+)x(\d+)", item)]
        self.assertEqual(len(named), 8)
        phones = [size for size in named if "phones" in item and size in named[:2]]
        self.assertEqual(set(records.SIZES), {*named, *((h, w) for w, h in phones)})
        self.assertEqual(len(records.SIZES), len(set(records.SIZES)))


class Dependency(WorkspaceCase):
    def test_gate_approval_precedes_task(self) -> None:
        tasks = (ROOT / "TASKS.md").read_text(encoding="utf-8")
        progress = (ROOT / "PROGRESS.md").read_text(encoding="utf-8")
        self.assertEqual(records.gate_approval_problems(tasks, progress), [])
        ticked = tasks.replace(BOX_12, BOX_12.replace("[ ]", "[x]"))
        if BOX_12 in tasks:
            # Today no slice S3 gate approval record exists, so a tick is refused.
            self.assertEqual(
                records.gate_approval_problems(ticked, progress),
                ["dependency box ticked without a slice S3 gate approval record"],
            )

    def test_a_ticked_box_needs_the_approval_record_and_its_citation(self) -> None:
        tasks = (
            "### S3-T20 — INVENTED\n- Goal: INVENTED.\n- Acceptance criteria: "
            + "; ".join(f"[x] INVENTED box {n}" for n in range(1, 12))
            + "; [x] dependency evidence shows the approval.\n"
        )
        heading = "#### " + APPROVAL
        cite = records.DEPENDENCY_LINE + APPROVAL
        missing = "dependency box ticked without a slice S3 gate approval record"
        uncited = "dependency box ticked without citing the approval record after it"
        for progress, wanted in (
            (f"{heading}\n\n{cite}\n", []),
            ("", [missing]),
            (f"{cite}\n", [missing]),
            (f"{heading.replace('S3', 'S2')}\n{cite}\n", [missing]),
            (f"{heading.replace('APPROVED', 'REJECTED')}\n{cite}\n", [missing]),
            (f"{heading}\n", [uncited]),
            (f"{cite}\n{heading}\n", [uncited]),
            (f"{heading}\n{records.DEPENDENCY_LINE}the S3 gate\n", [uncited]),
            (f"{heading}\nNote: {cite}\n", [uncited]),
        ):
            with self.subTest(progress=progress):
                self.assertEqual(
                    records.gate_approval_problems(tasks, progress), wanted
                )
        other = tasks.replace("### S3-T20 — ", "### S3-T21 — ")
        self.assertEqual(
            records.gate_approval_problems(other, ""),
            ["S3-T20 acceptance boxes cannot be read"],
        )
        unticked = tasks.replace("[x] dependency", "[ ] dependency")
        self.assertEqual(records.gate_approval_problems(unticked, ""), [])

    def test_unreadable_boxes_are_refused_not_passed(self) -> None:
        tasks = (ROOT / "TASKS.md").read_text(encoding="utf-8")
        unreadable = ["S3-T20 acceptance boxes cannot be read"]
        for planted in (
            tasks.replace("### S3-T20 — ", "### S3-T2O — "),
            tasks.replace("dependency evidence shows", "the evidence shows"),
            tasks.replace("; [ ] dependency evidence", "; dependency evidence"),
            tasks.replace("; [x] dependency evidence", "; dependency evidence"),
        ):
            if planted != tasks:
                self.assertEqual(
                    records.gate_approval_problems(planted, ""), unreadable
                )
        self.assertEqual(records.gate_approval_problems("", ""), unreadable)
