"""Write the web catalogue from the closed assistant catalogues.

The default command writes web/src/brief/catalogue.generated.json and the shared
web/src/api/reason-codes.generated.json vocabulary. With --check it compares both
files to fresh exports and writes nothing. The --path test override writes only
the specified assistant catalogue. A refusal from the
loader exits non-zero and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from importlib.resources.abc import Traversable
from pathlib import Path

from eii_core.reason_codes import CODES
from eii_core.reasons import closed_code
from eii_product.assistant.catalogue.load import catalogue_directory, load_catalogue
from eii_product.assistant.catalogue.schema import Refusal


def repo_root() -> Path:
    """Return the repository root that holds the product package."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (
            parent / "product/src/eii_product/assistant/catalogue/assets/claims.yaml"
        ).is_file():
            return parent
    raise FileNotFoundError("repository root not found")


def _convert(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _convert(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_convert(item) for item in value]
    if isinstance(value, list):
        return [_convert(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _convert(item) for key, item in value.items()}
    return value


def _prettier(text: str, root: Path) -> str:
    """Format JSON with the pinned Prettier so the file stays clean."""
    binary = root / "web" / "node_modules" / "prettier" / "bin" / "prettier.cjs"
    node = shutil.which("node")
    if node is None or not binary.is_file():
        raise FileNotFoundError("pinned prettier is not available")
    result = subprocess.run(
        [node, str(binary), "--stdin-filepath", "catalogue.generated.json"],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "prettier failed")
    return result.stdout


def render_catalogue(folder: Traversable) -> str | None:
    """Return the canonical JSON, or None when the loader refuses."""
    loaded = load_catalogue(folder)
    if isinstance(loaded, Refusal):
        print(closed_code(loaded.rule_code, "catalogue_refused"), file=sys.stderr)
        return None
    payload = _convert(loaded)
    raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return _prettier(raw, repo_root())


def default_target(root: Path) -> Path:
    """Return the committed catalogue path."""
    return root / "web" / "src" / "brief" / "catalogue.generated.json"


_TOP_KEYS = frozenset(
    {"claims", "components", "directives", "fragments", "questions", "version"}
)
_VERSION = re.compile(r"^[0-9a-f]{64}$")


def _malformed(current: str) -> bool:
    """A file is malformed when it is not the export's closed JSON shape."""
    try:
        parsed = json.loads(current)
    except json.JSONDecodeError:
        return True
    if not isinstance(parsed, dict) or set(parsed) != _TOP_KEYS:
        return True
    version = parsed.get("version")
    return not isinstance(version, str) or _VERSION.fullmatch(version) is None


def check_name(current: str, fresh: str) -> str | None:
    """Name why --check refuses a file, or None when the bytes match."""
    if current == fresh:
        return None
    if _malformed(current):
        return "malformed"
    current_version = json.loads(current)["version"]
    fresh_version = json.loads(fresh)["version"]
    if current_version != fresh_version:
        return "changed-version"
    return "stale"


def run(folder: Traversable, target: Path, check: bool) -> int:
    """Export or compare. A refusal writes nothing."""
    text = render_catalogue(folder)
    if text is None:
        return 1
    if check:
        if not target.is_file():
            print("catalogue_target_missing", file=sys.stderr)
            return 1
        current = target.read_text(encoding="utf-8")
        name = check_name(current, text)
        if name == "malformed":
            print(name, file=sys.stderr)
            return 1
        if name == "changed-version":
            print(name, file=sys.stderr)
            return 1
        if name == "stale":
            print(name, file=sys.stderr)
            return 1
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Export the closed catalogues, or compare them with --check."""
    parser = argparse.ArgumentParser(description="Export the web catalogue.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the committed file and write nothing.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Override the output path. Tests use this; the documented command does not.",
    )
    args = parser.parse_args(argv)
    root = repo_root()
    target = args.path if args.path is not None else default_target(root)
    result = run(catalogue_directory(), target, args.check)
    if result != 0 or args.path is not None:
        return result
    reasons = root / "web/src/api/reason-codes.generated.json"
    text = _prettier(json.dumps(sorted(CODES), ensure_ascii=False), root)
    if args.check:
        if not reasons.is_file() or reasons.read_text(encoding="utf-8") != text:
            print("reason_catalogue_stale", file=sys.stderr)
            return 1
    else:
        reasons.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
