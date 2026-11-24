"""Both operational entry points mount the checked, invented tile extract."""

import json
from importlib import import_module
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from platform import python_version
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

import pytest
from public_release_fixture import build_fixture
from routing_release_fixture import TILES, invented_extract
from test_live_public_release_load import embedded_fixture_store

from eii_product.assistant.playbooks.engine import execute
from eii_product.assistant.playbooks.models import Bundle
from operations.development import serve_embedded


@pytest.fixture
def runtime_application(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from operations import serve

    (tmp_path / "application.json").write_text(
        json.dumps(dict(python_version=python_version()))
    )
    (tmp_path / "runtime").mkdir()
    (tmp_path / "runtime/dependencies.json").write_text(
        json.dumps(dict(packages={"pyvalhalla": "3.9.1"}))
    )
    monkeypatch.setattr(serve, "APPLICATION_ROOT", tmp_path)


@pytest.mark.parametrize("state", ["pinned", "mismatch", "missing"])
def test_runtime_dependency_version(
    runtime_application: None, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    from operations import serve
    from operations.common import Refusal

    lookup = Mock(return_value="INVENTED-version" if state == "mismatch" else "3.9.1")
    if state == "missing":
        lookup.side_effect = PackageNotFoundError("pyvalhalla")
    metadata = SimpleNamespace(
        version=lookup, PackageNotFoundError=PackageNotFoundError
    )
    monkeypatch.setattr(serve, "importlib", SimpleNamespace(metadata=metadata))
    if state == "pinned":
        serve.verify_runtime()
    else:
        with pytest.raises(Refusal, match=r"^offline_dependency_missing$"):
            serve.verify_runtime()
    lookup.assert_called_once_with("pyvalhalla")


@pytest.mark.parametrize(
    ("fault", "reason"),
    [
        ("python", "offline_python_mismatch"),
        ("application.json", "application_verification_failed"),
        ("runtime/dependencies.json", "offline_dependency_missing"),
    ],
)
def test_runtime_refuses_its_specific_precondition(
    runtime_application: None, tmp_path: Path, fault: str, reason: str
) -> None:
    from operations import serve
    from operations.common import Refusal

    if fault == "python":
        (tmp_path / "application.json").write_text(
            json.dumps(dict(python_version="INVENTED-version"))
        )
    else:
        (tmp_path / fault).unlink()
    with pytest.raises(Refusal, match="^" + reason + "$"):
        serve.verify_runtime()


@pytest.fixture
def routed_release(tmp_path: Path) -> tuple[Path, str]:
    folder = tmp_path / "development/releases/INVENTED-release"
    reference = invented_extract(folder / TILES)
    identity = build_fixture(folder, cards=True, artefacts=(reference,))
    target = folder.with_name(identity)
    folder.rename(target)
    embedded_fixture_store(target, identity).close()
    return target, identity


def check_routes(app: Any) -> None:
    client = import_module("product.tests.public_http_support").Client(app)
    bundles: list[Bundle] = []

    def record(*args: Any, **kwargs: Any) -> Bundle:
        bundle = execute(*args, **kwargs)
        bundles.append(bundle)
        return bundle

    failures = []
    for mode, cutoff in (("walk", 5), ("drive", 10)):
        response = client.post(
            "/api/tools/make_area",
            json=dict(latitude=1, longitude=1, mode=mode, cutoff=cutoff),
        )
        if response.status_code != 200 or response.json()["status"] != "OK":
            failures.append(
                ("make_area", mode, cutoff, response.status_code, response.text)
            )
        with patch("eii_product.api.playbooks.execute", side_effect=record):
            response = client.post(
                "/api/playbooks/site_check",
                json=dict(
                    activity="INVENTED-activity",
                    pin=dict(lat=1, lon=1),
                    mode=mode,
                    cutoff=cutoff,
                ),
            )
        if response.status_code != 202:
            failures.append(
                ("site_check", mode, cutoff, response.status_code, response.text)
            )
        else:
            steps = {step["key"]: step for step in bundles[-1].steps}
            assert steps["near"]["status"] == "OK"
            assert steps["wider"]["status"] == "OK"
    for failure in failures:
        print("routing_baseline", failure[:4], json.loads(failure[4])["error"]["code"])
    assert not failures, failures


def test_development_serves_routing(
    routed_release: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _identity = routed_release
    serve_embedded(
        tmp_path,
        dict(
            EII_ENVIRONMENT="development",
            EII_RELEASE_DIR=str(folder),
            EII_STATE_DIR=str(tmp_path / "development/state"),
        ),
        server=lambda app, **kw: check_routes(app),
    )


def test_installed_serve_passes_routing(
    routed_release: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from operations import serve

    folder, identity = routed_release
    env = SimpleNamespace(
        name="development", release=folder, state=tmp_path / "state", home=tmp_path
    )
    request = dict(release_id=identity, application_sha256="ab" * 32, backend_port=8000)
    monkeypatch.setattr(serve, "APPLICATION_ROOT", tmp_path)
    monkeypatch.setattr(serve, "verify_runtime", lambda: None)
    monkeypatch.setattr("operations.config.read_environment", lambda *a: env)
    monkeypatch.setattr(
        "operations.config.persistent_paths",
        lambda e: (tmp_path / "ledger.sqlite", tmp_path / "count.log"),
    )
    monkeypatch.setattr("operations.deploy.request_for", lambda *a: request)
    monkeypatch.setattr("operations.evidence.exposure", lambda *a: None)
    monkeypatch.setattr(
        "operations.runtime.installed", lambda *a: (tmp_path, dict(features=[]))
    )
    monkeypatch.setattr(
        "operations.activation.entries", lambda *a: [dict(request=request)]
    )
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: check_routes(app))
    monkeypatch.setenv("EII_STORE", "embedded")
    monkeypatch.setattr(
        "sys.argv",
        [
            "serve",
            "--release-id",
            identity,
            "--application-sha256",
            "ab" * 32,
            "--port",
            "8000",
        ],
    )
    assert serve.main() == 0
