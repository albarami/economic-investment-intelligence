"""Embedded foreground construction contacts neither PostgreSQL nor Docker."""

import builtins
import shutil

from product.tests.public_http_support import Client
from product.tests.test_mounted_release_http import loaded as loaded

from operations.development import serve_embedded


def test_explicit_embedded_serves_checked_release_without_postgres(
    loaded, tmp_path, monkeypatch
):
    source, identity, _ = loaded
    home = tmp_path / "development"
    target = home / "releases" / identity
    target.parent.mkdir(parents=True)
    shutil.copytree(source, target)
    attempts = []
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] == "psycopg":
            attempts.append(name)
            raise AssertionError("INVENTED-postgres-import")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    calls = []

    def server(app, **options):
        calls.append(options)
        response = Client(app).get("/api/release")
        assert response.status_code == 200
        assert response.json()["release_id"] == identity

    serve_embedded(
        tmp_path,
        dict(
            EII_ENVIRONMENT="development",
            EII_RELEASE_DIR=str(target),
            EII_STATE_DIR=str(home / "state"),
        ),
        server=server,
    )
    assert calls == [
        dict(host="127.0.0.1", port=8000, access_log=False, log_config=None)
    ]
    assert attempts == []
    assert (home / "state/local-ledger.sqlite").is_file()
    assert not (home / "state/photoreal-count.log").exists()
