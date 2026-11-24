"""Import stays light even with the real packaged query inventory present."""

import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", ["eii_product.store", "eii_product.store.registry"])
def test_populated_store_import_loads_no_driver_or_parser(module: str) -> None:
    code = """
import importlib
import sys

importlib.import_module(sys.argv[1])
from eii_product.store import registry

assert tuple(registry.packaged_sql_dir().glob("*.sql")), "packaged queries absent"
loaded = sorted({name.split(".", 1)[0] for name in sys.modules}
                & {"duckdb", "psycopg", "sqlglot"})
assert loaded == [], loaded
from eii_product.store.registry import PACKAGED
assert PACKAGED.queries
assert registry.PACKAGED is PACKAGED
assert "sqlglot" in sys.modules
try:
    registry.syn_missing_attribute
except AttributeError:
    pass
else:
    raise AssertionError("unknown attribute accepted")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, module],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_concurrent_first_access_builds_the_packaged_inventory_once() -> None:
    code = """
import threading
import time

from eii_product.store import registry

real_load = registry.load_inventory
calls = []


def slow_load(folder):
    calls.append(folder)
    time.sleep(0.2)
    return real_load(folder)


registry.load_inventory = slow_load
gate = threading.Barrier(8)
seen = []


def first_access():
    gate.wait()
    seen.append(registry.PACKAGED)


threads = [threading.Thread(target=first_access) for _ in range(8)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert len(calls) == 1, len(calls)
assert len(seen) == 8, len(seen)
assert all(item is registry.PACKAGED for item in seen)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
