"""Built bundle on the real API, disposable loaded invented tables, no API mocks."""

import os
import socket
import subprocess
import threading
import time
from pathlib import Path

from product.tests import map_assets
from product.tests.test_mounted_release_http import loaded as loaded
from uvicorn import Config, Server

from eii_product.api.app import create_app
from eii_product.api.startup import developer_policy
from eii_product.ledger.local import LocalLedger
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.registry import PACKAGED


def test_built_browser_uses_mounted_http(loaded, tmp_path):
    folder, identity, _ = loaded
    store = EmbeddedStore(folder / "release.duckdb", identity, PACKAGED)
    ledger = LocalLedger(tmp_path / "browser-ledger.sqlite")
    fonts = tmp_path / "fonts"
    map_assets.write_assets(tmp_path / "tiles", fonts)
    server = None
    thread = None
    try:
        app = create_app(
            Path("product/tests/fixtures/tiles"),
            store=store,
            ledger=ledger,
            release_dir=folder,
            startup_policy=developer_policy(folder),
            web_dir=Path("web/dist"),
            font_dir=fonts,
            fc_setting_reader=lambda: None,
            key_reader=lambda: None,
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = Server(
            Config(
                app, host="127.0.0.1", port=port, log_level="error", access_log=False
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        result = subprocess.run(
            ["node", "tests/audit/mounted-release.mjs"],
            cwd="web",
            env={
                **os.environ,
                "EII_TEST_ORIGIN": f"http://127.0.0.1:{port}",
                "PLAYWRIGHT_BROWSERS_PATH": str(
                    Path("data/tools/playwright").resolve()
                ),
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "PASS mounted-browser: en/ar dark/light" in result.stdout
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=10)
            assert not thread.is_alive()
        ledger.close()
        store.close()
