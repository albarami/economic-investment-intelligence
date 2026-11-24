"""Part A: plant one inner failure at each real outer boundary, offline."""

from __future__ import annotations

import ast
import contextlib
import io
import json
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from public_assembly_fixture import approve, dump, inputs
from s3_t28_support import ROOT, WorkspaceCase

from eii_custodian.release import assembly, producer
from eii_custodian.release.public_only import WriterRefusal
from eii_product.store.release_check import ReleaseRefusal
from eii_product.store.startup import StartupRefusal
from operations.common import Refusal

# One table owns the Part-A D-row contract; each case changes only the inner fault.
ROWS = (
    ("D1", "producer_hash_mismatch"),
    ("D2", "null_not_allowed"),
    ("D3", "assembly_gate_pending"),
    ("D4", "column_mismatch"),
    ("D5", "assembly_gate_pending"),
    ("D6", "digest_mismatch"),
    ("D7", "startup_artefact_mismatch"),
    ("D8", "startup_inventory_mismatch"),
    ("D9", "routing_tiles"),
    ("D10", "digest_mismatch"),
    ("D11", "input_key_missing"),
    ("D12", "process_identity_mismatch"),
    ("D13", "basemap_missing"),
    ("D14", "startup_inventory_mismatch"),
    ("D15", "application_web_build_timeout"),
    ("D16", "question_capacity"),
    ("D17", "input_type_invalid"),
    ("D48", "producer_receipt_format_invalid"),
    ("D49", "resolve_query_coverage"),
    ("D50", "digest_mismatch"),
    ("D51", "fixture:startup_inventory_mismatch"),
    ("D52", "UNKNOWN_CLAIM"),
    ("D54", "application_checksum_mismatch"),
    *(
        ("D55", code)
        for code in (
            "question_manifest",
            "question_identity",
            "question_capacity",
            "question_families",
        )
    ),
)


class ClosedReasons(WorkspaceCase):
    def test_part_a_table(self) -> None:
        for row, expected in ROWS:
            with self.subTest(row=row, reason=expected):
                observed = (
                    self.d55(expected) if row == "D55" else getattr(self, row.lower())()
                )
                self.assertEqual(observed, expected)

    def build_fault(
        self,
        *,
        producer_error: Exception | None = None,
        stderr: str = "column_mismatch\n",
    ) -> str:
        from operations.build import build_release

        cache = self.root / "cache"
        dump(cache / "review/release_spec.json", {})
        result = SimpleNamespace(returncode=4, stderr=stderr)
        with patch(
            "eii_custodian.release.producer.produce", side_effect=producer_error
        ):
            with self.assertRaises(Refusal) as caught:
                build_release(self.root, cache=cache, sandbox=Mock(return_value=result))
        return caught.exception.reason

    def d1(self) -> str:
        return self.build_fault(producer_error=ValueError("producer_hash_mismatch"))

    def d2(self) -> str:
        with patch.object(
            producer, "_candidate", side_effect=WriterRefusal("null_not_allowed")
        ):
            with self.assertRaises(ValueError) as caught:
                producer.prepare(self.root)
        return str(caught.exception)

    def d3(self) -> str:
        from importlib import import_module

        main = import_module("sandbox_inside.public_release").main

        output = io.StringIO()
        with (
            patch.object(
                assembly,
                "read_assembly",
                side_effect=ValueError("assembly_gate_pending"),
            ),
            contextlib.redirect_stderr(output),
        ):
            self.assertEqual(main([str(ROOT), str(self.root), str(self.root)]), 4)
        return output.getvalue().strip()

    def d4(self) -> str:
        return self.build_fault()

    def test_sandbox_stderr_never_publishes_unstructured_text(self) -> None:
        for text in (
            "",
            "INVENTED/private SELECT secret",
            "column_mismatch\nINVENTED/private",
            "column_mismatchcolumn_mismatch",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.build_fault(stderr=text), "operation_failed")

    def test_sandbox_writer_refusal_is_preserved(self) -> None:
        from importlib import import_module

        output = io.StringIO()
        with (
            patch.object(assembly, "read_assembly", return_value={"scalars": {}}),
            patch.object(
                assembly, "build", side_effect=WriterRefusal("column_mismatch")
            ),
            contextlib.redirect_stderr(output),
        ):
            self.assertEqual(
                import_module("sandbox_inside.public_release").main(
                    [str(ROOT), str(self.root), str(self.root)]
                ),
                4,
            )
        self.assertEqual(output.getvalue(), "column_mismatch\n")

    def d5(self) -> str:
        inputs(self.root)
        approve(self.root)
        candidate = producer.prepare(self.root)
        review = json.loads((self.root / producer.APPROVAL).read_bytes())
        dump(self.root / "assembly/release.json", candidate)
        dump(self.root / "assembly/release_review.json", review)
        with patch(
            "eii_custodian.publicdata.assembly_reports.require_complete",
            side_effect=ValueError("assembly_gate_pending"),
        ):
            with self.assertRaises(ValueError) as caught:
                assembly.read_assembly(self.root)
        return str(caught.exception)

    def command_fault(
        self, module: str, target: str, error: Exception, *, embedded: bool = False
    ) -> str:
        from importlib import import_module

        from preflight import Report

        command = import_module("commands." + module)
        output = io.StringIO()
        with (
            patch(target, side_effect=error),
            patch("preflight.run_preflight", return_value=Report((), "postgres", 0)),
            patch("preflight.up_decision", return_value=(0, "")),
            contextlib.redirect_stderr(output),
        ):
            if module == "build_release":
                code = command.run(self.root, {}, [])
            elif module == "load_release":
                code = command.run({"EII_ENVIRONMENT": "staging"}, [], root=self.root)
            elif module == "question_lab":
                code = command.run(self.root, {}, ["run", "--n", "100", "--seed", "17"])
            else:
                code = command.run(
                    self.root,
                    {"EII_ENVIRONMENT": "development" if embedded else "staging"},
                    ["--embedded"] if embedded else [],
                )
        self.assertNotEqual(code, 0)
        return output.getvalue().splitlines()[0].split(": ", 1)[1]

    def d6(self) -> str:
        return self.command_fault(
            "build_release",
            "commands.build_release.build_release",
            ReleaseRefusal("digest_mismatch"),
        )

    def d7(self) -> str:
        return self.command_fault(
            "load_release",
            "operations.deploy.load",
            StartupRefusal("startup_artefact_mismatch"),
        )

    def d8(self) -> str:
        # Execute the installed-entry boundary without invoking a server or runtime.
        path = ROOT / "scripts/operations/serve.py"
        block = ast.parse(path.read_text()).body[-1]
        output = io.StringIO()
        with (
            contextlib.redirect_stderr(output),
            self.assertRaises(SystemExit) as caught,
        ):
            exec(
                compile(ast.Module(body=[block], type_ignores=[]), str(path), "exec"),
                {
                    "__name__": "__main__",
                    "main": Mock(
                        side_effect=StartupRefusal("startup_inventory_mismatch")
                    ),
                    "sys": sys,
                    "json": json,
                },
            )
        self.assertEqual(caught.exception.code, 4)
        body = json.loads(output.getvalue())
        return str(body.get("error_code", body["status"]))

    def d9(self) -> str:
        from eii_product.config import ConfigError

        return self.command_fault(
            "up_cmd",
            "operations.development.serve_embedded",
            ConfigError("routing_tiles"),
            embedded=True,
        )

    def d10(self) -> str:
        return self.command_fault(
            "up_cmd", "operations.deploy.up", ReleaseRefusal("digest_mismatch")
        )

    def preflight_fault(self, fault: str) -> str:
        from preflight_stubs import fake_tools

        import preflight
        import preflight_rows as rows
        import preflight_store as store

        good = store.Line("PASS", "INVENTED", "ok")
        with contextlib.ExitStack() as stack:
            for name, value in {
                "locked_dependencies_row": good,
                "env_tracked_row": good,
                "wsl_row": good,
                "api_port_row": store.Line("FAIL", "api-port", "busy"),
                "release_rows": {
                    key: store.Line("PASS", key, "ok")
                    for key in (*rows.RELEASE_ROWS, rows.REPLAY_ROW)
                },
            }.items():
                stack.enter_context(patch.object(rows, name, return_value=value))
            stack.enter_context(
                patch(
                    "preflight_database.check_postgres",
                    return_value=store.Selection(good, "postgres"),
                )
            )
            env = SimpleNamespace(release=self.root, name="staging", state=self.root)
            stack.enter_context(
                patch("operations.config.read_environment", return_value=env)
            )
            stack.enter_context(patch("operations.runtime.verify_peers"))
            stack.enter_context(
                patch(
                    "operations.deploy.request_for", return_value={"backend_port": 8123}
                )
            )
            stack.enter_context(
                patch("operations.runtime.installed", return_value=(self.root, {}))
            )
            stack.enter_context(patch("eii_product.store.release_check.check_release"))
            stack.enter_context(
                patch(
                    "eii_product.api.health.local_assets",
                    return_value=("missing", "ok", "ok")
                    if fault == "assets"
                    else ("ok", "ok", "ok"),
                )
            )
            stack.enter_context(
                patch(
                    "operations.runtime.check_stores",
                    side_effect=KeyError("INVENTED-private")
                    if fault == "startup"
                    else None,
                )
            )
            stack.enter_context(
                patch(
                    "operations.common.read_json",
                    return_value={"release_id": "INVENTED"},
                )
            )
            stack.enter_context(
                patch(
                    "operations.process.require_owned",
                    side_effect=Refusal("process_identity_mismatch"),
                )
            )
            report = preflight.run_preflight(
                self.root, {"EII_ENVIRONMENT": "staging"}, tools=fake_tools()
            )
        check = {
            "startup": "release",
            "process": "api-port",
            "assets": "tiles-glyphs-fonts",
        }[fault]
        return next(line.reason for line in report.lines if line.check == check)

    def d11(self) -> str:
        return self.preflight_fault("startup")

    def d12(self) -> str:
        return self.preflight_fault("process")

    def d13(self) -> str:
        return self.preflight_fault("assets")

    def d14(self) -> str:
        from eii_product.api.health import _Probe

        store = Mock()
        store.ping.return_value.ok = True
        with self.assertLogs("eii_product.api.health", level="WARNING") as logs:
            self.assertEqual(
                _Probe().read(
                    store,
                    Mock(side_effect=StartupRefusal("startup_inventory_mismatch")),
                ),
                (True, False),
            )
        return str(logs.records[0].error_code)  # type: ignore[attr-defined]

    def d15(self) -> str:
        from operations.package import prepare_archive

        with (
            patch("operations.package.source_files", return_value={"uv.lock": b""}),
            patch("operations.package.dependency_files", return_value={}),
            patch(
                "operations.package.subprocess.run",
                side_effect=subprocess.TimeoutExpired("INVENTED-private", 120),
            ),
        ):
            with self.assertRaises(Refusal) as caught:
                prepare_archive(self.root, "ab" * 20, self.root / "output", {})
        return caught.exception.reason

    def d16(self) -> str:
        return self.command_fault(
            "question_lab",
            "evals.question_lab.runner.run_lab",
            ValueError("question_capacity"),
        )

    def d17(self) -> str:
        from eii_custodian.publicdata.registers.__main__ import main

        output = io.StringIO()
        args = [
            part
            for key in (
                "frame-cells",
                "frame-sha256",
                "biz-index-sha256",
                "fc-index-sha256",
                "output",
                "release-kind",
            )
            for part in (
                "--" + key,
                "public_only" if key == "release-kind" else "INVENTED",
            )
        ]
        with (
            patch(
                "eii_custodian.publicdata.registers.__main__.read_file",
                side_effect=TypeError("INVENTED-private"),
            ),
            contextlib.redirect_stderr(output),
        ):
            self.assertEqual(main(args), 1)
        return output.getvalue().strip()

    def d48(self) -> str:
        ref = inputs(self.root)["sources"]["INVENTED-source"]
        ref["format"] = "INVENTED-invalid"
        with self.assertRaises(ValueError) as caught:
            producer._source(self.root, "INVENTED-source", ref, {})
        return str(caught.exception)

    def d49(self) -> str:
        import live_public_playbook

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(
                live_public_playbook.main(
                    [],
                    {},
                    runner=Mock(side_effect=ValueError("resolve_query_coverage")),
                ),
                1,
            )
        return output.getvalue().strip().split(": ", 1)[1]

    def d50(self) -> str:
        import live_public_release_load

        output = io.StringIO()
        with (
            patch.object(
                live_public_release_load,
                "_run",
                side_effect=ReleaseRefusal("digest_mismatch"),
            ),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(live_public_release_load.main([], {}), 1)
        return output.getvalue().strip().split(": ", 1)[1]

    def d51(self) -> str:
        return self.lab_fault(execution=False)

    def test_lab_execution_failure_keeps_inner_reason(self) -> None:
        self.assertEqual(
            self.lab_fault(execution=True), "execution:startup_inventory_mismatch"
        )

    def lab_fault(self, *, execution: bool) -> str:
        from evals.question_lab import runner
        from evals.question_lab.cases import load_cases

        case = load_cases(ROOT)[0]
        lab = self.root / "evals/question_lab"
        lab.mkdir(parents=True)
        (lab / "ledger.jsonl").write_bytes(b"")
        with contextlib.ExitStack() as stack:
            for name, value in {
                "load_cases": (case,),
                "select_cases": (case,),
                "git_text": "",
                "locked_budget": (b"{}", []),
                "ledger_problems": [],
                "packet_problems": [],
                "plant_results": [],
                "capture_answers": ([], []),
            }.items():
                stack.enter_context(patch.object(runner, name, return_value=value))
            if execution:
                fixture = SimpleNamespace(
                    build_fixture_app=Mock(return_value=(object(), Mock(), Mock())),
                    Client=Mock(),
                )
                stack.enter_context(
                    patch.object(runner, "import_module", return_value=fixture)
                )
                stack.enter_context(
                    patch.object(
                        runner,
                        "execute_case",
                        side_effect=StartupRefusal("startup_inventory_mismatch"),
                    )
                )
            else:
                stack.enter_context(
                    patch.object(
                        runner,
                        "import_module",
                        side_effect=StartupRefusal("startup_inventory_mismatch"),
                    )
                )
            stack.enter_context(patch.object(Path, "read_bytes", return_value=b"{}"))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(runner.run_lab(self.root, {}, 100, 17), 1)
        if execution:
            rows = next((lab / "runs").glob("*/results.jsonl")).read_text().splitlines()
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(
                    json.loads(row)["problems"],
                    ["execution:startup_inventory_mismatch"],
                )
            return "execution:startup_inventory_mismatch"
        result = json.loads(
            next((lab / "runs").glob("*/qualification.json")).read_text()
        )
        return str(
            next(item for item in result["problems"] if item.startswith("fixture:"))
        )

    def d52(self) -> str:
        import export_web_catalogue
        from eii_product.assistant.catalogue.schema import Refusal as CatalogueRefusal

        output = io.StringIO()
        with (
            patch.object(
                export_web_catalogue,
                "load_catalogue",
                return_value=CatalogueRefusal("UNKNOWN_CLAIM", "INVENTED/private"),
            ),
            contextlib.redirect_stderr(output),
        ):
            self.assertEqual(
                export_web_catalogue.run(self.root, self.root / "target", False), 1
            )
        return output.getvalue().strip()

    def d54(self) -> str:
        return self.retained_fault(Refusal("application_checksum_mismatch"))

    def retained_fault(self, error: Exception) -> str:
        from operations import deploy
        from operations.config import Environment

        env = Environment(
            "live",
            self.root / "releases/INVENTED-release",
            self.root / "state",
            8088,
            None,
        )
        with (
            patch("operations.runtime.verify_application", side_effect=error),
            self.assertRaises(Refusal) as caught,
        ):
            deploy.require_retained(
                env,
                {
                    "release_id": "INVENTED-release",
                    "application_sha256": "ab" * 32,
                    "code_version": "cd" * 20,
                },
            )
        self.assertEqual(caught.exception.code, 4)
        return caught.exception.reason

    def test_retention_unknown_text_uses_fixed_fallback(self) -> None:
        self.assertEqual(
            self.retained_fault(ValueError("INVENTED/private SELECT secret")),
            "rollback_retention_failed",
        )

    def d55(self, fault: str) -> str:
        from evals.question_lab.cases import load_cases, select_cases

        from commands import question_lab

        raw = json.loads((ROOT / "evals/question_lab/cases.v1.json").read_text())
        base = load_cases(ROOT)[0]
        cases = tuple(
            replace(base, identity=f"INVENTED-question-{index}", family=family)
            for index, family in enumerate(
                ["flagship"] * 97 + ["map", "chip", "refusal"]
            )
        )
        # A valid selection first; each negative changes one input only.
        self.assertEqual(len(select_cases(cases, 100, 17)), 100)
        raw["cases"] = [dict(case.__dict__) for case in cases]
        n = 100
        if fault == "question_manifest":
            raw["version"] = "INVENTED-invalid"
        elif fault == "question_identity":
            raw["cases"][-1]["identity"] = raw["cases"][0]["identity"]
        elif fault == "question_capacity":
            n = 101
        elif fault == "question_families":
            raw["cases"][-1]["family"] = "flagship"
        path = self.root / "evals/question_lab/cases.v1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw))
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            self.assertEqual(
                question_lab.run(self.root, {}, ["run", "--n", str(n), "--seed", "17"]),
                2,
            )
        self.assertEqual(output.getvalue(), "FAIL question-lab: " + fault + "\n")
        return fault

    def test_lab_unknown_input_error_withholds_text(self) -> None:
        from evals.question_lab import runner

        for error, expected in (
            (ValueError("INVENTED/private SELECT secret"), "operation_failed"),
            (OSError("INVENTED/private"), "operation_os_error"),
            (TypeError("INVENTED/private"), "input_type_invalid"),
            (KeyError("INVENTED/private"), "input_key_missing"),
        ):
            with (
                self.subTest(error=type(error)),
                patch.object(runner, "load_cases", side_effect=error),
                contextlib.redirect_stderr(io.StringIO()) as output,
            ):
                self.assertEqual(runner.run_lab(self.root, {}, 100, 17), 2)
            self.assertEqual(output.getvalue(), "FAIL question-lab: " + expected + "\n")

    def test_live_parser_and_store_handlers_withhold_exception_text(self) -> None:
        import live_public_release_load as live

        from eii_product.store.protocol import StoreRefusal

        class HostileStoreRefusal(StoreRefusal):
            def __str__(self) -> str:
                return "INVENTED/private SELECT secret"

        for error, expected in (
            (live._ParserRefusal("input_key_missing"), "input_key_missing"),
            (live._ParserRefusal("INVENTED/private SELECT secret"), "operation_failed"),
            (StoreRefusal("STORE_UNAVAILABLE"), "STORE_UNAVAILABLE"),
            (HostileStoreRefusal("STORE_UNAVAILABLE"), "STORE_UNAVAILABLE"),
        ):
            with (
                self.subTest(error=type(error)),
                patch.object(live, "_run", side_effect=error),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(live.main([], {}), 1)
            self.assertEqual(
                output.getvalue(), "FAIL public-release-load: " + expected + "\n"
            )


if __name__ == "__main__":
    unittest.main()
