"""Offline evidence files; tests use a temporary repository root only."""

import json
from pathlib import Path
from uuid import uuid4

from .memo import canonical
from .schema import Record, validate_record

RUNS = Path("evals/typed_decisions/runs")


class RecordStore:
    def __init__(self, root: Path, runs: Path = RUNS) -> None:
        if runs != RUNS:
            raise ValueError("records belong only in evals/typed_decisions/runs")
        self.folder = root / runs
        if self.folder.resolve() != root.resolve() / runs:
            raise ValueError("record directory escapes repository")
        self.folder.mkdir(parents=True, exist_ok=True)

    def write(self, record: Record) -> Path:
        validate_record(record)
        path = self.folder / f"{uuid4()}.json"
        with path.open("x", encoding="utf-8") as stream:
            stream.write(canonical(record) + "\n")
        return path

    def read(self, path: Path) -> Record:
        if path.resolve().parent != self.folder.resolve() or path.suffix != ".json":
            raise ValueError("record is outside runs")
        return validate_record(json.loads(path.read_text(encoding="utf-8")))

    def first(self, key: str) -> Record | None:
        records = [self.read(path) for path in sorted(self.folder.glob("*.json"))]
        matching = [record for record in records if record["memo_key"] == key]
        return (
            min(matching, key=lambda record: str(record["recorded_at"]))
            if matching
            else None
        )
