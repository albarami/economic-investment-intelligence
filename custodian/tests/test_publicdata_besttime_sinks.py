"""TST-237 temporary-cache sentinel and per-sink invented secret plants."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.test_publicdata_besttime_build import run, setup
from custodian.tests.test_publicdata_besttime_parse import forecast, query

from eii_custodian.publicdata.busyness.security import assert_clean


@pytest.mark.parametrize(
    "sink",
    [
        "log",
        "receipt",
        "error",
        "exception",
        "cache-name",
        "fixture",
        "written-file",
        "redirect",
        "header",
        "answer-field",
    ],
)
def test_besttime_secret_sink_plants(sink):
    secret = "SYN-" + "invented-private"
    address = (
        "https://besttime.app/api/v1/forecasts" + "?" + "api_key_private=" + secret
    )
    with pytest.raises(ValueError, match="secret_in_output"):
        assert_clean({"BESTTIME_API_KEY_PRIVATE": secret}, {sink: address})
    assert_clean(
        {"BESTTIME_API_KEY_PRIVATE": secret},
        {sink: "https://besttime.app/api/v1/forecasts"},
    )


def test_besttime_echoes_and_extra_fields_never_reach_cache(tmp_path):
    entry, review, cache, env = setup(tmp_path)
    first, second = forecast(), query()
    for answer in (first, second):
        answer["request_url"] = (
            "https://besttime.app/api/v1/forecasts"
            + "?api_key_private="
            + env["BESTTIME_API_KEY_PRIVATE"]
        )
        answer["unknown_field"] = env["BESTTIME_API_KEY_PRIVATE"]
        answer["nested"] = {"another_api_key": env["BESTTIME_API_KEY_PRIVATE"]}
    _, rows, manifest, _ = run(entry, review, cache, env, [first, second])
    assert "unknown_field" not in rows[0]
    assert_clean(env, manifest)
    files = tuple(
        path for path in sorted((cache / "busy_besttime").rglob("*")) if path.is_file()
    )
    assert files
    assert all("request_url" not in path.read_text() for path in files)


def sentinel_hits(files, sentinel):
    return tuple(name for name, body in files.items() if sentinel in body)


def test_besttime_temporary_cache_sentinel_and_planted_fixture(tmp_path):
    root = repository_root(Path(__file__))
    sentinel = ("SYN-busyness-" + uuid4().hex).encode()
    cache = tmp_path / "public_cache"
    cache.mkdir()
    (cache / "invented-value.json").write_bytes(sentinel)
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    files = {
        name: (root / name).read_bytes()
        for name in listed.decode().split("\0")
        if name and (root / name).is_file()
    }
    assert sentinel_hits(files, sentinel) == ()
    files["planted-fixture.json"] = json.dumps(
        {"busyness_index": sentinel.decode()}
    ).encode()
    assert sentinel_hits(files, sentinel) == ("planted-fixture.json",)


@pytest.mark.parametrize("parameter", ["api_key_private", "api_key_public"])
def test_besttime_keyed_address_refused_even_without_environment(parameter):
    with pytest.raises(ValueError):
        assert_clean(
            {}, "https://besttime.app/api/v1/forecasts?" + parameter + "=SYN-invented"
        )


@pytest.mark.parametrize(
    "sink",
    [
        "log",
        "receipt",
        "error",
        "exception",
        "cache-name",
        "fixture",
        "written-file",
        "header",
        "answer-field",
    ],
)
def test_besttime_bare_secret_refused_in_each_sink(sink):
    with pytest.raises(ValueError):
        assert_clean(
            {"BESTTIME_API_KEY_PUBLIC": "SYN-bare-invented"},
            {sink: "SYN-bare-invented"},
        )
