"""Source-specific refusal plants; all inputs are invented."""

import importlib
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from custodian.tests.test_gravity_atlas_review import CLOCK, acquire, modules, rewrite


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("real opener forbidden")

    monkeypatch.setattr("urllib.request.build_opener", forbidden)


CONFIG_PLANTS = [
    ("confirmed", 1, "configuration_type"),
    ("publisher", 1, "configuration_type"),
    ("publisher", " ", "metadata_missing"),
    ("country_width", True, "configuration_count"),
    ("country_width", 0, "code_width"),
    ("raw_rows", [1], "configuration_bounds"),
    ("raw_rows", [-1, 3], "configuration_bounds"),
    ("raw_rows", [4, 3], "configuration_bounds"),
    ("reviewed_urls", "wrong", "configuration_type"),
    ("measures", "wrong", "configuration_type"),
    ("method_version", "wrong", "method_version"),
    ("config_version", "wrong", "method_version"),
    ("access", "wrong", "access_state"),
    ("access", "unconfirmed", "access_state"),
    ("publisher_mapping", "wrong", "publisher_mapping"),
    ("bound_origin", "wrong", "bounds_origin"),
    ("bound_origin", "pending", "bounds_unconfirmed"),
    ("period_first", 0, "period_bounds"),
    ("period_last", 10000, "period_bounds"),
    ("period_first", 2092, "period_bounds"),
    ("year_selection", "wrong", "year_selection"),
    ("year_selection", "pending", "year_selection"),
    ("page_sha256", "wrong", "page_hash"),
    ("page", "https://www.data.gov.qa/invented-unreviewed", "blocked_host"),
    ("reviewed_urls", ["https://invented.invalid/file"], "blocked_host"),
    ("measures.0.signed", 1, "configuration_type"),
    ("measures.0.total_digits", 0, "decimal_limits"),
    ("measures.0.fractional_digits", -1, "decimal_limits"),
    ("measures.0.fractional_digits", 99, "decimal_limits"),
    ("measures.0.missing", ["NA", "NA"], "missing_tokens"),
    ("measures.0.missing", ["0.0"], "missing_is_zero"),
    ("measures.0.name", "wrong", "measure_fields"),
    ("member.name", "../invented.csv", "member_name"),
    ("member.kind", "wrong", "member_kind"),
    ("member.year", 2091, "member_year"),
    ("member.columns", [], "member_schema"),
    ("member.columns", {"code": "wrong"}, "member_schema"),
    ("member.header", ["wrong"], "member_schema"),
    ("member.sha256", "wrong", "member_checksum"),
    ("member.rows", [False, 3], "configuration_count"),
]


def set_field(raw, path, value, source):
    if path.startswith("member."):
        raw = (
            raw["members"][0]
            if source == "gravity"
            else raw["downloads"][0]["members"][0]
        )
        path = path.removeprefix("member.")
    parts = path.split(".")
    for part in parts[:-1]:
        raw = raw[int(part)] if isinstance(raw, list) else raw[part]
    raw[parts[-1]] = value


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize("field,value,reason", CONFIG_PLANTS)
def test_config_plants(source, field, value, reason):
    m = modules(source)
    raw = m.fixture.configuration()
    set_field(raw, field, value, source)
    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^" + reason + "$"
    ):
        m.config.Config.from_mapping(raw)


@pytest.mark.parametrize("source", ["gravity", "atlas"])
def test_config_helpers_edges(source, tmp_path):
    m = modules(source)
    error = getattr(m.config, source.capitalize() + "Error")
    with pytest.raises(error, match=r"^configuration_fields$"):
        m.config.Config.from_mapping({})
    with pytest.raises(error, match=r"^configuration_unreadable$"):
        m.config.load_config(tmp_path / "missing.yaml")
    assert m.config.bounds([0, 0]) == (0, 0)
    assert m.config.bounds([0, 1]) == (0, 1)
    for width in (1, 2):
        raw = m.fixture.configuration()
        raw["country_width"] = width
        assert m.config.Config.from_mapping(raw).country_width == width
    for first, last in ((1, 1), (9999, 9999), (1, 9999)):
        raw = m.fixture.configuration()
        raw.update(period_first=first, period_last=last)
        assert m.config.Config.from_mapping(raw).period_last == last
    for total, fractional in ((1, 0), (1, 1)):
        raw = m.fixture.configuration()
        raw["measures"][0].update(total_digits=total, fractional_digits=fractional)
        assert (
            m.config.Config.from_mapping(raw).measures[0].fractional_digits
            == fractional
        )


SPECIAL = [
    ("gravity", "members", [], "members"),
    ("gravity", "members", "wrong", "configuration_type"),
    ("gravity", "member_count", [0, 1], "member_count"),
    ("gravity", "flag_tokens", ["0"], "flag_tokens"),
    ("gravity", "flag_missing", ["1"], "missing_is_zero"),
    ("gravity", "flag_missing", ["0.0"], "missing_is_zero"),
    ("gravity", "publisher_sha256", "wrong", "archive_checksum"),
    ("atlas", "downloads", "wrong", "configuration_type"),
    ("atlas", "downloads", [], "download_order"),
    ("atlas", "finished_only", 1, "configuration_type"),
    ("atlas", "finished_only", False, "rebuild_refused"),
    ("atlas", "product_width", 0, "code_width"),
    ("atlas", "downloads.0.grain", "wrong", "rebuild_refused"),
    ("atlas", "downloads.0.members", "wrong", "configuration_type"),
    ("atlas", "downloads.0.member_count", [0, 2], "member_count"),
    ("atlas", "downloads.0.publisher_sha256", "wrong", "archive_checksum"),
    (
        "atlas",
        "downloads.0.url",
        "https://www.data.gov.qa/invented-unreviewed",
        "blocked_host",
    ),
]


@pytest.mark.parametrize("source,field,value,reason", SPECIAL)
def test_source_config_plants(source, field, value, reason):
    m = modules(source)
    raw = m.fixture.configuration()
    set_field(raw, field, value, source)
    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^" + reason + "$"
    ):
        m.config.Config.from_mapping(raw)


ENTRY_PLANTS = [
    ("source_id", "wrong", "source_id"),
    ("key", "wrong", "source_id"),
    ("commit_allowed", True, "registry_policy"),
    ("nightly_live_fetch", False, "registry_policy"),
    ("licence_basis", "wrong", "licence_basis"),
    ("licence_id", "", "licence_basis"),
    ("decision_record", "", "licence_basis"),
    ("terms_read_on", "wrong", "terms_date"),
    ("terms_read_on", "2026" + "1116", "terms_date"),
    ("publisher", "wrong", "publisher"),
    ("title_en", "", "publisher"),
    ("landing_url", "", "page"),
    ("row_count_min", 0, "raw_bounds"),
    ("row_count_max", 99, "raw_bounds"),
    ("period_first", "2090", "period_bounds"),
    ("period_last", "2092", "period_bounds"),
    ("release_tables", (), "release_contract"),
    ("columns", (), "release_contract"),
    ("fetch_host", "invented.invalid", "blocked_host"),
    ("terms_url", "https://www.data.gov.qa/invented-unreviewed", "blocked_host"),
]


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize("field,value,reason", ENTRY_PLANTS)
def test_entry_plants(source, field, value, reason, tmp_path):
    m = modules(source)

    def forbidden(_):
        raise AssertionError("entry failure contacted transport")

    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^" + reason + "$"
    ):
        getattr(m.fetch, "fetch_" + source)(
            replace(m.fixture.entry(), **{field: value}),
            m.config.Config.from_mapping(m.fixture.configuration()),
            forbidden,
            m.fixture.stream,
            tmp_path,
            lambda: CLOCK,
            lambda _: None,
        )
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("source", ["gravity", "atlas"])
def test_pending_terms_state_still_fetches_and_reads(source, tmp_path):
    """Ruling L-1001: pending terms fields never refuse the fetch or the release."""
    m = modules(source)
    row = replace(
        m.fixture.entry(),
        terms_words="terms to be read",
        terms_read_on="pending",
        licence_basis="pending",
        decision_record="",
    )
    result = getattr(m.fetch, "fetch_" + source)(
        row,
        m.config.Config.from_mapping(m.fixture.configuration()),
        m.fixture.metadata,
        m.fixture.stream,
        tmp_path,
        lambda: CLOCK,
        lambda _: None,
    )
    release = m.contracts.read_selected(tmp_path, result.digest)
    if source == "gravity":
        assert len(release.bilateral) == 2
    else:
        assert release.country_product_year
    assert release.manifest["receipt"]["terms_read_on"] == "pending"
    assert release.manifest["receipt"]["licence_basis"] == "pending"
    assert release.manifest["entry"]["terms_words"] == "terms to be read"


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize(
    "case,reason",
    [
        ("metadata", "metadata_changed_review_needed"),
        ("checksum", "archive_checksum"),
        ("stream", "stream_transport_missing"),
        ("clock", "retrieval_date"),
        ("version", "version"),
        ("licence", "licence_words"),
        ("bounds", "bounds_unconfirmed"),
    ],
)
def test_fetch_plants(source, case, reason, tmp_path):
    from eii_custodian.publicdata.fetch.transport import Response

    m = modules(source)
    config = m.config.Config.from_mapping(m.fixture.configuration())
    if case == "checksum":
        if source == "gravity":
            config = replace(config, publisher_sha256="a" * 64)
        else:
            config = replace(
                config,
                downloads=tuple(
                    replace(d, publisher_sha256="a" * 64) for d in config.downloads
                ),
            )
    if case in {"version", "licence", "bounds"}:
        config = replace(
            config,
            **{
                "version": {"source_version": ""},
                "licence": {"licence_words": ""},
                "bounds": {"bound_origin": "pending"},
            }[case],
        )
    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^" + reason + "$"
    ):
        getattr(m.fetch, "fetch_" + source)(
            m.fixture.entry(),
            config,
            (lambda url: Response(url, b"changed invented page", ()))
            if case == "metadata"
            else m.fixture.metadata,
            None if case == "stream" else m.fixture.stream,
            tmp_path,
            lambda: "wrong" if case == "clock" else CLOCK,
            lambda _: None,
        )
    assert not list(tmp_path.rglob("*.manifest.json"))


READER_PLANTS = [
    ("complete", False, "manifest_complete"),
    ("config.confirmed", False, "manifest_configuration"),
    ("config.access", "registration", "manifest_configuration"),
    ("method", "wrong", "lineage"),
    ("attribution", "wrong", "lineage"),
    ("publisher_mapping", "wrong", "publisher_mapping"),
    ("terms_fingerprint_kind", "wrong", "terms_fingerprint"),
    ("receipt.retrieved_utc", "wrong", "selected_manifest_invalid"),
    ("receipt.retrieved_utc", "2026-1-1T00:00:00Z", "retrieval_date"),
    ("receipt.publisher", "wrong", "source_chain"),
    ("receipt.landing_url", "wrong", "source_chain"),
    ("receipt.licence_basis", "wrong", "source_chain"),
    ("receipt.terms_read_on", "wrong", "source_chain"),
    ("receipt.commit_allowed", True, "source_chain"),
    ("receipt.terms_sha256", "wrong", "terms_fingerprint"),
    ("receipt.fetch_host", "unreviewed.invalid", "source_chain"),
    ("receipt.source_modified", "wrong", "source_chain"),
    ("selected", -1, "manifest_content"),
]


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize("field,value,reason", READER_PLANTS)
def test_reader_plants(source, field, value, reason, tmp_path):
    m = modules(source)
    result = acquire(source, tmp_path)
    selected = rewrite(
        tmp_path,
        source,
        result.digest,
        lambda manifest: set_field(manifest, field, value, source),
    )
    before = sorted(tmp_path.rglob("*.manifest.json"))
    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^" + reason + "$"
    ):
        m.contracts.read_selected(tmp_path, selected)
    assert sorted(tmp_path.rglob("*.manifest.json")) == before


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize(
    "case,reason",
    [
        ("selected", "selected_manifest"),
        ("missing", "selected_manifest_invalid"),
        ("manifest", "manifest_hash"),
        ("archive", "archive_hash"),
        ("output", "output_hash"),
        ("structure", "selected_manifest_invalid"),
    ],
)
def test_reader_file_plants(source, case, reason, tmp_path):
    import json

    m = modules(source)
    result = acquire(source, tmp_path)
    selected = result.digest
    directory = tmp_path / m.config.SOURCE_ID
    path = directory / (selected + ".manifest.json")
    manifest = json.loads(path.read_text())
    if case == "selected":
        selected = "wrong"
    elif case == "missing":
        selected = "a" * 64
    elif case == "manifest":
        path.write_text("{}")
    elif case == "structure":
        selected = rewrite(tmp_path, source, selected, lambda item: item.pop("receipt"))
    elif case == "archive":
        next(directory.glob("*.zip")).write_bytes(b"invented corrupt archive")
    else:
        digest = next(iter(manifest["outputs"].values()))["sha256"]
        (directory / (digest + ".jsonl")).write_text("{}\n")
    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^" + reason + "$"
    ):
        m.contracts.read_selected(tmp_path, selected)


def parse_fixture(source, grain, tmp_path, change=None, config_change=None):
    m = modules(source)
    config = m.config.Config.from_mapping(m.fixture.configuration())
    member_sets = (
        [deepcopy(m.fixture.MEMBERS)]
        if source == "gravity"
        else [deepcopy(m.fixture.CPY_MEMBERS), deepcopy(m.fixture.CPP_MEMBERS)]
    )
    members = config.members if source == "gravity" else config.downloads[grain].members
    if change:
        change(member_sets[grain], members)
    if config_change:
        config = config_change(config, members, member_sets[grain])
    parser = importlib.import_module("eii_custodian.publicdata." + source + ".parse")
    tmp_path.mkdir(parents=True, exist_ok=True)
    if source == "gravity":
        path = tmp_path / "invented.zip"
        path.write_bytes(m.fixture.archive(member_sets[0]))
        return parser.parse_archive(path, config, tmp_path / "out")
    paths = {}
    for download, content, zipper in zip(
        config.downloads,
        member_sets,
        (m.fixture.cpy_archive, m.fixture.cpp_archive),
        strict=True,
    ):
        path = tmp_path / (download.grain + ".zip")
        path.write_bytes(zipper(content))
        paths[download.grain] = path
    return parser.parse_archives(paths, config, tmp_path / "out")


GRAINS = [("gravity", 0), ("atlas", 0), ("atlas", 1)]


@pytest.mark.parametrize("source,grain", GRAINS)
@pytest.mark.parametrize(
    "case,reason",
    [
        ("header", "header"),
        ("row", "row_schema"),
        ("key", "dictionary_key"),
        ("description", "dictionary_description"),
        ("qatar", "qatar_key"),
        ("duplicate", "duplicate_trade_key"),
        ("country", "country_key"),
        ("year", "year"),
        ("old", "year"),
        ("future", "stale_period"),
        ("missing_final", "year_coverage"),
        ("inventory", "inventory"),
        ("member_checksum", "member_checksum"),
    ],
)
def test_parse_plants(source, grain, case, reason, tmp_path):
    m = modules(source)

    def change(content, members):
        country, data = members[0].name, members[-1].name
        if case == "header":
            content[data] = "wrong\n" + content[data].split("\n", 1)[1]
        elif case == "row":
            content[data] += "wrong\n"
        elif case == "key":
            content[country] = content[country].replace("00A", "00Q")
        elif case == "description":
            content[country] = content[country].replace("Invented target", " ")
        elif case == "qatar":
            content[country] = content[country].replace("00Q", "00Z")
        elif case == "duplicate":
            content[data] += content[data].splitlines()[1] + "\n"
        elif case == "country":
            content[data] = content[data].replace("00A", "00Z")
        elif case in {"year", "old", "future"}:
            content[data] = content[data].replace(
                "2091", {"year": "0201", "old": "2090", "future": "2092"}[case]
            )
        elif case == "inventory":
            content["invented-renamed.csv"] = content.pop(country)

    def update(config, members, content):
        if case == "missing_final":
            return replace(config, period_first=2090)
        if case == "member_checksum":
            updated = (replace(members[0], sha256="a" * 64), *members[1:])
            if source == "gravity":
                return replace(config, members=updated)
            downloads = list(config.downloads)
            downloads[grain] = replace(downloads[grain], members=updated)
            return replace(config, downloads=tuple(downloads))
        return config

    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^" + reason + "$"
    ):
        parse_fixture(source, grain, tmp_path, change, update)
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("source,grain", GRAINS)
@pytest.mark.parametrize(
    "bound", ["archive", "member_bytes", "member_count", "dictionary", "trade", "raw"]
)
@pytest.mark.parametrize("edge", ["low", "high", "below", "above"])
def test_numeric_edges(source, grain, bound, edge, tmp_path):
    m = modules(source)
    expected = {
        "archive": "archive_bytes",
        "member_bytes": "member_bytes",
        "member_count": "member_count",
        "dictionary": "dictionary_count",
        "trade": "trade_count",
        "raw": "raw_count",
    }[bound]

    def span(n):
        return {
            "low": (n, n + 1),
            "high": (n - 1, n),
            "below": (n + 1, n + 2),
            "above": (n - 2, n - 1),
        }[edge]

    def update(config, members, content):
        target = config if source == "gravity" else config.downloads[grain]
        if bound == "archive":
            zipper = (
                m.fixture.archive
                if source == "gravity"
                else (m.fixture.cpy_archive, m.fixture.cpp_archive)[grain]
            )
            target = replace(target, archive_bytes=span(len(zipper(content))))
        elif bound == "member_count":
            target = replace(target, member_count=span(len(members)))
        elif bound == "raw":
            n = target.raw_rows[0]
            target = replace(target, raw_rows=span(n))
            # The running upper bound intentionally refuses before final raw_count.
        else:
            index = -1 if bound == "trade" else 0
            member = members[index]
            field = "bytes" if bound == "member_bytes" else "rows"
            n = (
                len(content[member.name].encode())
                if field == "bytes"
                else member.rows[0]
            )
            updated = list(members)
            updated[index] = replace(member, **{field: span(n)})
            target = replace(target, members=tuple(updated))
        if source == "gravity":
            return target
        downloads = list(config.downloads)
        downloads[grain] = target
        return replace(config, downloads=tuple(downloads))

    if edge in {"low", "high"}:
        parse_fixture(source, grain, tmp_path, config_change=update)
    else:
        if bound == "raw" and edge == "above":
            expected = "trade_count"
        with pytest.raises(
            getattr(m.config, source.capitalize() + "Error"),
            match=r"^" + expected + "$",
        ):
            parse_fixture(source, grain, tmp_path, config_change=update)
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("grain", [0, 1])
@pytest.mark.parametrize(
    "case,reason",
    [
        ("product", "product_key"),
        ("product_key", "dictionary_key"),
        ("product_description", "dictionary_description"),
        ("revision", "revision"),
        ("product_count_low", "dictionary_count"),
        ("product_count_high", "dictionary_count"),
    ],
)
def test_atlas_product_plants(grain, case, reason, tmp_path):
    m = modules("atlas")

    def change(content, members):
        product, data = members[1].name, members[-1].name
        if case == "product":
            content[data] = content[data].replace("000001", "000002")
        elif case == "product_key":
            content[product] = content[product].replace("000001", "X")
        elif case == "product_description":
            content[product] = content[product].replace("Invented product", " ")
        elif case == "revision":
            content[product] = content[product].replace(
                "invented-HS-A", "invented-HS-B"
            )

    def update(config, members, content):
        if not case.startswith("product_count"):
            return config
        updated = list(members)
        updated[1] = replace(
            updated[1], rows=(2, 2) if case.endswith("low") else (0, 0)
        )
        downloads = list(config.downloads)
        downloads[grain] = replace(downloads[grain], members=tuple(updated))
        return replace(config, downloads=tuple(downloads))

    with pytest.raises(m.config.AtlasError, match=r"^" + reason + "$"):
        parse_fixture("atlas", grain, tmp_path, change, update)


@pytest.mark.parametrize("source", ["gravity", "atlas"])
def test_archive_integrity(source, tmp_path):
    m = modules(source)

    @contextmanager
    def corrupt(url):
        yield SimpleNamespace(
            final_url=url, hops=(), declared_length=5, chunks=iter([b"wrong"])
        )

    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^archive_integrity$"
    ):
        acquire(source, tmp_path, stream=corrupt)
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize("case", ["running", "final", "consistency"])
def test_member_stream_size_plants(source, case, tmp_path, monkeypatch):
    from io import BytesIO
    from zipfile import ZipFile

    parser = importlib.import_module("eii_custodian.publicdata." + source + ".parse")
    m = modules(source)
    original = ZipFile.open

    def opened(zipped, name, *args, **kwargs):
        if zipped.mode == "r" and not isinstance(name, str):
            size = {"running": 5000, "final": 0, "consistency": 2}[case]
            return BytesIO(b"x" * size)
        return original(zipped, name, *args, **kwargs)

    monkeypatch.setattr(parser.ZipFile, "open", opened)
    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^member_bytes$"
    ):
        parse_fixture(source, 0, tmp_path)
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("source", ["gravity", "atlas"])
def test_additional_configuration_inventory(source):
    m = modules(source)
    error = getattr(m.config, source.capitalize() + "Error")
    raw = m.fixture.configuration()
    if source == "gravity":
        raw["members"][-1]["name"] = raw["members"][0]["name"]
        with pytest.raises(error, match=r"^inventory$"):
            m.config.Config.from_mapping(raw)
    else:
        for index, reason in (
            (0, "dictionaries"),
            (1, "dictionaries"),
            (2, "finished_grain"),
        ):
            raw = m.fixture.configuration()
            download = raw["downloads"][0]
            download["members"].pop(index)
            download["member_count"] = [2, 2]
            with pytest.raises(error, match=r"^" + reason + "$"):
                m.config.Config.from_mapping(raw)
        raw = m.fixture.configuration()
        raw["downloads"][1]["url"] = raw["downloads"][0]["url"]
        with pytest.raises(error, match=r"^download_url$"):
            m.config.Config.from_mapping(raw)


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize(
    "case", ["hash_format", "receipt_hash", "publisher_checksum", "final_host"]
)
def test_reader_archive_plants(source, case, tmp_path):
    m = modules(source)
    result = acquire(source, tmp_path)
    reason = (
        "archive_checksum"
        if case == "publisher_checksum"
        else "source_chain"
        if case == "final_host"
        else "archive_hash"
    )

    def tamper(manifest):
        if case == "receipt_hash":
            manifest["receipt"]["sha256"] = "a" * 64
        elif source == "gravity":
            if case == "hash_format":
                manifest["archive_sha256"] = "wrong"
            elif case == "publisher_checksum":
                manifest["config"]["publisher_sha256"] = "a" * 64
            else:
                manifest["archive_host"] = "unreviewed.invalid"
                manifest["receipt"]["fetch_host"] = "unreviewed.invalid"
        else:
            item = manifest["archives"][m.config.FINISHED[0]]
            if case == "hash_format":
                item["sha256"] = "wrong"
            elif case == "publisher_checksum":
                manifest["config"]["downloads"][0]["publisher_sha256"] = "a" * 64
            else:
                item["host"] = "unreviewed.invalid"

    selected = rewrite(tmp_path, source, result.digest, tamper)
    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^" + reason + "$"
    ):
        m.contracts.read_selected(tmp_path, selected)


@pytest.mark.parametrize("grain", [0, 1])
@pytest.mark.parametrize(
    "case,reason",
    [("bytes", "archive_bytes"), ("host", "source_chain"), ("hash", "archive_hash")],
)
def test_atlas_each_archive_reader(grain, case, reason, tmp_path):
    m = modules("atlas")
    result = acquire("atlas", tmp_path)

    def tamper(manifest):
        item = manifest["archives"][m.config.FINISHED[grain]]
        if case == "bytes":
            item["bytes"] += 1
        elif case == "host":
            item["host"] = "unreviewed.invalid"
        else:
            (tmp_path / m.config.SOURCE_ID / (item["sha256"] + ".zip")).write_bytes(
                b"wrong"
            )

    selected = rewrite(tmp_path, "atlas", result.digest, tamper)
    with pytest.raises(m.config.AtlasError, match=r"^" + reason + "$"):
        m.contracts.read_selected(tmp_path, selected)


@pytest.mark.parametrize(
    "field,value,reason",
    [("finished_only", False, "rebuild_refused"), ("archives", {}, "archive_hash")],
)
def test_atlas_reader_structure(field, value, reason, tmp_path):
    m = modules("atlas")
    result = acquire("atlas", tmp_path)
    selected = rewrite(
        tmp_path,
        "atlas",
        result.digest,
        lambda manifest: manifest.update({field: value}),
    )
    with pytest.raises(m.config.AtlasError, match=r"^" + reason + "$"):
        m.contracts.read_selected(tmp_path, selected)


@pytest.mark.parametrize(
    "case,reason",
    [
        ("finished", "rebuild_refused"),
        ("order", "finished_grain"),
        ("url", "download_url"),
    ],
)
def test_atlas_entry_additional(case, reason, tmp_path):
    m = modules("atlas")
    config = m.config.Config.from_mapping(m.fixture.configuration())
    entry = m.fixture.entry()
    if case == "finished":
        config = replace(config, finished_only=False)
    elif case == "order":
        config = replace(config, downloads=tuple(reversed(config.downloads)))
    else:
        entry = replace(entry, url=m.fixture.CPP_URL)
    with pytest.raises(m.config.AtlasError, match=r"^" + reason + "$"):
        m.fetch.fetch_atlas(
            entry,
            config,
            m.fixture.metadata,
            m.fixture.stream,
            tmp_path,
            lambda: CLOCK,
            lambda _: None,
        )
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize(
    "value,reason",
    [("wrong", "year"), ("0201", "year"), ("2090", "year"), ("2092", "stale_period")],
)
def test_year_branches(source, value, reason):
    m = modules(source)
    parser = importlib.import_module("eii_custodian.publicdata." + source + ".parse")
    config = m.config.Config.from_mapping(m.fixture.configuration())
    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^" + reason + "$"
    ):
        parser._year(value, config)
    assert parser._year("2091", config) == (2091, "keep")
    config = replace(config, year_selection="narrower")
    assert parser._year("2090", config) == (2090, "exclude")
    assert parser._year("2092", config) == (2092, "exclude")


@pytest.mark.parametrize("case", ["finished", "grain", "measure", "output"])
def test_atlas_internal_contracts(case, tmp_path):
    m = modules("atlas")
    parser = importlib.import_module("eii_custodian.publicdata.atlas.parse")
    config = m.config.Config.from_mapping(m.fixture.configuration())
    path = tmp_path / "invented.zip"
    path.write_bytes(m.fixture.cpy_archive())
    if case == "output":
        with pytest.raises(m.config.AtlasError, match=r"^output_hash$"):
            m.contracts._lines(tmp_path, "wrong")
    elif case == "finished":
        with pytest.raises(m.config.AtlasError, match=r"^rebuild_refused$"):
            parser.parse_archives({}, replace(config, finished_only=False), tmp_path)
    else:
        download = config.downloads[0]
        if case == "grain":
            download = replace(download, grain="wrong")
        else:
            config = replace(
                config, measures=(replace(config.measures[0], name="wrong"),)
            )
        with pytest.raises(
            m.config.AtlasError,
            match=r"^"
            + ("rebuild_refused" if case == "grain" else "measure_fields")
            + "$",
        ):
            parser._parse_one(path, download, config, tmp_path)


@pytest.mark.parametrize("edge", ["low", "high", "below", "above"])
def test_atlas_total_raw_edges(edge, tmp_path):
    m = modules("atlas")
    bounds = {"low": (5, 6), "high": (4, 5), "below": (6, 7), "above": (3, 4)}[edge]

    def update(config, members, content):
        return replace(config, raw_rows=bounds)

    if edge in {"low", "high"}:
        parse_fixture("atlas", 0, tmp_path, config_change=update)
    else:
        with pytest.raises(m.config.AtlasError, match=r"^raw_count$"):
            parse_fixture("atlas", 0, tmp_path, config_change=update)


@pytest.mark.parametrize("source", ["gravity", "atlas"])
def test_earlier_guards_cover_redundant_sites(source, tmp_path):
    m = modules(source)
    error = getattr(m.config, source.capitalize() + "Error")
    raw = m.fixture.configuration()
    raw["hs_revision"] = " "
    with pytest.raises(error, match=r"^metadata_missing$"):
        m.config.Config.from_mapping(raw)
    result = acquire(source, tmp_path)

    def tamper(manifest):
        next(iter(manifest["outputs"].values()))["sha256"] = "wrong"

    selected = rewrite(tmp_path, source, result.digest, tamper)
    with pytest.raises(error, match=r"^manifest_content$"):
        m.contracts.read_selected(tmp_path, selected)


@pytest.mark.parametrize("source", ["gravity", "atlas"])
def test_duplicate_zip_inventory(source, tmp_path):
    from io import BytesIO
    from zipfile import ZipFile

    m = modules(source)
    members = m.fixture.MEMBERS if source == "gravity" else m.fixture.CPY_MEMBERS
    buffer = BytesIO()
    with ZipFile(buffer, "w") as zipped:
        for name, body in members.items():
            zipped.writestr(name, body)
        with pytest.warns(UserWarning, match="Duplicate name"):
            zipped.writestr(next(iter(members)), "wrong")

    @contextmanager
    def stream(url):
        body = buffer.getvalue()
        yield SimpleNamespace(
            final_url=url, hops=(), declared_length=len(body), chunks=iter([body])
        )

    raw = m.fixture.configuration()
    if source == "gravity":
        raw["member_count"] = [2, 3]
    else:
        raw["downloads"][0]["member_count"] = [3, 4]
    with pytest.raises(
        getattr(m.config, source.capitalize() + "Error"), match=r"^inventory$"
    ):
        acquire(source, tmp_path, raw=raw, stream=stream)
    assert not list(tmp_path.rglob("*.manifest.json"))


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize("phase", ["clock", "terms", "measure"])
def test_remaining_refusal_sites(source, phase, tmp_path):
    from eii_custodian.publicdata.fetch.transport import Response

    m = modules(source)
    error = getattr(m.config, source.capitalize() + "Error")
    if phase == "measure":

        def change(content, members):
            data = members[-1].name
            lines = content[data].splitlines()
            fields = lines[1].split(",")
            fields[3 if source == "gravity" else -1] = "undeclared"
            lines[1] = ",".join(fields)
            content[data] = "\n".join(lines) + "\n"

        with pytest.raises(error, match=r"^missing_undeclared$"):
            parse_fixture(source, 0, tmp_path, change)
    else:
        config = m.config.Config.from_mapping(m.fixture.configuration())
        entry = m.fixture.entry()
        if phase == "terms":
            entry = replace(entry, terms_url=m.fixture.PAGE)

        def metadata(url):
            return (
                Response(url, b"paid tier", ())
                if phase == "terms"
                else m.fixture.metadata(url)
            )

        with pytest.raises(
            error,
            match=r"^"
            + ("access_obstacle" if phase == "terms" else "retrieval_date")
            + "$",
        ):
            getattr(m.fetch, "fetch_" + source)(
                entry,
                config,
                metadata,
                m.fixture.stream,
                tmp_path,
                lambda: "2026-1-1T00:00:00Z",
                lambda _: None,
            )
    assert not list(tmp_path.rglob("*.manifest.json"))


def test_gravity_flag_paths():
    m = modules("gravity")
    parser = importlib.import_module("eii_custodian.publicdata.gravity.parse")
    config = m.config.Config.from_mapping(m.fixture.configuration())
    assert parser._flag("absent", replace(config, flag_missing=("absent",))) is None
    with pytest.raises(m.config.GravityError, match=r"^missing_undeclared$"):
        parser._flag("wrong", config)


@pytest.mark.parametrize("source", ["gravity", "atlas"])
@pytest.mark.parametrize("edge", ["low", "high", "below", "above"])
def test_config_member_count_edges(source, edge):
    m = modules(source)
    raw = m.fixture.configuration()
    target = raw if source == "gravity" else raw["downloads"][0]
    n = len(target["members"])
    target["member_count"] = {
        "low": [n, n + 1],
        "high": [n - 1, n],
        "below": [n + 1, n + 2],
        "above": [n - 2, n - 1],
    }[edge]
    if edge in {"low", "high"}:
        m.config.Config.from_mapping(raw)
    else:
        with pytest.raises(
            getattr(m.config, source.capitalize() + "Error"), match=r"^member_count$"
        ):
            m.config.Config.from_mapping(raw)


@pytest.mark.parametrize("grain", [0, 1])
@pytest.mark.parametrize("edge", ["low", "high"])
def test_atlas_product_count_edges(grain, edge, tmp_path):
    def update(config, members, content):
        updated = list(members)
        updated[1] = replace(updated[1], rows=(1, 2) if edge == "low" else (0, 1))
        downloads = list(config.downloads)
        downloads[grain] = replace(downloads[grain], members=tuple(updated))
        return replace(config, downloads=tuple(downloads))

    parse_fixture("atlas", grain, tmp_path, config_change=update)
