"""Counterexamples to campaign seven's registry equivalence claims."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import TracebackType

import pytest
from product.tests.test_store_lint_survivors import full_message
from product.tests.test_store_registry_survivors import _TEXT, _sql, _write

from eii_product.store import registry


def test_translation_keeps_the_literal_mutation_marker() -> None:
    assert registry.translate("XX::XX", "postgres") == "XX::XX"
    assert registry.translate("XX::XX", "embedded") == "XX::XX"


def test_packaged_directory_resolves_the_actual_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "syn_package"
    target = tmp_path / "syn_target"
    folder.mkdir()
    target.mkdir()
    marker = target / "syn_marker.py"
    marker.write_text('"""Invented package marker."""\n', encoding="utf-8")
    (folder / "__init__.py").symlink_to(marker)
    monkeypatch.setattr(registry, "files", lambda package: folder)
    assert registry.packaged_sql_dir() == target


@pytest.mark.parametrize(
    ("kind", "attributes"),
    [("Alias", {}), ("Alias", {"alias": "syn_output"}), ("Column", {})],
)
def test_bare_projection_handles_absent_object_attributes(
    kind: str, attributes: dict[str, object]
) -> None:
    # The public signature here accepts object, including a partial AST holder.
    node = type(kind, (), attributes)()
    output, column = registry._bare_projected(node)
    assert output is None
    if kind == "Column":
        assert column is node
    else:
        assert column is None


@pytest.mark.parametrize(
    ("name", "message"),
    [
        (
            "syn_missing",
            "module 'eii_product.store.registry' has no attribute 'syn_missing'",
        ),
        (
            "XXPACKAGEDXX",
            "module 'eii_product.store.registry' has no attribute 'XXPACKAGEDXX'",
        ),
        (
            "packaged",
            "module 'eii_product.store.registry' has no attribute 'packaged'",
        ),
    ],
)
def test_unknown_lazy_attribute_is_refused_whole(name: str, message: str) -> None:
    with pytest.raises(AttributeError) as caught:
        registry.__getattr__(name)
    full_message(caught.value, message)


class _ContendedLock:
    """Both calls enter the getter before either can acquire the real lock."""

    def __init__(self) -> None:
        self.gate = threading.Barrier(2)
        self.lock = threading.Lock()

    def __enter__(self) -> None:
        self.gate.wait(timeout=5)
        self.lock.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.lock.release()


def test_contended_first_access_rechecks_and_publishes_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "syn_queries"
    _write(
        folder,
        "syn_rows",
        _sql(
            "syn_rows",
            "",
            "unit_id text",
            "unit_id",
            "SELECT p.unit_id FROM control_rows AS p",
        ),
        _TEXT,
    )
    calls: list[Path] = []
    real_load = registry.load_inventory

    def recorded_load(path: Path) -> registry.Inventory:
        calls.append(path)
        return real_load(path)

    # Restore these slots even if a mutant publishes under an incorrect key.
    for key in ("PACKAGED", "XXPACKAGEDXX", "packaged"):
        monkeypatch.setitem(registry.__dict__, key, None)
    monkeypatch.setattr(registry, "packaged_sql_dir", lambda: folder)
    monkeypatch.setattr(registry, "load_inventory", recorded_load)
    monkeypatch.setattr(registry, "_PACKAGED_LOCK", _ContendedLock())
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(registry.__getattr__, "PACKAGED")
        second = executor.submit(registry.__getattr__, "PACKAGED")
        left, right = first.result(timeout=10), second.result(timeout=10)
    assert calls == [folder]
    assert isinstance(left, registry.Inventory)
    assert right is left
    assert registry.__dict__["PACKAGED"] is left
    assert registry.__dict__["XXPACKAGEDXX"] is None
    assert registry.__dict__["packaged"] is None
    assert tuple(query.name for query in left.queries) == ("syn_rows",)
