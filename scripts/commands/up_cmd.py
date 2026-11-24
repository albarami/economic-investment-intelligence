"""Probe, then activate an explicitly installed live or staging application."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import preflight
from eii_core.reasons import reason
from preflight_rows import RELEASE_ROWS
from preflight_store import Line

from . import exits, table


def run(root: Path, environ: Mapping[str, str], args: Sequence[str]) -> int:
    """Probe once, verify/load an absent schema, then start the selected service."""
    if tuple(args) == ("--embedded",):
        embedded = True
    elif len(args) == 0:
        embedded = False
    else:
        table.write_usage()
        return 2
    if embedded and environ.get("EII_ENVIRONMENT") in {"live", "staging"}:
        return exits.finish(4, "up", "embedded_environment_refused")
    from operations.remote import take_host

    # Only the final activation reads the remote host; every probe, load and
    # closed-list check before it sees the environment without that name.
    exposing, environ = environ, take_host(environ)[0]
    report = preflight.run_preflight(
        root,
        environ,
        embedded=embedded,
        docker=False,
    )
    for line in report.text_lines():
        print(line)
    code, detail = preflight.up_decision(environ, report)
    if (
        code == 4
        and environ.get("EII_ENVIRONMENT") in {"live", "staging"}
        and not any(
            line.severity == "FAIL" and line.check not in RELEASE_ROWS
            for line in report.lines
        )
    ):
        from operations.common import Refusal
        from operations.deploy import ensure_schema

        try:
            loaded = ensure_schema(environ)
        except Exception as error:
            if isinstance(error, Refusal):
                return exits.finish(error.code, "up", error.reason)
            from eii_product.store.loader import LoadRefusal
            from eii_product.store.receipt import ReceiptRefusal
            from eii_product.store.release_check import ReleaseRefusal
            from eii_product.store.startup import StartupRefusal

            if isinstance(error, (LoadRefusal, ReleaseRefusal)):
                return exits.finish(error.exit_code, "up", error.reason)
            if isinstance(error, (ReceiptRefusal, StartupRefusal)):
                return exits.finish(4, "up", error.reason)
            return exits.finish(4, "up", reason(error))
        if loaded:
            # This is the pinned state-changing load step, not a probe retry.
            updated = tuple(
                Line("PASS", line.check, "verified after owner-only load")
                if line.check in RELEASE_ROWS
                else line
                for line in report.lines
            )
            report = preflight.Report(updated, "postgres", 0)
            print("PASS load-release: absent schema loaded and both stores verified")
            code, detail = preflight.up_decision(environ, report)
    if code != 0:
        return exits.finish(code, "up", detail)
    if environ.get("EII_ENVIRONMENT") not in {"live", "staging"}:
        if embedded:
            from operations.common import Refusal
            from operations.development import serve_embedded

            try:
                serve_embedded(root, environ)
            except Refusal as error:
                return exits.finish(error.code, "up", error.reason)
            except Exception as error:
                return exits.finish(4, "up", reason(error))
            return 0
        return exits.finish(1, "up", table.by_word("up").detail)
    from operations.common import Refusal
    from operations.deploy import up

    try:
        up(exposing)
    except Refusal as error:
        return exits.finish(error.code, "up", error.reason)
    except Exception as error:
        from eii_product.store.receipt import ReceiptRefusal
        from eii_product.store.startup import StartupRefusal

        if isinstance(error, (ReceiptRefusal, StartupRefusal)):
            return exits.finish(4, "up", error.reason)
        return exits.finish(4, "up", reason(error))
    print("PASS up: owned loopback entry is ready on the authorised release")
    return 0
