"""Preflight checks: run every row and decide store and exit status."""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import preflight_database as database
import preflight_proc as proc
import preflight_rows as rows
import preflight_store as store
from eii_core.reasons import reason

CHECKS = (
    "python",
    "node-npm",
    "locked-dependencies",
    "duckdb-extensions",
    "postgresql",
    "release",
    "load-receipt",
    "embedded-reader",
    "tiles-glyphs-fonts",
    "recorded-replays",
    "bubblewrap-sandbox",
    "api-port",
    "model-key",
    "traffic-provider-key",
    "night-lights-key",
    "cdse-client-id",
    "cdse-client-secret",
    "imagery-provider-key",
    "photorealistic-3d-key",
    "env-not-tracked",
    "wsl-interop",
)
EXIT_USAGE = 2
ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Report:
    """Full preflight report."""

    lines: tuple[store.Line, ...]
    store: str
    status: int

    def text_lines(self) -> list[str]:
        """Return printable lines including store."""
        out = [line.text() for line in self.lines]
        out.append(f"store: {self.store}")
        return out


def run_preflight(
    root: Path,
    environ: Mapping[str, str],
    *,
    embedded: bool = False,
    docker: bool = True,
    limit: float = proc.PROBE_TIMEOUT_S,
    api_port: int = rows.API_PORT,
    tools: rows.ToolChecks | None = None,
) -> Report:
    """Run every preflight row inside a temporary scratch folder."""
    from operations.common import Refusal
    from operations.config import DEFAULT_PORTS
    from operations.config import api_port as configured_port

    port_reason = None
    try:
        api_port = configured_port(
            environ.get("EII_API_PORT", ""),
            DEFAULT_PORTS.get(environ.get("EII_ENVIRONMENT", ""), api_port),
        )
    except Refusal as error:
        port_reason = error.reason
    operational = environ.get("EII_ENVIRONMENT") in {"live", "staging"}
    if operational:
        docker = False
    with tempfile.TemporaryDirectory(prefix="eii-preflight-") as scratch_name:
        scratch = Path(scratch_name)
        out_lines: list[store.Line] = []
        tool_checks = (
            rows.default_tools(root, environ, limit) if tools is None else tools
        )

        out_lines.append(tool_checks.python())
        out_lines.append(tool_checks.node_npm())
        out_lines.append(
            rows.locked_dependencies_row(root, environ, scratch, limit),
        )
        out_lines.append(tool_checks.extensions())
        if embedded:
            sel = database.check_postgres(
                environ,
                scratch,
                limit,
                embedded=True,
                docker=docker,
            )
        else:
            sel = database.check_postgres(
                environ,
                scratch,
                limit,
                embedded=False,
                docker=docker,
            )
        if sel.line is not None:
            out_lines.append(sel.line)
        database_conflict = (
            sel.line is not None and sel.line.reason == "environment_database_conflict"
        )
        if (
            operational
            and (embedded or sel.store != "postgres")
            and not database_conflict
        ):
            sel = store.Selection(
                store.Line("FAIL", "postgresql", "postgres_required"), "none"
            )
            out_lines = [line for line in out_lines if line.check != "postgresql"]
            out_lines.append(store.Line("FAIL", "postgresql", "postgres_required"))

        rel = (
            {
                name: store.Line("FAIL", name, "environment_database_conflict")
                for name in (*rows.RELEASE_ROWS, rows.REPLAY_ROW)
            }
            if database_conflict
            else rows.release_rows(environ)
        )
        tile_line = (
            store.Line("FAIL", "tiles-glyphs-fonts", "application_not_verified")
            if operational
            else rows.tiles_row(root)
        )
        if operational:
            from eii_product.api.health import asset_reason, local_assets
            from operations.config import read_environment
            from operations.deploy import request_for
            from operations.runtime import check_stores, installed, verify_peers

            try:
                env = read_environment(environ)
                verify_peers(env)
                request = request_for(env, environ)
                api_port = request["backend_port"]
                application, _ = installed(env, request)
                assets = local_assets(env.release, application / "web/dist")
                tile_line = store.Line(
                    "PASS" if assets == ("ok", "ok", "ok") else "FAIL",
                    "tiles-glyphs-fonts",
                    "installed_local_assets"
                    if assets == ("ok", "ok", "ok")
                    else asset_reason(assets),
                )
                check_stores(env, environ, embedded=embedded)
            except Exception as error:
                rel["release"] = store.Line("FAIL", "release", reason(error))
        out_lines.append(rel["release"])
        out_lines.append(rel["load-receipt"])
        out_lines.append(rel["embedded-reader"])
        out_lines.append(tile_line)
        out_lines.append(rel["recorded-replays"])
        out_lines.append(tool_checks.bubblewrap())
        port_line = (
            rows.api_port_row(api_port)
            if port_reason is None
            else store.Line("FAIL", "api-port", port_reason)
        )
        if operational and port_line.severity == "FAIL" and port_reason is None:
            from operations.common import read_json
            from operations.config import read_environment
            from operations.process import process_record, require_owned

            try:
                env = read_environment(environ)
                record = read_json(
                    process_record(env.state, api_port), "process_identity_mismatch"
                )
                require_owned(record, env.name)
                if record["release_id"] != env.release.name and env.name != "staging":
                    raise Refusal("process_identity_mismatch")
                port_line = store.Line(
                    "PASS", "api-port", "verified owned application process"
                )
            except Exception as error:
                port_line = store.Line("FAIL", "api-port", reason(error))
        out_lines.append(port_line)
        out_lines.append(rows.model_key_row(environ))
        traffic = rows.traffic_provider_key_row(environ)
        if traffic.severity == "PASS" and environ.get(
            "EII_TRAFFIC_PROVIDER", ""
        ) not in {"", "simulated"}:
            traffic = store.Line("FAIL", "traffic-provider-key", "traffic_mode_refused")
        out_lines.append(traffic)
        out_lines.append(rows.night_lights_key_row(environ))
        out_lines.append(rows.cdse_client_id_row(environ))
        out_lines.append(rows.cdse_client_secret_row(environ))
        out_lines.append(rows.imagery_provider_key_row(environ))
        out_lines.append(rows.photorealistic_3d_key_row(environ))
        out_lines.append(rows.env_tracked_row(root, environ, limit))
        out_lines.append(rows.wsl_row(root, environ, limit))

        status = 1 if any(line.severity == "FAIL" for line in out_lines) else 0
        return Report(tuple(out_lines), sel.store, status)


def up_decision(
    environ: Mapping[str, str],
    report: Report,
) -> tuple[int, str]:
    """Map a report to an exit code for ./eii up."""
    if not environ.get("EII_RELEASE_DIR", ""):
        return (
            4,
            "./eii up requires a configured, complete release: EII_RELEASE_DIR is not set",
        )
    failed = [line.check for line in report.lines if line.severity == "FAIL"]
    release_failed = [c for c in failed if c in rows.RELEASE_ROWS]
    if release_failed:
        joined = ", ".join(release_failed)
        return (4, f"release missing, incomplete or not verified: {joined}")
    if failed == ["api-port"]:
        return (5, "API port already in use")
    if failed:
        joined = ", ".join(failed)
        return (1, f"a check failed: {joined}")
    return (0, "")


def main(argv: Sequence[str]) -> int:
    """CLI entry: print lines and return status."""
    if argv:
        sys.stderr.write("usage: preflight.py takes no arguments\n")
        return EXIT_USAGE
    report = run_preflight(ROOT, os.environ)
    for line in report.text_lines():
        print(line)
    return report.status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
