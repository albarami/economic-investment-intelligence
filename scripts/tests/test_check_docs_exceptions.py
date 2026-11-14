"""Planted cases of the place-scoped exception of scripts/check_docs.py (TST-263, S1-T14).

Every name in this file is invented and built at run time. No case reads the
private list: every child run drops ``EII_FORBIDDEN_PATTERNS_FILE`` and sets it
only to a temporary pattern file written outside the scanned tree. Each case
builds a minimal valid repository, copies the current ``scripts/check_docs.py``
into it, runs the copy and asserts the exit code and the exact FAIL lines.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import types
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_docs.py"
CONFIG = "scripts/check_docs_place_exceptions.toml"
DOC04 = "docs/04_PUBLIC_DATA_PACK.md"
DOC05 = "docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md"
ATTR = "web/src/stage/attribution.ts"

NAME = "Quill" + "map"
OTHER = "Brim" + "fold"
DIGITS = "1234" + "5678"
IDS = ("sat_tiles", "sat_tiles_hd*")
EMPTY = hashlib.sha256(b"").hexdigest()

NUMBERED = [
    "01_PROJECT_BRIEF",
    "02_ARCHITECTURE",
    "03_DATA_CONTRACTS",
    "05_SYNTHETIC_WORLD_AND_SIMULATION",
    "06_PRIVACY_AND_DISCLOSURE_CONTROL",
    "07_ECONOMIC_METHODS",
    "08_BACKEND",
    "09_AI_ASSISTANT",
    "10_FRONTEND",
    "11_DESIGN_DIRECTION",
    "12_TESTING_AND_QUALITY",
    "13_DEPLOYMENT_AND_OPERATIONS",
    "14_IMPLEMENTATION_PLAN",
    "15_REVIEWER_CHECKLIST",
    "16_DEMO_RUNBOOK",
]

HEADER = (
    "# {title}\n\n| | |\n|---|---|\n| Status | Draft |\n| Date | 2026-11-14 |\n"
    "| Owner | fixture |\n| Purpose | Fixture. |\n"
)


def digest(text: str) -> str:
    """The digest of the design, computed here independently of the script."""
    return hashlib.sha256(text.casefold().encode("utf-8")).hexdigest()


def doc04(name: str) -> str:
    return HEADER.format(title="Public data pack") + (
        "\n## 1. Scope\n\nScope prose.\n\n"
        "## 2. Source registry\n\nRegistry prose.\n\n"
        "### 2.1 Identity\n\n"
        "| source_id | Dataset | Publisher | Licence |\n"
        "|---|---|---|---|\n"
        "| `alpha_tiles` | Alpha tiles | Publisher A | Open |\n"
        f"| `sat_tiles` | Satellite tiles | {name} | Open |\n\n"
        "### 2.2 Traps\n\n"
        "| source_id | Coverage | Known traps |\n"
        "|---|---|---|\n"
        "| `alpha_tiles` | national | none |\n"
        f"| `sat_tiles`, `sat_tiles_hd*` | national | credit {name} on the map |\n\n"
        "## 3. Fetcher rules\n\nFetcher prose.\n"
    )


def decl(name: str) -> str:
    return f"export const MAP_ATTRIBUTION = `© {name} imagery`;"


def config(
    *digests: str, ids: tuple[str, ...] = IDS, reason: str = "fixture credit"
) -> str:
    out = "# Place-scoped exceptions of the fixture.\n"
    listed = ", ".join(f'"{item}"' for item in ids)
    for value in digests:
        out += (
            f'\n[[exception]]\nsha256 = "{value}"\nreason = "{reason}"\n'
            f"source_ids = [{listed}]\n"
        )
    return out


def base(name: str = NAME) -> dict[str, str | bytes]:
    files: dict[str, str | bytes] = {
        name_: "Fixture.\n"
        for name_ in (
            "README.md",
            "TASKS.md",
            "PROGRESS.md",
            "OPEN_ITEMS.md",
            "LICENSE",
            "docs/README.md",
            "docs/GLOSSARY.md",
            "docs/decisions/0001-fixture.md",
        )
    }
    files["AGENTS.md"] = files["CLAUDE.md"] = "Rules.\n"
    for doc in NUMBERED:
        files[f"docs/{doc}.md"] = HEADER.format(title=doc)
    files[DOC04] = doc04(name)
    files[ATTR] = f"// Map credits.\n{decl(name)}\n"
    files[CONFIG] = config(digest(NAME))
    files["scripts/check_docs.py"] = SCRIPT.read_text(encoding="utf-8")
    return files


def line_numbers(text: str, needle: str) -> list[int]:
    folded = needle.casefold()
    return [
        number
        for number, line in enumerate(text.splitlines(), 1)
        if folded in line.casefold()
    ]


def refused(
    path: str, lines: list[int], *, extra: int | None = 1, listed: bool = True
) -> list[str]:
    out: list[str] = []
    for line in lines:
        if extra is not None:
            out.append(
                f"FAIL extra-{extra}: {path}:{line}: extra forbidden pattern: "
                "(matched text not shown)"
            )
        if listed:
            out.append(
                f"FAIL listed-name: {path}:{line}: a listed name outside its places: "
                "(matched text not shown)"
            )
    return out


def config_fail(detail: str) -> str:
    return f"FAIL place-exception-config: {CONFIG}: {detail}"


def run(
    files: dict[str, str | bytes],
    patterns: list[str] | None,
    prepare: Callable[[Path], None] | None = None,
    missing_patterns: bool = False,
) -> tuple[int, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        for rel, content in files.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content, encoding="utf-8")
        if prepare is not None:
            prepare(root)
        env = dict(os.environ)
        env.pop("EII_FORBIDDEN_PATTERNS_FILE", None)
        if patterns is not None:
            pattern_file = Path(tmp) / "patterns.txt"
            pattern_file.write_text("\n".join(patterns) + "\n", encoding="utf-8")
            env["EII_FORBIDDEN_PATTERNS_FILE"] = str(pattern_file)
        if missing_patterns:
            env["EII_FORBIDDEN_PATTERNS_FILE"] = str(Path(tmp) / "absent.txt")
        done = subprocess.run(
            [sys.executable, "scripts/check_docs.py"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    fails = sorted(line for line in done.stdout.splitlines() if line.startswith("FAIL"))
    return done.returncode, fails


PRIVATE = [NAME.lower(), OTHER.lower()]


class Base(unittest.TestCase):
    maxDiff = None

    def assertRun(
        self,
        files: dict[str, str | bytes],
        patterns: list[str] | None,
        expected: list[str],
        prepare: Callable[[Path], None] | None = None,
    ) -> None:
        code, fails = run(files, patterns, prepare)
        self.assertEqual(fails, sorted(expected))
        self.assertEqual(code, 1 if expected else 0)

    def all_places(self, files: dict[str, str | bytes], **kw: object) -> list[str]:
        """The refusal of every occurrence of the name in its two places."""
        text = str(files[DOC04])
        return refused(DOC04, line_numbers(text, NAME), **kw) + refused(  # type: ignore[arg-type]
            ATTR,
            line_numbers(str(files[ATTR]), NAME),
            **kw,  # type: ignore[arg-type]
        )


class AllowedPlaces(Base):
    def test_listed_name_passes_in_its_places_with_private_list(self) -> None:
        self.assertRun(base(), PRIVATE, [])

    def test_listed_name_passes_without_private_list(self) -> None:
        self.assertRun(base(), None, [])

    def test_upper_and_lower_case_forms_pass(self) -> None:
        for form in (NAME.upper(), NAME.lower()):
            with self.subTest(form=form):
                self.assertRun(base(form), PRIVATE, [])

    def test_case_folded_form_passes(self) -> None:
        files = base()
        files[ATTR] = decl("Quill" + "straße") + "\n"
        files[CONFIG] = config(hashlib.sha256(b"quill" + b"strasse").hexdigest())
        self.assertRun(files, ["quillstra(?:ss|ß)e"], [])

    def test_name_digest_matches_independent_digest(self) -> None:
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            import check_docs
        finally:
            sys.path.pop(0)
        for text in (NAME, "Quill" + "Straße", OTHER.upper()):
            self.assertEqual(check_docs.name_digest(text), digest(text))
        self.assertEqual(
            check_docs.name_digest("Quill" + "straße"),
            hashlib.sha256(b"quill" + b"strasse").hexdigest(),
        )


class RefusedElsewhere(Base):
    def edit(self, old: str, new: str, path: str = DOC04) -> dict[str, str | bytes]:
        files = base()
        text = str(files[path])
        self.assertIn(old, text)
        files[path] = text.replace(old, new, 1)
        return files

    def only(self, files: dict[str, str | bytes], path: str, needle: str) -> None:
        lines = line_numbers(str(files[path]), needle)
        self.assertTrue(lines)
        self.assertRun(files, PRIVATE, refused(path, lines))

    def whole_doc04(self, files: dict[str, str | bytes]) -> None:
        """Document 04 has no allowed line: every occurrence there is refused."""
        lines = line_numbers(str(files[DOC04]), NAME)
        self.assertGreaterEqual(len(lines), 3)
        self.assertRun(files, PRIVATE, refused(DOC04, lines))

    def row(self, dataset: str) -> str:
        return f"| `sat_tiles` | {dataset} | {NAME} | Open |"

    def table(self, dataset: str) -> str:
        return (
            "| source_id | Dataset | Publisher | Licence |\n|---|---|---|---|\n"
            + self.row(dataset)
        )

    def test_prose_in_section_2(self) -> None:
        files = self.edit("Registry prose.", f"Registry prose names {NAME}.")
        self.only(files, DOC04, "Registry prose")

    def test_source_shaped_row_in_section_1(self) -> None:
        files = self.edit(
            "Scope prose.", "Scope prose.\n\n" + self.table("Scope tiles")
        )
        self.only(files, DOC04, "Scope tiles")

    def test_source_shaped_row_in_section_3(self) -> None:
        files = self.edit(
            "Fetcher prose.", "Fetcher prose.\n\n" + self.table("Fetcher tiles")
        )
        self.only(files, DOC04, "Fetcher tiles")

    def test_row_inside_a_fence_lifts_the_file(self) -> None:
        files = self.edit(
            "Registry prose.", "Registry prose.\n\n```\n" + self.row("Fenced") + "\n```"
        )
        self.whole_doc04(files)

    def test_tilde_line_inside_backtick_fence_lifts_the_file(self) -> None:
        files = self.edit(
            "Registry prose.",
            "Registry prose.\n\n```\n~~~\n" + self.row("Tilde") + "\n~~~\n```",
        )
        self.whole_doc04(files)

    def test_header_row_of_section_2_table(self) -> None:
        files = self.edit(
            "| source_id | Dataset | Publisher | Licence |",
            f"| source_id | Dataset | Publisher {NAME} | Licence |",
        )
        self.only(files, DOC04, "Publisher " + NAME)

    def test_same_heading_and_rows_in_another_numbered_document(self) -> None:
        files = base()
        files[DOC05] = files[DOC04]
        self.assertRun(
            files, PRIVATE, refused(DOC05, line_numbers(str(files[DOC05]), NAME))
        )

    def test_known_traps_cell_of_another_source(self) -> None:
        files = self.edit(
            "| `alpha_tiles` | national | none |",
            f"| `alpha_tiles` | national | not {NAME} |",
        )
        self.only(files, DOC04, "not " + NAME)

    def test_first_cell_mixing_listed_and_unlisted_ids(self) -> None:
        files = self.edit(
            "| `sat_tiles`, `sat_tiles_hd*` |", "| `sat_tiles`, `alpha_tiles` |"
        )
        self.only(files, DOC04, "credit " + NAME)

    def test_form_feed_inside_prose_lifts_the_file(self) -> None:
        files = self.edit("Registry prose.", "Registry prose.\x0c" + self.row("Feed"))
        self.whole_doc04(files)

    def test_line_separator_inside_prose_lifts_the_file(self) -> None:
        files = self.edit("Registry prose.", "Registry prose.\u2028" + self.row("Sep"))
        self.whole_doc04(files)

    def test_row_inside_html_comment_lifts_the_file(self) -> None:
        files = self.edit(
            "Registry prose.",
            "Registry prose.\n\n<!--\n" + self.row("Hidden") + "\n-->",
        )
        self.whole_doc04(files)

    def test_fake_section_in_html_comment_before_section_2(self) -> None:
        files = self.edit(
            "Scope prose.",
            "Scope prose.\n\n<!--\n## 2. Source registry\n\n"
            + self.table("Comment tiles")
            + "\n-->",
        )
        self.whole_doc04(files)

    def test_indented_heading_ends_section_2(self) -> None:
        files = self.edit(
            "## 3. Fetcher rules",
            "   ## Fake heading\n\n"
            + self.table("Indented tiles")
            + "\n\n## 3. Fetcher rules",
        )
        self.only(files, DOC04, "Indented tiles")

    def test_setext_heading_lifts_the_file(self) -> None:
        files = self.edit(
            "## 3. Fetcher rules",
            "Fake heading\n---\n\n"
            + self.table("Setext tiles")
            + "\n\n## 3. Fetcher rules",
        )
        self.whole_doc04(files)

    def test_lone_row_inside_a_paragraph(self) -> None:
        files = self.edit(
            "Registry prose.", "Registry prose.\n" + self.row("Lone tiles")
        )
        self.only(files, DOC04, "Lone tiles")

    def test_tilde_line_does_not_close_a_backtick_fence_before_section_2(self) -> None:
        files = self.edit(
            "Scope prose.",
            "Scope prose.\n\n```\n~~~\n## 2. Source registry\n\n"
            + self.table("Tilde fake tiles")
            + "\n```",
        )
        self.whole_doc04(files)

    def test_shorter_fence_does_not_close_a_longer_one_before_section_2(self) -> None:
        files = self.edit(
            "Scope prose.",
            "Scope prose.\n\n````\n```\n## 2. Source registry\n\n"
            + self.table("Short fake tiles")
            + "\n````",
        )
        self.whole_doc04(files)

    def test_table_header_not_after_a_blank_line(self) -> None:
        files = self.edit(
            "Registry prose.", "Registry prose.\n" + self.table("No blank tiles")
        )
        self.only(files, DOC04, "No blank tiles")

    def test_html_block_in_section_2_lifts_the_file(self) -> None:
        files = self.edit(
            "Registry prose.",
            "Registry prose.\n\n<div hidden>\n\n"
            + self.table("Html tiles")
            + "\n\n</div>",
        )
        self.whole_doc04(files)

    def test_comment_line_of_attribution_file(self) -> None:
        files = self.edit("// Map credits.", f"// Map credits of {NAME}.", ATTR)
        self.only(files, ATTR, "// Map credits")

    def test_line_break_trap_in_a_comment_lifts_the_attribution_file(self) -> None:
        """A character that str.splitlines ends a line at, but a JavaScript
        comment or an editor may not, never splits off a declaration line."""
        control = base()
        control[ATTR] = f"// Map credits.\n{decl(NAME)}\n"
        self.assertRun(control, PRIVATE, [])
        for trap in ("\x0b", "\x0c", "\x1c", "\x85", "\u2028", "\u2029", "\r"):
            with self.subTest(trap=hex(ord(trap))):
                files = base()
                files[ATTR] = f"// Map credits.{trap}{decl(NAME)}\n"
                self.assertEqual(len(str(files[ATTR]).splitlines()), 2)
                self.only(files, ATTR, NAME)

    def test_quoted_declaration_with_an_escape(self) -> None:
        files = base()
        files[ATTR] = f"export const MAP_ATTRIBUTION = '© {NAME} imagery\\'s';\n"
        self.only(files, ATTR, NAME)

    def test_formatter_split_declaration(self) -> None:
        files = base()
        files[ATTR] = f"export const MAP_ATTRIBUTION =\n  '© {NAME} imagery';\n"
        self.only(files, ATTR, NAME)

    def test_indented_declaration(self) -> None:
        files = base()
        files[ATTR] = "  " + decl(NAME) + "\n"
        self.only(files, ATTR, NAME)

    def test_two_declarations(self) -> None:
        files = base()
        files[ATTR] = f"{decl(NAME)}\n{decl(NAME)}\n"
        self.only(files, ATTR, NAME)

    def test_declaration_inside_block_comment(self) -> None:
        files = base()
        files[ATTR] = (
            f"/*\n{decl(NAME)}\n*/\nexport const MAP_ATTRIBUTION = '© {NAME} imagery';\n"
        )
        self.only(files, ATTR, NAME)

    def test_second_statement_on_the_declaration_line(self) -> None:
        files = base()
        files[ATTR] = f"{decl(NAME)} export const OTHER_SETTING = 1;\n"
        self.only(files, ATTR, NAME)

    def test_declaration_inside_another_template_literal(self) -> None:
        files = base()
        files[ATTR] = (
            "export const NOTE = `\n"
            f'export const MAP_ATTRIBUTION = "© {NAME} imagery";\n`;\n'
        )
        self.only(files, ATTR, NAME)

    def test_declaration_inside_braces(self) -> None:
        files = base()
        files[ATTR] = f"function credits() {{\n{decl(NAME)}\n}}\n"
        self.only(files, ATTR, NAME)

    def test_slash_outside_comments_lifts_the_attribution_file(self) -> None:
        files = base()
        files[ATTR] = f"{decl(NAME)}\nexport const HALF = 1 / 2;\n"
        self.only(files, ATTR, NAME)

    def test_substitution_in_a_template_lifts_the_attribution_file(self) -> None:
        files = base()
        files[ATTR] = f"{decl(NAME)}\nexport const LABEL = `${{1}}`;\n"
        self.only(files, ATTR, NAME)

    def test_declaration_in_another_web_file(self) -> None:
        files = base()
        files["web/src/stage/other.ts"] = decl(NAME) + "\n"
        self.only(files, "web/src/stage/other.ts", NAME)

    def test_name_in_the_reason_field(self) -> None:
        files = base()
        files[CONFIG] = config(digest(NAME), reason=f"credit of {NAME}")
        self.only(files, CONFIG, "reason")

    def test_empty_configuration_lists_nothing(self) -> None:
        files = base()
        files[CONFIG] = "# Place-scoped exceptions: none.\n"
        self.assertRun(files, PRIVATE, self.all_places(files, listed=False))

    def test_name_in_a_comment_of_check_docs(self) -> None:
        files = base()
        files["scripts/check_docs.py"] = str(files["scripts/check_docs.py"]) + (
            f"# A note on {NAME}.\n"
        )
        last = len(str(files["scripts/check_docs.py"]).splitlines())
        self.assertRun(files, PRIVATE, refused("scripts/check_docs.py", [last]))
        self.assertRun(
            files, None, refused("scripts/check_docs.py", [last], extra=None)
        )


class OtherNamesAndBuiltIns(Base):
    def test_second_private_name_fails_while_listed_name_passes(self) -> None:
        files = base()
        files[ATTR] = decl(f"{NAME} and {OTHER}") + "\n"
        self.assertRun(files, PRIVATE, refused(ATTR, [1], extra=2, listed=False))

    def test_another_spelling_of_the_listed_name_fails(self) -> None:
        files = base()
        files[ATTR] = decl("Quill" + " map") + "\n"
        self.assertRun(files, ["quill ?map"], refused(ATTR, [1], listed=False))

    def test_listed_eight_digit_run_fails_as_identifier_number(self) -> None:
        files = base(DIGITS)
        files[CONFIG] = config(digest(DIGITS))
        why = "identifier-shaped number (exactly 8 or 11 digits)"
        expected = [
            f"FAIL identifier-number: {DOC04}:{line}: {why}: (matched text not shown)"
            for line in line_numbers(str(files[DOC04]), DIGITS)
        ] + [f"FAIL identifier-number: {ATTR}:2: {why}: (matched text not shown)"]
        self.assertEqual(len(expected), 3)
        self.assertRun(files, None, expected)


class MalformedConfiguration(Base):
    def both(
        self,
        files: dict[str, str | bytes],
        detail: str,
        prepare: Callable[[Path], None] | None = None,
        also: list[str] | None = None,
    ) -> None:
        lines = [config_fail(detail)] + (also or [])
        self.assertRun(files, None, lines, prepare)
        self.assertRun(
            files, PRIVATE, lines + self.all_places(files, listed=False), prepare
        )

    def with_config(self, text: str | bytes) -> dict[str, str | bytes]:
        files = base()
        files[CONFIG] = text
        return files

    def test_missing(self) -> None:
        files = base()
        del files[CONFIG]
        self.both(files, "missing or not a regular file")

    def test_directory(self) -> None:
        files = base()
        del files[CONFIG]
        self.both(
            files,
            "missing or not a regular file",
            lambda root: (root / CONFIG).mkdir(),
        )

    def test_symbolic_link(self) -> None:
        files = base()
        files["scripts/real.toml"] = files.pop(CONFIG)

        def link(root: Path) -> None:
            (root / CONFIG).symlink_to("real.toml")

        self.both(files, "missing or not a regular file", link)

    def test_not_utf8(self) -> None:
        self.both(
            self.with_config(b"# \xff\n"),
            "not valid UTF-8",
            also=[f"FAIL encoding: {CONFIG}: not valid UTF-8"],
        )

    def test_not_toml(self) -> None:
        self.both(self.with_config("[[exception]\n"), "not valid TOML")

    def test_unknown_top_level_key(self) -> None:
        self.both(self.with_config("other = 1\n"), "unknown top-level key")

    def test_exception_not_list_of_tables(self) -> None:
        for text in (
            "exception = 1\n",
            "exception = [1, 2]\n",
            "[exception]\nsha256 = 1\n",
        ):
            with self.subTest(text=text):
                self.both(self.with_config(text), "exception is not a list of tables")

    def entry(self, sha: str, reason: str, ids: str, extra: str = "") -> str:
        return (
            f"[[exception]]\nsha256 = {sha}\nreason = {reason}\nsource_ids = {ids}\n"
            + extra
        )

    def test_keys_not_exact(self) -> None:
        good = f'"{digest(NAME)}"'
        for text in (
            f'[[exception]]\nsha256 = {good}\nreason = "r"\n',
            self.entry(good, '"r"', '["sat_tiles"]', "name = 1\n"),
        ):
            with self.subTest(text=text):
                self.both(
                    self.with_config(text),
                    "entry 1: keys are not exactly sha256, reason and source_ids",
                )

    def test_sha256_not_lowercase_hex(self) -> None:
        for sha in (f'"{digest(NAME).upper()}"', "1", f'"{digest(NAME)}\\n"'):
            with self.subTest(sha=sha):
                self.both(
                    self.with_config(self.entry(sha, '"r"', '["sat_tiles"]')),
                    "entry 1: sha256 is not 64 lowercase hexadecimal digits",
                )

    def test_sha256_of_empty_text(self) -> None:
        self.both(
            self.with_config(self.entry(f'"{EMPTY}"', '"r"', '["sat_tiles"]')),
            "entry 1: sha256 is the digest of empty text",
        )

    def test_reason_empty(self) -> None:
        for reason in ('"   "', "1"):
            with self.subTest(reason=reason):
                self.both(
                    self.with_config(
                        self.entry(f'"{digest(NAME)}"', reason, '["sat_tiles"]')
                    ),
                    "entry 1: reason is empty",
                )

    def test_source_ids_invalid(self) -> None:
        for ids in (
            "[]",
            '["sat_tiles", "sat_tiles"]',
            '["Sat"]',
            '"sat_tiles"',
            "[1]",
        ):
            with self.subTest(ids=ids):
                self.both(
                    self.with_config(self.entry(f'"{digest(NAME)}"', '"r"', ids)),
                    "entry 1: source_ids is not a non-empty list of distinct source ids",
                )

    def test_more_than_one_entry(self) -> None:
        files = base()
        files[CONFIG] = config(digest(NAME), digest(OTHER))
        files[ATTR] = decl(f"{NAME} and {OTHER}") + "\n"
        line = config_fail("more than one entry")
        self.assertRun(files, None, [line])
        self.assertRun(
            files,
            PRIVATE,
            [
                line,
                *refused(DOC04, line_numbers(str(files[DOC04]), NAME), listed=False),
                *refused(ATTR, [1], listed=False),
                *refused(ATTR, [1], extra=2, listed=False),
            ],
        )


class ListedNameCheck(Base):
    """Check 8 runs without the private list whenever a digest is listed."""

    def plant(self, path: str, text: str | bytes, expected: list[str]) -> None:
        files = base()
        files[path] = text
        self.assertRun(files, None, expected)

    def test_snake_case_in_python(self) -> None:
        self.plant(
            "tools/fetch.py",
            "quillmap_layer = 1\n",
            refused("tools/fetch.py", [1], extra=None),
        )

    def test_screaming_case_setting(self) -> None:
        self.plant(
            "tools/settings.py",
            "x = 1\nQUILLMAP_API_KEY = 'x'\n",
            refused("tools/settings.py", [2], extra=None),
        )

    def test_camel_case_in_typescript(self) -> None:
        self.plant(
            "web/src/layers.ts",
            "export const quillmapLayer = 1;\n",
            refused("web/src/layers.ts", [1], extra=None),
        )

    def test_dotted_host_in_mjs(self) -> None:
        self.plant(
            "web/scripts/hosts.mjs",
            "export const host = 'tiles.quillmap.example';\n",
            refused("web/scripts/hosts.mjs", [1], extra=None),
        )

    def test_env_example(self) -> None:
        self.plant(
            ".env.example", "QUILLMAP_KEY=\n", refused(".env.example", [1], extra=None)
        )

    def test_file_path(self) -> None:
        self.plant(
            "web/public/quillmap-logo.png",
            b"\x89PNG\x00\xff",
            [
                "FAIL listed-name: (path not shown): a listed name in a file or "
                "folder name: (matched text not shown)"
            ],
        )

    def test_hidden_path_hides_every_other_line_of_the_file(self) -> None:
        self.plant(
            "notes/quillmap.md",
            "Notes.\n[x](missing.md)\n",
            [
                "FAIL listed-name: (path not shown): a listed name in a file or "
                "folder name: (matched text not shown)",
                "FAIL link: (path not shown):2: target does not exist: missing.md",
            ],
        )

    def test_reason_field(self) -> None:
        files = base()
        files[CONFIG] = config(digest(NAME), reason=f"credit of {NAME}")
        lines = line_numbers(str(files[CONFIG]), "reason")
        self.assertRun(files, None, refused(CONFIG, lines, extra=None))

    def test_two_part_name_in_snake_and_camel_case(self) -> None:
        files = base()
        files[CONFIG] = config(digest("Brim fold"))
        files["tools/a.py"] = "brim_fold = 1\n"
        files["web/src/b.ts"] = "const brimFold = 1;\n"
        self.assertRun(
            files,
            None,
            refused("tools/a.py", [1], extra=None)
            + refused("web/src/b.ts", [1], extra=None),
        )


def hidden_path(why: str = "a listed name in a file or folder name") -> str:
    return f"FAIL listed-name: {HIDDEN}: {why}: (matched text not shown)"


HIDDEN = "(path not shown)"


class ReviewedPasses(Base):
    """Forms of the two places that a review found wrongly refused (they pass)."""

    def both(self, files: dict[str, str | bytes]) -> None:
        self.assertRun(files, PRIVATE, [])
        self.assertRun(files, None, [])

    def test_attribution_file_with_byte_order_mark(self) -> None:
        files = base()
        files[ATTR] = "﻿" + str(files[ATTR])
        self.both(files)

    def test_annotated_and_quoted_declarations(self) -> None:
        for line in (
            f"export const MAP_ATTRIBUTION: string = `© {NAME} imagery`;",
            f'export const MAP_ATTRIBUTION = "© {NAME} imagery";',
            f"export const MAP_ATTRIBUTION = '© {NAME} imagery';",
            f'export const MAP_ATTRIBUTION: string = "© {NAME} imagery";',
        ):
            with self.subTest(line=line):
                files = base()
                files[ATTR] = line + "\n"
                self.both(files)

    def test_other_code_and_comments_in_attribution_file(self) -> None:
        files = base()
        files[ATTR] = (
            'import { layers } from "./layers";\n\n'
            "/** Map credits. */\n"
            f"{decl(NAME)}\n"
            "export const OTHER_SETTING = { size: [1, 2] };\n"
            "/* A block\n   comment. */\n"
            "export const QUOTE = 'it\\'s // not a comment';\n"
            "export function credit(): string {\n  return layers;\n}\n"
        )
        self.both(files)

    def test_padded_first_cell(self) -> None:
        files = base()
        files[DOC04] = str(files[DOC04]).replace(
            "| `sat_tiles` | Satellite tiles |", "|   `sat_tiles`   | Satellite tiles |"
        )
        self.assertIn("|   `sat_tiles`", str(files[DOC04]))
        self.both(files)

    def test_comment_in_a_later_section_and_thematic_break_in_section_2(self) -> None:
        files = base()
        text = str(files[DOC04])
        text = text.replace("Registry prose.", "Registry prose.\n\n---")
        text = text.replace("Fetcher prose.", "Fetcher prose.\n\n<!-- a note -->")
        files[DOC04] = text
        self.both(files)

    def test_private_pattern_matching_part_of_the_name(self) -> None:
        self.assertRun(base(), [*PRIVATE, NAME.lower()[-5:]], [])


class ReviewedRefusals(Base):
    """Bypasses a review found (each is refused)."""

    def edit(self, old: str, new: str) -> dict[str, str | bytes]:
        files = base()
        text = str(files[DOC04])
        self.assertIn(old, text)
        files[DOC04] = text.replace(old, new, 1)
        return files

    def whole_doc04(self, files: dict[str, str | bytes]) -> None:
        lines = line_numbers(str(files[DOC04]), NAME)
        self.assertGreaterEqual(len(lines), 2)
        self.assertRun(files, PRIVATE, refused(DOC04, lines))
        self.assertRun(files, None, refused(DOC04, lines, extra=None))

    def table(self, dataset: str) -> str:
        return (
            "| source_id | Dataset | Publisher | Licence |\n|---|---|---|---|\n"
            f"| `sat_tiles` | {dataset} | {NAME} | Open |"
        )

    def test_duplicate_heading_before_section_2(self) -> None:
        fake = "## 2. Source registry\n\n" + self.table("Dup tiles") + "\n\n"
        for files in (
            self.edit("## 2. Source registry", fake + "## 2. Source registry"),
            self.edit("Scope prose.", "Scope prose.\n\n" + fake + "## 1b. More\n"),
        ):
            with self.subTest():
                self.whole_doc04(files)

    def test_heading_swallowed_by_an_html_block(self) -> None:
        files = self.edit(
            "Scope prose.",
            "Scope prose.\n\n<div>\n## 2. Source registry\n\n"
            + self.table("Div tiles")
            + "\n",
        )
        self.whole_doc04(files)

    def test_other_spelling_of_the_real_heading_and_a_fake_at_the_end(self) -> None:
        for real in ("## 2. Source registry ##", "## 2&#46; Source registry"):
            with self.subTest(real=real):
                files = self.edit("## 2. Source registry", real)
                files[DOC04] = (
                    str(files[DOC04])
                    + "\n<div>\n## 2. Source registry\n\n"
                    + self.table("End tiles")
                    + "\n"
                )
                self.whole_doc04(files)

    def test_fake_heading_in_a_pre_block(self) -> None:
        files = self.edit(
            "Scope prose.",
            "Scope prose.\n\n<pre>\n## 2. Source registry\n\n"
            + self.table("Pre tiles")
            + "\n\n## end of sample\nprose.</pre>\n",
        )
        self.whole_doc04(files)

    def test_fake_heading_after_an_unclosed_fence_in_a_list_item(self) -> None:
        files = self.edit(
            "Scope prose.",
            "Scope prose.\n\n- sample:\n  ```\n## 2. Source registry\n\n"
            + self.table("List tiles")
            + "\n\n## end of sample\n",
        )
        self.whole_doc04(files)

    def test_comment_open_across_the_heading(self) -> None:
        files = self.edit("Scope prose.", "Scope prose. <!-- open")
        files[DOC04] = str(files[DOC04]).replace("Fetcher prose.", "Fetcher -->")
        self.whole_doc04(files)

    def test_delimiter_row_with_fewer_cells_than_the_header(self) -> None:
        files = self.edit(
            "Registry prose.",
            "Registry prose.\n\n| source_id | Dataset | Publisher |\n|---|\n"
            f"| `sat_tiles` | Pseudo | {NAME} |",
        )
        self.assertRun(
            files, PRIVATE, refused(DOC04, line_numbers(str(files[DOC04]), "Pseudo"))
        )

    def test_name_in_a_cell_past_the_header(self) -> None:
        files = self.edit(
            f"| `sat_tiles` | Satellite tiles | {NAME} | Open |",
            f"| `sat_tiles` | Satellite tiles | Pub | Open | {NAME} |",
        )
        self.assertRun(
            files, PRIVATE, refused(DOC04, line_numbers(str(files[DOC04]), "Pub |"))
        )

    def plant(
        self,
        files: dict[str, str | bytes],
        expected: list[str],
        prepare: Callable[[Path], None] | None = None,
        patterns: list[str] | None = None,
    ) -> None:
        self.assertRun(files, patterns, expected, prepare)

    def test_link_target_holds_the_name(self) -> None:
        def links(root: Path) -> None:
            (root / "docs/more.md").symlink_to("../quillmap/notes.md")
            (root / "docs/other.md").symlink_to("../Quill_Map/notes.md")

        why = "a listed name in a link target"
        self.plant(
            base(),
            [
                f"FAIL listed-name: docs/more.md: {why}: (matched text not shown)",
                f"FAIL listed-name: docs/other.md: {why}: (matched text not shown)",
            ],
            links,
        )

    def test_link_named_with_the_name(self) -> None:
        def links(root: Path) -> None:
            (root / "docs/quillmap").symlink_to("decisions")
            (root / "docs/quillmap-old").symlink_to("nothing-here")

        self.plant(base(), [hidden_path(), hidden_path()], links)

    def test_file_that_is_not_utf8(self) -> None:
        files = base()
        files["tables/a.csv"] = b"x\xe9\nquillmap\n"
        files["web/a.mjs"] = b"// \xe9\nexport const q = 'quillmap';\n"
        files["tables/b.csv"] = "id\nquillmap\n".encode("utf-16")
        self.plant(
            files,
            refused("tables/a.csv", [2], extra=None)
            + refused("web/a.mjs", [2], extra=None)
            + refused("tables/b.csv", [2], extra=None),
        )

    def test_file_name_that_is_not_utf8(self) -> None:
        def odd(root: Path) -> None:
            (root / "docs").joinpath(os.fsdecode(b"note\xff.md")).write_text(
                "quillmap\n", encoding="utf-8"
            )

        self.plant(
            base(),
            [
                f"FAIL path-encoding: {HIDDEN}: a file or folder name is not valid UTF-8",
                f"FAIL listed-name: {HIDDEN}:1: a listed name outside its places: "
                "(matched text not shown)",
            ],
            odd,
        )

    def test_name_inside_longer_words(self) -> None:
        files = base()
        files["web/a.mjs"] = "export const h = 'tiles.quillmapcdn.example';\n"
        files["web/b.svg"] = "<svg><title>quillmaps</title></svg>\n"
        files["tables/c.csv"] = "id,quillmaps\n"
        files["tools/run"] = "geoquillmap\n"
        files["docs/quillmaps.md"] = "Fixture.\n"
        files["README.md"] = "quillmaps\ngeoquillmap\nquillmapquillmap\n"
        files["web/t.ts"] = "const tilesquillmapurl = 1;\n"
        self.plant(
            files,
            [
                hidden_path(),
                *refused("web/a.mjs", [1], extra=None),
                *refused("web/b.svg", [1], extra=None),
                *refused("tables/c.csv", [1], extra=None),
                *refused("tools/run", [1], extra=None),
                *refused("README.md", [1, 2, 3], extra=None),
                *refused("web/t.ts", [1], extra=None),
            ],
        )

    def test_alternating_case_cut_and_hidden_forms(self) -> None:
        files = base()
        files["web/c.mjs"] = "const q = 'qUiLlMaP';\n"
        files["README.md"] = (
            "QuIlLmAp\n"
            "Qu-il-lm-ap\n"
            "Qu\u200bil\u200blm\u200bap\n"
            "Quill&#109;ap\n"
            "Quill\u043cap and Quillm\u0430p\n"
            "Fixture.\n"
            "credit Quill-\n"
            "map here\n"
        )
        files["web/e.ts"] = "const s = '\\u0051uillmap\\x2e';\n"
        self.plant(
            files,
            refused("web/c.mjs", [1], extra=None)
            + refused("README.md", [1, 2, 3, 4, 5, 8], extra=None)
            + refused("web/e.ts", [1], extra=None),
        )

    def test_names_of_four_parts(self) -> None:
        for listed, text in (
            ("Quill3DMapia", "Quill3DMapia\n"),
            ("Brim fold Quill map", "brim_fold_quill_map\n"),
        ):
            with self.subTest(listed=listed):
                files = base()
                files[CONFIG] = config(digest(listed))
                files["README.md"] = text
                self.plant(files, refused("README.md", [1], extra=None))

    def test_missing_pattern_file(self) -> None:
        code, fails = run(base(), None, missing_patterns=True)
        self.assertEqual(
            fails,
            ["FAIL extra-patterns: EII_FORBIDDEN_PATTERNS_FILE names no readable file"],
        )
        self.assertEqual(code, 1)

    def test_second_private_name_in_a_path_an_svg_and_an_mjs(self) -> None:
        files = base()
        files["docs/brimfold.md"] = "Fixture.\n"
        files["web/x.svg"] = "<svg>brimfold</svg>\n"
        files["web/y.mjs"] = "// brimfold\n"
        self.plant(
            files,
            [
                "FAIL extra-2: (path not shown): extra forbidden pattern in a file "
                "or folder name: (matched text not shown)",
                *refused("web/x.svg", [1], extra=2, listed=False),
                *refused("web/y.mjs", [1], extra=2, listed=False),
            ],
            patterns=PRIVATE,
        )

    def test_built_in_tokens_are_hidden_on_lines_with_a_name(self) -> None:
        files = base()
        files["README.md"] = (
            "Write to press" + "@quillmap.example now.\n"
            "[terms](quillmap-terms.md)\n"
            "See /home/" + "quillmap/x here.\n"
        )
        hidden = "(matched text not shown)"
        self.plant(
            files,
            [
                f"FAIL email: README.md:1: e-mail address: {hidden}",
                f"FAIL link: README.md:2: target does not exist: {hidden}",
                f"FAIL local-path: README.md:3: absolute local path: {hidden}",
                *refused("README.md", [1, 2, 3]),
            ],
            patterns=PRIVATE,
        )


class FileListing(unittest.TestCase):
    """In-process cases of the file listing of a checkout."""

    def module(self) -> types.ModuleType:
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            import check_docs
        finally:
            sys.path.pop(0)
        return check_docs

    def test_git_listing_keeps_names_that_are_not_utf8(self) -> None:
        check_docs = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            raw = b"note\xff.md"
            (root / os.fsdecode(raw)).write_text("x\n", encoding="utf-8")
            (root / "a.md:Zone.Identifier").write_text("x\n", encoding="utf-8")
            done = subprocess.CompletedProcess(
                [], 0, stdout=raw + b"\0a.md:Zone.Identifier\0", stderr=b""
            )
            with (
                mock.patch.object(check_docs, "ROOT", root),
                mock.patch.object(check_docs.subprocess, "run", return_value=done),
            ):
                found = check_docs.listed_files()
        self.assertEqual(
            sorted(path.name for path in found),
            sorted([os.fsdecode(raw), "a.md:Zone.Identifier"]),
        )


if __name__ == "__main__":
    unittest.main()
