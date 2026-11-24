"""Native offline components under the descendant syscall tripwire.

The complete dispatcher sequence is covered in scripts/tests. This companion
runs its real sandbox/writer, archive/dependency closure, entry and owned-child
interfaces on invented inputs. PostgreSQL server proof remains lead-owned.
"""

import sys
from pathlib import Path

from s3_t28_network import trace

ROOT = Path(__file__).resolve().parents[2]


def test_native_operations_components_have_zero_outbound_attempts(tmp_path):
    program = """
import importlib.util
import sys
from pathlib import Path
root, scratch = Path(sys.argv[1]), Path(sys.argv[2])
sys.path[:0] = [str(root / p) for p in ("scripts/tests", "scripts", "core/src", "custodian/src", "product/src")]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, root / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
assembly = load("invented_assembly_tests", "custodian/tests/test_operations_assembly.py")
archive = load("invented_archive_tests", "product/tests/test_offline_installation.py")
process = load("invented_process_tests", "product/tests/test_operational_process.py")
for name, function in (
    ("assembly", assembly.test_real_sandbox_writes_verified_public_export_and_removes_vault),
    ("archive", archive.test_native_offline_archive_installs_identically_without_editable_paths),
    ("entry", process.test_one_entry_forwards_changed_identity_and_backend_then_rollback),
    ("child", process.test_owned_child_ready_and_shutdown_without_signalling_a_foreign_record),
):
    folder = scratch / name
    folder.mkdir()
    function(folder)
    print("native component:", name, flush=True)
"""
    code, attempts, output = trace(
        (sys.executable, "-I", "-B", "-c", program, str(ROOT), str(tmp_path)),
        tmp_path,
    )
    assert code == 0, (attempts, output)
    assert output.splitlines() == [
        "native component: assembly",
        "native component: archive",
        "native component: entry",
        "native component: child",
    ]
    assert attempts == []
