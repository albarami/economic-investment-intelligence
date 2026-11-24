"""BE-69 local ledger. L-698's pre-seat stand-in is isolated in tool_entry."""

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

COLUMNS = (
    "entry_id",
    "occurred_at",
    "seat_key",
    "organisation_id",
    "brief_id",
    "answer_id",
    "kind",
    "playbook",
    "tool",
    "arguments",
    "question_text",
    "area_cell",
    "activity_key",
    "release_id",
    "engine",
    "status",
    "fact_ids",
    "writer",
    "injection_flag",
    "origin",
)
JSON_COLUMNS = {"arguments", "fact_ids"}


def without_coordinates(value: Any) -> Any:
    """Coordinates are never persisted, including nested stage targets."""
    if isinstance(value, str) and value.startswith("ma1/"):
        return "area_redacted"
    if isinstance(value, dict):
        return {
            key: without_coordinates(item)
            for key, item in value.items()
            if key not in {"latitude", "longitude", "lat", "lon", "pin", "coordinates"}
        }
    if isinstance(value, list):
        return [without_coordinates(item) for item in value]
    return value


def tool_entry(
    *,
    answer_id: str,
    tool: str,
    arguments: dict[str, Any],
    release_id: str,
    engine: str,
    status: str,
    fact_ids: list[str],
) -> dict[str, Any]:
    """The temporary empty seat and null organisation are replaced at S9."""
    generate_uuid7 = getattr(uuid, "uuid7", None)
    if not callable(generate_uuid7):
        raise RuntimeError("python_version_refused")
    return dict(
        entry_id=str(generate_uuid7()),
        occurred_at=datetime.now(UTC).isoformat(),
        seat_key="",
        organisation_id=None,
        brief_id=None,
        answer_id=answer_id,
        kind="tool_call",
        playbook="site_check",
        tool=tool,
        arguments=without_coordinates(arguments),
        question_text=None,
        area_cell=None,
        activity_key=arguments.get("activity"),
        release_id=release_id,
        engine=engine,
        status=status,
        fact_ids=fact_ids,
        writer="template",
        injection_flag=False,
        origin="live",
    )


class LocalLedger:
    """One durable row per call; exact replays are idempotent, conflicts refuse."""

    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        definitions = ", ".join(name + " TEXT" for name in COLUMNS)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS ledger_entry ("
            + definitions
            + ", PRIMARY KEY (entry_id), CHECK (origin = 'live'))"
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def row_count(self) -> int:
        """Fixed operational read of the durable journal, used by OPS-30."""
        row = self.connection.execute("SELECT COUNT(*) FROM ledger_entry").fetchone()
        if row is None or type(row[0]) is not int:
            raise ValueError("ledger_count_unavailable")
        return int(row[0])

    def rows(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM ledger_entry ORDER BY rowid"
        ).fetchall()
        result = []
        for row in rows:
            item = dict(zip(COLUMNS, row, strict=True))
            for key in JSON_COLUMNS:
                item[key] = json.loads(item[key])
            item["injection_flag"] = bool(int(item["injection_flag"]))
            result.append(item)
        return result

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Nested savepoints keep a failed playbook from retaining partial calls."""
        self.connection.execute("SAVEPOINT playbook_write")
        try:
            yield
        except Exception:
            self.connection.execute("ROLLBACK TO playbook_write")
            self.connection.execute("RELEASE playbook_write")
            raise
        else:
            self.connection.execute("RELEASE playbook_write")

    def write(self, entry: dict[str, Any]) -> None:
        if (
            set(entry) != set(COLUMNS)
            or entry["origin"] != "live"
            or entry["kind"] != "tool_call"
        ):
            raise ValueError("ledger_entry_invalid")
        if entry["arguments"] != without_coordinates(entry["arguments"]):
            raise ValueError("ledger_entry_invalid")
        existing = [row for row in self.rows() if row["entry_id"] == entry["entry_id"]]
        if existing:
            if existing != [entry]:
                raise ValueError("ledger_replay_conflict")
            return
        values = [
            json.dumps(entry[name], sort_keys=True, separators=(",", ":"))
            if name in JSON_COLUMNS
            else entry[name]
            for name in COLUMNS
        ]
        with self.transaction():
            self.connection.execute(
                "INSERT INTO ledger_entry VALUES ("
                + ",".join("?" for _ in COLUMNS)
                + ")",
                values,
            )
        self.require_entry(entry)

    def require_entry(self, entry: dict[str, Any]) -> None:
        if [row for row in self.rows() if row["entry_id"] == entry["entry_id"]] != [
            entry
        ]:
            raise ValueError("ledger_cardinality")

    def require_entries(self, entries: list[dict[str, Any]]) -> None:
        answer_ids = {entry["answer_id"] for entry in entries}
        rows = [row for row in self.rows() if row["answer_id"] in answer_ids]
        if rows != entries:
            raise ValueError("ledger_cardinality")
