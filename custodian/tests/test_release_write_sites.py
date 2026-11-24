"""Every filesystem write and read of the release writers goes through ``pinned``.

Ruling L-1515 item 2: a source scan (AST) of the modules S3-P04 changed fails
on any write call outside ``pinned``'s own primitives. Round 3c extends the
scan to file reads (``open`` for reading, ``os.open`` with read flags,
``fdopen`` for reading, ``Path.read_*``, ``stat`` and the pathname probes and
listings). The allowed sites are exact multisets, so a new site, a moved site
or a removed site all fail and the site table of the S3-P04 return must change
with them.

Under ruling L-1632 these two guards catch regressions in honest release code.
They do not contain hostile code inside the same interpreter: genuine pinned
code can run with rebound globals or caller-supplied callables. Containing a
hostile writer requires a process boundary, recorded as an open item; pinning
runtime call sites and the outermost pinned frame is not implemented here.
"""

from __future__ import annotations

import ast
import json
import marshal
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from public_assembly_fixture import approve, inputs

RELEASE = Path(__file__).resolve().parents[1] / "src" / "eii_custodian" / "release"
# S3-T16: the heights staging of the draft writes only through place_artefact.
MODULES = (
    "artefacts.py",
    "heights_artefacts.py",
    "pinned.py",
    "producer.py",
    "spec_draft.py",
)

# (module, function, family): pinned's primitives and reviewed ctypes boundary.
WRITES = Counter(
    {
        ("pinned.py", "_renameat2", "renameat2"): 1,
        ("pinned.py", "_roll_back", "renameat2"): 1,
        ("pinned.py", "publish", "renameat2"): 2,
        ("pinned.py", "target", "mkdir"): 1,
        ("pinned.py", "publish", "os.open-write"): 1,
        ("pinned.py", "publish", "fdopen-write"): 1,
        ("pinned.py", "_unlink_owned", "unlink"): 1,
        ("pinned.py", "<module>", "ctypes"): 2,  # import and CDLL(None)
        ("pinned.py", "_renameat2", "ctypes"): 7,  # get_errno; six argtypes/restype
        ("pinned.py", "publish", "replace"): 1,  # the bool parameter read as a value
    }
)
# Reads: pinned's no-follow descriptor walk and read, and one exempt site,
# ``artefacts._source``, which opens the caller's source file outside the cache
# no-follow and checks it is regular on the descriptor before anything is made.
READS = Counter(
    {
        ("pinned.py", "_identity", "stat"): 1,
        ("pinned.py", "_pin", "os.open-read"): 1,
        ("pinned.py", "root", "os.open-read"): 1,
        ("pinned.py", "read", "os.open-read"): 1,
        ("pinned.py", "read", "fdopen-read"): 1,
        ("artefacts.py", "_source", "os.open-read"): 1,
        ("artefacts.py", "_source", "fdopen-read"): 1,
        # Part A's exact approval-missing outcome probes the path before reading.
        ("producer.py", "produce", "probe"): 2,
    }
)
ALLOWED = WRITES + READS

_NAMED = {
    "system": "process",
    "popen": "process",
    "posix_spawn": "process",
    "posix_spawnp": "process",
    "fork": "process",
    "forkpty": "process",
    "execv": "process",
    "execve": "process",
    "execl": "process",
    "execle": "process",
    "execlp": "process",
    "execlpe": "process",
    "execvp": "process",
    "execvpe": "process",
    "spawnv": "process",
    "spawnve": "process",
    "spawnl": "process",
    "spawnle": "process",
    "spawnlp": "process",
    "spawnlpe": "process",
    "spawnvp": "process",
    "spawnvpe": "process",
    "replace": "replace",
    "rename": "rename",
    "renames": "rename",
    "mkdir": "mkdir",
    "makedirs": "makedirs",
    "unlink": "unlink",
    "remove": "unlink",
    "removedirs": "rmdir",
    "rmdir": "rmdir",
    "touch": "touch",
    "write_text": "write_text",
    "write_bytes": "write_bytes",
    "link": "link",
    "symlink": "link",
    "symlink_to": "link",
    "hardlink_to": "link",
    "truncate": "truncate",
    "ftruncate": "truncate",
    # Round 3e (cf2 finding 3): metadata mutations of a path are writes too.
    "chmod": "metadata",
    "lchmod": "metadata",
    "fchmod": "metadata",
    "chown": "metadata",
    "lchown": "metadata",
    "fchown": "metadata",
    "utime": "metadata",
    "futimes": "metadata",
    "setxattr": "metadata",
    "lsetxattr": "metadata",
    "fsetxattr": "metadata",
    "removexattr": "metadata",
    "lremovexattr": "metadata",
    "fremovexattr": "metadata",
    "chflags": "metadata",
    "lchflags": "metadata",
    "mkfifo": "mknod",
    "mknod": "mknod",
    "read_bytes": "read_bytes",
    "read_text": "read_text",
    "stat": "stat",
    "lstat": "stat",
    "is_file": "probe",
    "is_dir": "probe",
    "exists": "probe",
    "is_symlink": "probe",
    "iterdir": "listing",
    "listdir": "listing",
    "scandir": "listing",
    "glob": "listing",
    "rglob": "listing",
    "walk": "listing",
}
READ_FAMILIES = {
    "open-read",
    "os.open-read",
    "fdopen-read",
    "read_bytes",
    "read_text",
    "stat",
    "probe",
    "listing",
}
_MODULE_FAMILIES = {
    "ctypes",
    "tempfile",
    "shutil",
    "subprocess",
    "multiprocessing",
    "concurrent.futures",
    "pty",
}
_WRITE_FLAGS = {"O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND", "O_TMPFILE"}
_JOINS = {"_path", "local", "joinpath", "join"}


def _name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _argument(call: ast.Call, index: int, keyword: str) -> ast.expr | None:
    if len(call.args) > index:
        return call.args[index]
    return next((k.value for k in call.keywords if k.arg == keyword), None)


def _writes_mode(mode: ast.expr | None) -> bool:
    """A literal read mode is not a write; any other mode is (fail closed)."""
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return any(flag in mode.value for flag in "wax+")
    return True


def _writes_flags(flags: ast.expr | None, constants: dict[str, ast.expr]) -> bool:
    """``os.open`` flags naming a write flag, or flags that cannot be read."""
    if flags is None:
        return True
    names: set[str] = set()
    pending = [flags]
    while pending:
        node = pending.pop()
        for child in ast.walk(node):
            name = _name(child) if isinstance(child, ast.expr) else None
            if isinstance(child, ast.Name) and child.id in constants:
                pending.append(constants.pop(child.id))
            elif isinstance(child, ast.Name) and child.id != "os":
                return True  # a variable the scan cannot read
            elif name is not None:
                names.add(name)
    return bool(names & _WRITE_FLAGS)


Aliases = dict[str, tuple[str | None, str | None]]


def _aliases(tree: ast.Module) -> Aliases:
    """Each local name and the ``(owner, name)`` it stands for.

    Round 3f (cf3 finding 2): ``from os import f as g``, ``import os as m``
    and a simple ``g = f`` or ``g = os.f`` anywhere in the module, whatever
    its scope (conservative: a name aliased in one function counts in all)."""
    found: Aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (
                    node.module == "os"
                    or alias.name == "pinned"
                    or (node.module and node.module.split(".")[-1] == "pinned")
                ):
                    found[alias.asname or alias.name] = (node.module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    found[alias.asname] = (None, alias.name)
        elif isinstance(node, ast.Assign) and isinstance(
            node.value, (ast.Name, ast.Attribute)
        ):
            value = node.value
            owner = _name(value.value) if isinstance(value, ast.Attribute) else None
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = (owner, _name(value))
    return found


def _resolve(name: str | None, aliases: Aliases) -> tuple[str | None, str | None]:
    """Follow ``name`` through the aliases to its canonical ``(owner, name)``."""
    owner: str | None = None
    seen: set[str] = set()
    while name is not None and name in aliases and name not in seen:
        seen.add(name)
        aliased, name = aliases[name]
        owner = aliased or owner
    return owner, name


def _family(
    call: ast.Call, constants: dict[str, ast.expr], aliases: Aliases
) -> str | None:
    function = call.func
    name = _name(function)
    owner = ast.unparse(function.value) if isinstance(function, ast.Attribute) else None
    if isinstance(function, ast.Name):
        owner, name = _resolve(name, aliases)
    owner = _resolve(owner, aliases)[1]
    if owner in _MODULE_FAMILIES:
        return owner
    if name == "getattr" and any(
        isinstance(a, ast.Constant) and a.value == "renameat2" for a in call.args
    ):
        return "renameat2"
    if name is None:
        return None
    if "renameat2" in name:
        return "renameat2"
    if name in _NAMED:
        return _NAMED[name]
    if name == "open" and owner == "os":
        flags = _argument(call, 1, "flags")
        writes = _writes_flags(flags, dict(constants))
        return "os.open-write" if writes else "os.open-read"
    if name == "open":
        index = 1 if isinstance(function, ast.Name) else 0
        writes = _writes_mode(_argument(call, index, "mode"))
        return "open-write" if writes else "open-read"
    if name == "fdopen":
        writes = _writes_mode(_argument(call, 1, "mode"))
        return "fdopen-write" if writes else "fdopen-read"
    return None


def _is_join(node: ast.AST) -> bool:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return True
    return isinstance(node, ast.Call) and _name(node.func) in _JOINS


def _pinned_owner(node: ast.expr, aliases: Aliases) -> bool:
    name = _resolve(ast.unparse(node), aliases)[1]
    return name is not None and name.split(".")[-1] == "pinned"


def _private_sites(node: ast.AST, aliases: Aliases) -> int:
    if isinstance(node, ast.Attribute):
        return node.attr.startswith("_") and _pinned_owner(node.value, aliases)
    if isinstance(node, ast.ImportFrom):
        if node.module and node.module.split(".")[-1] == "pinned":
            return sum(alias.name.startswith("_") for alias in node.names)
        return 0
    return (
        isinstance(node, ast.Call)
        and _name(node.func) == "getattr"
        and bool(node.args)
        and _pinned_owner(node.args[0], aliases)
    )


def _value_family(
    node: ast.AST, parent: ast.AST | None, aliases: Aliases
) -> str | None:
    if not isinstance(node, (ast.Name, ast.Attribute)) or not isinstance(
        node.ctx, ast.Load
    ):
        return None
    if isinstance(parent, ast.Call) and parent.func is node:
        return None
    if isinstance(parent, ast.Attribute) and parent.value is node:
        return None
    # No mode/flags are known when a callable is passed on: count a write.
    family = _family(ast.Call(func=node, args=[], keywords=[]), {}, aliases)
    if family in {"open-read", "fdopen-read"}:
        return family.replace("-read", "-write")
    return family if family not in READ_FAMILIES else None


def _sites(module: str, source: str) -> Counter[tuple[str, str, str]]:
    tree = ast.parse(source)
    constants = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    aliases = _aliases(tree)
    found: Counter[tuple[str, str, str]] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom) and node.module:
                names.extend([node.module, *(node.module + "." + n for n in names)])
            for family in _MODULE_FAMILIES:
                if not any(n == family or n.startswith(family + ".") for n in names):
                    continue
                found[(module, "<module>", family)] += 1
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    owners = {
        id(child): function.name
        for function in functions
        for child in ast.walk(function)
    }
    parents = {
        id(child): node
        for node in ast.walk(tree)
        for child in ast.iter_child_nodes(node)
    }
    for node in ast.walk(tree):
        owner = owners.get(id(node), "<module>")
        if module != "pinned.py":
            if count := _private_sites(node, aliases):
                found[(module, owner, "pinned-private")] += count
        family = _value_family(node, parents.get(id(node)), aliases)
        if family is not None:
            found[(module, owner, family)] += 1
        if isinstance(node, ast.Call):
            family = _family(node, constants, aliases)
            if family is not None:
                found[(module, owners.get(id(node), "<module>"), family)] += 1
    # A path join used after a check: in a function that publishes through
    # ``pinned``, a joined path may only be a discarded check expression.
    for function in functions:
        if function.name == "publish" or not any(
            isinstance(n, ast.Attribute) and n.attr == "publish"
            for n in ast.walk(function)
        ):
            continue
        discarded = {
            id(statement.value)
            for statement in ast.walk(function)
            if isinstance(statement, ast.Expr)
        }
        for node in ast.walk(function):
            if _is_join(node) and id(node) not in discarded:
                found[(module, function.name, "join")] += 1
    return found


def _all_sites() -> Counter[tuple[str, str, str]]:
    found: Counter[tuple[str, str, str]] = Counter()
    for module in MODULES:
        found += _sites(module, (RELEASE / module).read_text(encoding="utf-8"))
    return found


def _compare(found: Counter[tuple[str, str, str]], allowed: Counter) -> None:
    assert found == allowed, {
        "unexpected": dict(found - allowed),
        "missing": dict(allowed - found),
    }


def test_every_write_site_is_one_of_pinneds_own_primitives() -> None:
    found = _all_sites()
    _compare(
        Counter({k: n for k, n in found.items() if k[2] not in READ_FAMILIES}), WRITES
    )


def test_every_read_site_is_one_of_pinneds_own_primitives() -> None:
    found = _all_sites()
    _compare(Counter({k: n for k, n in found.items() if k[2] in READ_FAMILIES}), READS)


def test_the_two_tables_cover_every_site() -> None:
    _compare(_all_sites(), ALLOWED)


@pytest.mark.parametrize(
    ("line", "family"),
    [
        ("open(p, 'w')", "open-write"),
        ("open(p, mode)", "open-write"),
        ("Path(p).open('a')", "open-write"),
        ("os.open(p, os.O_WRONLY)", "os.open-write"),
        ("os.open(p, flags)", "os.open-write"),
        ("os.fdopen(d, 'wb')", "fdopen-write"),
        ("os.replace(a, b)", "replace"),
        ("os.rename(a, b)", "rename"),
        ("pinned._renameat2(d, a, b, 0)", "renameat2"),
        ("getattr(libc, 'renameat2')", "renameat2"),
        ("os.mkdir(p)", "mkdir"),
        ("os.makedirs(p)", "makedirs"),
        ("os.unlink(p)", "unlink"),
        ("os.remove(p)", "unlink"),
        ("os.rmdir(p)", "rmdir"),
        ("tempfile.mkstemp()", "tempfile"),
        ("shutil.copyfile(a, b)", "shutil"),
        ("subprocess.run(a)", "subprocess"),
        ("multiprocessing.Process(a)", "multiprocessing"),
        ("concurrent.futures.ProcessPoolExecutor()", "concurrent.futures"),
        ("pty.spawn(a)", "pty"),
        ("os.system(s)", "process"),
        ("os.popen(s)", "process"),
        ("os.posix_spawn(p, a, b)", "process"),
        ("os.posix_spawnp(p, a, b)", "process"),
        ("os.fork()", "process"),
        ("os.forkpty()", "process"),
        ("os.execv(p, a)", "process"),
        ("os.execve(p, a, b)", "process"),
        ("os.execl(p, a)", "process"),
        ("os.execle(p, a, b)", "process"),
        ("os.execlp(p, a)", "process"),
        ("os.execlpe(p, a, b)", "process"),
        ("os.execvp(p, a)", "process"),
        ("os.execvpe(p, a, b)", "process"),
        ("os.spawnv(0, p, a)", "process"),
        ("os.spawnve(0, p, a, b)", "process"),
        ("os.spawnl(0, p, a)", "process"),
        ("os.spawnle(0, p, a, b)", "process"),
        ("os.spawnlp(0, p, a)", "process"),
        ("os.spawnlpe(0, p, a, b)", "process"),
        ("os.spawnvp(0, p, a)", "process"),
        ("os.spawnvpe(0, p, a, b)", "process"),
        ("ctypes.CDLL(None)", "ctypes"),
        ("ctypes.get_errno()", "ctypes"),
        ("Path(p).write_text(s)", "write_text"),
        ("Path(p).write_bytes(b)", "write_bytes"),
        ("Path(p).touch()", "touch"),
        ("Path(p).mkdir()", "mkdir"),
        ("Path(p).unlink()", "unlink"),
        ("os.chmod(p, 0)", "metadata"),
        ("os.lchmod(p, 0)", "metadata"),
        ("os.fchmod(d, 0)", "metadata"),
        ("Path(p).chmod(0)", "metadata"),
        ("Path(p).lchmod(0)", "metadata"),
        ("os.chown(p, 0, 0)", "metadata"),
        ("os.lchown(p, 0, 0)", "metadata"),
        ("os.fchown(d, 0, 0)", "metadata"),
        ("os.utime(p)", "metadata"),
        ("os.setxattr(p, s, b)", "metadata"),
        ("os.removexattr(p, s)", "metadata"),
        ("os.chflags(p, 0)", "metadata"),
        ("os.truncate(p, 0)", "truncate"),
        ("os.ftruncate(d, 0)", "truncate"),
        ("Path(p).rename(a)", "rename"),
        ("Path(p).replace(a)", "replace"),
        ("Path(p).rmdir()", "rmdir"),
        ("os.link(a, b)", "link"),
        ("os.symlink(a, b)", "link"),
        ("Path(p).symlink_to(a)", "link"),
        ("Path(p).hardlink_to(a)", "link"),
        ("os.mkfifo(p)", "mknod"),
        ("os.mknod(p)", "mknod"),
        ("shutil.chown(p, s)", "shutil"),
        ("shutil.copymode(a, b)", "shutil"),
        ("open(p)", "open-read"),
        ("open(p, 'rb')", "open-read"),
        ("Path(p).open()", "open-read"),
        ("os.open(p, os.O_RDONLY | os.O_NOFOLLOW)", "os.open-read"),
        ("os.fdopen(d, 'rb')", "fdopen-read"),
        ("Path(p).read_bytes()", "read_bytes"),
        ("Path(p).read_text()", "read_text"),
        ("os.stat(p)", "stat"),
        ("Path(p).stat()", "stat"),
        ("Path(p).is_file()", "probe"),
        ("Path(p).exists()", "probe"),
        ("os.listdir(p)", "listing"),
        ("Path(p).iterdir()", "listing"),
    ],
)
def test_each_call_family_is_detected(line: str, family: str) -> None:
    source = f"def f(p, a, b, d, s, mode, flags, libc):\n    {line}\n"
    expected = Counter({("m.py", "f", family): 1})
    if line.startswith("pinned._"):
        expected[("m.py", "f", "pinned-private")] = 1
    assert _sites("m.py", source) == expected


@pytest.mark.parametrize(
    "line", ["stream.write(b)", "stream.read()", "os.fstat(d)", "os.close(d)"]
)
def test_descriptor_reads_and_writes_are_not_sites(line: str) -> None:
    source = f"def f(p, d, b, stream):\n    {line}\n"
    assert _sites("m.py", source) == Counter()


# Round 3f (cf3 finding 2): an alias of ``os`` or of one of its functions is
# resolved to the canonical call before it is classified.
@pytest.mark.parametrize(
    ("lines", "family"),
    [
        (["from os import chmod as change_mode", "change_mode(p, 0)"], "metadata"),
        (["from os import chmod", "chmod(p, 0)"], "metadata"),
        (["from os import open as low", "low(p, os.O_WRONLY)"], "os.open-write"),
        (["from os import open", "open(p, os.O_RDONLY)"], "os.open-read"),
        (["from os import replace as swap", "swap(a, b)"], "replace"),
        (["import os as system", "system.open(p, system.O_CREAT)"], "os.open-write"),
        (["change_mode = os.chmod", "change_mode(p, 0)"], "metadata"),
        (["change = os.chmod", "again = change", "again(p, 0)"], "metadata"),
        (["system = os", "system.open(p, flags)"], "os.open-write"),
        (["m = os", "low = m.open", "low(p, os.O_RDONLY)"], "os.open-read"),
        (["writer = open", "writer(p, 'w')"], "open-write"),
        (["loop = again", "again = loop", "again(p, 0)"], None),
    ],
)
def test_an_aliased_call_is_classified_as_its_canonical_call(
    lines: list[str], family: str | None
) -> None:
    body = "".join(f"    {line}\n" for line in lines)
    source = f"def f(p, a, b, flags):\n{body}"
    values = (
        sum(" = " in line for line in lines)
        if family not in {None, "os.open-read"}
        else 0
    )
    # Assigning the os module is not a write-callable value.
    values -= sum(line.endswith(" = os") for line in lines) if values else 0
    expected = (
        Counter() if family is None else Counter({("m.py", "f", family): 1 + values})
    )
    if family == "os.open-read" and lines[0] == "m = os":
        expected[("m.py", "f", "os.open-write")] = 1
    assert _sites("m.py", source) == expected


@given(
    name=st.sampled_from([*sorted(n for n in _NAMED if hasattr(os, n)), "open"]),
    alias=st.text("abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=6),
    depth=st.integers(0, 3),
    imported=st.booleans(),
)
def test_any_alias_chain_of_an_os_function_is_classified_as_the_function(
    name: str, alias: str, depth: int, imported: bool
) -> None:
    first = (
        f"from os import {name} as z_{alias}0"
        if imported
        else f"z_{alias}0 = os.{name}"
    )
    chain = [f"z_{alias}{i + 1} = z_{alias}{i}" for i in range(depth)]
    lines = [first, *chain, f"z_{alias}{depth}(p, os.O_WRONLY)"]
    aliased = _sites("m.py", "def f(p):\n" + "".join(f"    {x}\n" for x in lines))
    plain = _sites("m.py", f"def f(p):\n    os.{name}(p, os.O_WRONLY)\n")
    count = depth + (1 if imported else 2)
    family = next(iter(plain))[2]
    if family in READ_FAMILIES:
        count = 1
    assert aliased == Counter({("m.py", "f", family): count})
    assert sum(plain.values()) == 1


def test_a_joined_path_kept_in_a_publishing_function_is_a_site() -> None:
    source = (
        "def w(cache, name):\n"
        "    _path(cache, name)\n"
        "    kept = cache / name\n"
        "    with pinned.publish(leaf) as out:\n"
        "        out.write(b'')\n"
    )
    assert _sites("m.py", source) == Counter({("m.py", "w", "join"): 1})


def test_an_imported_tempfile_or_shutil_is_a_site() -> None:
    source = "import shutil\nfrom tempfile import mkstemp\n"
    assert _sites("m.py", source) == Counter(
        {("m.py", "<module>", "shutil"): 1, ("m.py", "<module>", "tempfile"): 1}
    )


# Round 3e (cf2 finding 3) and round 3f (cf3 finding 2): a metadata write
# planted in either publication caller, plain or through an alias of ``os``,
# is exactly one unexpected write site.
PLANTS = {
    "spec_draft.py": (
        "draft",
        "        document = _document(cache, listing)\n",
    ),
    "producer.py": (
        "_write",
        "            stream.write(canonical_json(value).encode())\n",
    ),
    "artefacts.py": (
        "place_artefact",
        "            with _source(Path(source_file)) as stream:\n",
    ),
}
ALIASED_CHMOD = ("from os import chmod as change_mode", "change_mode(cache, 0)")


def _planted(module: str, *lines: str) -> str:
    """The module's source with ``lines`` planted in its publication caller."""
    source = (RELEASE / module).read_text(encoding="utf-8")
    anchor = PLANTS[module][1]
    assert source.count(anchor) == 1
    indent = anchor[: len(anchor) - len(anchor.lstrip())]
    return source.replace(anchor, "".join(f"{indent}{x}\n" for x in lines) + anchor)


@pytest.mark.parametrize("module", sorted(PLANTS))
@pytest.mark.parametrize(
    ("lines", "family"),
    [
        (("Path(cache).chmod(0)",), "metadata"),
        (ALIASED_CHMOD, "metadata"),
        (("change_mode = os.chmod", "change_mode(cache, 0)"), "metadata"),
        (("if False:", "    os.system('exit 0')"), "process"),
        (("if False:", "    import ctypes"), "ctypes"),
    ],
)
def test_a_planted_write_in_a_publication_caller_fails_the_guard(
    module: str, lines: tuple[str, ...], family: str
) -> None:
    source = (RELEASE / module).read_text(encoding="utf-8")
    planted = _planted(module, *lines)
    found = _all_sites() - _sites(module, source) + _sites(module, planted)
    writes = Counter({k: n for k, n in found.items() if k[2] not in READ_FAMILIES})
    function = "<module>" if family == "ctypes" else PLANTS[module][0]
    count = 2 if lines[0] == "change_mode = os.chmod" else 1
    assert writes - WRITES == Counter({(module, function, family): count})
    with pytest.raises(AssertionError):
        _compare(writes, WRITES)


# Rulings L-1530 and L-1539: parent-side fixture setup, then the hook before
# importing any writer. Round 4 refuses every event by default, independent of
# its pathname and dispatch spelling. Only the named read/import events and
# pinned's required primitives are exempt. Limit: executed paths only; libc
# renameat2 has no pathname audit event, nor does a write to an open descriptor.
_AUDIT = r"""
import ctypes, importlib.util, json, os, sys, types
from pathlib import Path
# NumPy initializes process environment flags; do so before auditing writers,
# rather than permit os.putenv/unsetenv in the guarded execution.
import numpy

writer, cache, pinned_file, source, listing = sys.argv[1:6]
planted = sys.stdin.read()
early = sorted(
    m for m in sys.modules
    if m.startswith("eii_custodian") or m == "public_assembly_fixture"
)
if early:
    print("early " + " ".join(early))
    sys.exit(3)
WRITE = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
# Events that do not themselves mutate files or start another process.
READ_ONLY = {
    "import",  # load dependencies; their own events still pass through hook
    "exec",  # pinned identity is the code object, not its filename
    "compile",  # compiling a filename grants no pinned privileges
    "marshal.loads",  # decoded code must still match a genuine code object
    "os.listdir",  # import machinery enumerates package search directories
    "os.scandir",  # read directory entries, never mutate them
    "sys._getframe",  # inspect the caller below without recursive hook calls
    "object.__getattr__",  # read frame.f_code to attribute each event
    "sys._getframemodulename",  # standard-library caller introspection
    "builtins.id",  # dependency import bookkeeping
}
READ_ONLY = frozenset(READ_ONLY)
# Only these direct pinned calls may mutate; a new primitive needs review.
PINNED = frozenset({"open", "os.mkdir", "os.remove"})
STDLIB = os.path.dirname(os.__file__) + os.sep
lines = []


def code_objects(code):
    yield code
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            yield from code_objects(constant)


GENUINE = frozenset(code_objects(compile(Path(pinned_file).read_bytes(), pinned_file, "exec")))


def hook(event, args, GENUINE=GENUINE, PINNED=PINNED, READ_ONLY=READ_ONLY,
         WRITE=WRITE, STDLIB=STDLIB, cache=cache):
    if event == "object.__setattr__":
        if args[1] not in {"__code__", "__defaults__", "__kwdefaults__"}:
            return
    elif event in READ_ONLY:
        return
    # Read-flag opens (including descriptor reads) cannot modify a file.
    if event == "open" and isinstance(args[2], int) and not args[2] & WRITE:
        return
    frame = sys._getframe(1)
    filename = frame.f_code.co_filename
    # The harness changes directory once; a writer's chdir is never exempt.
    if event == "os.chdir" and filename == "<string>" and args == (cache,):
        return
    while frame.f_back and (
        frame.f_code.co_filename.startswith(STDLIB)
        or frame.f_code.co_filename.startswith("<frozen ")
    ):
        frame = frame.f_back
    if frame.f_code in GENUINE:
        # Load only the current process's libc and resolve only renameat2;
        # arbitrary dynamic libraries and symbols are not read-only imports.
        if event == "ctypes.dlopen" and args == (None,):
            return
        if event == "ctypes.dlsym" and args[1] == "renameat2":
            return
        # CPython audits the raw libc call, without pathname arguments.
        if event in {"ctypes.call_function", "ctypes.get_errno"} and frame.f_code.co_name == "_renameat2":
            lines.append("pinned " + event)
            return
        if event in PINNED:
            lines.append("pinned " + event)
            return
    lines.append("outside " + event + " " + Path(frame.f_code.co_filename).name)
    raise RuntimeError("release_write_outside_pinned")


sys.addaudithook(hook)
os.chdir(cache)
try:
    name = "eii_custodian.release." + writer.removesuffix(".py")
    if planted:
        spec = importlib.util.find_spec(name)
        module = sys.modules[name] = importlib.util.module_from_spec(spec)
        exec(compile(planted, spec.origin, "exec"), module.__dict__)
    else:
        module = importlib.import_module(name)
    if writer == "spec_draft.py":
        module.draft(Path(cache), json.loads(listing))
    elif writer == "producer.py":
        module.produce(Path(cache))
    else:
        for _ in range(2):  # the second run replaces: exchange and unlink
            module.place_artefact(Path(cache), "artefacts/INVENTED/file", Path(source))
finally:
    print("\n".join(lines))
"""


def _audited(
    tmp_path: Path,
    module: str,
    planted: str = "",
    before: str = "",
    *,
    cold: bool = False,
    existing_draft: bool = False,
    heights: bool = False,
) -> tuple[int, list[str]]:
    """Prepare the cache here, then run ``module`` in a hooked child."""
    cache = tmp_path.resolve() / "INVENTED-cache"
    cache.mkdir()
    source = cache.parent / "INVENTED-source"
    (cache / "INVENTED-existing").write_bytes(b"INVENTED-unchanged")
    listing = {}
    if module == "spec_draft.py":
        from custodian.tests.test_release_spec_draft import heights_inputs, setup

        _, listing = setup(cache)
        if heights:
            heights_inputs(cache)
        if existing_draft:
            (cache / "review/release_spec.draft.json").write_bytes(b"INVENTED-draft")
    elif module == "producer.py":
        inputs(cache)
        approve(cache)
    else:
        source.write_bytes(b"INVENTED-artefact")
    arguments = [
        module,
        str(cache),
        str(RELEASE / "pinned.py"),
        str(source),
        json.dumps(listing),
    ]
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    if cold:
        bytecode = tmp_path / "INVENTED-bytecode"
        bytecode.mkdir()
        environment.update(
            PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(bytecode)
        )
    done = subprocess.run(
        [sys.executable, "-B", "-c", before + _AUDIT, *arguments],
        input=planted,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    if existing_draft:
        assert "ValueError: spec_draft_exists" in done.stderr.splitlines()
        assert (
            cache / "review/release_spec.draft.json"
        ).read_bytes() == b"INVENTED-draft"
    return done.returncode, done.stdout.splitlines()


@pytest.mark.parametrize("module", sorted(PLANTS))
@pytest.mark.parametrize(
    "early",
    [
        "eii_custodian.release.producer",
        "eii_custodian.release.artefacts",
        "public_assembly_fixture",
    ],
)
def test_a_writer_imported_before_the_hook_is_refused(
    tmp_path: Path, module: str, early: str
) -> None:
    code, lines = _audited(tmp_path, module, before=f"import {early}\n")
    assert code == 3
    assert len(lines) == 1 and lines[0].split()[0] == "early"
    assert early in lines[0].split()


# The form cf4 names: the source scan does not see it, the hook must.
TOP_LEVEL = "getattr(__import__('os'), 'chmod')('.', 0)\n"


@pytest.mark.parametrize("module", sorted(PLANTS))
def test_a_module_top_level_dynamic_write_fails_the_audit_hook(
    tmp_path: Path, module: str
) -> None:
    source = (RELEASE / module).read_text(encoding="utf-8")
    assert _sites(module, source + TOP_LEVEL) == _sites(module, source)
    code, lines = _audited(tmp_path, module, source + TOP_LEVEL)
    assert code != 0
    assert lines == [f"outside os.chmod {module}"]


@pytest.mark.parametrize("module", sorted(PLANTS))
def test_every_executed_release_write_comes_from_pinned(
    tmp_path: Path, module: str
) -> None:
    code, lines = _audited(tmp_path, module)
    assert code == 0, lines
    assert lines and {line.split()[0] for line in lines} == {"pinned"}
    assert "pinned open" in lines
    if module != "spec_draft.py":
        assert "pinned os.remove" in lines


@pytest.mark.parametrize("module", sorted(PLANTS))
def test_a_cold_writer_import_comes_from_genuine_pinned_code(
    tmp_path: Path, module: str
) -> None:
    code, lines = _audited(tmp_path, module, cold=True)
    assert code == 0, lines
    assert lines and {line.split()[0] for line in lines} == {"pinned"}
    assert not any((tmp_path / "INVENTED-bytecode").iterdir())


def test_a_hooked_heights_draft_places_every_file_through_pinned(
    tmp_path: Path,
) -> None:
    """S3-T16: the four heights files enter the release only by pinned writes."""
    code, lines = _audited(tmp_path, "spec_draft.py", heights=True)
    assert code == 0, lines
    assert lines and {line.split()[0] for line in lines} == {"pinned"}
    placed = tmp_path.resolve() / "INVENTED-cache/artefacts/heights"
    assert len(list(placed.iterdir())) == 4


def test_a_hooked_existing_draft_keeps_its_own_refusal(tmp_path: Path) -> None:
    code, lines = _audited(tmp_path, "spec_draft.py", existing_draft=True)
    assert code != 0
    assert lines and {line.split()[0] for line in lines} == {"pinned"}
    assert "pinned ctypes.get_errno" in lines


@pytest.mark.parametrize("module", sorted(PLANTS))
@pytest.mark.parametrize("name", ["GENUINE", "PINNED", "READ_ONLY", "WRITE", "STDLIB"])
def test_hook_allowlists_are_captured_before_writer_import(
    tmp_path: Path, module: str, name: str
) -> None:
    value = {"WRITE": "0", "STDLIB": "'/'"}.get(name, "frozenset()")
    line = f"__import__('sys').modules['__main__'].{name} = {value}"
    code, lines = _audited(tmp_path, module, _planted(module, line))
    assert code == 0, lines
    assert lines and {line.split()[0] for line in lines} == {"pinned"}


@pytest.mark.parametrize("module", sorted(PLANTS))
def test_rebinding_cache_never_grants_the_harness_chdir_exception(
    tmp_path: Path, module: str
) -> None:
    lines = (
        "__import__('sys').modules['__main__'].cache = 'INVENTED-rebound'",
        "exec(compile(\"__import__('os').chdir('INVENTED-rebound')\", '<string>', 'exec'))",
    )
    code, seen = _audited(tmp_path, module, _planted(module, *lines))
    assert code != 0
    assert [line for line in seen if line.startswith("outside")] == [
        "outside os.chdir <string>"
    ]


@pytest.mark.parametrize("module", sorted(PLANTS))
@pytest.mark.parametrize("form", ["fsdecode", "global", "fix_filename", "bytecode"])
def test_filename_rebinding_never_grants_pinned_privileges(
    tmp_path: Path, module: str, form: str
) -> None:
    filename = repr(str(RELEASE / "pinned.py"))
    write = "open('INVENTED-spoof', 'w').close()"
    if form == "fsdecode":
        lines = (
            "__import__('os').fsdecode = lambda n: ''",
            f"exec(compile({write!r}, {filename}, 'exec'))",
        )
    elif form == "global":
        lines = (
            "__import__('sys').modules['__main__'].pinned_file = __file__",
            write,
        )
    elif form == "fix_filename":
        lines = (
            f"c = compile({write!r}, 'INVENTED', 'exec')",
            f"__import__('_imp')._fix_co_filename(c, {filename})",
            "exec(c)",
        )
    else:
        body = marshal.dumps(compile(write, str(RELEASE / "pinned.py"), "exec"))
        lines = (
            "exec(__import__('importlib._bootstrap_external', fromlist=['_compile_bytecode'])"
            f"._compile_bytecode({body!r}))",
        )
    code, seen = _audited(tmp_path, module, _planted(module, *lines))
    assert code != 0
    origin = module if form == "global" else "pinned.py"
    assert [line for line in seen if line.startswith("outside")] == [
        f"outside open {origin}"
    ]
    assert not (tmp_path / "INVENTED-cache/INVENTED-spoof").exists()


@pytest.mark.parametrize("module", sorted(PLANTS))
@pytest.mark.parametrize(
    ("lines", "family", "count"),
    [
        (
            (
                "from eii_custodian.release import pinned as _p",
                "_p._unlink_owned(-100, 'INVENTED-existing', _p._identity(-100, 'INVENTED-existing'))",
            ),
            "pinned-private",
            2,
        ),
        (
            (
                "from eii_custodian.release import pinned as _p",
                "getattr(_p, '_renameat2')(-100, 'INVENTED-existing', 'INVENTED-spoof', 0)",
            ),
            "pinned-private",
            1,
        ),
        (
            (
                "import functools",
                "pinned.publish(leaf, check=functools.partial(open, 'INVENTED-spoof', 'w'))",
            ),
            "open-write",
            1,
        ),
        (("from eii_custodian.release.pinned import _identity",), "pinned-private", 1),
    ],
)
def test_pinned_private_and_callable_plants_fail_the_static_guard(
    module: str, lines: tuple[str, ...], family: str, count: int
) -> None:
    original = _sites(module, (RELEASE / module).read_text(encoding="utf-8"))
    added = _sites(module, _planted(module, *lines)) - original
    assert added == Counter({(module, PLANTS[module][0], family): count})
    with pytest.raises(AssertionError, match=family):
        _compare(ALLOWED + added, ALLOWED)


@pytest.mark.parametrize(
    "source",
    [
        "from . import pinned as p\np._identity",
        "import eii_custodian.release.pinned as p\np._identity",
        "from eii_custodian.release import pinned\np = pinned\np._identity",
        "from .pinned import _identity as probe",
        "from . import pinned\ngetattr(pinned, name)",
        "from . import pinned\ngetattr(pinned, 'publish')",
    ],
)
def test_pinned_private_import_and_access_forms_are_sites(source: str) -> None:
    assert _sites("m.py", source) == Counter(
        {("m.py", "<module>", "pinned-private"): 1}
    )


def test_each_private_import_is_counted_and_public_pinned_access_is_allowed() -> None:
    assert _sites("m.py", "from .pinned import _identity, _unlink_owned") == Counter(
        {("m.py", "<module>", "pinned-private"): 2}
    )
    assert not _sites("m.py", "from . import pinned\npinned.publish(leaf)")


@given(
    name=st.text("abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=12),
    depth=st.integers(0, 4),
    form=st.sampled_from(["attribute", "getattr", "from"]),
)
def test_private_pinned_names_remain_sites_through_aliases(
    name: str, depth: int, form: str
) -> None:
    lines = ["from . import pinned as p0"]
    lines.extend(f"p{i + 1} = p{i}" for i in range(depth))
    if form == "attribute":
        lines.append(f"p{depth}._{name}")
    elif form == "getattr":
        lines.append(f"getattr(p{depth}, '_{name}')")
    else:
        lines.append(f"from .pinned import _{name} as z")
    assert _sites("m.py", "\n".join(lines)) == Counter(
        {("m.py", "<module>", "pinned-private"): 1}
    )


@pytest.mark.parametrize(
    ("value", "family"),
    [
        ("open", "open-write"),
        ("os.open", "os.open-write"),
        ("os.fdopen", "fdopen-write"),
        ("os.remove", "unlink"),
        ("os.chmod", "metadata"),
        ("Path(p).write_text", "write_text"),
    ],
)
@pytest.mark.parametrize(
    "context",
    [
        "partial({value}, p)",
        "map({value}, paths)",
        "saved = {value}",
        "stack.callback({value}, p)",
    ],
)
@pytest.mark.parametrize("module", ["m.py", "pinned.py"])
def test_write_callables_used_as_values_are_sites(
    value: str, family: str, context: str, module: str
) -> None:
    assert _sites(module, context.format(value=value)) == Counter(
        {(module, "<module>", family): 1}
    )


def test_a_value_use_unlink_planted_in_pinned_root_fails_the_static_guard() -> None:
    source = (RELEASE / "pinned.py").read_text(encoding="utf-8")
    anchor = "        stack.callback(os.close, parent)\n"
    assert source.count(anchor) == 1
    planted = source.replace(
        anchor, anchor + "        stack.callback(os.remove, 'x')\n"
    )
    added = _sites("pinned.py", planted) - _sites("pinned.py", source)
    assert added == Counter({("pinned.py", "root", "unlink"): 1})
    with pytest.raises(AssertionError, match="unlink"):
        _compare(_all_sites() + added, ALLOWED)


@example(values=[], context="stack.callback({value}, p)")
@example(values=[("os.remove", "unlink")], context="map({value}, paths)")
@example(values=[("open", "open-write")] * 6, context="partial({value}, p)")
@example(
    values=[("os.remove", "unlink"), ("os.chmod", "metadata"), ("os.remove", "unlink")],
    context="stack.callback({value}, p)",
)
@given(
    values=st.lists(
        st.sampled_from(
            [("os.remove", "unlink"), ("open", "open-write"), ("os.chmod", "metadata")]
        ),
        max_size=6,
    ),
    context=st.sampled_from(
        ["stack.callback({value}, p)", "map({value}, paths)", "partial({value}, p)"]
    ),
)
def test_pinned_value_use_sites_preserve_multiplicity(
    values: list[tuple[str, str]], context: str
) -> None:
    body = "\n".join("    " + context.format(value=value) for value, _ in values)
    source = "def root(p, paths, stack):\n    pass\n" + body
    assert _sites("pinned.py", source) == Counter(
        ("pinned.py", "root", family) for _, family in values
    )


@pytest.mark.parametrize("module", sorted(PLANTS))
@pytest.mark.parametrize(
    ("lines", "event"),
    [
        (
            (
                "__import__('sys').modules['__main__'].WRITE = 0",
                "getattr(__import__('os'), 'open')('INVENTED-spoof', 0o101)",
            ),
            "open",
        ),
        (
            (
                f"exec(compile(\"open('INVENTED-spoof', 'w').close()\", {str(RELEASE / 'pinned.py')!r}, 'exec'))",
            ),
            "open pinned.py",
        ),
        (
            (
                "exec(__import__('marshal').loads("
                + repr(
                    marshal.dumps(
                        compile(
                            "open('INVENTED-spoof', 'w').close()",
                            str(RELEASE / "pinned.py"),
                            "exec",
                        )
                    )
                )
                + "))",
            ),
            "open pinned.py",
        ),
        (
            ("def INVENTED(): pass", "INVENTED.__code__ = (lambda: None).__code__"),
            "object.__setattr__",
        ),
        (
            ("__import__('sys').modules['__main__'].hook.__defaults__ = ()",),
            "object.__setattr__",
        ),
        (
            ("__import__('sys').modules['__main__'].hook.__kwdefaults__ = {}",),
            "object.__setattr__",
        ),
        (ALIASED_CHMOD, "os.chmod"),
        (("getattr(__import__('os'), 'chdir')(cache)",), "os.chdir"),
        (("__import__('os').putenv('INVENTED_KEY', 'INVENTED')",), "os.putenv"),
        (("__import__('ctypes').CDLL(None)",), "ctypes.dlopen"),
        (("open(cache.parent / 'INVENTED-outside', 'w')",), "open"),
        (("getattr(__import__('os'), 'utime')(cache, None)",), "os.utime"),
        (("getattr(__import__('os'), 'mkdir')(cache / 'INVENTED-d')",), "os.mkdir"),
        (
            (
                "getattr(__import__('os'), 'symlink')('INVENTED-a', cache / 'INVENTED-b')",
            ),
            "os.symlink",
        ),
        (
            ("getattr(__import__('os'), 'truncate')(cache / 'INVENTED-existing', 0)",),
            "os.truncate",
        ),
        (
            (
                "__import__('subprocess').run([__import__('sys').executable, '-c', 'pass'])",
            ),
            "subprocess.Popen",
        ),
        (("__import__('os').system('exit 0')",), "os.system"),
        (("open(cache / 'INVENTED-x', 'w')",), "open"),
        (("__import__('os').rename(cache / 'a', 'b')",), "os.rename"),
        (("__import__('os').replace('a', cache / 'b')",), "os.rename"),
        (("__import__('os').remove(cache / 'a')",), "os.remove"),
        (("__import__('os').unlink('a')",), "os.remove"),
        (("__import__('shutil').rmtree(cache)",), "shutil.rmtree"),
        (("__import__('shutil').copyfile(__file__, 'a')",), "shutil.copyfile"),
    ],
)
def test_a_planted_write_outside_pinned_fails_the_audit_hook(
    tmp_path: Path, module: str, lines: tuple[str, ...], event: str
) -> None:
    code, seen = _audited(tmp_path, module, _planted(module, *lines))
    assert code != 0
    assert [line for line in seen if line.startswith("outside")] == [
        f"outside {event}"
        if event.endswith("pinned.py")
        else f"outside {event} {module}"
    ]
    cache = tmp_path / "INVENTED-cache"
    assert (cache / "INVENTED-existing").read_bytes() == b"INVENTED-unchanged"
    assert not (cache / "INVENTED-x").exists()
    assert not (cache / "INVENTED-spoof").exists()
    assert not (cache / "INVENTED-d").exists()
    assert not (cache / "INVENTED-b").is_symlink()
    assert not (tmp_path / "INVENTED-outside").exists()


@pytest.mark.parametrize(
    "family", ["subprocess", "multiprocessing", "concurrent.futures", "pty", "ctypes"]
)
@pytest.mark.parametrize(
    "form", ["import {family}", "import {family} as m", "from {family} import INVENTED"]
)
def test_process_module_imports_are_sites(family: str, form: str) -> None:
    assert _sites("m.py", form.format(family=family)) == Counter(
        {("m.py", "<module>", family): 1}
    )


@settings(max_examples=20, deadline=None)
@example(module="producer.py", form="str", mode="exec")
@example(module="spec_draft.py", form="bytes", mode="eval")
@example(module="artefacts.py", form="path", mode="single")
@given(
    module=st.sampled_from(sorted(PLANTS)),
    form=st.sampled_from(["str", "bytes", "path"]),
    mode=st.sampled_from(["exec", "eval", "single"]),
)
def test_pinned_filename_spoof_is_refused_in_any_compile_form(
    module: str, form: str, mode: str
) -> None:
    filename = repr(str(RELEASE / "pinned.py"))
    if form == "bytes":
        filename = f"__import__('os').fsencode({filename})"
    elif form == "path":
        filename = f"Path({filename})"
    line = (
        f"exec(compile(\"open('INVENTED-spoof', 'w').close()\", {filename}, {mode!r}))"
    )
    with tempfile.TemporaryDirectory(prefix="INVENTED-compile-") as folder:
        code, seen = _audited(Path(folder), module, _planted(module, line))
        assert code != 0
        assert [line for line in seen if line.startswith("outside")] == [
            "outside open pinned.py"
        ]
        assert not (Path(folder) / "INVENTED-cache/INVENTED-spoof").exists()


def test_a_pathname_write_planted_in_the_draft_is_in_the_scanned_modules(
    monkeypatch,
) -> None:
    path = RELEASE / "spec_draft.py"
    original = Path.read_text
    before = _all_sites()
    planted = _planted("spec_draft.py", '(cache / "INVENTED-x").write_text("INVENTED")')
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **kw: planted if self == path else original(self, *a, **kw),
    )
    assert _all_sites() - before == Counter(
        {("spec_draft.py", "draft", "write_text"): 1}
    )


def test_a_direct_heights_write_is_a_site_of_the_scanned_modules(
    monkeypatch,
) -> None:
    """S3-T16: a heights file written past place_artefact fails the scan."""
    path = RELEASE / "heights_artefacts.py"
    original = Path.read_text
    source = original(path, encoding="utf-8")
    anchor = "            placed = place_artefact(cache, target, source)\n"
    assert source.count(anchor) == 1
    planted = source.replace(
        anchor, "            _path(cache, target).write_bytes(b'INVENTED')\n" + anchor
    )
    before = _all_sites()
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **kw: planted if self == path else original(self, *a, **kw),
    )
    found = _all_sites()
    assert found - before == Counter(
        {("heights_artefacts.py", "stage_heights", "write_bytes"): 1}
    )
    with pytest.raises(AssertionError):
        _compare(found, ALLOWED)


@settings(max_examples=20, deadline=None)
@example(module="spec_draft.py", suffix="")
@example(module="producer.py", suffix="a")
@example(module="artefacts.py", suffix="." * 30)
@given(
    module=st.sampled_from(sorted(PLANTS)),
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz.", max_size=30),
)
def test_any_unknown_audit_event_is_refused(module: str, suffix: str) -> None:
    event = "INVENTED." + suffix
    with tempfile.TemporaryDirectory(prefix="INVENTED-audit-") as folder:
        code, lines = _audited(
            Path(folder),
            module,
            _planted(module, f"__import__('sys').audit({event!r})"),
        )
    assert code != 0
    assert [line for line in lines if line.startswith("outside")] == [
        f"outside {event} {module}"
    ]
