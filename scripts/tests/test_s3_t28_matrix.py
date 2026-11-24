"""Individual controls-off cases for the supplied S3-T28 verification matrix.

All state is invented. A compiled copy changes exactly the deciding refusal,
and a nested assertion must fail by admission, never another refusal or error.
Shared component checks complement (rather than replace) dispatcher/native IO
tests. The return report distinguishes redundant defences and unproved rows.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import itertools
import shutil
import sys
import unittest
from dataclasses import replace
from typing import Any
from unittest.mock import Mock, patch

import test_s3_t28_controls as controls_fixture
import test_s3_t28_promotion as promotion_fixture
from s3_t28_support import (
    APPLICATION,
    COMMIT,
    IDENTITY,
    ROOT,
    WorkspaceCase,
    fixture_reads,
    snapshots,
)
from test_s3_t28_install import archive_fixture
from test_s3_t28_promotion import request

from eii_core import source_chain
from eii_core.manifest import CATALOGUE, FORBIDDEN_PUBLIC_ONLY
from eii_product.api.startup import ServingPolicy
from eii_product.store import release_shape, startup
from eii_product.store.release_check import ReleaseRefusal, manifest_rows
from operations import activation, config, evidence, install, process
from operations.common import Refusal, encoded, sha


class Matrix(WorkspaceCase):
    sensitive = controls_fixture.Controls.sensitive

    def promotion(self) -> promotion_fixture.Promotion:
        fixture = promotion_fixture.Promotion()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def env(self, name: str) -> config.Environment:
        home = self.root / name
        return config.Environment(
            name,
            home / "releases" / IDENTITY,
            home / "state",
            config.DEFAULT_PORTS[name],
            ("127.0.0.1", 5432, "INVENTED_" + name),
        )

    def test_ac1_each_closed_operation_property(self) -> None:
        valid = request()
        self.assertEqual(evidence.operation(valid), valid)
        for key, value in (
            ("extra", True),
            ("operation", "INVENTED-unknown"),
            ("exposure", "INVENTED-exposure"),
            ("release_id", "short"),
            ("code_version", "short"),
            ("application_sha256", "short"),
            ("entry_port", True),
            ("backend_port", 0),
        ):
            with self.subTest(key=key):
                self.sensitive(
                    evidence.operation,
                    (dict(valid, **{key: value}),),
                    "operation_schema_invalid",
                )
        for key in ("code_version", "release_id", "application_sha256"):
            changed = dict(valid)
            del changed[key]
            with self.subTest(missing=key):
                self.sensitive(
                    evidence.operation, (changed,), "operation_schema_invalid"
                )

    def test_ac1_each_gate_binding_and_verdict(self) -> None:
        raw = dict(request(), operation="expose_public", exposure="public_entry")
        gate = {
            key: raw[key]
            for key in ("code_version", "release_id", "application_sha256")
        }
        gate.update(gate="S3", verdict="APPROVED")
        path = self.root / "gate.json"
        for key, value in (
            ("verdict", "REJECTED"),
            ("code_version", "ba" * 20),
            ("release_id", "bc" * 32),
            ("application_sha256", "bc" * 32),
            ("gate", "S2"),
        ):
            path.write_bytes(encoded(dict(gate, **{key: value})))
            raw["gate_approval"] = dict(file=path.name, sha256=sha(path))
            with self.subTest(key=key):
                self.sensitive(
                    evidence.exposure,
                    (self.root, raw, lambda: None),
                    "public_gate_approval_required",
                )
        path.write_bytes(encoded(gate))
        raw["gate_approval"] = dict(file=path.name, sha256=sha(path))
        self.sensitive(
            evidence.exposure, (self.root, raw), "public_entry_requires_s3_t20"
        )

    def test_ac6_report_digest_binds_the_same_bytes_that_are_parsed(self) -> None:
        path = self.root / "INVENTED-evidence.json"
        original = dict(release_id=IDENTITY, result="INVENTED-original")
        path.write_bytes(encoded(original))
        reference = dict(file=path.name, sha256=sha(path))
        self.assertEqual(
            evidence.referenced(self.root, reference, "promotion_evidence_review"),
            original,
        )
        # The old implementation hashed an open file, then opened it again for
        # JSON parsing. A swap between those reads must not pass its old hash.
        with patch(
            "pathlib.Path.read_bytes",
            return_value=encoded(dict(original, result="INVENTED-swapped")),
        ):
            with self.assertRaisesRegex(Refusal, "promotion_evidence_review"):
                evidence.referenced(self.root, reference, "promotion_evidence_review")

    def test_ac1_missing_gate_and_ac6_missing_report_share_proved_input_controls(
        self,
    ) -> None:
        path = self.root / "INVENTED-evidence.json"
        path.write_bytes(encoded(dict(result="INVENTED-valid")))
        valid = dict(file=path.name, sha256=sha(path))
        evidence.require_reference_shape(valid, "public_gate_approval_required")
        evidence.referenced(self.root, valid, "promotion_evidence_review")
        for reason in (
            "public_gate_approval_required",
            *(
                "gate_evidence_required"
                if item == "gates"
                else "promotion_evidence_" + item
                for item in sorted(evidence.ITEMS)
            ),
        ):
            with self.subTest(reason=reason, control="missing-reference"):
                self.sensitive(evidence.require_reference_shape, (None, reason), reason)
            absent = self.root / "INVENTED-absent-report.json"
            with self.subTest(reason=reason, control="missing-file"):
                self.sensitive(evidence.read_evidence_bytes, (absent, reason), reason)
            with self.subTest(reason=reason, control="digest"):
                self.sensitive(
                    evidence.referenced,
                    (self.root, dict(valid, sha256="bc" * 32), reason),
                    reason,
                )

    def test_ac2_each_pairwise_port_allocation_and_path_boundary(self) -> None:
        environments = tuple(self.env(name) for name in config.DEFAULT_PORTS)
        config.isolated(environments)
        for index, environment in enumerate(environments):
            for port in config.LIVE_BACKENDS:
                with self.subTest(environment=environment.name, backend=port):
                    changed = list(environments)
                    changed[index] = replace(environment, port=port)
                    self.sensitive(
                        config.isolated, (changed,), "environment_port_conflict"
                    )
            for other in environments[index + 1 :]:
                with self.subTest(left=environment.name, right=other.name):
                    self.sensitive(
                        config.isolated,
                        ((environment, replace(other, port=environment.port)),),
                        "environment_port_conflict",
                    )
        live, stage = self.env("live"), self.env("staging")
        for target in (
            live.release,
            live.applications,
            live.state / "ledger",
            live.state / "journal",
            live.state / "route.json",
        ):
            with self.subTest(target=target.name):
                self.sensitive(
                    config.write_target, (stage, target), "cross_environment_write"
                )
        self.assertFalse(live.home.exists())

    def test_ac2_release_leaf_and_ancestor_aliases(self) -> None:
        live, stage = self.env("live"), self.env("staging")
        live.release.mkdir(parents=True)
        stage.release.parent.mkdir(parents=True)
        stage.release.symlink_to(live.release, target_is_directory=True)
        self.sensitive(config.isolated, ((live, stage),), "environment_path_conflict")
        stage.release.unlink()
        # Alias to a different, unconfigured root isolates the symlink guard
        # from the independently tested resolved-root collision guard.
        stage.release.parent.rmdir()
        standin = self.root / "INVENTED-other-releases"
        standin.mkdir()
        stage.release.parent.symlink_to(standin, target_is_directory=True)
        self.sensitive(config.isolated, ((stage,),), "environment_path_conflict")

    def test_ac2_database_alias_and_each_numeric_port_range(self) -> None:
        live, stage = self.env("live"), self.env("staging")
        alias = config.database_identity(
            "postgresql://eii_app" + "@" + "LOCALHOST/INVENTED_live"
        )
        self.assertEqual(alias, live.database)
        with self.assertRaisesRegex(Refusal, "environment_database_conflict"):
            replace(stage, database=alias)
        # Preserve the independent duplicate-identity controls-off proof.
        with patch("operations.config.require_database_environment"):
            database_collision = replace(stage, database=alias)
        self.sensitive(
            config.isolated,
            ((live, database_collision),),
            "environment_database_conflict",
        )
        for value in ("-1", "0", "65536"):
            with self.subTest(value=value):
                self.sensitive(config.api_port, (value,), "api_port_invalid")

    def test_ac3_each_store_inventory_identity_and_interruption(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        with fixture_reads(checked, receipt, left):
            startup.verify_snapshots(checked, receipt, left, right)
            for side in ("embedded", "postgres"):
                for mode, reason in (
                    ("inventory", "startup_inventory_mismatch"),
                    ("identity", "startup_identity_mismatch"),
                    ("interruption", "interrupted_load_refused"),
                ):
                    bad = left if side == "embedded" else right
                    if mode == "inventory":
                        bad = replace(bad, names=bad.names | {"INVENTED-extra"})
                    elif mode == "identity":
                        rows: dict[str, Any] = copy.deepcopy(dict(bad.rows))
                        rows["release_manifest"][0]["release_id"] = "ab" * 8 + "dd" * 24
                        bad = replace(bad, rows=rows)
                    else:
                        bad = replace(bad, interrupted=True)
                    with self.subTest(side=side, mode=mode):
                        if mode == "identity":
                            with self.assertRaisesRegex(startup.StartupRefusal, reason):
                                startup.verify_snapshots(
                                    checked,
                                    receipt,
                                    bad if side == "embedded" else left,
                                    bad if side == "postgres" else right,
                                )
                            self.sensitive(
                                startup.require_manifest_identity,
                                (bad, manifest_rows(checked.document)),
                                reason,
                                kind=startup.StartupRefusal,
                            )
                        else:
                            self.sensitive(
                                startup.verify_snapshots,
                                (
                                    checked,
                                    receipt,
                                    bad if side == "embedded" else left,
                                    bad if side == "postgres" else right,
                                ),
                                reason,
                                kind=startup.StartupRefusal,
                            )

    def test_ac3_each_actual_partial_marker_with_complete_receipt(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        with fixture_reads(checked, receipt, left):
            for marker in ("release.duckdb.partial", ".load_receipt.json.partial"):
                path = self.root / marker
                path.write_text("INVENTED-interruption")
                # Artefact IO is a distinct later boundary. A complete receipt
                # and equal stores remain available to isolate the marker check.
                with (
                    self.subTest(marker=marker),
                    patch("eii_product.store.startup.verify_artefacts"),
                ):
                    self.sensitive(
                        startup.verify_startup,
                        (self.root,),
                        "interrupted_load_refused",
                        kind=startup.StartupRefusal,
                        kwargs=dict(
                            environment="live",
                            embedded_reader=lambda _: left,
                            postgres_reader=lambda _: right,
                        ),
                    )
                path.unlink()

    def test_ac3_complete_receipt_parity_metadata_each_field(self) -> None:
        checked, receipt, left, right = snapshots(self.root)
        with fixture_reads(checked, receipt, left):
            for field, value in (
                ("engines", ["embedded"]),
                ("tables", []),
                ("digests", {}),
                ("row_counts", {}),
            ):
                with self.subTest(field=field):
                    changed = dict(receipt, **{field: value})
                    with self.assertRaisesRegex(
                        startup.StartupRefusal, "startup_parity_failed"
                    ):
                        startup.verify_snapshots(checked, changed, left, right)
                    self.sensitive(
                        startup.require_receipt_inventory,
                        (changed, left.names),
                        "startup_parity_failed",
                        kind=startup.StartupRefusal,
                    )

    def test_ac3_direct_api_policy_every_mode_and_identity(self) -> None:
        store = Mock(engine="postgres", release_id=IDENTITY)
        verify = Mock()
        valid = ServingPolicy("live", IDENTITY, verify)
        valid.require(store, self.root)
        verify.assert_called_once()
        for environment in ("live", "staging"):
            for field, value, reason in (
                ("traffic", "tomtom", "traffic_mode_refused"),
                ("presenter", True, "presenter_mode_refused"),
                ("release_id", "bc" * 32, "startup_identity_mismatch"),
            ):
                changes: dict[str, Any] = dict(
                    environment=environment, **{field: value}
                )
                bad = replace(valid, **changes)
                with self.subTest(environment=environment, field=field):
                    self.sensitive(
                        ServingPolicy.require,
                        (bad, store, self.root),
                        reason,
                        kind=startup.StartupRefusal,
                    )
            with self.subTest(environment=environment, field="engine"):
                self.sensitive(
                    ServingPolicy.require,
                    (
                        replace(valid, environment=environment),
                        Mock(engine="embedded", release_id=IDENTITY),
                        self.root,
                    ),
                    "postgres_required",
                    kind=startup.StartupRefusal,
                )

    def test_ac3_immutable_application_each_executable_asset_dependency(self) -> None:
        with patch("operations.install.verify_runtime"):
            archive = archive_fixture(self.root)
            folder, digest = install.install_application(
                archive, self.env("staging"), COMMIT
            )
        install.verify_application(
            folder, code_version=COMMIT, application_sha256=digest
        )
        for name in (
            "product/src/eii_product/api/app.py",
            "scripts/operations/serve.py",
            "web/dist/index.html",
            "runtime/site-packages/INVENTED.py",
        ):
            path = folder / name
            original = path.read_bytes()
            path.write_bytes(original + b"INVENTED-mutation")
            with self.subTest(name=name):
                self.sensitive(
                    install.verify_application,
                    (folder,),
                    "application_verification_failed",
                    kwargs=dict(code_version=COMMIT, application_sha256=digest),
                )
            path.write_bytes(original)
        moved = folder.with_name("INVENTED-mutable-checkout")
        shutil.copytree(folder, moved)
        self.sensitive(
            install.verify_application,
            (moved,),
            "mutable_application_refused",
            kwargs=dict(
                code_version=COMMIT, application_sha256=digest, archive=archive
            ),
        )
        archive.with_suffix(".zip.sha256").write_text("ba" * 32)
        self.sensitive(
            install.archive_manifest, (archive,), "application_checksum_mismatch"
        )

    def test_ac4_valid_public_table_with_each_wrong_valid_class(self) -> None:
        entry = dict(
            name="pub_parcel",
            file="tables/pub_parcel.parquet",
            grain="INVENTED-grain",
            provenance_class="public",
            row_count=0,
            sha256="ab" * 32,
            schema_sha256="bc" * 32,
        )
        # Pick an actual Public catalogue name; this avoids an unknown-name plant.
        entry["name"] = next(
            table.name for table in CATALOGUE if table.manifest_class == "public"
        )
        self.assertEqual(release_shape._refuse_table_entry(entry), entry["name"])
        for value in ("protected", "simulated", "frame", "graph", "lineage", "control"):
            with self.subTest(provenance=value):
                self.sensitive(
                    release_shape._refuse_table_entry,
                    (dict(entry, provenance_class=value),),
                    "table_class_invalid",
                    kind=ReleaseRefusal,
                )

    def test_ac4_every_known_protected_simulated_and_privacy_written_table(
        self,
    ) -> None:
        self.assertEqual(
            sum(row.manifest_class in {"protected", "simulated"} for row in CATALOGUE),
            13,
        )
        for table in CATALOGUE:
            entry = dict(
                name=table.name,
                file="tables/" + table.name + ".parquet",
                grain=table.grain,
                provenance_class=table.manifest_class,
                row_count=0,
                sha256="ab" * 32,
                schema_sha256="bc" * 32,
            )
            if table.manifest_class in {"protected", "simulated"}:
                with self.subTest(name=table.name, control="class"):
                    with self.assertRaisesRegex(
                        ReleaseRefusal, "forbidden_table_class"
                    ):
                        release_shape._refuse_table_entry(entry)
                    self.sensitive(
                        release_shape.require_public_catalogue_class,
                        (table,),
                        "forbidden_table_class",
                        kind=ReleaseRefusal,
                    )
            elif table.writer == "privacy":
                with self.subTest(name=table.name, control="writer"):
                    self.sensitive(
                        release_shape._refuse_table_entry,
                        (entry,),
                        "privacy_written_table",
                        kind=ReleaseRefusal,
                    )

    def test_ac4_every_forbidden_field_at_the_existing_writer_boundary(self) -> None:
        # Tooling tests may inspect Custodian validators. Product never imports
        # them, and these validators lazily import the engine only when writing.
        with patch.object(sys, "path", [str(ROOT / "custodian/src"), *sys.path]):
            from eii_custodian.release import public_only
        scalars = dict(
            build_id="INVENTED-build",
            built_at="2026-11-20T00:00:00Z",
            code_version=COMMIT,
            engine_versions=dict(duckdb="2.0.0", postgis_target="3.6", python="3.14"),
            release_contract_version="v1",
            rules_version_id="INVENTED-rules",
        )
        public_only._refuse_scalars(scalars)
        self.assertEqual(len(FORBIDDEN_PUBLIC_ONLY), 8)
        for field in sorted(FORBIDDEN_PUBLIC_ONLY):
            with self.subTest(field=field):
                self.sensitive(
                    public_only._refuse_scalars,
                    (dict(scalars, **{field: "INVENTED-forbidden"}),),
                    "forbidden_manifest_field",
                    kind=public_only.WriterRefusal,
                )

    def public_chain(
        self,
    ) -> tuple[list[dict[str, Any]], tuple[source_chain.ChainTable, ...]]:
        source = dict(
            source_id="INVENTED-source",
            publisher="INVENTED-publisher",
            title="INVENTED-dataset",
            url="https://invented.invalid/data",
            licence="INVENTED-licence",
            licence_basis="dataset",
            retrieved_on="2026-11-20",
            sha256="ab" * 32,
        )
        tables = (
            source_chain.ChainTable(
                "source_registry", (dict(source, kind="public_dataset"),)
            ),
            source_chain.ChainTable(
                "pub_census_national", (dict(source_id=source["source_id"]),)
            ),
            source_chain.ChainTable(
                "fact_lineage",
                (
                    dict(
                        table_name="pub_census_national",
                        source_id=source["source_id"],
                        transform="invented.method@v1",
                        input_class="public",
                    ),
                ),
            ),
        )
        source_chain.require_public_chain([source], tables)
        return [source], tables

    def test_ac4_explicit_generated_producer_cannot_disguise_a_public_chain(
        self,
    ) -> None:
        for key, value in (
            ("kind", "synthetic_feed"),
            ("kind", "simulation_output"),
            ("origin", "synthetic"),
            ("origin", "simulated"),
        ):
            sources, tables = self.public_chain()
            changed = replace(
                tables[0], rows=(dict(tables[0].rows[0], **{key: value}),)
            )
            with self.subTest(key=key, value=value):
                with self.assertRaisesRegex(
                    source_chain.SourceChainRefusal, "source_link_mismatch"
                ):
                    source_chain.require_public_chain(sources, (changed, *tables[1:]))
                self.sensitive(
                    source_chain._registry,
                    (changed,),
                    "source_link_mismatch",
                    kind=source_chain.SourceChainRefusal,
                )
        for value in ("synthetic", "simulated"):
            sources, tables = self.public_chain()
            lineage = replace(
                tables[2], rows=(dict(tables[2].rows[0], input_class=value),)
            )
            with self.subTest(input_class=value):
                with self.assertRaisesRegex(
                    source_chain.SourceChainRefusal, "source_link_mismatch"
                ):
                    source_chain.require_public_chain(sources, (*tables[:2], lineage))
                self.sensitive(
                    source_chain._lineage,
                    (
                        lineage,
                        {table.name: table for table in tables},
                        source_chain._registry(tables[0]),
                    ),
                    "source_link_mismatch",
                    kind=source_chain.SourceChainRefusal,
                )

    def test_ac6_each_report_mode_with_only_its_deciding_guard_off(self) -> None:
        for item in sorted(evidence.ITEMS):
            for mode in ("failed", "stale", "boolean"):
                fixture = self.promotion()
                original = fixture.reports[item]
                if mode == "stale":
                    changed = dict(original, release_id="ba" * 32)
                elif mode == "boolean":
                    changed = {
                        key: fixture.raw[key]
                        for key in ("code_version", "release_id", "application_sha256")
                    }
                    changed["green"] = True
                else:
                    field = dict(
                        merged="checks",
                        review="verdict",
                        whole_test="exit_code",
                        staging="installation_verified",
                        retention="retained_release_id",
                        features="completed",
                        gates="results",
                    )[item]
                    changed = dict(original, **{field: None})
                path = fixture.root / (item + ".json")
                path.write_bytes(encoded(changed))
                fixture.raw["evidence"][item]["sha256"] = sha(path)
                reason = (
                    "gate_evidence_required"
                    if item == "gates"
                    else "promotion_evidence_" + item
                )
                with self.subTest(item=item, mode=mode):
                    self.sensitive(
                        evidence.verify_evidence,
                        (fixture.root, fixture.raw),
                        reason,
                        kwargs=dict(
                            features=["INVENTED-finished"], staging_probe=lambda _: None
                        ),
                    )

    def test_ac6_every_hosted_result_missing_failed_stale(self) -> None:
        for name in sorted(evidence.CHECKS):
            for mode in ("missing", "failed", "stale"):
                fixture = self.promotion()
                checks = fixture.reports["merged"]["checks"]
                if mode == "missing":
                    del checks[name]
                else:
                    checks[name]["conclusion" if mode == "failed" else "commit"] = (
                        "failure" if mode == "failed" else "ba" * 20
                    )
                fixture.bind()
                with self.subTest(name=name, mode=mode):
                    self.sensitive(
                        evidence.verify_evidence,
                        (fixture.root, fixture.raw),
                        "promotion_evidence_merged",
                        kwargs=dict(
                            features=["INVENTED-finished"], staging_probe=lambda _: None
                        ),
                    )

    def test_ac6_unmerged_same_maker_whole_test_and_unfinished(self) -> None:
        for item, field, value in (
            ("merged", "ancestors", []),
            ("review", "reviewer", "OpenAI"),
            ("whole_test", "exit_code", 1),
            ("whole_test", "passed", 0),
            ("whole_test", "failed", 1),
            ("whole_test", "seed", ""),
            ("features", "enabled", ["INVENTED-unfinished"]),
            ("features", "completed", []),
        ):
            fixture = self.promotion()
            fixture.reports[item][field] = value
            fixture.bind()
            with self.subTest(item=item, field=field):
                self.sensitive(
                    evidence.verify_evidence,
                    (fixture.root, fixture.raw),
                    "promotion_evidence_" + item,
                    kwargs=dict(
                        features=["INVENTED-finished"], staging_probe=lambda _: None
                    ),
                )

    def test_ac7_route_binding_each_identity_field_and_missing_log(self) -> None:
        fixture = self.promotion()
        original = fixture.execute()
        for key, value in (
            ("authorization", "ba" * 32),
            ("sequence", 2),
            ("release_id", "bc" * 32),
            ("application_sha256", "bc" * 32),
            ("backend_port", 18089),
            ("entry_port", 8089),
            ("code_version", "ba" * 20),
            ("environment", "staging"),
            ("exposure", "public_entry"),
        ):
            changed = dict(original, **{key: value})
            (fixture.state / "route.json").write_bytes(encoded(changed))
            with self.subTest(key=key):
                with self.assertRaisesRegex(Refusal, "promotion_log_mismatch"):
                    activation.active_route(fixture.state)
                # Bind the independent outcome witness to the plant too, so
                # the authorisation component's controls-off proof is not
                # masked by the additional switch-witness guard.
                (fixture.state / "outcomes.jsonl").write_bytes(
                    encoded(dict(changed, state="switched")) + b"\n"
                )
                self.sensitive(
                    activation.active_route, (fixture.state,), "promotion_log_mismatch"
                )
        (fixture.state / "route.json").write_bytes(encoded(original))
        (fixture.state / "outcomes.jsonl").write_bytes(
            encoded(dict(original, state="switched")) + b"\n"
        )
        (fixture.state / "promotions.jsonl").unlink()
        self.sensitive(activation.entries, (fixture.state,), "promotion_log_mismatch")

    def test_ac7_retained_predecessor_is_bound_to_its_own_authorisation(self) -> None:
        fixture = self.promotion()
        fixture.execute()
        fixture.raw.update(
            operation="promote",
            previous_release_id=IDENTITY,
            release_id="bb" * 32,
            backend_port=18089,
        )
        fixture.bind()
        original = fixture.execute()
        for key, value in (
            ("application_sha256", "bc" * 32),
            ("backend_port", 18090),
            ("release_id", "bc" * 32),
            ("authorization", "bc" * 32),
        ):
            changed = copy.deepcopy(original)
            changed["predecessor"][key] = value
            (fixture.state / "route.json").write_bytes(encoded(changed))
            with self.subTest(key=key):
                with self.assertRaisesRegex(Refusal, "promotion_log_mismatch"):
                    activation.active_route(fixture.state)
                self.sensitive(
                    activation.require_predecessor,
                    (
                        changed["predecessor"],
                        activation.entries(fixture.state),
                        changed["sequence"],
                        "live",
                    ),
                    "promotion_log_mismatch",
                )

    def test_ac7_log_hash_sequence_and_previous_reference_each(self) -> None:
        for mode in ("hash", "sequence", "previous"):
            fixture = self.promotion()
            route = fixture.execute()
            entry = activation.entries(fixture.state)[0]
            if mode == "hash":
                entry["sha256"] = "bc" * 32
            else:
                entry["sequence" if mode == "sequence" else "previous"] = (
                    2 if mode == "sequence" else "bc" * 32
                )
                entry["sha256"] = hashlib.sha256(
                    encoded(
                        {key: value for key, value in entry.items() if key != "sha256"}
                    )
                ).hexdigest()
            (fixture.state / "promotions.jsonl").write_bytes(encoded(entry) + b"\n")
            (fixture.state / "history.json").write_bytes(
                encoded(dict(sequence=entry["sequence"], sha256=entry["sha256"]))
            )
            route.update(sequence=entry["sequence"], authorization=entry["sha256"])
            (fixture.state / "route.json").write_bytes(encoded(route))
            with self.subTest(mode=mode):
                self.sensitive(
                    activation.entries, (fixture.state,), "promotion_log_mismatch"
                )

    def test_ac7_owned_process_each_field(self) -> None:
        pid = 17
        folder = self.root / str(pid)
        folder.mkdir()
        (folder / "stat").write_text(
            "17 (INVENTED worker) " + " ".join(["S"] + ["0"] * 18 + ["123"])
        )
        (folder / "cmdline").write_bytes(
            b"python\0--nonce\0INVENTED-nonce\0--environment\0staging\0--port\08089\0"
        )
        ticks, command = process.identity(pid, proc_root=self.root)
        valid = dict(
            pid=pid,
            environment="staging",
            start_ticks=ticks,
            cmdline_sha256=command,
            nonce="INVENTED-nonce",
            port=8089,
        )
        process.require_owned(valid, "staging", proc_root=self.root)
        for key, value in (
            ("environment", "live"),
            ("start_ticks", "ticks:124"),
            ("cmdline_sha256", "ba" * 32),
            ("nonce", "INVENTED-other"),
            ("port", 8090),
        ):
            with self.subTest(key=key):
                self.sensitive(
                    process.require_owned,
                    (dict(valid, **{key: value}), "staging"),
                    "process_identity_mismatch",
                    kwargs=dict(proc_root=self.root),
                )

    def test_ac7_append_error_and_fsync_are_independent(self) -> None:
        state = self.env("live").state
        state.mkdir(parents=True)
        # append_authorisation's IO failure translation must refuse even when
        # there was no append at all; fsync is separately proved in Controls.
        with patch("pathlib.Path.open", side_effect=OSError("INVENTED-write-failure")):
            self.sensitive(
                activation.append_authorisation,
                (state, request(), {}, [], self.env("live")),
                "promotion_log_unwritable",
            )

    def test_ac7_readiness_timeout_without_any_other_failure(self) -> None:
        record = dict(port=18088, release_id=IDENTITY)
        # Each call has its own bounded fake clock. Removing only the timeout
        # refusal admits the unready child by returning normally.
        with patch(
            "operations.process.time.monotonic", side_effect=itertools.cycle((0.0, 6.0))
        ):
            self.sensitive(
                process.wait_ready, (record, "live", Mock()), "startup_not_ready"
            )

    def activation_case(
        self, fixture: promotion_fixture.Promotion, reason: str
    ) -> None:
        calls: list[str] = []

        def start(*_: Any) -> tuple[object, bool]:
            calls.append("admitted")
            return object(), True

        raw = fixture.raw
        scope = config.Environment(
            "live",
            fixture.root / "releases" / raw["release_id"],
            fixture.state,
            8088,
            ("127.0.0.1", 5432, "INVENTED_live"),
        )
        self.sensitive(
            activation.activate,
            (fixture.state, raw),
            reason,
            kwargs=dict(
                scope=scope,
                evidence_root=fixture.root,
                features=["INVENTED-finished"],
                verify_installation=lambda _: None,
                staging_probe=lambda _: None,
                retain=lambda _: None,
                start=start,
                ready=lambda *_: None,
                stop=lambda _: None,
                retire=lambda _: None,
            ),
        )
        self.assertEqual(calls, ["admitted"])

    def bind_activation_reports(self, fixture: promotion_fixture.Promotion) -> None:
        raw = fixture.raw
        fixture.reports["staging"]["installation_verified"] = raw["application_sha256"]
        fixture.reports["merged"]["main_commit"] = raw["code_version"]
        fixture.reports["merged"]["ancestors"] = [raw["code_version"]]
        for report in fixture.reports["merged"]["checks"].values():
            report["commit"] = raw["code_version"]
        for report in fixture.reports["gates"]["results"].values():
            report["commit"] = raw["code_version"]
        fixture.bind()

    def test_ac7_each_activation_target_and_reused_bootstrap(self) -> None:
        for mode in (
            "bootstrap",
            "predecessor",
            "entry_port",
            "backend_port",
            "same_port",
            "same_release",
            "restart_identity",
            "restart_archive",
        ):
            fixture = self.promotion()
            fixture.execute()
            if mode != "bootstrap":
                fixture.raw.update(
                    operation="promote",
                    previous_release_id=IDENTITY,
                    release_id="bb" * 32,
                    backend_port=18089,
                )
            reason = "activation_target_mismatch"
            if mode == "bootstrap":
                reason = "bootstrap_reused"
            elif mode == "predecessor":
                fixture.raw["previous_release_id"] = "bc" * 32
            elif mode == "entry_port":
                fixture.raw["entry_port"] = 8089
            elif mode == "backend_port":
                fixture.raw["backend_port"] = 18090
            elif mode == "same_port":
                fixture.raw["backend_port"] = 18088
            elif mode == "same_release":
                fixture.raw["release_id"] = IDENTITY
            else:
                fixture.raw.update(
                    operation="restart", release_id=IDENTITY, backend_port=18088
                )
                fixture.raw[
                    "release_id" if mode == "restart_identity" else "application_sha256"
                ] = "bc" * 32
            fixture.reports["retention"]["retained_release_id"] = (
                fixture.raw["previous_release_id"] or fixture.raw["release_id"]
            )
            self.bind_activation_reports(fixture)
            with self.subTest(mode=mode):
                self.activation_case(fixture, reason)

    def test_ac7_rollback_each_target_field(self) -> None:
        for key, value in (
            ("release_id", "bc" * 32),
            ("application_sha256", "bc" * 32),
            ("backend_port", 18089),
            ("code_version", "ba" * 20),
        ):
            fixture = self.promotion()
            fixture.execute()
            fixture.raw.update(
                operation="promote",
                previous_release_id=IDENTITY,
                release_id="bb" * 32,
                backend_port=18089,
            )
            fixture.bind()
            fixture.execute()
            fixture.raw.update(
                operation="rollback",
                previous_release_id="bb" * 32,
                release_id=IDENTITY,
                backend_port=18088,
            )
            fixture.raw[key] = value
            fixture.reports["retention"]["retained_release_id"] = "bb" * 32
            self.bind_activation_reports(fixture)
            with self.subTest(key=key):
                self.activation_case(fixture, "activation_target_mismatch")

    def test_ac5_every_step_omission_and_each_wrong_result(self) -> None:
        from operations import runbook

        rows: list[dict[str, Any]] = []
        for step, command, environment in runbook.STEPS:
            candidate = step.startswith("candidate_") or step == "promotion"
            rows.append(
                dict(
                    step=step,
                    command=command,
                    environment=environment,
                    exit_code=0,
                    verified_result=dict(
                        release_id=("bb" * 32 if candidate else IDENTITY),
                        release_sha256=("cc" if candidate else "aa") * 32,
                        application_sha256=None
                        if environment == "custodian"
                        else APPLICATION,
                        backend_port=None
                        if environment == "custodian"
                        else 8089
                        if environment == "staging"
                        else 18089
                        if candidate
                        else 18088,
                    ),
                )
            )
        runbook.verify_transcript(rows)
        for index, (step, _, _) in enumerate(runbook.STEPS):
            missing = rows[:index] + rows[index + 1 :]
            with self.subTest(step=step, mode="omitted"):
                with self.assertRaisesRegex(Refusal, "runbook_step_missing"):
                    runbook.verify_transcript(missing)
                self.sensitive(
                    runbook.require_step_count, (missing,), "runbook_step_missing"
                )
            for mode in ("exit", "checksum"):
                changed = copy.deepcopy(rows)
                if mode == "exit":
                    changed[index]["exit_code"] = 4
                else:
                    changed[index]["verified_result"]["release_sha256"] = "dd" * 32
                with self.subTest(step=step, mode=mode):
                    self.sensitive(
                        runbook.verify_transcript, (changed,), "runbook_result_invalid"
                    )

    def test_ac8_rule24_catalogue_shape_does_not_certify_semantics(self) -> None:
        import yaml

        from eii_product.assistant.catalogue import load
        from eii_product.assistant.catalogue.schema import FILE_NAMES, Catalogue

        folder = self.root / "INVENTED-catalogue"
        folder.mkdir()
        for name in FILE_NAMES:
            (folder / name).write_bytes(
                (load.catalogue_directory() / name).read_bytes()
            )
        self.assertIsInstance(load.load_catalogue(folder), Catalogue)
        claims = yaml.safe_load((folder / "claims.yaml").read_text())
        # L-1256 leaves semantic review with the catalogue's owning review.
        # Keep this shape-versus-meaning evidence; it does not certify text or
        # grant permission to render the planted words under rule 24.
        for text in (
            "Certified formal privacy: {value}",
            "This product is operated by a ministry: {value}",
            "Measured from the real register: {value}",
            "Synthetic footfall at a named building: {value}",
            "A forecast of venture success: {value}",
            "An inferior existing public service: {value}",
            "Lookup of an individual: {value}",
        ):
            changed = copy.deepcopy(claims)
            changed["claims"][0]["template_en"] = text
            (folder / "claims.yaml").write_text(
                yaml.safe_dump(changed, allow_unicode=True)
            )
            with self.subTest(meaning=text):
                self.assertIsInstance(load.load_catalogue(folder), Catalogue)

    def test_ac8_existing_generated_chain_official_word_control(self) -> None:
        from eii_product import backend_origin

        markers = dict(
            origin="synthetic",
            generator_name="INVENTED-pipeline",
            generator_version="v1",
        )
        chain = dict(
            method="INVENTED-method",
            method_version="v1",
            pipeline="INVENTED-pipeline",
            pipeline_version="v1",
        )
        backend_origin.require_truthful_chain(chain, markers)
        for word in ("official", "measured", "ministry", "real register"):
            with self.subTest(word=word):
                self.sensitive(
                    backend_origin.require_truthful_chain,
                    (dict(chain, label_en=word), markers),
                    "claim_word",
                    kind=backend_origin.BackendOriginRefusal,
                )

    def test_ac8_every_static_database_executable_in_each_permitted_process_module(
        self,
    ) -> None:
        from operations.policy import BANNED, PROCESS_MODULES, require_sources

        for module in sorted(PROCESS_MODULES):
            for executable in sorted(BANNED):
                with self.subTest(module=module, executable=executable):
                    self.sensitive(
                        require_sources,
                        (
                            {
                                module: "import subprocess\nsubprocess.run(["
                                + repr(executable)
                                + ", 'start'])\n"
                            },
                        ),
                        "operation_command_refused",
                    )

    def test_ac8_unlisted_release_output(self) -> None:
        checked, _, _, _ = snapshots(self.root)
        (self.root / "INVENTED-extra-output").write_text("INVENTED-only")
        self.sensitive(
            startup.verify_artefacts,
            (checked,),
            "startup_inventory_mismatch",
            kind=startup.StartupRefusal,
        )

    def test_ac8_loopback_gate_does_not_require_public_approval(self) -> None:
        raw = request()
        evidence.exposure(self.root, raw)

        # A planted unconditional public-only check would reject this valid
        # pre-gate setup; the nested regression must turn red for that reason.
        def planted() -> None:
            try:
                with patch.dict(raw, exposure="public_entry"):
                    evidence.exposure(self.root, raw)
            except Refusal as error:
                self.assertEqual(error.reason, "public_gate_approval_required")
                self.fail(
                    "unconditional public approval check rejected valid loopback setup"
                )

        result = unittest.TestResult()
        unittest.FunctionTestCase(planted).run(result)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertIn("rejected valid loopback", result.failures[0][1])

    def test_ac3_no_fallback_and_explicit_embedded_each_serving_environment(
        self,
    ) -> None:
        checked, receipt, left, _ = snapshots(self.root)
        with fixture_reads(checked, receipt, left):
            for environment in ("live", "staging"):
                for embedded, reason in (
                    (True, "embedded_environment_refused"),
                    (False, "postgres_required"),
                ):
                    with self.subTest(environment=environment, embedded=embedded):
                        self.sensitive(
                            startup.verify_startup,
                            (self.root,),
                            reason,
                            kind=startup.StartupRefusal,
                            kwargs=dict(
                                environment=environment,
                                embedded=embedded,
                                embedded_reader=lambda _: left,
                            ),
                        )

    def test_ac3_missing_assembly_and_unresolved_source_or_lineage_each(self) -> None:
        with patch.object(sys, "path", [str(ROOT / "custodian/src"), *sys.path]):
            import public_release_fixture as fixture

            from eii_custodian.release import assembly, public_only

        self.sensitive(
            assembly.read_assembly,
            (self.root,),
            "operation_os_error",
            kind=ValueError,
        )
        tables = fixture.fixture_tables()
        sources = fixture._manifest_sources()
        public_only._refuse_chain(sources, tables)
        for mode, name, field, value, reason in (
            (
                "incomplete-source",
                "source_registry",
                "publisher",
                "",
                "source_link_incomplete",
            ),
            (
                "unresolved-source",
                "pub_census_national",
                "source_id",
                "INVENTED-unresolved",
                "source_link_unknown",
            ),
            ("unresolved-lineage", "fact_lineage", None, None, "source_link_missing"),
        ):
            changed = []
            for table in tables:
                if table.name != name:
                    changed.append(table)
                    continue
                rows = [dict(row) for row in table.rows]
                if field is None:
                    rows = []
                else:
                    rows[0][field] = value
                changed.append(replace(table, rows=tuple(rows)))
            with self.subTest(mode=mode):
                self.sensitive(
                    public_only._refuse_chain,
                    (sources, tuple(changed)),
                    reason,
                    kind=public_only.WriterRefusal,
                )

    def test_ac7_lock_serialization_and_initial_rollback_guard(self) -> None:
        state = self.root / "state"
        mutant = controls_fixture.without_refusal(
            inspect.unwrap(activation.operation_lock), "operation_in_progress"
        )
        with activation.operation_lock(state):
            with self.assertRaisesRegex(Refusal, "operation_in_progress"):
                with activation.operation_lock(state):
                    self.fail("second operation admitted")

            def assertion() -> None:
                with self.assertRaisesRegex(Refusal, "operation_in_progress"):
                    with mutant(state):
                        (state / "INVENTED-admitted-operation").write_text(
                            "INVENTED-only"
                        )

            result = unittest.TestResult()
            unittest.FunctionTestCase(assertion).run(result)
            self.assertEqual(result.errors, [])
            self.assertEqual(len(result.failures), 1)
            self.assertIn("not raised", result.failures[0][1])
            self.assertTrue((state / "INVENTED-admitted-operation").exists())
        self.sensitive(
            activation.require_previous_release,
            (None,),
            "no_previous_release_for_rollback",
        )

    def test_ac7_route_sequence_and_predecessor_shape_order_and_environment(
        self,
    ) -> None:
        fixture = self.promotion()
        route = fixture.execute()
        (fixture.state / "route.json").write_bytes(encoded(dict(route, sequence=True)))
        self.sensitive(
            activation.active_route, (fixture.state,), "promotion_log_mismatch"
        )
        history = activation.entries(fixture.state)
        for mode, predecessor, before, environment in (
            ("shape", dict(route, extra=True), 2, "live"),
            ("order", route, 1, "live"),
            ("environment", route, 2, "staging"),
        ):
            with self.subTest(mode=mode):
                self.sensitive(
                    activation.require_predecessor,
                    (predecessor, history, before, environment),
                    "promotion_log_mismatch",
                )
