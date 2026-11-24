"""Product install/load, local readiness and explicit activation wiring."""

from __future__ import annotations

import http.client
import json
import secrets
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from eii_core.reasons import reason
from operations import process
from operations.activation import activate, active_route, operation_lock
from operations.common import Refusal, atomic_json, read_json
from operations.config import (
    Environment,
    read_environment,
    runtime_environment,
    write_target,
)
from operations.evidence import operation
from operations.install import install_application, install_release, public_kind
from operations.runtime import check_stores, inspect_schema, installed, verify_peers


def request_for(env: Environment, environ: Mapping[str, str]) -> dict[str, Any]:
    path = Path(environ.get("EII_OPERATION_RECORD", ""))
    if (
        not path.is_file()
        or not path.resolve().is_relative_to(env.home.resolve())
        or path.is_symlink()
    ):
        raise Refusal("operation_schema_invalid")
    request = operation(read_json(path, "operation_schema_invalid"))
    if (
        request["environment"] != env.name
        or request["release_id"] != env.release.name
        or request["entry_port"] != env.port
    ):
        raise Refusal("activation_target_mismatch")
    if env.name == "staging" and request["backend_port"] != env.port:
        raise Refusal("activation_target_mismatch")
    return request


def load(root: Path, environ: Mapping[str, str], *, connect: Any = None) -> int:
    from eii_product.store.loader import run_load
    from eii_product.store.release_check import check_release

    env = read_environment(environ, installing=True)
    verify_peers(env)
    source_name = environ.get("EII_SOURCE_RELEASE_DIR", "")
    if not source_name:
        raise Refusal("source_release_missing")
    source = Path(source_name)
    document = public_kind(source)
    check_release(source)
    archive_name = environ.get("EII_APPLICATION_ARCHIVE", "")
    if not archive_name:
        if env.name != "staging":
            raise Refusal("application_archive_required")
        from operations.package import prepare_archive

        archive = (
            root / ".operations/archives" / (str(document["code_version"]) + ".zip")
        )
        if not archive.exists():
            prepare_archive(root, str(document["code_version"]), archive, environ)
    else:
        archive = Path(archive_name)
    application, digest = install_application(
        archive, env, str(document["code_version"])
    )
    install_release(source, env, application)
    # Load is the only path receiving the owner connector; the API never does.
    from commands.load_release import _connect

    target = env.database
    if target is None:
        raise Refusal("postgres_required")
    # A durable sibling reservation precedes any database mutation. The
    # deployment lock serializes the peer check and reservation across names.
    with operation_lock(env.home.parent):
        verify_peers(env)
        with operation_lock(env.state):
            atomic_json(
                write_target(env, env.state / "environment.json"),
                dict(
                    environment=env.name,
                    release_id=env.release.name,
                    port=env.port,
                    database=list(target),
                ),
            )
    code = run_load(
        env.release,
        host=target[0],
        port=target[1],
        database=target[2],
        connect=_connect if connect is None else connect,
    )
    if code != 0:
        return code
    clean = {
        k: v
        for k, v in environ.items()
        if k not in {"EII_SOURCE_RELEASE_DIR", "EII_APPLICATION_ARCHIVE"}
    }
    check_stores(env, clean)
    with operation_lock(env.state):
        installations = env.state / "installations"
        installations.mkdir(exist_ok=True)
        atomic_json(
            installations / (env.release.name + ".json"),
            dict(
                release_id=env.release.name,
                application_sha256=digest,
                code_version=document["code_version"],
            ),
        )
    return 0


def get(port: int, path: str, timeout: float = 4.0) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def ensure_schema(environ: Mapping[str, str]) -> bool:
    """Up's sole implicit load: verified installation, absent namespace, owner role."""
    from commands.load_release import _connect
    from eii_product.store.loader import perform

    env = read_environment(environ)
    verify_peers(env)
    request = request_for(env, environ)
    installed(env, request)
    if inspect_schema(env, environ):
        return False
    if env.database is None:
        raise Refusal("postgres_required")
    perform(
        env.release,
        host=env.database[0],
        port=env.database[1],
        database=env.database[2],
        connect=_connect,
    )
    check_stores(env, environ)
    return True


def health_probe(port: int, timeout: float) -> dict[str, Any] | None:
    from eii_product.api.health import Health

    try:
        status, body = get(port, "/health", timeout)
        document = json.loads(body)
        if not isinstance(document, dict):
            raise Refusal("startup_not_ready")
        if status != 200:
            raise Refusal("startup_not_ready")
        health = Health.model_validate(document)
        if (
            health.status != "ok"
            or health.parity != "identical"
            or health.traffic != "simulated"
            or health.model == "live"
            or (health.tiles, health.fonts, health.replays) != ("ok", "ok", "ok")
            or (health.store == "postgres" and health.postgres != "up")
            or (health.store == "embedded" and health.postgres != "not_used")
        ):
            raise Refusal("startup_not_ready")
        return health.model_dump()
    except (OSError, http.client.HTTPException):
        return None
    except ValueError:
        raise Refusal("startup_not_ready") from None


def staging_probe(env: Environment, report: Mapping[str, Any]) -> None:
    staging_home = env.home.parent / "staging"
    state = staging_home / "state"
    route = active_route(state)
    if (
        route is None
        or any(
            route[key] != report[key]
            for key in ("release_id", "code_version", "application_sha256")
        )
        or route["backend_port"] != report["port"]
    ):
        raise Refusal("promotion_evidence_staging")
    identity = read_json(state / "environment.json", "environment_database_conflict")
    staged = Environment(
        "staging",
        staging_home / "releases" / report["release_id"],
        state,
        report["port"],
        (identity["database"][0], identity["database"][1], identity["database"][2]),
    )
    installed(staged, route)
    record = read_json(
        process.process_record(state, report["port"]), "process_identity_mismatch"
    )
    process.require_owned(record, "staging")
    try:
        health = health_probe(report["port"], 4.0)
        if (
            health is None
            or health["release_id"] != report["release_id"]
            or health["status"] != "ok"
        ):
            raise ValueError
        for path in ("/", "/api/release", "/api/layers/parcels"):
            status, body = get(report["port"], path)
            if status != 200:
                raise ValueError
            if (
                path == "/api/release"
                and json.loads(body)["release_id"] != report["release_id"]
            ):
                raise ValueError
    except (OSError, ValueError, KeyError, http.client.HTTPException):
        raise Refusal("promotion_evidence_staging") from None


def public_handover() -> Any:
    """S3-T20 owns supplying this entry; setup never opens a public route."""
    return None


def require_retained(env: Environment, target: Mapping[str, Any] | None) -> None:
    """Verify the retained release and archive before any rollback service."""
    if target is None:
        raise Refusal("rollback_retention_failed")
    retained = Environment(
        env.name,
        env.release.parent / target["release_id"],
        env.state,
        env.port,
        env.database,
    )
    try:
        installed(retained, target)
    except Exception as error:
        raise Refusal(reason(error, "rollback_retention_failed")) from None


def up(environ: Mapping[str, str], *, handover: Any = None) -> dict[str, Any]:
    env = read_environment(environ)
    verify_peers(env)
    raw = request_for(env, environ)
    if handover is None:
        handover = public_handover()
    application, manifest = installed(env, raw)
    check_stores(env, environ)
    child_env = runtime_environment(environ)
    child_env["EII_STORE"] = "postgres"

    def start(
        request: Mapping[str, Any], entry: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        del entry
        port = request["backend_port"]
        path = process.process_record(env.state, port)
        if path.exists():
            record = read_json(path, "process_identity_mismatch")
            if record.get("stopped") is not True:
                process.require_owned(record, env.name)
                if any(
                    record.get(key) != request[key]
                    for key in ("release_id", "application_sha256")
                ):
                    if env.name != "staging":
                        raise Refusal("process_identity_mismatch")
                    process.terminate(record, env.name)
                    atomic_json(path, dict(record, stopped=True))
                else:
                    return record, False
        nonce = "operation-" + secrets.token_hex(16)
        argv = (
            sys.executable,
            "-I",
            "-B",
            "-S",
            "scripts/operations/serve.py",
            "--nonce",
            nonce,
            "--environment",
            env.name,
            "--release-id",
            request["release_id"],
            "--application-sha256",
            request["application_sha256"],
            "--port",
            str(port),
        )
        record = process.launch(
            application,
            path,
            argv,
            child_env,
            environment=env.name,
            nonce=nonce,
            port=port,
            release_id=request["release_id"],
            application_sha256=request["application_sha256"],
        )
        return record, True

    def retire(route: Mapping[str, Any]) -> None:
        path = process.process_record(env.state, route["backend_port"])
        record = read_json(path, "process_identity_mismatch")
        if record.get("stopped") is True:
            return
        process.terminate(record, env.name)
        atomic_json(path, dict(record, stopped=True))

    route = activate(
        env.state,
        raw,
        scope=env,
        evidence_root=env.home,
        features=manifest["features"],
        verify_installation=lambda _: check_stores(env, environ),
        staging_probe=lambda report: staging_probe(env, report),
        retain=lambda target: require_retained(env, target),
        start=start,
        ready=lambda record, _: process.wait_ready(
            cast(dict[str, Any], record), env.name, health_probe
        ),
        stop=lambda record: process.terminate(cast(dict[str, Any], record), env.name),
        retire=retire,
        handover=handover,
    )
    if env.name == "live":
        with operation_lock(env.state):
            path = process.process_record(env.state, 8088)
            spawned_entry = False
            if (
                path.exists()
                and read_json(path, "process_identity_mismatch").get("stopped")
                is not True
            ):
                entry_record = read_json(path, "process_identity_mismatch")
                process.require_owned(entry_record, env.name)
            else:
                nonce = "entry-" + secrets.token_hex(16)
                argv = (
                    sys.executable,
                    "-I",
                    "-B",
                    "-S",
                    "scripts/operations/entry.py",
                    "--nonce",
                    nonce,
                    "--environment",
                    env.name,
                    "--port",
                    "8088",
                )
                entry_record = process.launch(
                    application,
                    path,
                    argv,
                    child_env,
                    environment=env.name,
                    nonce=nonce,
                    port=8088,
                    release_id=raw["release_id"],
                    application_sha256=raw["application_sha256"],
                )
                spawned_entry = True
            # The fixed entry can retain its process while its upstream changes.
            expected = dict(entry_record, release_id=raw["release_id"])
            try:
                process.wait_ready(expected, env.name, health_probe)
            except BaseException:
                if spawned_entry:
                    process.terminate(entry_record, env.name)
                    atomic_json(path, dict(entry_record, stopped=True))
                raise
    return route


def down(environ: Mapping[str, str]) -> None:
    env = read_environment(environ)
    with operation_lock(env.state):
        process.down(env.state, env.name)
