"""Repository-contained evidence packet and linked static evaluation gallery."""

from __future__ import annotations

import csv
import html
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from evals.question_lab.locks import digest

# Decision 0049 plus the existing TST-90 sizes and both phone rotations.
SIZES = (
    (360, 640),
    (640, 360),
    (390, 844),
    (844, 390),
    (768, 1024),
    (1024, 768),
    (1366, 768),
    (1440, 900),
    (1920, 1080),
    (2560, 1440),
    (3440, 1440),
    (3840, 2160),
)


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )


def ledger_problems(raw: bytes, *, committed: bytes) -> list[str]:
    if not raw.startswith(committed):
        return ["ledger:committed_prefix_changed"]
    previous = b""
    seen = set()
    problems = []
    for line in raw.splitlines(keepends=True):
        try:
            row = json.loads(line)
            if row["previous_sha256"] != digest(previous) or row["run"] in seen:
                problems.append("ledger:chain")
            if row["status"] not in {"incomplete", "failed", "passed"} or row[
                "exit"
            ] != (0 if row["status"] == "passed" else 1):
                problems.append("ledger:outcome")
            seen.add(row["run"])
        except (ValueError, TypeError, KeyError):
            problems.append("ledger:invalid")
        previous += line
    return sorted(set(problems))


def capture_path(folder: Path, name: str) -> Path:
    path = PurePosixPath(name)
    if (
        re.fullmatch(r"[A-Za-z0-9_./-]+[.]png", name) is None
        or path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.suffix != ".png"
    ):
        raise ValueError("capture_path")
    candidate = folder
    for part in path.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("capture_path")
    return candidate


def packet_problems(folder: Path, identities: Sequence[str]) -> list[str]:
    problems = []
    result_path = folder / "results.jsonl"
    if not result_path.is_file():
        problems.append("packet:results_missing")
    else:
        rows = [json.loads(line) for line in result_path.read_text().splitlines()]
        expected = {
            (identity, language) for identity in identities for language in ("en", "ar")
        }
        actual = [(row.get("question_id"), row.get("language")) for row in rows]
        if set(actual) != expected or len(actual) != len(expected):
            problems.append("packet:bilingual_results")
    index = folder / "captures.json"
    if not index.is_file():
        problems.append("packet:captures_missing")
    else:
        captures = json.loads(index.read_text())
        expected_captures = {
            (identity, lang, theme, f"{w}x{h}", state)
            for identity in identities
            for lang in ("en", "ar")
            for theme in ("dark", "light")
            for w, h in SIZES
            for state in (
                ("answer", "comparison", "evidence", "drawer")
                + (
                    ("refusal",)
                    if identity.startswith("INVENTED-question-refusal-")
                    else ()
                )
            )
        }
        keys = [
            (
                row["question_id"],
                row["language"],
                row["theme"],
                row["size"],
                row.get("state"),
            )
            for row in captures
        ]
        if set(keys) != expected_captures or len(keys) != len(expected_captures):
            problems.append("packet:capture_matrix")
        for row in captures:
            if row.get("sealed") is not False:
                problems.append("packet:sealed_capture")
                continue
            try:
                image = capture_path(folder, row["path"])
                if not image.is_file() or digest(image.read_bytes()) != row.get(
                    "sha256"
                ):
                    problems.append("packet:capture_hash")
            except (ValueError, OSError):
                problems.append("packet:capture_path")
    return sorted(set(problems))


def write_results(folder: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with (folder / "results.jsonl").open("x") as output:
        for row in rows:
            output.write(
                json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False)
                + "\n"
            )
    with (folder / "results.csv").open("x", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "question_id",
                "language",
                "family",
                "scope",
                "status",
                "problems",
                "accuracy",
                "smoothness",
                "value",
                "visual",
                "map",
            )
        )
        for row in rows:
            writer.writerow(
                [
                    row.get(key, "")
                    for key in ("question_id", "language", "family", "scope", "status")
                ]
                + [";".join(row.get("problems", []))]
                + [
                    row.get("judgements", {}).get(key, "waiting")
                    for key in ("accuracy", "smoothness", "value", "visual", "map")
                ]
            )


def write_gallery(folder: Path, captures: Sequence[Mapping[str, Any]]) -> None:
    cards = []
    for row in captures:
        if row.get("sealed") is not False:
            raise ValueError("gallery_sealed")
        name = row["path"]
        capture_path(folder, name)
        title = " / ".join(
            str(row[key]) for key in ("question_id", "language", "theme", "size")
        )
        safe_name, safe_title = html.escape(name, quote=True), html.escape(title)
        cards.append(
            f'<figure><a href="{safe_name}"><img loading="lazy" src="{safe_name}" alt="Answer capture"></a><figcaption><bdi>{safe_title}</bdi></figcaption></figure>'
        )
    body = (
        "\n".join(cards)
        if cards
        else "<p>Captures waiting: qualification prerequisites are incomplete. No image or visual pass is claimed.</p>"
    )
    # Evaluation statistics/identities, not product facts or application claims.
    (folder / "gallery.html").write_text(
        '<!doctype html><html lang="en" dir="ltr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Conversation lab evidence</title><style>body{font-family:system-ui;margin:2rem;background:#101827;color:#eef2f9}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(18rem,1fr));gap:1rem}figure{margin:0}img{width:100%;height:auto}bdi{overflow-wrap:anywhere}a{color:#bcd7ff}</style><h1>Conversation lab evidence</h1><p>Invented loaded fixture. Layout emulation supplies no native performance, human beauty or Arabic approval. Sealed captures are excluded.</p><a href="coverage.json">Coverage and empty cells</a> · <a href="results.csv">Per-question results</a> · <a href="qualification.json">Qualification limits</a><main>'
        + body
        + "</main></html>"
    )
    write_json(folder / "curated.json", [dict(row) for row in captures[:30]])
