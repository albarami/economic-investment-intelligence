"""Controls-off proofs in compiled copies: no production source or switch changes.

Only the selected refusal is disabled. A nested unittest assertion must really
turn red because that component admitted the plant, never because setup failed
or another refusal masked it. The production validator remains unchanged.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import re
import textwrap
import unittest
from collections.abc import Callable
from dataclasses import replace
from typing import Any
from unittest.mock import Mock, patch

from s3_t28_support import IDENTITY, WorkspaceCase, fixture_reads, snapshots

from eii_product.store import startup
from operations import activation, config, evidence, install, process
from operations.common import Refusal, encoded, sha
from operations.policy import require_sources


def without_refusal(function: Any, reason: str, *, line: int | None = None) -> Any:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))

    class DisableOne(ast.NodeTransformer):
        changed = 0

        def visit_Raise(self, node: ast.Raise) -> Any:
            call = node.exc
            if (
                not isinstance(call, ast.Call)
                or not isinstance(call.func, ast.Name)
                or not call.func.id.endswith(("Refusal", "Error", "Failure"))
                or not call.args
                or self.changed
                or (line is not None and node.lineno != line)
            ):
                return node
            if isinstance(call.args[0], ast.Constant) and call.args[0].value != reason:
                return node
            self.changed += 1
            return ast.copy_location(
                ast.If(
                    test=ast.Compare(
                        left=copy.deepcopy(call.args[0]),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(reason)],
                    ),
                    body=[ast.Pass()],
                    orelse=[node],
                ),
                node,
            )

    namespace = dict(function.__globals__)
    namespace.update(inspect.getclosurevars(function).nonlocals)
    disable = DisableOne()
    modified = ast.fix_missing_locations(disable.visit(tree))
    if disable.changed != 1:
        raise AssertionError("controls-off must select exactly one refusal site")
    exec(
        compile(
            modified,
            "<invented-controls-off>",
            "exec",
        ),
        namespace,
    )
    return namespace[function.__name__]


def without_call(function: Any, target: str, *, occurrence: int | None = None) -> Any:
    """Delete one required invocation in a compiled copy, leaving other checks."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))

    class DisableOneCall(ast.NodeTransformer):
        changed = 0
        seen = 0

        def visit_Expr(self, node: ast.Expr) -> Any:
            if (
                isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func) == target
            ):
                index = self.seen
                self.seen += 1
                if occurrence is not None and index != occurrence:
                    return node
                self.changed += 1
                return ast.copy_location(ast.Pass(), node)
            return node

    disabled = DisableOneCall()
    modified = ast.fix_missing_locations(disabled.visit(tree))
    if disabled.changed != 1:
        raise AssertionError("one required invocation must be selected")
    namespace = dict(function.__globals__)
    namespace.update(inspect.getclosurevars(function).nonlocals)
    exec(compile(modified, "<invented-call-off>", "exec"), namespace)
    return namespace[function.__name__]


def without_return(function: Any, expression: str) -> Any:
    """Disable one refusing return, leaving every other branch intact."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))

    class DisableOneReturn(ast.NodeTransformer):
        changed = 0

        def visit_Return(self, node: ast.Return) -> Any:
            if node.value is not None and ast.unparse(node.value) == expression:
                self.changed += 1
                return ast.copy_location(ast.Pass(), node)
            return node

    disabled = DisableOneReturn()
    modified = ast.fix_missing_locations(disabled.visit(tree))
    if disabled.changed != 1:
        raise AssertionError("one refusing return must be selected")
    namespace = dict(function.__globals__)
    namespace.update(inspect.getclosurevars(function).nonlocals)
    exec(compile(modified, "<invented-return-off>", "exec"), namespace)
    return namespace[function.__name__]


class Controls(WorkspaceCase):
    def test_disabling_one_site_keeps_another_same_reason_refusal(self) -> None:
        def two_sites() -> None:
            if True:
                raise Refusal("INVENTED-same-reason")
            if True:
                raise Refusal("INVENTED-same-reason")

        mutant = without_refusal(two_sites, "INVENTED-same-reason")
        with self.assertRaisesRegex(Refusal, "INVENTED-same-reason"):
            mutant()

    def test_actual_full_data_parity_on_each_store_turns_red_without_guard(
        self,
    ) -> None:
        checked, receipt, left, right = snapshots(self.root)
        for side in ("embedded", "postgres"):
            for change in ("row", "count"):
                rows: dict[str, Any] = copy.deepcopy(dict(left.rows))
                if change == "row":
                    rows["source_registry"][0]["source_id"] = "INVENTED-tampered"
                else:
                    rows["source_registry"] = []
                bad = replace(left, rows=rows)
                with (
                    self.subTest(side=side, change=change),
                    fixture_reads(checked, receipt, left),
                ):
                    self.sensitive(
                        startup.verify_snapshots,
                        (
                            checked,
                            receipt,
                            bad if side == "embedded" else left,
                            bad if side == "postgres" else right,
                        ),
                        "startup_parity_failed",
                        kind=startup.StartupRefusal,
                    )

    def test_each_readiness_identity_guard_turns_red_when_removed(self) -> None:
        record = dict(port=18088, release_id=IDENTITY)
        for value in (
            dict(status="degraded", release_id=IDENTITY, release_hash=IDENTITY),
            dict(status="ok", release_id="cd" * 32, release_hash="cd" * 32),
            dict(status="ok", release_id=IDENTITY, release_hash="cd" * 32),
        ):
            with self.subTest(value=value), patch("operations.process.require_owned"):
                self.sensitive(
                    process.wait_ready,
                    (record, "live", Mock(return_value=value)),
                    "startup_not_ready",
                )

    def test_each_logged_result_guard_turns_red_after_valid_chain_rebinding(
        self,
    ) -> None:
        from test_s3_t28_promotion import request

        state = self.root / "state"
        state.mkdir()
        for item in sorted(evidence.ITEMS):
            for mode in ("missing", "failed"):
                results = {
                    name: dict(result="passed", report={}) for name in evidence.ITEMS
                }
                if mode == "missing":
                    del results[item]
                else:
                    results[item]["result"] = "failed"
                body = dict(
                    sequence=1, previous=None, request=request(), results=results
                )
                entry = dict(body, sha256=hashlib.sha256(encoded(body)).hexdigest())
                (state / "promotions.jsonl").write_bytes(encoded(entry) + b"\n")
                with self.subTest(item=item, mode=mode):
                    self.sensitive(
                        activation.entries, (state,), "promotion_log_mismatch"
                    )

    def test_fsync_guard_admits_failed_durability_only_when_disabled(self) -> None:
        from test_s3_t28_promotion import request

        state = self.root / "state"
        state.mkdir()
        scope = config.Environment(
            "live",
            self.root / "releases" / IDENTITY,
            state,
            8088,
            ("127.0.0.1", 5432, "INVENTED_live"),
        )
        with patch(
            "operations.activation.os.fsync",
            side_effect=OSError("INVENTED-fsync-failure"),
        ):
            self.sensitive(
                activation.append_authorisation,
                (state, request(), {}, [], scope),
                "promotion_log_unwritable",
            )

    def sensitive(
        self: unittest.TestCase,
        function: Any,
        args: tuple[Any, ...],
        reason: str,
        *,
        kwargs: dict[str, Any] | None = None,
        kind: type[Exception] = Refusal,
        reset_fixture: Callable[[], object] | None = None,
    ) -> None:
        supplied = {} if kwargs is None else kwargs
        selected = None
        if reset_fixture is not None:
            reset_fixture()
        try:
            function(*args, **supplied)
        except kind as error:
            self.assertTrue(str(error) == reason or str(error).startswith(reason + ":"))
            trace = error.__traceback__
            while trace is not None:
                if trace.tb_frame.f_code is function.__code__:
                    selected = trace.tb_lineno - inspect.getsourcelines(function)[1] + 1
                trace = trace.tb_next
        else:
            self.fail("the production control admitted the plant")
        self.assertIsNotNone(selected, "the named component must decide the refusal")
        mutant = without_refusal(function, reason, line=selected)

        def assertion() -> None:
            if reset_fixture is not None:
                reset_fixture()
            with unittest.TestCase().assertRaisesRegex(kind, re.escape(reason)):
                mutant(*args, **supplied)

        result = unittest.TestResult()
        unittest.FunctionTestCase(assertion).run(result)
        self.assertEqual(
            result.errors, [], "a setup/other exception is not red evidence"
        )
        self.assertEqual(len(result.failures), 1)
        self.assertIn(
            "not raised", result.failures[0][1], "another refusal is not admission"
        )

    def test_each_key_and_runtime_mode(self) -> None:
        config.runtime_environment({})
        for key in sorted(
            config.RESTRICTED
            | {
                "EII_REGISTER_FILE",
                "EII_UNKNOWN",
                "EII_SOURCE_RELEASE_DIR",
                "EII_STORE",
                "EII_BESTTIME_RUN_CREDIT_LIMIT",
                "PGHOSTADDR",
                "PGSERVICE",
                "PGPASSFILE",
                "PGSSLROOTCERT",
            }
        ):
            with self.subTest(key=key):
                self.sensitive(
                    config.runtime_environment,
                    ({key: "INVENTED-marker"},),
                    "unwanted_runtime_setting",
                )
        for key, value, reason in (
            ("EII_TRAFFIC_PROVIDER", "tomtom", "traffic_mode_refused"),
            ("EII_PRESENTER", "1", "presenter_mode_refused"),
            ("EII_DECISION_PROVIDER", "jev", "decision_mode_refused"),
        ):
            with self.subTest(key=key):
                self.sensitive(config.runtime_environment, ({key: value},), reason)

    def test_independent_isolation_components(self) -> None:
        live = config.Environment(
            "live",
            self.root / "live/releases" / IDENTITY,
            self.root / "live/state",
            8088,
            ("127.0.0.1", 5432, "INVENTED_live"),
        )
        stage = config.Environment(
            "staging",
            self.root / "staging/releases" / IDENTITY,
            self.root / "staging/state",
            8089,
            ("127.0.0.1", 5432, "INVENTED_staging"),
        )
        config.isolated((live, stage))
        with self.assertRaisesRegex(Refusal, "environment_database_conflict"):
            replace(stage, database=live.database)
        # Isolate the pair guard from the earlier constructor namespace guard.
        with patch("operations.config.require_database_environment"):
            database_collision = replace(stage, database=live.database)
        for changed, reason in (
            (replace(stage, release=live.release), "environment_path_conflict"),
            (database_collision, "environment_database_conflict"),
            (replace(stage, port=live.port), "environment_port_conflict"),
        ):
            with self.subTest(reason=reason):
                self.sensitive(config.isolated, ((live, changed),), reason)
        self.sensitive(
            config.write_target,
            (stage, live.state / "ledger"),
            "cross_environment_write",
        )
        self.sensitive(config.api_port, ("0",), "api_port_invalid")
        env = dict(
            EII_ENVIRONMENT="live",
            EII_RELEASE_DIR=str(live.release),
            EII_STATE_DIR=str(live.state),
            EII_DATABASE_URL="postgres://eii_app"
            + "@"
            + "127.0.0.1:5432/INVENTED_live",
            EII_LISTEN_HOST="0.0.0.0",
        )
        self.sensitive(config.read_environment, (env,), "host_not_loopback")

    def test_public_kind_components(self) -> None:
        path = self.root / "manifest.json"
        public = dict(release_kind="public_only", release_id=IDENTITY)
        path.write_bytes(encoded(public))
        install.public_kind(self.root)
        for choice in ("A", "B"):
            with self.subTest(choice=choice):
                self.sensitive(
                    install.public_kind,
                    (self.root,),
                    "public_only_parameter_selection",
                    kwargs=dict(parameter_set=choice),
                )
        path.write_bytes(encoded(dict(public, release_kind="protected")))
        self.sensitive(
            install.public_kind, (self.root,), "protected_release_requires_s11_t09"
        )
        path.write_bytes(encoded(public))
        descriptor = self.root / "freeze.json"
        descriptor.write_text("{}")
        self.sensitive(
            install.public_kind, (self.root,), "public_only_freeze_forbidden"
        )
        descriptor.unlink()
        register = self.root / "register.jsonl"
        register.write_bytes(encoded(dict(release_id=IDENTITY)) + b"\n")
        self.sensitive(
            install.public_kind, (self.root, register), "public_only_register_forbidden"
        )

    def test_roles_and_physical_inventory_components(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        with fixture_reads(checked, receipt, left):
            startup.verify_snapshots(checked, receipt, left, right)
            for role in (
                ("eii_owner", False, False),
                ("INVENTED-other", False, False),
                ("eii_app", True, False),
                ("eii_app", False, True),
            ):
                with self.subTest(role=role):
                    self.sensitive(
                        startup.verify_snapshots,
                        (checked, receipt, left, replace(right, role=role)),
                        "startup_role_refused",
                        kind=startup.StartupRefusal,
                    )
            self.sensitive(
                startup.verify_snapshots,
                (
                    checked,
                    receipt,
                    replace(left, names=left.names | {"INVENTED_extra"}),
                    right,
                ),
                "startup_inventory_mismatch",
                kind=startup.StartupRefusal,
            )
            self.sensitive(
                startup.verify_snapshots,
                (checked, receipt, left, replace(right, interrupted=True)),
                "interrupted_load_refused",
                kind=startup.StartupRefusal,
            )

    def test_public_exposure_and_operation_schema_components(self) -> None:
        from test_s3_t28_promotion import request

        raw = request()
        evidence.operation(raw)
        self.sensitive(
            evidence.operation, (dict(raw, extra=True),), "operation_schema_invalid"
        )
        self.sensitive(
            evidence.operation,
            (dict(raw, operation="INVENTED-operation"),),
            "operation_schema_invalid",
        )
        self.sensitive(
            evidence.operation,
            (dict(raw, actor="operator"),),
            "activation_lead_required",
        )
        gate = {
            key: raw[key]
            for key in ("code_version", "release_id", "application_sha256")
        }
        gate.update(gate="S3", verdict="REJECTED")
        path = self.root / "gate.json"
        path.write_bytes(encoded(gate))
        raw.update(
            operation="expose_public",
            exposure="public_entry",
            gate_approval=dict(file=path.name, sha256=sha(path)),
        )
        self.sensitive(
            evidence.exposure,
            (self.root, raw, lambda: None),
            "public_gate_approval_required",
        )
        gate["verdict"] = "APPROVED"
        path.write_bytes(encoded(gate))
        raw["gate_approval"]["sha256"] = sha(path)
        raw["actor"] = "operator"
        self.sensitive(
            evidence.exposure,
            (self.root, raw, lambda: None),
            "public_handover_lead_required",
        )

    def test_each_failed_checklist_component(self) -> None:
        import test_s3_t28_promotion as fixtures

        fixture = fixtures.Promotion()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        evidence.verify_evidence(
            fixture.root,
            fixture.raw,
            features=["INVENTED-finished"],
            staging_probe=lambda _: None,
        )
        for item in sorted(evidence.ITEMS):
            original = copy.deepcopy(fixture.reports[item])
            fixture.reports[item] = {
                key: fixture.raw[key]
                for key in ("code_version", "release_id", "application_sha256")
            }
            fixture.bind()
            reason = (
                "gate_evidence_required"
                if item == "gates"
                else "promotion_evidence_" + item
            )
            with self.subTest(item=item):
                self.sensitive(
                    evidence.verify_evidence,
                    (fixture.root, fixture.raw),
                    reason,
                    kwargs=dict(
                        features=["INVENTED-finished"], staging_probe=lambda _: None
                    ),
                )
            fixture.reports[item] = original
            fixture.bind()

    def test_forbidden_process_executables(self) -> None:
        for executable in ("docker", "compose", "pg_ctl", "postgres", "systemctl"):
            with self.subTest(executable=executable):
                self.sensitive(
                    process.require_command,
                    ((executable, "up"),),
                    "operation_command_refused",
                )

    def test_static_policy_itself_turns_red_without_its_refusal(self) -> None:
        self.sensitive(
            require_sources,
            ({"deploy.py": "import subprocess\n"},),
            "operation_command_refused",
        )
        self.sensitive(
            require_sources,
            ({"process.py": "import subprocess\nsubprocess.run(['docker', 'up'])\n"},),
            "operation_command_refused",
        )

    def test_each_maker_shape_and_spelling_has_independent_controls_off_proof(
        self,
    ) -> None:
        import test_s3_t28_promotion as fixtures

        fixture = fixtures.Promotion()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = copy.deepcopy(fixture.reports["review"])
        for key, value in (
            ("builder", []),
            ("builder", True),
            ("builder", ""),
            ("builder", " "),
            ("reviewer", []),
            ("reviewer", True),
            ("reviewer", ""),
            ("reviewer", " "),
            ("reviewer", " openai "),
        ):
            fixture.reports["review"] = copy.deepcopy(original)
            fixture.bind()
            evidence.verify_evidence(
                fixture.root,
                fixture.raw,
                features=["INVENTED-finished"],
                staging_probe=lambda _: None,
            )
            fixture.reports["review"][key] = value
            fixture.bind()
            with self.subTest(key=key, value=value):
                self.sensitive(
                    evidence.verify_evidence,
                    (fixture.root, fixture.raw),
                    "promotion_evidence_review",
                    kwargs=dict(
                        features=["INVENTED-finished"], staging_probe=lambda _: None
                    ),
                )

    def test_late_lock_alias_is_admitted_only_when_its_guard_is_disabled(self) -> None:
        live = self.root / "live/state"
        live.mkdir(parents=True)
        stage = self.root / "staging/state"
        stage.parent.mkdir()
        stage.symlink_to(live, target_is_directory=True)
        with self.assertRaisesRegex(Refusal, "cross_environment_write"):
            with activation.operation_lock(stage):
                pass
        self.assertFalse((live / "operation.lock").exists())
        mutant = without_refusal(
            inspect.unwrap(activation.operation_lock), "cross_environment_write"
        )

        def assertion() -> None:
            with unittest.TestCase().assertRaisesRegex(
                Refusal, "cross_environment_write"
            ):
                with mutant(stage):
                    pass

        result = unittest.TestResult()
        unittest.FunctionTestCase(assertion).run(result)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertIn("not raised", result.failures[0][1])
        self.assertTrue((live / "operation.lock").is_file())
