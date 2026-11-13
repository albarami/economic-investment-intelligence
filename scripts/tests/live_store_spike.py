"""Mandatory live parity command, run only by the lead; never collected offline.

Offline discovery proves contracts and DuckDB only. This command requires both
real stores and fails on absent PostgreSQL, drivers, or any query error. It never
starts a service, skips a case or falls back. --diverge must fail after a passing
baseline, changing only the DuckDB integer primitive in a new isolated fixture.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from store_spike import QUERY_NAME, DuckStore, PostgresStore, query_hash
from store_spike_fixture import (
    FIXTURE_ID,
    ROWS,
    UNITS,
    duck_fixture,
    expected,
    postgres_fixture,
)
from store_spike_normalise import ParityMismatch, QueryResult, SpikeRefusal, compare


def run_live(environ: Mapping[str, str], *, diverge: bool) -> None:
    import duckdb
    import psycopg

    with postgres_fixture(environ) as pg, duck_fixture() as duck:
        left, right = PostgresStore(pg), DuckStore(duck)
        full: QueryResult | None = None
        for units in (list(UNITS), [], [UNITS[0]], ["SYN-unit-' OR 'x'='x"]):
            a = left.fetch(QUERY_NAME, {"units": units})
            b = right.fetch(QUERY_NAME, {"units": units})
            compare(expected(units), a)
            compare(expected(units), b)
            compare(a, b)
            if units == list(UNITS):
                full = a
        if full is None or not full.rows:
            raise SpikeRefusal("baseline result missing")
        evidence = {
            "fixture_sha256": FIXTURE_ID,
            "query_sha256": query_hash(),
            "fixture_rows": len(ROWS),
            "result_rows": len(full.rows),
            "duckdb": duckdb.__version__,
            "psycopg": psycopg.__version__,
            "postgresql_server_version": pg.info.server_version,
            "normalisation": "integer exact; decimal six places ROUND_HALF_EVEN; text NFC",
            "ordered_rows": full.rows,
        }
        print("PASS store-spike: both engines match")
        print(json.dumps(evidence, default=str, ensure_ascii=False, sort_keys=True))
        if diverge:
            with duck_fixture(diverge=True) as changed:
                compare(
                    full, DuckStore(changed).fetch(QUERY_NAME, {"units": list(UNITS)})
                )
            raise SpikeRefusal("divergence was not detected")


def main(args: Sequence[str], environ: Mapping[str, str]) -> int:
    if list(args) not in ([], ["--diverge"]):
        print("FAIL store-spike: usage: live_store_spike.py [--diverge]")
        return 2
    try:
        run_live(environ, diverge=bool(args))
    except ParityMismatch as error:
        print(f"FAIL store-spike: {error}")
        return 3
    except SpikeRefusal as error:
        print(f"FAIL store-spike: {error}")
        return 1
    except ImportError:
        print("FAIL store-spike: driver missing; install the engine group")
        return 1
    except Exception:
        # Never print a driver exception, URL, credentials, or a traceback.
        print("FAIL store-spike: engine operation failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], os.environ))
