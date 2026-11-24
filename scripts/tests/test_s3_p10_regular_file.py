"""S3-P10 round 3 (R1 of rv2): the build hashes only a regular, unfollowed file.

Every file here is invented. Each case changes only the object
EII_FC_REGISTER_FILE names; the refusal is ``fc_register_unreadable`` with
neither the value nor the path. The guard below keeps every read of the
register file inside the one descriptor helper, following definition-time
expressions, import aliases, bound names, ``getattr`` literals and
``partial`` wrappers (L-1515, rule 37; L-1527).
"""

from __future__ import annotations

import ast
import errno
import hashlib
import multiprocessing
import os
import tempfile
import textwrap
import unittest
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
import s3_t28_support  # noqa: F401  (puts scripts, core and product on the path)
from hypothesis import given, settings
from hypothesis import strategies as st

from operations.build import fc_register_sha256
from operations.common import Refusal

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "product/tests/fixtures/fc_register/stand_in_register.json"
NAME = "EII_FC_REGISTER_FILE"
SECRET = "INVENTED-secret-place"
WAIT = 5.0

HELPER_MODULE = "product/src/eii_product/register_file.py"
HELPER = "read_register_bytes"
SCANNED = ("core/src", "custodian/src", "product/src", "scripts/operations")
# A function that touches the register setting or its reader must not read a
# file itself; it hands the path to the helper.
REGISTER_NAMES = frozenset(
    {"read_fc_register_file", "read_fc_register_rows", "fc_setting", NAME}
)
READ_CALLS = frozenset({"read_bytes", "read_text", "open", "file_digest", "sha"})
INTAKE_MODULE = "custodian/src/eii_custodian/publicdata/registers/intake.py"
INTAKE_READER = "read_file"
# Functions allowed to read a path. Anything else reached from the setting,
# including a new delegate, is a breach. The intake reader is the custodian
# plane's own helper (rule 11); the product helper is the only other site.
REVIEWED_READ_SITES = frozenset(
    {(HELPER_MODULE, HELPER), (INTAKE_MODULE, INTAKE_READER)}
)
_FUNCTION = ast.FunctionDef | ast.AsyncFunctionDef


def _hash(value: str) -> tuple[str, str | None]:
    """Return ("hash", digest) or ("refused", reason) for one setting value."""
    with patch.dict(os.environ, {NAME: value}, clear=True):
        try:
            return "hash", fc_register_sha256()
        except Refusal as exc:
            text = str(exc) + repr(exc)
            assert SECRET not in text and exc.__cause__ is None
            return "refused", exc.reason


def _in_child(value: str) -> tuple[str, str | None]:
    """Hash in a forked child so a blocking open can never hang the test."""
    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    process = context.Process(target=lambda: queue.put(_hash(value)))
    process.start()
    try:
        process.join(WAIT)
        if process.is_alive():
            raise AssertionError("the build blocks instead of refusing")
        result: tuple[str, str | None] = queue.get(timeout=WAIT)
        return result
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        queue.close()
        queue.join_thread()


REFUSED = ("refused", "fc_register_unreadable")


class RegularFileOnly(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.folder = Path(scratch.name) / SECRET
        self.folder.mkdir()
        self.body = FIXTURE.read_bytes()
        self.file = self.folder / "register.json"
        self.file.write_bytes(self.body)

    def test_the_regular_file_hashes_to_its_bytes(self) -> None:
        expected = hashlib.sha256(self.body).hexdigest()
        self.assertEqual(_hash(str(self.file)), ("hash", expected))

    def test_a_symlink_to_a_valid_file_refuses(self) -> None:
        link = self.folder / "link.json"
        link.symlink_to(self.file)
        self.assertEqual(_hash(str(link)), REFUSED)

    def test_a_fifo_with_no_writer_refuses_without_blocking(self) -> None:
        pipe = self.folder / "pipe.json"
        os.mkfifo(pipe)
        self.assertEqual(_in_child(str(pipe)), REFUSED)

    def test_a_fifo_whose_writer_supplies_the_bytes_refuses(self) -> None:
        pipe = self.folder / "pipe.json"
        os.mkfifo(pipe)
        keep = os.open(pipe, os.O_RDONLY | os.O_NONBLOCK)
        writer = os.open(pipe, os.O_WRONLY)
        try:
            self.assertEqual(os.write(writer, self.body), len(self.body))
            self.assertEqual(_in_child(str(pipe)), REFUSED)
        finally:
            os.close(writer)
            os.close(keep)

    def test_a_directory_refuses(self) -> None:
        folder = self.folder / "folder.json"
        folder.mkdir()
        self.assertEqual(_hash(str(folder)), REFUSED)

    def test_a_directory_refusal_closes_its_descriptor(self) -> None:
        folder = self.folder / "folder.json"
        folder.mkdir()
        opened: list[int] = []
        real = os.open

        def opener(name: str, mode: int, *args: int) -> int:
            descriptor = real(name, mode, *args)
            opened.append(descriptor)
            return descriptor

        try:
            with patch("os.open", side_effect=opener):
                for _ in range(4):
                    self.assertEqual(_hash(str(folder)), REFUSED)
            self.assertEqual(len(opened), 4)
            for descriptor in opened:
                with self.assertRaises(OSError) as caught:
                    os.fstat(descriptor)
                self.assertEqual(caught.exception.errno, errno.EBADF)
        finally:
            for descriptor in opened:
                try:
                    os.fstat(descriptor)
                except OSError as exc:
                    self.assertEqual(exc.errno, errno.EBADF)
                else:
                    os.close(descriptor)

    def test_a_missing_file_refuses(self) -> None:
        self.assertEqual(_hash(str(self.folder / "absent.json")), REFUSED)

    @unittest.skipUnless(os.path.exists("/dev/null"), "no device node here")
    def test_a_device_refuses(self) -> None:
        self.assertEqual(_in_child("/dev/null"), REFUSED)

    def test_a_path_replaced_during_the_read_refuses(self) -> None:
        other = self.folder / "other.json"
        other.write_bytes(self.body)
        real = os.fstat
        calls: list[int] = []

        def fstat(descriptor: int) -> os.stat_result:
            calls.append(descriptor)
            if len(calls) == 2:
                os.replace(other, self.file)
            return real(descriptor)

        with patch("os.fstat", side_effect=fstat):
            self.assertEqual(_hash(str(self.file)), REFUSED)
        self.assertEqual(len(calls), 2)


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _mentions_register(node: ast.AST) -> bool:
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and item.id in REGISTER_NAMES:
            return True
        if isinstance(item, ast.Constant) and item.value in REGISTER_NAMES:
            return True
    return False


def _loads_mention(node: ast.AST, names: set[str]) -> bool:
    """True when the node reads (Load context) one of ``names``."""
    if not names:
        return False
    for item in ast.walk(node):
        if (
            isinstance(item, ast.Name)
            and item.id in names
            and isinstance(item.ctx, ast.Load)
        ):
            return True
    return False


def _functions(tree: ast.AST) -> Iterator[_FUNCTION]:
    for item in ast.walk(tree):
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield item


def _calls_here(node: ast.AST) -> Iterator[ast.Call]:
    """Calls under ``node`` — itself included — skipping nested definitions."""
    if isinstance(node, ast.Call):
        yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield from _calls_here(child)


def _class_exprs(statement: ast.ClassDef) -> Iterator[ast.AST]:
    """The expressions a class statement runs when it is defined."""
    yield from statement.decorator_list
    yield from statement.bases
    for keyword in statement.keywords:
        yield keyword.value


def _definition_time(function: _FUNCTION) -> tuple[ast.AST, ...]:
    nodes: list[ast.AST] = list(function.decorator_list)
    nodes.extend(function.args.defaults)
    nodes.extend(node for node in function.args.kw_defaults if node is not None)
    return tuple(nodes)


def _statement_lists(node: ast.AST) -> Iterator[list[ast.stmt]]:
    """Child statement lists, including handler and case bodies, in field order."""
    for field, value in ast.iter_fields(node):
        if node._field_types[field] == list[ast.stmt]:
            yield value
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, ast.ExceptHandler):
                    yield from _statement_lists(child)
                elif isinstance(child, ast.match_case):
                    yield from _statement_lists(child)


def _function_units(function: _FUNCTION) -> Iterator[tuple[str, ast.AST]]:
    """Every unit scanned in a function: definition-time, nested classes, body."""
    for node in _definition_time(function):
        yield function.name, node
    for body in _statement_lists(function):
        for statement in body:
            if isinstance(statement, ast.ClassDef):
                yield from _loose_nodes([statement], statement.name)
                continue
            yield function.name, statement
            yield from _buried_class_units(statement)


def _function_calls(function: _FUNCTION) -> Iterator[ast.Call]:
    for _place, node in _function_units(function):
        yield from _calls_here(node)


def _loose_nodes(
    body: list[ast.stmt], place: str, *, nested: bool = False
) -> Iterator[tuple[str, ast.AST]]:
    """Module and class statements that run outside a function body.

    A plain statement is yielded whole once, at its top level; a compound
    statement's nested definitions get their own loose pass, so a ``def`` or
    ``class`` under an ``if``, ``try``, ``with`` or ``match`` is still seen.
    """
    for statement in body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in _definition_time(statement):
                yield place, node
            continue
        if isinstance(statement, ast.ClassDef):
            inner = f"class {statement.name}"
            for node in _class_exprs(statement):
                yield inner, node
            for child_body in _statement_lists(statement):
                yield from _loose_nodes(child_body, inner)
            continue
        if not nested:
            yield place, statement
        for child_body in _statement_lists(statement):
            yield from _loose_nodes(child_body, place, nested=True)


def _buried_class_units(node: ast.AST) -> Iterator[tuple[str, ast.AST]]:
    """The loose units of class statements hidden under compound statements.

    ``_calls_here`` skips every nested ``ClassDef``, so a class beneath an
    ``if``, ``try``, ``with``, ``for``, ``while`` or ``match`` inside a
    reached function would go unseen; its body still runs when its block
    does, so it gets the same loose pass a module or class body gets. A
    nested function is left to its own reachability scan.
    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return
    for body in _statement_lists(node):
        for child in body:
            if isinstance(child, ast.ClassDef):
                yield from _loose_nodes([child], child.name)
                continue
            yield from _buried_class_units(child)


def _by_name(tree: ast.AST) -> dict[str, list[_FUNCTION]]:
    found: dict[str, list[_FUNCTION]] = {}
    for function in _functions(tree):
        found.setdefault(function.name, []).append(function)
    return found


def _allowed(name: str, *, helper_module: bool, module: str | None) -> bool:
    if helper_module and name == HELPER:
        return True
    return (module, name) in REVIEWED_READ_SITES and not helper_module


_CONTROL_NAMES = frozenset({"getattr", "partial"})


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    """Local names a ``from`` import gives a read or dynamic-call name."""
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in READ_CALLS | _CONTROL_NAMES:
                    found[alias.asname or alias.name] = alias.name
    return found


def _target_names(target: ast.AST) -> Iterator[str]:
    """The plain names a binding target stores."""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            yield from _target_names(item)
    elif isinstance(target, ast.Starred):
        yield from _target_names(target.value)


def _bound_pairs(node: ast.AST) -> Iterator[tuple[ast.expr, ast.expr]]:
    """``(target, value)`` pairs bound under ``node``, skipping nested defs."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            yield target, node.value
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
        yield node.target, node.value
    elif isinstance(node, ast.NamedExpr):
        yield node.target, node.value
    elif isinstance(node, (ast.For, ast.AsyncFor)):
        yield node.target, node.iter
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        for item in node.items:
            if item.optional_vars is not None:
                yield item.optional_vars, item.context_expr
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield from _bound_pairs(child)


def _scope_bindings(node: ast.AST, outer: dict[str, ast.expr]) -> dict[str, ast.expr]:
    """Simple name bindings visible in ``node``: the outer scope, then its own."""
    bound = dict(outer)
    for target, value in _bound_pairs(node):
        for name in _target_names(target):
            bound[name] = value
    return bound


def _resolved_name(
    node: ast.AST, aliases: dict[str, str], bindings: dict[str, ast.expr]
) -> str | None:
    """The simple name of the callable ``node`` yields, when it can be resolved.

    Follows ``from``-import aliases, one-name bindings, ``getattr`` string
    literals and ``partial`` wrappers; the unresolved name or ``None`` is
    returned otherwise.
    """
    seen: set[str] = set()
    while True:
        if isinstance(node, ast.Name):
            if node.id in seen:
                return None
            seen.add(node.id)
            if node.id in bindings:
                node = bindings[node.id]
                continue
            if node.id in aliases:
                return aliases[node.id]
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            name = _resolved_name(node.func, aliases, bindings)
            if name == "getattr" and len(node.args) >= 2:
                option = node.args[1]
                if isinstance(option, ast.Constant) and isinstance(option.value, str):
                    return option.value
                return "getattr"
            if name == "partial" and node.args:
                return _resolved_name(node.args[0], aliases, bindings) or "partial"
            return name
        return None


def _read_values(node: ast.AST, called: set[int]) -> Iterator[ast.Attribute]:
    """Read methods taken as values: read-attribute references never called.

    ``called`` holds ``id()`` of call ``func`` nodes, which name the read on
    their own; any other read-named attribute is an unreviewed callable.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if (
            isinstance(child, ast.Attribute)
            and child.attr in READ_CALLS
            and id(child) not in called
        ):
            yield child
        yield from _read_values(child, called)


def _note(
    found: list[str],
    place: str,
    call: ast.Call,
    aliases: dict[str, str],
    bindings: dict[str, ast.expr],
) -> None:
    name = _resolved_name(call.func, aliases, bindings)
    local = _call_name(call)
    if name in READ_CALLS:
        label = name if local in (None, name) else f"{local}={name}"
        found.append(f"{place}:{call.lineno}:{label}")
    if name == "getattr" and len(call.args) >= 2:
        option = call.args[1]
        if isinstance(option, ast.Constant) and option.value in READ_CALLS:
            found.append(f"{place}:{call.lineno}:getattr={option.value}")
    if name == "partial" and call.args:
        target = _resolved_name(call.args[0], aliases, bindings)
        if target in READ_CALLS:
            found.append(f"{place}:{call.lineno}:partial={target}")
    for expr in (*call.args, *(item.value for item in call.keywords)):
        target = _resolved_name(expr, aliases, bindings)
        if target in READ_CALLS:
            found.append(f"{place}:{call.lineno}:arg={target}")


def _extend_scope(node: ast.AST, bound: dict[str, ast.expr], tainted: set[str]) -> None:
    """Record the node's name bindings and register-derived names."""
    for target, value in _bound_pairs(node):
        names = list(_target_names(target))
        for name in names:
            bound[name] = value
        if _mentions_register(value) or _loads_mention(value, tainted):
            tainted.update(names)


def _reachable(
    defined: dict[str, list[_FUNCTION]],
    seeds: list[_FUNCTION],
    aliases: dict[str, str],
    outer: dict[str, ast.expr],
) -> list[_FUNCTION]:
    seen: set[int] = set()
    reached: list[_FUNCTION] = []
    queue = list(seeds)
    while queue:
        function = queue.pop()
        if id(function) in seen:
            continue
        seen.add(id(function))
        reached.append(function)
        bindings = _scope_bindings(function, outer)
        for call in _function_calls(function):
            callee = _resolved_name(call.func, aliases, bindings) or _call_name(call)
            if callee is not None:
                queue.extend(defined.get(callee, []))
    return reached


def _scan_scope(
    found: list[str],
    units: list[tuple[str, ast.AST]],
    aliases: dict[str, str],
    bindings: dict[str, ast.expr],
) -> None:
    """Note every read call and unbound read value in one scope's units."""
    calls = [(place, call) for place, unit in units for call in _calls_here(unit)]
    called = {id(call.func) for _place, call in calls}
    for place, call in calls:
        _note(found, place, call, aliases, bindings)
    for place, unit in units:
        for attribute in _read_values(unit, called):
            found.append(f"{place}:{attribute.lineno}:method={attribute.attr}")


def register_read_breaches(
    source: str, *, helper_module: bool, module: str | None = None
) -> list[str]:
    """Name each register read outside the one reviewed helper.

    The helper module may read only inside ``read_register_bytes``. Every
    other module's module-level, class-level and definition-time calls are
    inspected, and so is any function reached from a statement that names the
    register or a name bound from it. Read functions reached through import
    aliases, bound names, ``getattr`` literals, ``partial`` wrappers or a
    method taken as a value are treated as breaches. The custodian intake's
    ``read_file`` is the one reviewed exception. A call to the helper does
    not excuse another read.
    """
    tree = ast.parse(source)
    defined = _by_name(tree)
    aliases = _import_aliases(tree)
    found: list[str] = []
    seeds: list[_FUNCTION] = []
    tainted: set[str] = set()
    bound: dict[str, ast.expr] = {}
    for place, node in _loose_nodes(tree.body, "module"):
        mentions = (
            helper_module or _mentions_register(node) or _loads_mention(node, tainted)
        )
        calls = list(_calls_here(node))
        for call in calls:
            if mentions or _mentions_register(call) or _loads_mention(call, tainted):
                _note(found, place, call, aliases, bound)
            if mentions:
                callee = _resolved_name(call.func, aliases, bound) or _call_name(call)
                if callee is not None:
                    seeds.extend(defined.get(callee, []))
        if mentions:
            called = {id(call.func) for call in calls}
            for attribute in _read_values(node, called):
                found.append(f"{place}:{attribute.lineno}:method={attribute.attr}")
        _extend_scope(node, bound, tainted)
    seeds.extend(
        function
        for function in _functions(tree)
        if _mentions_register(function) or _loads_mention(function, tainted)
    )
    reached = (
        list(_functions(tree))
        if helper_module
        else _reachable(defined, seeds, aliases, bound)
    )
    for function in reached:
        if _allowed(function.name, helper_module=helper_module, module=module):
            continue
        _scan_scope(
            found,
            list(_function_units(function)),
            aliases,
            _scope_bindings(function, bound),
        )
    if helper_module:
        opens = [
            call
            for function in defined.get(HELPER, [])
            for call in _function_calls(function)
            if _resolved_name(call.func, aliases, _scope_bindings(function, bound))
            == "open"
        ]
        if len(opens) != 1:
            found.append(f"{HELPER}:open_count:{len(opens)}")
    return found


_PLANTS: dict[str, tuple[str, bool]] = {
    "product path read": (
        "def _read_path(path, listed):\n"
        "    return Path(path).read_bytes()\n"
        "def read_register_bytes(path):\n"
        "    return os.open(path, 0)\n",
        True,
    ),
    "product second open": (
        "def read_register_bytes(path):\n"
        "    os.open(path, 0)\n"
        "    return open(path, 'rb').read()\n",
        True,
    ),
    "build hash by path": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    return sha(Path(setting))\n",
        False,
    ),
    "app text read": (
        "def create_app(fc_setting_reader):\n"
        "    fc_setting = fc_setting_reader()\n"
        "    Path(fc_setting).read_text()\n",
        False,
    ),
    "builtin open of the setting": (
        "def load():\n"
        "    with open(os.environ['EII_FC_REGISTER_FILE'], 'rb') as f:\n"
        "        return f.read()\n",
        False,
    ),
    "module read_bytes": (
        "from pathlib import Path\n"
        "UNSAFE = Path(os.environ['EII_FC_REGISTER_FILE']).read_bytes()\n",
        True,
    ),
    "module open": (
        "UNSAFE = open(os.environ['EII_FC_REGISTER_FILE'], 'rb').read()\n",
        True,
    ),
    "module Path read_text": (
        "from pathlib import Path\n"
        "UNSAFE = Path.read_text(Path(os.environ['EII_FC_REGISTER_FILE']))\n",
        True,
    ),
    "delegated build read": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    _unsafe_bytes(setting)\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n"
        "def _unsafe_bytes(path):\n"
        "    return Path(path).read_bytes()\n",
        False,
    ),
    "class level open": (
        "class Holder:\n"
        "    data = open(os.environ['EII_FC_REGISTER_FILE'], 'rb').read()\n",
        False,
    ),
    "aliased read import": (
        "from io import open as load_input\n"
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    unsafe_alias(setting)\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n"
        "def unsafe_alias(path):\n"
        "    return load_input(path, 'rb').read()\n",
        False,
    ),
    "attribute module open": (
        "import builtins\n"
        "UNSAFE = builtins.open("
        "os.environ['EII_FC_REGISTER_FILE'], 'rb').read()\n",
        False,
    ),
    "partial read": (
        "from functools import partial\n"
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    unsafe_partial(setting)\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n"
        "def unsafe_partial(path):\n"
        "    loader = partial(open, path, 'rb')\n"
        "    return loader().read()\n",
        False,
    ),
    "getattr read": (
        "from pathlib import Path\n"
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    unsafe_getattr(setting)\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n"
        "def unsafe_getattr(path):\n"
        "    return getattr(Path(path), 'read_bytes')()\n",
        False,
    ),
    "split module flow": (
        "from pathlib import Path\n"
        "selected = os.environ['EII_FC_REGISTER_FILE']\n"
        "UNSAFE = Path(selected).read_bytes()\n"
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "read method taken as value": (
        "def load():\n"
        "    reader = Path.read_bytes\n"
        "    return reader(os.environ['EII_FC_REGISTER_FILE'])\n",
        False,
    ),
    "bound read method": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    reader = Path.read_bytes\n"
        "    unsafe_value(reader)\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n"
        "def unsafe_value(read):\n"
        "    return read\n",
        False,
    ),
    "function default read": (
        "def unsafe_default("
        "body=open(os.environ['EII_FC_REGISTER_FILE'], 'rb')):\n"
        "    return body.read()\n",
        False,
    ),
    "class base read": (
        "class Holder(\n"
        "    open(os.environ['EII_FC_REGISTER_FILE'], 'rb').read()):\n"
        "    pass\n",
        False,
    ),
    "nested definition read": (
        "if True:\n"
        "    class Holder(\n"
        "        open(os.environ['EII_FC_REGISTER_FILE'], 'rb').read()):\n"
        "        pass\n",
        False,
    ),
    "product aliased open": (
        "from io import open as load_input\n"
        "def read_register_bytes(path):\n"
        "    os.open(path, 0)\n"
        "    return load_input(path, 'rb').read()\n",
        True,
    ),
    "class body under if": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    if setting:\n"
        "        class Holder:\n"
        "            value = open(setting, 'rb').read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "class body under else": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    if setting is None:\n"
        "        pass\n"
        "    else:\n"
        "        class Holder:\n"
        "            value = open(setting, 'rb').read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "class body under except": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    try:\n"
        "        pass\n"
        "    except OSError:\n"
        "        class Holder:\n"
        "            value = open(setting, 'rb').read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "class body under finally": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    try:\n"
        "        pass\n"
        "    finally:\n"
        "        class Holder:\n"
        "            value = open(setting, 'rb').read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "class body under with": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    with lock():\n"
        "        class Holder:\n"
        "            value = open(setting, 'rb').read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "class body under for": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    for item in (setting,):\n"
        "        class Holder:\n"
        "            value = open(setting, 'rb').read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "class body under while": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    while setting:\n"
        "        class Holder:\n"
        "            value = open(setting, 'rb').read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "class body under match": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    match setting:\n"
        "        case _:\n"
        "            class Holder:\n"
        "                value = open(setting, 'rb').read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "class in class under if": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    if setting:\n"
        "        class Outer:\n"
        "            class Holder:\n"
        "                value = open(setting, 'rb').read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
    "def default in buried class": (
        "def fc_register_sha256():\n"
        "    setting = read_fc_register_file()\n"
        "    if setting:\n"
        "        class Holder:\n"
        "            def load(path=open(setting, 'rb')):\n"
        "                return path.read()\n"
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n",
        False,
    ),
}

_MARKERS = {
    "product path read": "_read_path:",
    "product second open": "open_count:2",
    "build hash by path": ":sha",
    "app text read": ":read_text",
    "builtin open of the setting": ":open",
    "module read_bytes": "module:",
    "module open": "module:",
    "module Path read_text": "module:",
    "delegated build read": "_unsafe_bytes:",
    "class level open": "class Holder:",
    "aliased read import": "load_input=open",
    "attribute module open": "module:",
    "partial read": "partial=open",
    "getattr read": "getattr=read_bytes",
    "split module flow": "module:",
    "read method taken as value": "method=read_bytes",
    "bound read method": "arg=read_bytes",
    "function default read": ":open",
    "class base read": "class Holder:",
    "nested definition read": "class Holder:",
    "product aliased open": "open_count:2",
    "class body under if": "class Holder:",
    "class body under else": "class Holder:",
    "class body under except": "class Holder:",
    "class body under finally": "class Holder:",
    "class body under with": "class Holder:",
    "class body under for": "class Holder:",
    "class body under while": "class Holder:",
    "class body under match": "class Holder:",
    "class in class under if": "class Holder:",
    "def default in buried class": "class Holder:",
}


class OneReadHelper(unittest.TestCase):
    def test_no_register_read_outside_the_helper(self) -> None:
        files = sorted(
            path for folder in SCANNED for path in (ROOT / folder).rglob("*.py")
        )
        self.assertIn(ROOT / HELPER_MODULE, files)
        breaches: list[str] = []
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            for breach in register_read_breaches(
                path.read_text(encoding="utf-8"),
                helper_module=relative == HELPER_MODULE,
                module=relative,
            ):
                breaches.append(f"{relative}:{breach}")
        self.assertEqual(breaches, [])

    def test_the_build_and_the_reader_both_call_the_helper(self) -> None:
        # Presence of the helper is required and is not sufficient: the
        # delegated plant below keeps the call and is still a breach.
        for relative in ("scripts/operations/build.py", HELPER_MODULE):
            tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
            names = {
                _call_name(call)
                for call in ast.walk(tree)
                if isinstance(call, ast.Call)
            }
            with self.subTest(file=relative):
                self.assertIn(HELPER, names)

    def test_planted_reads_are_found(self) -> None:
        for label, (source, helper_module) in _PLANTS.items():
            with self.subTest(plant=label):
                found = register_read_breaches(source, helper_module=helper_module)
                self.assertTrue(
                    any(_MARKERS[label] in item for item in found),
                    found,
                )

    def test_an_unrelated_read_is_not_a_breach(self) -> None:
        source = "def other(path):\n    return Path(path).read_bytes()\n"
        self.assertEqual(register_read_breaches(source, helper_module=False), [])
        module_level = "UNSAFE = open('invented.json', 'rb').read()\n"
        self.assertEqual(register_read_breaches(module_level, helper_module=False), [])
        aliased = (
            "from io import open as load_input\n"
            "def other(path):\n"
            "    return load_input(path, 'rb').read()\n"
        )
        self.assertEqual(register_read_breaches(aliased, helper_module=False), [])
        nested_class = (
            "def fc_register_sha256():\n"
            "    setting = read_fc_register_file()\n"
            "    if setting:\n"
            "        class Holder:\n"
            "            value = len(setting)\n"
            "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n"
        )
        self.assertEqual(register_read_breaches(nested_class, helper_module=False), [])
        unreached = (
            "def fc_register_sha256():\n"
            "    setting = read_fc_register_file()\n"
            "    def helper():\n"
            "        if setting:\n"
            "            class Holder:\n"
            "                value = open('invented.txt', 'rb').read()\n"
            "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()\n"
        )
        self.assertEqual(register_read_breaches(unreached, helper_module=False), [])

    def test_reviewed_dynamic_forms_stay_allowed(self) -> None:
        """A ``getattr``/``partial`` of a non-read callable is not a breach."""
        source = (
            "from functools import partial\n"
            "def load(fc_setting):\n"
            "    probe = getattr(fc_setting, 'strip')\n"
            "    return partial(str.upper, probe())()\n"
        )
        self.assertEqual(register_read_breaches(source, helper_module=False), [])
        unlisted = (
            "from functools import partial\n"
            "_UNLISTED_READER = partial(read_fc_register_rows, listed_sha256=None)\n"
        )
        self.assertEqual(register_read_breaches(unlisted, helper_module=False), [])

    def test_the_custodian_intake_reader_is_a_reviewed_exception(self) -> None:
        source = (
            "def from_environment():\n"
            "    setting = 'EII_FC_REGISTER_FILE'\n"
            "    return read_file(setting)\n"
            "def read_file(path):\n"
            "    return open(path, 'rb').read()\n"
        )
        self.assertEqual(
            register_read_breaches(source, helper_module=False, module=INTAKE_MODULE),
            [],
        )
        added = (
            "def from_environment():\n"
            "    setting = 'EII_FC_REGISTER_FILE'\n"
            "    read_file(setting)\n"
            "    return _unsafe(setting)\n"
            "def read_file(path):\n"
            "    return open(path, 'rb').read()\n"
            "def _unsafe(path):\n"
            "    return Path(path).read_bytes()\n"
        )
        found = register_read_breaches(added, helper_module=False, module=INTAKE_MODULE)
        self.assertTrue(any(item.startswith("_unsafe:") for item in found), found)


_ALIAS_FRAME = (
    "def fc_register_sha256():\n"
    "    setting = read_fc_register_file()\n"
    "    return {name}(setting, 'rb').read()\n"
)


@settings(max_examples=30, deadline=None, database=None)
@given(suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10))
def test_the_read_guard_survives_import_alias_renaming(suffix: str) -> None:
    direct = _ALIAS_FRAME.format(name="open")
    assert any(
        ":open" in item for item in register_read_breaches(direct, helper_module=False)
    )
    alias = "load_" + suffix
    renamed = "from io import open as " + alias + "\n" + _ALIAS_FRAME.format(name=alias)
    namespace: dict[str, object] = {"read_fc_register_file": lambda: str(FIXTURE)}
    exec(compile(renamed, "<invented-alias>", "exec"), namespace)
    function = namespace["fc_register_sha256"]
    assert callable(function)
    assert function() == FIXTURE.read_bytes()
    found = register_read_breaches(renamed, helper_module=False)
    assert found, "an import alias must preserve prohibited-read detection"


_WRAPPER_HEADS: dict[str, tuple[str, int]] = {
    "if": ("    if setting:", 8),
    "else": ("    if setting is None:\n        pass\n    else:", 8),
    "except": ("    try:\n        pass\n    except OSError:", 8),
    "except*": ("    try:\n        pass\n    except* OSError:", 8),
    "finally": ("    try:\n        pass\n    finally:", 8),
    "with": ("    with lock():", 8),
    "for": ("    for item in (setting,):", 8),
    "while": ("    while setting:", 8),
    "match": ("    match setting:\n        case _:", 12),
}

_WRAPPED_READS = {
    "open": "open(setting, 'rb').read()",
    "read_bytes": "Path(setting).read_bytes()",
    "read_text": "Path(setting).read_text()",
}


def _nested_class_source(
    head: str, indent: int, read: str, *, base_read: bool = False
) -> str:
    """A reached function holding a register-reading class under one block."""
    lines = [
        "def fc_register_sha256():",
        "    setting = read_fc_register_file()",
        *head.splitlines(),
        " " * indent + (f"class Holder({read}):" if base_read else "class Holder:"),
        " " * (indent + 4) + ("pass" if base_read else f"value = {read}"),
        "    return hashlib.sha256(read_register_bytes(setting)).hexdigest()",
    ]
    return "\n".join(lines) + "\n"


@settings(max_examples=32, deadline=None, database=None)
@given(
    wrapper=st.sampled_from(sorted(_WRAPPER_HEADS)),
    read=st.sampled_from(sorted(_WRAPPED_READS)),
)
def test_the_read_guard_survives_class_bodies_under_blocks(
    wrapper: str, read: str
) -> None:
    head, indent = _WRAPPER_HEADS[wrapper]
    source = _nested_class_source(head, indent, _WRAPPED_READS[read])
    found = register_read_breaches(source, helper_module=False)
    assert any("class Holder:" in item for item in found), found


@pytest.mark.parametrize("wrapper", ["except", "except*", "match"])
@pytest.mark.parametrize("base_read", [False, True], ids=["body", "base"])
def test_reads_in_classes_nested_under_handlers_and_cases(
    wrapper: str, base_read: bool
) -> None:
    head, indent = _WRAPPER_HEADS[wrapper]
    head = "    class Outer:\n" + textwrap.indent(head, "    ")
    source = _nested_class_source(
        head, indent + 4, _WRAPPED_READS["open"], base_read=base_read
    )
    found = register_read_breaches(source, helper_module=False)
    assert any(
        item.startswith("class Holder:") and item.endswith(":open") for item in found
    ), found
    clean = _nested_class_source(head, indent + 4, "None", base_read=base_read)
    assert register_read_breaches(clean, helper_module=False) == []


@pytest.mark.parametrize("body_count", [0, 1, 2])
@pytest.mark.parametrize("container_count", [0, 1, 2])
def test_statement_lists_cover_the_ast_grammar(
    body_count: int, container_count: int
) -> None:
    kinds: set[type[ast.AST]] = {
        kind
        for kind in vars(ast).values()
        if isinstance(kind, type)
        and issubclass(kind, ast.stmt)
        and kind is not ast.stmt
    } | {ast.ExceptHandler, ast.match_case}
    for kind in sorted(kinds, key=lambda item: item.__name__):
        values: dict[str, object] = {name: [] for name in kind._fields}
        for name, field_type in kind._field_types.items():
            body: list[ast.stmt] = [ast.Pass() for _ in range(body_count)]
            if field_type == list[ast.stmt]:
                values[name] = body
            elif field_type == list[ast.excepthandler]:
                values[name] = [
                    ast.ExceptHandler(type=None, name=None, body=body)
                    for _ in range(container_count)
                ]
            elif field_type == list[ast.match_case]:
                values[name] = [
                    ast.match_case(pattern=ast.MatchAs(), guard=None, body=body)
                    for _ in range(container_count)
                ]
        node = kind(**values)
        expected = [
            value
            for child in ast.walk(node)
            for name, value in ast.iter_fields(child)
            if child._field_types[name] == list[ast.stmt]
        ]
        assert sorted(map(id, _statement_lists(node))) == sorted(map(id, expected)), (
            kind.__name__
        )


@settings(max_examples=80, deadline=None, database=None)
@given(
    wrapper=st.sampled_from(sorted(_WRAPPER_HEADS)),
    read=st.sampled_from(sorted(_WRAPPED_READS)),
    base_read=st.booleans(),
    depth=st.integers(min_value=1, max_value=3),
)
def test_the_read_guard_survives_blocks_inside_nested_classes(
    wrapper: str, read: str, base_read: bool, depth: int
) -> None:
    head, indent = _WRAPPER_HEADS[wrapper]
    for _ in range(depth):
        head = "    class Outer:\n" + textwrap.indent(head, "    ")
        indent += 4
    source = _nested_class_source(
        head, indent, _WRAPPED_READS[read], base_read=base_read
    )
    found = register_read_breaches(source, helper_module=False)
    assert any(
        item.startswith("class Holder:") and item.endswith(":" + read) for item in found
    ), found


if __name__ == "__main__":
    unittest.main()
