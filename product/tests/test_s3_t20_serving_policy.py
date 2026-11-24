"""S3-T20 B4 and B5: the serving policy owns the one assistant key reader and
provider opener, and a hosted service reads no relative busyness."""

import ast
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen

import pytest
from product.tests.public_http_support import Client
from product.tests.test_playbook_lineage_http import frames
from product.tests.test_selected_area_playbook import BASE, request_for
from product.tests.test_selected_area_playbook import capture as capture
from product.tests.test_tools_http import CardStore

from eii_product.api.app import create_app
from eii_product.api.startup import ServingPolicy
from eii_product.ledger.local import LocalLedger
from eii_product.store.startup import StartupRefusal

SRC = Path(__file__).parents[1] / "src/eii_product"
PAID = "remote_paid_assistant_refused"
VENUE = "/api/tools/venue_busyness"
ENVIRONMENTS = ("development", "staging", "live")
HOSTED = ("staging", "live")
# BE-94: the keys of one log line.
LOG_KEYS = {
    "ts",
    "level",
    "event",
    "answer_id",
    "seat_key",
    "tool",
    "engine",
    "release_id",
    "status",
    "duration_ms",
    "error_code",
    "error_id",
}

# Source guard vocabulary.
ENVIRONMENT_READS = {"environ", "environb", "getenv", "getenvb"}
OPENERS = {"socket", "ssl", "http", "urllib", "httpx", "httpx2", "requests", "aiohttp"}
ANSWER_PATH = ("assistant/", "api/answers.py", "api/playbooks.py", "api/startup.py")
# The environment readers of config.py at this base: the SHA-256 of their sorted
# names, one per line. None of them is an assistant key reader.
CONFIG_READERS_SHA256 = (
    "9e73c04bd1f66b1852d81dba3a84c7054f9d655592b6921fd0111cbed4c462cf"
)
TOOLS = "tools/public_context_tools.py"
BUSYNESS_READS = {"venue_busyness_rows", "venue_busyness_places", "pub_venue_busyness"}
# The one reader, and the parity registry's list of the query names it owns.
BUSYNESS_OWNERS = {
    (TOOLS, "venue"),
    ("tools/registry.py", "public_card_descriptors"),
}
CAPABILITY = "'busyness' in context.hosting_off"


class CountingStore(CardStore):
    """The cards fixture as a served store that counts each relative-busyness read."""

    def __init__(self):
        super().__init__()
        self.busyness_reads = 0

    def fetch(self, query, params):
        if "venue_busyness" in query.name or "pub_venue_busyness" in params.values():
            self.busyness_reads += 1
        return super().fetch(query, params)


class Plant:
    """A planted model writer: it asks the policy for a key, or for a provider call."""

    def __init__(self, url):
        self.url, self.mode, self.calls = url, "idle", 0

    def __call__(self, key, opener, bundle, definition, catalogue):
        self.calls += 1
        if self.mode == "key":
            key()
        if self.mode == "call":
            opener(Request(self.url), timeout=1.0)
        return None


@pytest.fixture
def provider():
    """An invented provider on the loopback. It only counts what reaches it."""
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            del args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(
            url=f"http://127.0.0.1:{server.server_port}/v1/invented", hits=hits
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def plant(provider):
    return Plant(provider.url)


@pytest.fixture
def service(request, tmp_path, plant):
    """The real factory over the cards fixture, under the policy a test names.

    The parameter is ``(environment, planted)``; without one no policy is given.
    """
    environment, planted = getattr(request, "param", (None, False))
    store = CountingStore()
    ledger = LocalLedger(tmp_path / "ledger.sqlite")
    policy = (
        None
        if environment is None
        else ServingPolicy(
            environment,
            store.release_id,
            lambda: None,
            writer=plant if planted else None,
        )
    )
    app = create_app(
        Path("product/tests/fixtures/tiles"),
        store=store,
        ledger=ledger,
        fc_setting_reader=lambda: None,
        startup_policy=policy,
    )
    yield Client(app), ledger, store, policy
    ledger.close()


def under(*cases):
    return pytest.mark.parametrize(
        "service", cases, indirect=True, ids=[str(case) for case in cases]
    )


def answer(client, capsys):
    """One real playbook request: frame kinds, writers and logged assistant refusals."""
    capsys.readouterr()
    started = client.post(
        "/api/playbooks/site_check", json={**BASE, **request_for(client, "polygon")}
    )
    assert started.status_code == 202
    sent = frames(client, started)
    logged = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    return SimpleNamespace(
        kinds=[kind for kind, _ in sent],
        writers=[data["writer"] for kind, data in sent if kind == "status"],
        refused=[row for row in logged if row["event"] == "assistant_refused"],
    )


def assert_template_answer(result):
    assert "done" in result.kinds and "error" not in result.kinds
    assert result.writers == ["template"]


def assert_refused_before_the_provider(capture, plant, provider, capsys, mode):
    client, *_ = capture
    plant.mode = mode
    result = answer(client, capsys)
    assert plant.calls == 1
    assert [row["error_code"] for row in result.refused] == [PAID]
    assert set(result.refused[0]) == LOG_KEYS
    assert result.refused[0]["status"] == "fallback"
    assert provider.hits == []
    assert_template_answer(result)
    # The fixture does count a request that reaches it.
    urlopen(provider.url, timeout=5).close()
    assert provider.hits == ["/v1/invented"]


@under(*((name, True) for name in ENVIRONMENTS))
def test_planted_provider_key_read_refused(capture, plant, provider, capsys):
    assert_refused_before_the_provider(capture, plant, provider, capsys, "key")


@under(*((name, True) for name in ENVIRONMENTS))
def test_planted_paid_call_refused(capture, plant, provider, capsys):
    assert_refused_before_the_provider(capture, plant, provider, capsys, "call")


@under(("live", True), ("live", False), (None, False))
def test_a_writer_that_asks_for_nothing_logs_no_refusal(capture, plant, capsys):
    client, _ledger, _store, policy, _bundles = capture
    result = answer(client, capsys)
    assert result.refused == []
    assert plant.calls == (0 if policy is None or policy.writer is None else 1)
    assert_template_answer(result)


@pytest.mark.parametrize("environment", ENVIRONMENTS)
def test_policy_key_reader_and_opener_refuse_in_every_environment(environment):
    policy = ServingPolicy(environment, "ab" * 32, lambda: None)
    with pytest.raises(StartupRefusal, match=f"^{PAID}$"):
        policy.assistant_key()
    with pytest.raises(StartupRefusal, match=f"^{PAID}$"):
        policy.assistant_open(Request("http://provider.invalid/v1"), timeout=1.0)


def test_only_the_paid_refusal_falls_back_to_the_template(capsys):
    def other(*_):
        raise StartupRefusal("startup_parity_failed")

    policy = ServingPolicy("live", "ab" * 32, lambda: None, writer=other)
    with pytest.raises(StartupRefusal, match=r"^startup_parity_failed$"):
        policy.candidate(None, None, None)
    assert "assistant_refused" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "environment,off",
    [("development", set()), *((name, {"busyness", "weather"}) for name in HOSTED)],
)
def test_hosting_off_follows_the_environment(environment, off):
    assert ServingPolicy(environment, "ab" * 32, lambda: None).hosting_off() == off


@under(*((name, False) for name in HOSTED))
@pytest.mark.parametrize("place", ["INVENTED-venue-a", "INVENTED-unknown"])
def test_hosted_tool_request_reads_no_busyness(service, place):
    client, ledger, store, _policy = service
    response = client.post(VENUE, json={"place_keys": [place]})
    body = response.json()
    assert response.status_code == 200
    assert (body["status"], body["facts"], body["payload"]) == (
        "OUT_OF_SCOPE",
        [],
        None,
    )
    assert body["caveat_keys"] == ["hosting_off_source"]
    assert store.busyness_reads == 0
    assert len(ledger.rows()) == 1


@under((None, False), ("development", False))
def test_development_keeps_its_busyness_card(service):
    client, _ledger, store, _policy = service
    body = client.post(VENUE, json={"place_keys": ["INVENTED-venue-a"]}).json()
    assert body["status"] == "OK" and len(body["facts"]) == 167
    assert "hosting_off_source" not in body["caveat_keys"]
    assert store.busyness_reads > 0


@under(*((name, False) for name in HOSTED))
def test_hosted_playbook_request_reads_no_busyness(capture, capsys):
    client, _ledger, store, _policy, bundles = capture
    assert_template_answer(answer(client, capsys))
    assert store.busyness_reads == 0
    assert all(card["kind"] != "venue_busyness" for card in bundles[-1].cards)


def scoped(tree):
    """Each node with the name of its top-level definition, or ``<module>``."""
    for top in tree.body:
        scope = getattr(top, "name", "<module>")
        for node in ast.walk(top):
            yield scope, node


def imported(node):
    """The modules and the names an import statement binds."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names], set()
    if isinstance(node, ast.ImportFrom):
        return [node.module or ""], {alias.name for alias in node.names}
    return [], set()


def key_and_opener_violations(tree, name):
    found = set()
    on_answer_path = name.startswith(ANSWER_PATH)
    readers = set()
    for scope, node in scoped(tree):
        modules, names = imported(node)
        reads = (
            isinstance(node, ast.Attribute) and node.attr in ENVIRONMENT_READS
        ) or (modules == ["os"] and bool(names & (ENVIRONMENT_READS | {"*"})))
        if reads:
            readers.add(scope)
            if name != "config.py":
                found.add("second_key_reader")
        if on_answer_path and any(m.split(".")[0] in OPENERS for m in modules):
            found.add("second_provider_opener")
        if (
            on_answer_path
            and "eii_product.config" in modules
            and names != {"ConfigError"}
        ):
            found.add("second_key_reader")
    digest = hashlib.sha256("\n".join(sorted(readers)).encode()).hexdigest()
    if name == "config.py" and digest != CONFIG_READERS_SHA256:
        found.add("second_key_reader")
    return found


def busyness_violations(tree, name):
    found = set()
    for scope, node in scoped(tree):
        if (
            isinstance(node, ast.Constant)
            and node.value in BUSYNESS_READS
            and (name, scope) not in BUSYNESS_OWNERS
        ):
            found.add("unguarded_busyness_read")
        _modules, names = imported(node)
        if "venue" in names or (
            isinstance(node, ast.Attribute) and node.attr == "venue"
        ):
            found.add("unguarded_busyness_read")
    if name != TOOLS:
        return found
    guarded = 0
    for node in ast.walk(tree):
        for block in (getattr(node, "body", None), getattr(node, "orelse", None)):
            if not isinstance(block, list):
                continue
            for before, statement in zip([None, *block], block, strict=False):
                if not isinstance(statement, ast.Return) or not calls_venue(statement):
                    continue
                guarded += 1
                if not (
                    isinstance(before, ast.If)
                    and ast.unparse(before.test) == CAPABILITY
                    and isinstance(before.body[-1], ast.Return)
                    and not calls_venue(before)
                ):
                    found.add("unguarded_busyness_read")
    if calls_venue(tree) != guarded or guarded != 1:
        found.add("unguarded_busyness_read")
    return found


def calls_venue(node):
    """How many calls of the one busyness reader a node holds."""
    return sum(
        isinstance(inner, ast.Call)
        and isinstance(inner.func, ast.Name)
        and inner.func.id == "venue"
        for inner in ast.walk(node)
    )


def violations(text, name):
    """Closed codes for one product source, named by its path under the package."""
    tree = ast.parse(text)
    return key_and_opener_violations(tree, name) | busyness_violations(tree, name)


def source(name):
    return (SRC / name).read_text(encoding="utf-8")


def test_product_sources_keep_one_key_reader_one_opener_and_one_guarded_read():
    for path in sorted(SRC.rglob("*.py")):
        name = path.relative_to(SRC).as_posix()
        assert violations(path.read_text(encoding="utf-8"), name) == set(), name


PLANTS = [
    ("assistant/invented.py", "import os\nkey = os.environ['X']", "second_key_reader"),
    ("tools/invented.py", "import os\nkey = os.getenv('X')", "second_key_reader"),
    ("api/answers.py", "from os import getenv", "second_key_reader"),
    ("api/playbooks.py", "from os import *", "second_key_reader"),
    (
        "api/playbooks.py",
        "from eii_product.config import read_invented_key",
        "second_key_reader",
    ),
    ("assistant/invented.py", "import eii_product.config", "second_key_reader"),
    (
        "assistant/invented.py",
        "from urllib.request import urlopen",
        "second_provider_opener",
    ),
    ("api/startup.py", "import socket", "second_provider_opener"),
    ("api/answers.py", "import http.client", "second_provider_opener"),
    (
        "tools/invented.py",
        "rows = read(store, 'venue_busyness_rows')",
        "unguarded_busyness_read",
    ),
    (
        "api/tools.py",
        "from eii_product.tools.public_context_tools import venue",
        "unguarded_busyness_read",
    ),
    ("api/tools.py", "cards = public_context_tools.venue", "unguarded_busyness_read"),
]


@pytest.mark.parametrize("name,text,code", PLANTS)
def test_source_guard_plants(name, text, code):
    assert violations(text, name) == {code}


def test_source_guard_plants_in_the_real_sources():
    tools, config = source(TOOLS), source("config.py")
    reader = "\n\ndef read_invented_assistant_key():\n    return os.environ.get('X')\n"
    peek = "\n\ndef peek(store):\n    return read(store, 'venue_busyness_places')\n"
    second = "\n\ndef peek(store, args):\n    return venue(store, args)\n"
    unguarded = tools.replace('if "busyness" in context.hosting_off:', "if False:")
    assert unguarded != tools
    for name, text, code in (
        ("config.py", config + reader, "second_key_reader"),
        (TOOLS, tools + peek, "unguarded_busyness_read"),
        (TOOLS, unguarded, "unguarded_busyness_read"),
        (TOOLS, tools + second, "unguarded_busyness_read"),
    ):
        assert violations(text, name) == {code}, (name, code)
