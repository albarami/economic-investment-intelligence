"""Native loader cleanup/output plants with invented Parquet and PostgreSQL IO."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from test_s3_t28_controls import without_call

from eii_product.store import loader
from operations.install import file_inventory

ROOT = Path(__file__).resolve().parents[2]


def fixture_module():
    spec = importlib.util.spec_from_file_location(
        "INVENTED-loader-fixture", ROOT / "product/tests/test_release_cleanup.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_red(assertion):
    result = unittest.TestResult()
    unittest.FunctionTestCase(assertion).run(result)
    assert result.errors == [], "another error is not cleanup/output admission"
    assert len(result.failures) == 1


def test_each_loader_failure_branch_cleans_its_partial_output_and_transaction(tmp_path):
    fixture = fixture_module()
    for index, mode in enumerate(("closed", "unexpected")):
        for disabled in (False, True):
            folder = tmp_path / (mode + ("-off" if disabled else "-on"))
            folder.mkdir()
            fixture._write_parquet(folder)
            checked = fixture._checked(folder)
            connection = fixture._Ledger()
            partial = folder / loader.PARTIAL_READER

            def fail(*args, pending=partial, kind=mode):
                pending.write_bytes(b"INVENTED-owned-partial")
                if kind == "closed":
                    raise loader.LoadRefusal("store_verification_failed")
                raise OSError("INVENTED-interruption")

            def assertion(
                function, link=connection, document=checked, kind=mode, pending=partial
            ):
                try:
                    function(link, document)
                except loader.LoadRefusal as error:
                    assert error.reason == (
                        "store_verification_failed"
                        if kind == "closed"
                        else "engine_operation_failed"
                    )
                else:
                    raise AssertionError("invented failure was not reached")
                assert not pending.exists(), "partial output admitted after failure"
                assert link.working == {}
                assert link.committed == {}

            with patch("eii_product.store.loader._stage_embedded", side_effect=fail):
                execute = (
                    without_call(loader.load_checked, "_abandon", occurrence=index)
                    if disabled
                    else loader.load_checked
                )
                if disabled:
                    require_red(lambda function=execute: assertion(function))
                    assert partial.read_bytes() == b"INVENTED-owned-partial"
                    assert connection.working
                else:
                    assertion(execute)


def test_each_loader_output_boundary_has_a_deciding_snapshot(tmp_path):
    fixture = fixture_module()
    original_receipt = loader.write_receipt
    for mode in ("valid", "manifest", "extra"):
        folder = tmp_path / mode
        folder.mkdir()
        fixture._write_parquet(folder)
        checked = fixture._checked(folder)
        manifest = folder / "manifest.json"
        manifest.write_bytes(b"INVENTED-immutable-manifest")
        before = file_inventory(folder)

        def write(*args, kind=mode, path=manifest, root=folder, **kwargs):
            if kind == "manifest":
                path.write_bytes(b"INVENTED-rewritten-manifest")
            elif kind == "extra":
                (root / "INVENTED-extra-output").write_bytes(b"INVENTED-only")
            return original_receipt(*args, **kwargs)

        def assertion(document=checked, root=folder, snapshot=before):
            loader.load_checked(fixture._Ledger(), document)
            after = file_inventory(root)
            assert {name: after.get(name) for name in snapshot} == snapshot, (
                "immutable input changed"
            )
            assert set(after) - set(snapshot) == {
                "release.duckdb",
                "load_receipt.json",
            }, "unlisted output admitted"

        with patch("eii_product.store.loader.write_receipt", side_effect=write):
            if mode == "valid":
                assertion()
            else:
                require_red(assertion)
