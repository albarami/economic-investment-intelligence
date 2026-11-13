"""Round trip and planted violations of the closed record and path contracts."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eii_gateway import Gateway
from eii_gateway.records import RUNS, RecordStore
from eii_gateway.schema import FIELDS, Record, validate_record

from .support import request


class DecisionRecordSchema(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        with patch.dict(os.environ, {"EII_DECISION_PROVIDER": "none"}):
            self.record = Gateway(self.root).decide(request())
        self.store = RecordStore(self.root)

    def test_round_trip(self) -> None:
        self.assertEqual(
            FIELDS,
            {
                "decision_class",
                "kind",
                "provider_configured",
                "provider_used",
                "reported_model_id",
                "rubric_id",
                "rubric_sha256",
                "input_class",
                "input_sha256",
                "language",
                "route",
                "option_order",
                "returned_label",
                "returned_scores",
                "top_score",
                "threshold_in_force",
                "threshold_outcome",
                "memo_key",
                "latency_ms",
                "fallback_applied",
                "permitted_effect",
                "recorded_at",
                "human_disposition",
            },
        )
        path = self.store.write(self.record)
        self.assertEqual(self.store.read(path), self.record)
        self.assertNotIn("SYNTHETIC activity example", path.read_text())

    def test_extra_field_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.store.write({**self.record, "numeric_fact": 1})
        for key in self.record:
            value = dict(self.record)
            del value[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_record(value)

    def test_malformed_values_rejected_on_read_and_write(self) -> None:
        plants: dict[str, object] = {
            "decision_class": "privacy",
            "kind": "number",
            "provider_configured": "other",
            "provider_used": "other",
            "reported_model_id": "",
            "rubric_id": 2,
            "rubric_sha256": "wrong",
            "input_sha256": "bad",
            "memo_key": "bad",
            "input_class": "visitor_typed",
            "threshold_outcome": "APPROVED",
            "permitted_effect": "clear_gate",
            "option_order": [["yes", "yes"]],
            "returned_label": "invented",
            "returned_scores": {"invented": 0.8},
            "top_score": 0.8,
            "threshold_in_force": {"high": 0.5, "low": 0.5},
            "latency_ms": -1,
            "fallback_applied": False,
            "human_disposition": 7,
            "recorded_at": "2026-11-13T00:00:00",
        }
        for key, value in plants.items():
            with self.subTest(key=key):
                broken = {**self.record, key: value}
                with self.assertRaises(ValueError):
                    self.store.write(broken)
                path = self.root / RUNS / "synthetic-invalid.json"
                path.write_text(json.dumps(broken))
                with self.assertRaises(ValueError):
                    self.store.read(path)
                path.unlink()
        for order in (
            [],
            [["no", "yes"], ["yes", "no"]],
            [["", "yes"]],
            [["1", "yes"]],
            [["yes", "no"]],
        ):
            with self.subTest(order=order), self.assertRaises(ValueError):
                validate_record({**self.record, "option_order": order})
        for latency in (True, float("nan"), float("inf")):
            with self.subTest(latency=latency), self.assertRaises(ValueError):
                validate_record({**self.record, "latency_ms": latency})

    def test_result_consistency(self) -> None:
        record: Record = {
            **self.record,
            "returned_label": "yes",
            "returned_scores": {"yes": 0.9, "no": 0.1},
            "top_score": 0.9,
            "threshold_outcome": "DECIDED",
            "fallback_applied": False,
        }
        self.assertEqual(validate_record(record), record)
        plants: tuple[dict[str, object], ...] = (
            {"returned_label": None},
            {"top_score": 0.1},
            {"returned_scores": {"no": 0.1}},
            {"returned_scores": {"yes": True, "no": 0.1}},
            {"returned_scores": {"yes": 1.1, "no": 0.1}},
            {"returned_scores": []},
        )
        for changes in plants:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_record({**record, **changes})
        choice = {
            **record,
            "kind": "choice",
            "option_order": [["yes", "no"], ["no", "yes"]],
        }
        validate_record(choice)
        broken = copy.deepcopy(choice)
        broken["option_order"] = [["yes", "no"], ["yes", "no"]]
        with self.assertRaises(ValueError):
            validate_record(broken)

    def test_wrong_runs_dir_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RecordStore(self.root, Path("other/runs"))
        with self.assertRaises(ValueError):
            self.store.read(self.root / "outside.json")
        with self.assertRaises(ValueError):
            self.store.read(self.root / RUNS / "wrong.txt")
        other = self.root / "synthetic-repository"
        other.mkdir()
        (other / "evals").symlink_to(self.root / "evals", target_is_directory=True)
        with self.assertRaises(ValueError):
            RecordStore(other)

    def test_later_human_disposition_is_readable(self) -> None:
        path = self.root / RUNS / "synthetic-reviewed.json"
        path.write_text(
            json.dumps(
                {**self.record, "human_disposition": "synthetic-review-complete"}
            )
        )
        self.assertEqual(
            self.store.read(path)["human_disposition"], "synthetic-review-complete"
        )

        for disposition in ("", False):
            with self.subTest(disposition=disposition), self.assertRaises(ValueError):
                validate_record({**self.record, "human_disposition": disposition})
