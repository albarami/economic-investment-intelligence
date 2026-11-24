"""Direct ASGI requests, matching existing HTTP tests without a new dependency."""

import asyncio
import json
from http.cookies import SimpleCookie
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit


class Client:
    def __init__(self, app):
        self.app = app
        self.cookies = {}

    def get(self, path, headers=None):
        return self.request("GET", path, headers=headers)

    def post(self, path, *, json=None, content=None, headers=None):
        encoded = (
            __import__("json").dumps(json).encode() if content is None else content
        )
        return self.request(
            "POST",
            path,
            encoded,
            {"Content-Type": "application/json", **(headers or {})},
        )

    def request(self, method, path, body=b"", headers=None):
        async def run():
            sent = []
            received = False

            async def receive():
                nonlocal received
                if not received:
                    received = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await asyncio.Event().wait()

            async def send(message):
                sent.append(message)

            split = urlsplit(path)
            fields = {key.lower(): value for key, value in (headers or {}).items()}
            if self.cookies:
                fields["cookie"] = "; ".join(
                    f"{k}={v}" for k, v in self.cookies.items()
                )
            scope = dict(
                type="http",
                asgi={"version": "3.0", "spec_version": "2.3"},
                http_version="1.1",
                method=method,
                scheme="http",
                path=unquote(split.path),
                raw_path=split.path.encode(),
                query_string=split.query.encode(),
                root_path="",
                headers=[(k.encode(), v.encode()) for k, v in fields.items()],
                server=("testserver", 80),
                client=("127.0.0.1", 1234),
            )
            await self.app(scope, receive, send)
            start = next(m for m in sent if m["type"] == "http.response.start")
            response_headers = {k.decode(): v.decode() for k, v in start["headers"]}
            for key, value in start["headers"]:
                if key == b"set-cookie":
                    parsed = SimpleCookie(value.decode())
                    self.cookies.update({k: v.value for k, v in parsed.items()})
            content = b"".join(
                m.get("body", b"") for m in sent if m["type"] == "http.response.body"
            )
            return SimpleNamespace(
                status_code=start["status"],
                headers=response_headers,
                content=content,
                text=content.decode(errors="replace"),
                json=lambda: json.loads(content),
            )

        return asyncio.run(run())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


_MANIFEST_COLUMNS = (
    "release_id",
    "table_name",
    "provenance_class",
    "file",
    "sha256",
    "row_count",
    "schema_sha256",
    "release_kind",
    "release_contract_version",
    "build_id",
    "built_at",
    "code_version",
    "rules_version_id",
    "engine_versions",
    "fc_register_sha256",
)


class AreaStore:
    """In-memory projections of the cards fixture, through existing named reads."""

    engine = "embedded"
    release_id = "ab" * 32

    def __init__(self):
        from public_release_fixture import _cards_tables

        self.tables = {table.name: table.rows for table in _cards_tables()}
        # The sealed table list a mounted release reads (public_release_manifest).
        self.tables["release_manifest"] = [
            {
                **dict.fromkeys(_MANIFEST_COLUMNS, "INVENTED"),
                "release_id": self.release_id,
                "table_name": name,
                "row_count": len(rows),
            }
            for name, rows in sorted(self.tables.items())
        ]

    def fetch(self, query, params):
        from eii_product.store.normalise import hold_geometry
        from eii_product.store.protocol import QueryResult

        if query.name == "make_area_municipalities":
            return QueryResult(
                ("municipality_code", "geometry"),
                tuple(
                    (r["municipality_code"], hold_geometry(r["geometry"].hex()))
                    for r in self.tables["municipality"]
                ),
            )
        if query.name == "make_area_grid_cells":
            return QueryResult(
                ("cell", "resolution"),
                tuple(
                    sorted(
                        (r["cell"], r["resolution"]) for r in self.tables["grid_cell"]
                    )
                ),
            )
        raise AssertionError("unexpected named read")
