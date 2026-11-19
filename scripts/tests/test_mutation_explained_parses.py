"""Keep the real mutation ledger in ordinary unittest discovery (S2-T43)."""

import importlib
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

LEDGER = Path(__file__).resolve().parents[1] / "mutation_explained.toml"


def check_ledger(path: Path) -> None:
    """Parse and check the ledger shape consumed by mutation.judge."""
    # judge is importable without mutmut, but returns a verdict, not parsed rows.
    # Use tomllib for shape inspection and the real judge for runner compatibility.
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    if set(document) != {"survivors"}:
        raise ValueError("Ledger must contain only the survivors array")
    rows = document["survivors"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Ledger must contain at least one survivor row")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"module", "mutation", "reason"}:
            raise ValueError("Survivor rows need module, mutation and reason")
        if any(
            not isinstance(value, str) or not value.strip() for value in row.values()
        ):
            raise ValueError("Survivor fields must be nonempty strings")
    runner = importlib.import_module("scripts.mutation")
    if runner.judge(rows, path) != 0:
        raise ValueError("Ledger rows must be accepted by the mutation runner")


class MutationExplainedParsesTests(unittest.TestCase):
    def assert_refused(self, text: str, error: type[Exception]) -> None:
        with TemporaryDirectory(prefix="synthetic-ledger-") as temporary:
            copy = Path(temporary) / "mutation_explained.toml"
            copy.write_text(text, encoding="utf-8")
            with self.assertRaises(error):
                check_ledger(copy)

    def test_real_repository_ledger_parses(self) -> None:
        check_ledger(LEDGER)

    def test_duplicate_key_inside_row_is_refused(self) -> None:
        text = LEDGER.read_text(encoding="utf-8")
        broken = text.replace(
            "[[survivors]]\n",
            '[[survivors]]\nmodule = "synthetic-duplicate"\n',
            1,
        )
        self.assertNotEqual(broken, text)
        self.assert_refused(broken, tomllib.TOMLDecodeError)

    def test_removed_row_header_is_refused(self) -> None:
        text = LEDGER.read_text(encoding="utf-8")
        prefix, first_row, rest = text.split("[[survivors]]", 2)
        broken = prefix + "[[survivors]]" + first_row + rest
        self.assert_refused(broken, tomllib.TOMLDecodeError)

    def test_stray_key_without_header_is_refused(self) -> None:
        text = LEDGER.read_text(encoding="utf-8")
        broken = 'reason = "Synthetic stray line without a row header."\n' + text
        self.assert_refused(broken, ValueError)

    def test_invalid_runner_shapes_are_refused(self) -> None:
        valid_row = (
            'module = "synthetic/module.py"\n'
            'mutation = "synthetic diff"\n'
            'reason = "Synthetic shape fixture."\n'
        )
        valid = "[[survivors]]\n" + valid_row
        invalid = [
            "",
            "survivors = []\n",
            'survivors = "wrong type"\n',
            'survivors = ["wrong row type"]\n',
            "[survivors]\n" + valid_row,
        ]
        for field in ("module", "mutation", "reason"):
            line = next(
                line for line in valid.splitlines(True) if line.startswith(field)
            )
            invalid.extend(
                (
                    valid.replace(line, ""),
                    valid.replace(line, field + " = 1\n"),
                    valid.replace(line, field + ' = " "\n'),
                )
            )
        for text in invalid:
            with self.subTest(text=text):
                self.assert_refused(text, ValueError)


if __name__ == "__main__":
    unittest.main()
