"""S3-P10: live and staging read the financial-centre register through one setting."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import io
import json
import logging
import os
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import s3_t28_support  # noqa: F401  (puts scripts, core and product on the path)
from hypothesis import given, settings
from hypothesis import strategies as st

from eii_product.api.app import create_app
from eii_product.config import ConfigError, read_fc_register_file
from eii_product.register_file import RegisterRefusal, read_fc_register_rows
from operations.common import Refusal
from operations.config import (
    API_NAMES,
    ENVIRONMENT_NAMES,
    RESTRICTED,
    fc_setting_reader,
    runtime_environment,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "product/tests/fixtures/fc_register/stand_in_register.json"
NAME = "EII_FC_REGISTER_FILE"
ROUTE = "/api/layers/fc_firms_per_tower"
SERVED = ("live", "staging")


def _listed(path: Path) -> Callable[[object], str]:
    """A store-free stand-in for the release's listed hash (L-1509)."""

    def reader(_store: object) -> str:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return "0" * 64

    return reader


def _get(app: object, path: str) -> tuple[int, bytes]:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 80),
    }
    asyncio.run(app(scope, receive, send))  # type: ignore[operator]
    start = next(item for item in sent if item["type"] == "http.response.start")
    body = b"".join(
        chunk
        for item in sent
        if item["type"] == "http.response.body"
        and isinstance(chunk := item.get("body"), bytes)
    )
    return int(start["status"]), body  # type: ignore[call-overload]


class Names(unittest.TestCase):
    def test_served_environments_pass_exactly_the_one_name(self) -> None:
        for name in SERVED:
            with self.subTest(name=name):
                self.assertEqual(ENVIRONMENT_NAMES[name], frozenset({NAME}))
                child = runtime_environment(
                    {"EII_ENVIRONMENT": name, NAME: "/invented/register.json"}
                )
                self.assertEqual(child[NAME], "/invented/register.json")
        self.assertNotIn(NAME, API_NAMES)

    def test_development_keeps_refusing_the_name(self) -> None:
        for environ in ({}, {"EII_ENVIRONMENT": "development"}):
            with (
                self.subTest(environ=environ),
                self.assertRaisesRegex(Refusal, "^unwanted_runtime_setting$"),
            ):
                runtime_environment({**environ, NAME: "/invented/register.json"})

    def test_unknown_environment_gets_no_extra_name(self) -> None:
        with self.assertRaisesRegex(Refusal, "^unwanted_runtime_setting$"):
            runtime_environment(
                {"EII_ENVIRONMENT": "INVENTED", NAME: "/invented/register.json"}
            )

    def test_planted_other_eii_name_is_refused_in_every_environment(self) -> None:
        for name in ("development", *SERVED):
            for planted in (
                "EII_PLANTED_OTHER",
                "EII_REGISTER_FILE",
                "EII_FC_REGISTER",
            ):
                with (
                    self.subTest(name=name, planted=planted),
                    self.assertRaisesRegex(Refusal, "^unwanted_runtime_setting$"),
                ):
                    runtime_environment({"EII_ENVIRONMENT": name, planted: "x"})

    def test_restricted_keys_stay_refused_beside_the_name(self) -> None:
        for name in SERVED:
            for key in sorted(RESTRICTED):
                with (
                    self.subTest(name=name, key=key),
                    self.assertRaisesRegex(Refusal, "^unwanted_runtime_setting$"),
                ):
                    runtime_environment(
                        {"EII_ENVIRONMENT": name, NAME: "/invented/r.json", key: "x"}
                    )

    @settings(max_examples=200, deadline=None)
    @given(
        st.sampled_from(("development", "staging", "live", "")),
        st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ_", min_size=1, max_size=20),
    )
    def test_property_only_listed_eii_names_pass(self, name: str, suffix: str) -> None:
        key = "EII_" + suffix
        allowed = API_NAMES | ENVIRONMENT_NAMES.get(name or "development", frozenset())
        environ = {"EII_ENVIRONMENT": name, key: "x"} if name else {key: "x"}
        if key in allowed:
            if key in {"EII_ENVIRONMENT"}:
                return
            try:
                runtime_environment(environ)
            except Refusal as refusal:
                self.assertNotEqual(str(refusal), "unwanted_runtime_setting")
        else:
            with self.assertRaisesRegex(Refusal, "^unwanted_runtime_setting$"):
                runtime_environment(environ)


class Served(unittest.TestCase):
    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)
        self.tiles = self.root / "tiles"
        self.tiles.mkdir()
        self.copy = self.root / "INVENTED-secret-place" / "stand_in_register.json"
        self.copy.parent.mkdir()
        self.copy.write_bytes(FIXTURE.read_bytes())

    def _child(self, name: str, path: str) -> dict[str, str]:
        return runtime_environment({"EII_ENVIRONMENT": name, NAME: path})

    def test_reader_per_environment(self) -> None:
        for name in SERVED:
            self.assertIs(fc_setting_reader(name), read_fc_register_file)
        with patch.dict(os.environ, {NAME: str(self.copy)}):
            self.assertIsNone(fc_setting_reader("development")())

    def test_served_app_with_stand_in_returns_towers(self) -> None:
        for name in SERVED:
            with (
                self.subTest(name=name),
                patch.dict(os.environ, self._child(name, str(self.copy)), clear=True),
            ):
                app = create_app(
                    self.tiles,
                    fc_setting_reader=fc_setting_reader(name),
                    fc_listed_reader=_listed(self.copy),
                )
                status, raw = _get(app, ROUTE)
                body = json.loads(raw)
                self.assertEqual(status, 200)
                self.assertEqual(body["status"], "ok")
                features = body["payload"]["layers"][0]["features"]
                self.assertTrue(features)
                self.assertNotIn(str(self.copy).encode(), raw)
                self.assertNotIn(b"INVENTED-secret-place", raw)

    def test_unset_setting_gives_no_data_with_reason(self) -> None:
        for name in SERVED:
            environ = runtime_environment({"EII_ENVIRONMENT": name})
            with self.subTest(name=name), patch.dict(os.environ, environ, clear=True):
                app = create_app(self.tiles, fc_setting_reader=fc_setting_reader(name))
                status, raw = _get(app, ROUTE)
                self.assertEqual(status, 200)
                self.assertEqual(
                    json.loads(raw),
                    {"status": "NO_DATA", "reason": "missing_input", "facts": []},
                )

    def test_planted_other_path_is_refused(self) -> None:
        other = self.root / "other.json"
        other.write_bytes(FIXTURE.read_bytes())
        with patch.dict(os.environ, self._child("live", str(self.copy)), clear=True):
            setting = fc_setting_reader("live")()
            with self.assertRaises(RegisterRefusal) as caught:
                read_fc_register_rows(
                    setting, listed_sha256="0" * 64, asked_path=str(other)
                )
        self.assertEqual(caught.exception.reason, "path_refused")

    def test_path_is_never_printed_or_logged(self) -> None:
        missing = self.root / "INVENTED-secret-place" / "absent.json"
        broken = self.root / "INVENTED-secret-place" / "broken.json"
        broken.write_text("{", encoding="utf-8")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        old_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)
        self.addCleanup(root_logger.removeHandler, handler)
        self.addCleanup(root_logger.setLevel, old_level)
        out, err = io.StringIO(), io.StringIO()
        messages: list[str] = []
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            for path, error, reason in (
                (missing, ConfigError, NAME),
                (broken, RegisterRefusal, "register_json_invalid"),
            ):
                environ = self._child("staging", str(path))
                with patch.dict(os.environ, environ, clear=True):
                    with self.assertRaises(error) as caught:
                        create_app(
                            self.tiles,
                            fc_setting_reader=fc_setting_reader("staging"),
                            fc_listed_reader=_listed(path),
                        )
                self.assertEqual(str(caught.exception), reason)
                messages.append(repr(caught.exception))
                messages.append(str(caught.exception.__context__))
                messages.append(str(caught.exception.__cause__))
            with patch.dict(os.environ, {NAME: str(self.copy) + "\n"}, clear=True):
                with self.assertRaises(ConfigError) as bad:
                    read_fc_register_file()
            messages.append(repr(bad.exception))
        captured = "\n".join(
            [stream.getvalue(), out.getvalue(), err.getvalue(), *messages]
        )
        self.assertNotIn("INVENTED-secret-place", captured)
        self.assertNotIn(str(self.root), captured)


if __name__ == "__main__":
    unittest.main()
