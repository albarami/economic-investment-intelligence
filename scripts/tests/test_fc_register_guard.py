"""The runtime hook of ruling L-1528, beside the lexical register guard.

Only the authorised product ``read_fc_register_rows`` and custodian
``from_environment`` entry frames can exempt their configured primary and
active validated sibling (decision 0022 item 1). A subprocess installs
``sys.addaudithook`` for the ``open`` event and fails any open of a file in
the watched folder, which holds only invented stand-ins of the register's
shape under the test's temporary
folder, that no pinned reader performs. The hook covers only the paths
these tests execute, so the lexical guard in ``read_fc_register_rows``
(that checks both supplied paths against fresh configuration) stays.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pytest_no_provider import provider_request_log

# The test needs both planes, so it lives here and not under product/tests
# (rule 11); the runner's safe-path Python needs the root for both imports.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Loaded by name so the type check of scripts/ does not follow the planes' tests.
_INTAKE: Any = import_module("custodian.tests.test_registers_intake")
index_pins, write_inputs = _INTAKE.index_pins, _INTAKE.write_inputs
FIXTURE: Path = import_module("product.tests.test_fc_register_read").FIXTURE

__all__ = ["provider_request_log"]
REASON = "fc-register-open-outside-pinned-reader"
SCENE_OK = "scene-ok"
SIDE_SETTING = "EII_FC_REGISTER_FILE_STANDIN"

_PRELUDE = r"""
import os
import pathlib
import sys

WATCH = pathlib.Path(os.environ["FC_WATCH"]).resolve()


def pinned_on_stack(resolved):
    frame = sys._getframe()
    capture = None
    product = sys.modules.get("eii_product.register_file")
    intake = sys.modules.get("eii_custodian.publicdata.registers.intake")
    product_entry = getattr(getattr(product, "read_fc_register_rows", None), "__code__", None)
    intake_entry = getattr(getattr(intake, "from_environment", None), "__code__", None)
    capture_entry = getattr(getattr(intake, "_capture", None), "__code__", None)
    while frame is not None:
        local = frame.f_locals
        if frame.f_code is product_entry:
            configured = local.get("configured")
            return configured is not None and resolved == pathlib.Path(configured).resolve()
        if intake is not None:
            if frame.f_code is capture_entry:
                capture = local
            elif frame.f_code is intake_entry and "primary" in local:
                primary = pathlib.Path(local["environ"][local["setting"]])
                allowed = {primary, primary.with_name(primary.name + ".register.json")}
                if capture is not None and capture["primary"] == primary:
                    # The active sibling name has passed _capture's closed selection.
                    allowed.add(primary.parent / capture["name"])
                return resolved in {path.resolve() for path in allowed}
        frame = frame.f_back
    return False

def audit(event, args):
    if event != "open" or not args:
        return
    path = args[0]
    if isinstance(path, int):
        return
    try:
        resolved = pathlib.Path(os.fsdecode(os.fspath(path))).resolve()
    except (OSError, TypeError, ValueError):
        raise SystemExit("fc-register-open-outside-pinned-reader") from None
    if not resolved.is_relative_to(WATCH):
        return
    if not pinned_on_stack(resolved):
        raise SystemExit("fc-register-open-outside-pinned-reader")
"""

# A real import loader plants an open before the reader module executes.
_IMPORT_PLANT = r"""
import importlib.machinery

class ImportReadPlant:
    @staticmethod
    def find_spec(fullname, path, target=None):
        if fullname != os.environ["FC_IMPORT_MODULE"]:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        original = spec.loader.exec_module
        def exec_module(module):
            pathlib.Path(os.environ["EII_FC_REGISTER_FILE_STANDIN"]).read_bytes()
            original(module)
        spec.loader.exec_module = exec_module
        return spec

sys.meta_path.insert(0, ImportReadPlant)
"""

_SCENES: dict[str, str] = {
    "product_read": r"""
sys.addaudithook(audit)
from eii_product.config import read_fc_register_file
from eii_product.register_file import read_fc_register_rows

setting = read_fc_register_file()
assert setting is not None
bundle = read_fc_register_rows(setting, listed_sha256=os.environ["FC_LISTED"])
assert bundle is not None and bundle.rows
print("scene-ok")
""",
    "intake_read": r"""
import json
env = json.loads(os.environ["FC_INTAKE_ENV"])
pins = json.loads(os.environ["FC_INTAKE_PINS"])
assert "eii_custodian.publicdata.registers.intake" not in sys.modules
sys.addaudithook(audit)
from eii_custodian.publicdata.registers.intake import from_environment

current, history = from_environment(env, index_hashes=pins)
assert len(current) == 2 and len(history) == 2
print("scene-ok")
""",
    "direct_intake_helper": r"""
sys.addaudithook(audit)
from eii_custodian.publicdata.registers.intake import read_file
read_file(pathlib.Path(os.environ["EII_FC_REGISTER_FILE_STANDIN"]), 100000)
print("scene-ok")
""",
    "forged_intake_entry": r"""
sys.addaudithook(audit)
from eii_custodian.publicdata.registers.intake import read_file
def unauthorised(environ, setting, primary):
    return read_file(primary, 100000)
other = os.environ["EII_FC_REGISTER_FILE_STANDIN"]
unauthorised({"EII_FC_REGISTER_FILE": other}, "EII_FC_REGISTER_FILE", pathlib.Path(other))
print("scene-ok")
""",
    "direct_product_helper": r"""
sys.addaudithook(audit)
from eii_product.register_file import _read_path
_read_path(os.environ["EII_FC_REGISTER_FILE_STANDIN"], os.environ["FC_LISTED"])
print("scene-ok")
""",
    "path_read_bytes": r"""
sys.addaudithook(audit)
pathlib.Path(os.environ["EII_FC_REGISTER_FILE_STANDIN"]).read_bytes()
print("scene-ok")
""",
    "pathlike_event": r"""
sys.addaudithook(audit)
sys.audit("open", pathlib.Path(os.environ["EII_FC_REGISTER_FILE_STANDIN"]), "r", 0)
print("scene-ok")
""",
    "bad_path_type": r"""
sys.addaudithook(audit)
sys.audit("open", object(), "r", 0)
print("scene-ok")
""",
    "pathlike_oserror": r"""
sys.addaudithook(audit)
class BrokenPath:
    def __fspath__(self):
        raise OSError("invented path resolution failure")
sys.audit("open", BrokenPath(), "r", 0)
print("scene-ok")
""",
    "bytes_event": r"""
sys.addaudithook(audit)
sys.audit("open", os.fsencode(os.environ["EII_FC_REGISTER_FILE_STANDIN"]), "r", 0)
print("scene-ok")
""",
    "intake_wrong_capture": r"""
sys.addaudithook(audit)
import json
from eii_custodian.publicdata.registers import intake
original = intake.read_file
planted = False
def substituted(path, limit):
    global planted
    if not planted and path.name.endswith(".register.json"):
        planted = True
        intake._capture(pathlib.Path(os.environ["FC_SECONDARY_PRIMARY"]), "biz_register", json.loads(os.environ["FC_SECONDARY_CURRENT"]), historical=False)
    return original(path, limit)
intake.read_file = substituted
intake.from_environment(json.loads(os.environ["FC_INTAKE_ENV"]), index_hashes=json.loads(os.environ["FC_INTAKE_PINS"]))
print("scene-ok")
""",
    "bad_path_value": r"""
sys.addaudithook(audit)
sys.audit("open", "invented\0path", "r", 0)
print("scene-ok")
""",
    "product_wrong_path": r"""
sys.addaudithook(audit)
from eii_product import register_file
original = register_file._read_path
def substituted(path, listed):
    return original(os.environ["EII_FC_REGISTER_FILE_STANDIN"], listed)
register_file._read_path = substituted
register_file.read_fc_register_rows(
    os.environ["EII_FC_REGISTER_FILE"], listed_sha256=os.environ["FC_LISTED"]
)
print("scene-ok")
""",
    "intake_wrong_path": r"""
sys.addaudithook(audit)
import json
from eii_custodian.publicdata.registers import intake
original = intake.read_file
def substituted(path, limit):
    return original(pathlib.Path(os.environ["EII_FC_REGISTER_FILE_STANDIN"]), limit)
intake.read_file = substituted
intake.from_environment(json.loads(os.environ["FC_INTAKE_ENV"]), index_hashes=json.loads(os.environ["FC_INTAKE_PINS"]))
print("scene-ok")
""",
    "intake_wrong_sibling": r"""
sys.addaudithook(audit)
import json
from eii_custodian.publicdata.registers import intake
original = intake.read_file
def substituted(path, limit):
    if path.name == "qfc_companies.csv":
        path = path.with_name("2026-11.companies.csv")
    return original(path, limit)
intake.read_file = substituted
intake.from_environment(json.loads(os.environ["FC_INTAKE_ENV"]), index_hashes=json.loads(os.environ["FC_INTAKE_PINS"]))
print("scene-ok")
""",
    "descriptor_event": r"""
sys.addaudithook(audit)
sys.audit("open", 0, "r", 0)
print("scene-ok")
""",
    "hard_coded": r"""
sys.addaudithook(audit)
hard_coded = %OTHER%
with open(hard_coded, "rb") as handle:
    handle.read()
print("scene-ok")
""",
    "second_env": r"""
sys.addaudithook(audit)
side = os.environ["EII_FC_REGISTER_FILE_STANDIN"]
assert side != os.environ["EII_FC_REGISTER_FILE"]
with open(side, "rb") as handle:
    handle.read()
print("scene-ok")
""",
    "joined": r"""
sys.addaudithook(audit)
folder = os.environ["FC_FOLDER"]
name = os.environ["FC_OTHER_NAME"]
joined = os.path.join(folder, name)
assert joined != os.environ["EII_FC_REGISTER_FILE"]
with open(joined, "rb") as handle:
    handle.read()
print("scene-ok")
""",
    "alias_open": r"""
sys.addaudithook(audit)
alias_open = open
with alias_open(os.environ["EII_FC_REGISTER_FILE"], "rb") as handle:
    handle.read()
print("scene-ok")
""",
    "alias_os_open": r"""
sys.addaudithook(audit)
aliased = os.open
descriptor = aliased(os.environ["EII_FC_REGISTER_FILE"], os.O_RDONLY)
os.close(descriptor)
print("scene-ok")
""",
    "outside_watch": r"""
sys.addaudithook(audit)
outside = os.environ["FC_OUTSIDE"]
with open(outside, "rb") as handle:
    handle.read()
print("scene-ok")
""",
    "spelled": r"""
sys.addaudithook(audit)
folder = os.environ["FC_FOLDER"]
name = os.environ["FC_OTHER_NAME"]
spelled = folder + "/./" + name
assert spelled != os.environ["EII_FC_REGISTER_FILE"]
with open(spelled, "rb") as handle:
    handle.read()
print("scene-ok")
""",
    "symlink": r"""
sys.addaudithook(audit)
link = os.environ["FC_LINK"]
with open(link, "rb") as handle:
    handle.read()
print("scene-ok")
""",
}

_GREEN = ("product_read", "intake_read", "outside_watch")


def _scene(tmp_path: Path, name: str) -> subprocess.CompletedProcess[str]:
    """Run one scene in a subprocess over invented stand-ins under tmp_path."""
    watched = tmp_path / "guard"
    watched.mkdir()
    standin = watched / "stand_in_register.json"
    standin.write_bytes(FIXTURE.read_bytes())
    other = watched / "stand_in_register_two.json"
    other.write_bytes(FIXTURE.read_bytes())
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"invented plain file\n")
    link = tmp_path / "invented_alias_to_stand_in.json"
    link.symlink_to(standin)
    intake_env, indexes = write_inputs(watched)
    pins = index_pins(indexes)
    secondary_env, secondary_current = {}, {}
    if name == "intake_wrong_capture":
        secondary = Path(intake_env["EII_REGISTER_FILE"]).with_name(
            "invented_other.csv"
        )
        secondary.write_bytes(Path(intake_env["EII_REGISTER_FILE"]).read_bytes())
        secondary_env = {"EII_REGISTER_FILE": str(secondary)}
        secondary_current = {
            "receipt": indexes[0][1]["current"]["receipt"],
            "files": {"establishments": secondary.name},
        }
    import_module = ""
    if name in {"product_import_read", "intake_import_read"}:
        entry = "product_read" if name == "product_import_read" else "intake_read"
        import_module = (
            "eii_product.register_file"
            if entry == "product_read"
            else "eii_custodian.publicdata.registers.intake"
        )
        body = _IMPORT_PLANT + _SCENES[entry]
    else:
        body = _SCENES[name]
    program = (_PRELUDE + body).replace("%OTHER%", repr(str(other)))
    environment = {
        **os.environ,
        "EII_FC_REGISTER_FILE": str(standin),
        "FC_LISTED": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        SIDE_SETTING: str(other),
        "FC_WATCH": str(watched),
        "FC_SECONDARY_PRIMARY": secondary_env.get("EII_REGISTER_FILE", ""),
        "FC_SECONDARY_CURRENT": json.dumps(secondary_current),
        "FC_IMPORT_MODULE": import_module,
        "FC_INTAKE_ENV": json.dumps(intake_env),
        "FC_INTAKE_PINS": json.dumps(pins),
        "FC_FOLDER": str(watched),
        "FC_OTHER_NAME": other.name,
        "FC_OUTSIDE": str(outside),
        "FC_LINK": str(link),
    }
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(REPO_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_green(
    done: subprocess.CompletedProcess[str], tmp_path: Path, scene: str
) -> None:
    assert done.returncode == 0, scene + ": " + done.stderr
    assert done.stdout.strip() == SCENE_OK
    assert done.stderr == ""
    assert str(tmp_path) not in done.stdout + done.stderr


def _assert_refused(
    done: subprocess.CompletedProcess[str], tmp_path: Path, scene: str
) -> None:
    assert done.returncode != 0, scene + ": the planted read was allowed"
    assert done.stderr.splitlines() == [REASON], scene + ": " + done.stderr
    assert done.stdout == ""
    assert str(tmp_path) not in done.stderr


def test_the_pinned_product_reader_passes_the_hook(tmp_path: Path) -> None:
    _assert_green(_scene(tmp_path, "product_read"), tmp_path, "product_read")


def test_the_pinned_custodian_intake_passes_the_hook(tmp_path: Path) -> None:
    _assert_green(_scene(tmp_path, "intake_read"), tmp_path, "intake_read")


def test_a_hard_coded_path_read_fails(tmp_path: Path) -> None:
    _assert_refused(_scene(tmp_path, "hard_coded"), tmp_path, "hard_coded")


def test_a_second_environment_variable_read_fails(tmp_path: Path) -> None:
    _assert_refused(_scene(tmp_path, "second_env"), tmp_path, "second_env")


def test_a_path_joined_from_parts_fails(tmp_path: Path) -> None:
    _assert_refused(_scene(tmp_path, "joined"), tmp_path, "joined")


def test_open_called_by_an_alias_fails(tmp_path: Path) -> None:
    _assert_refused(_scene(tmp_path, "alias_open"), tmp_path, "alias_open")


def test_an_aliased_os_open_fails(tmp_path: Path) -> None:
    _assert_refused(_scene(tmp_path, "alias_os_open"), tmp_path, "alias_os_open")


def test_an_open_outside_the_watch_passes(tmp_path: Path) -> None:
    _assert_green(_scene(tmp_path, "outside_watch"), tmp_path, "outside_watch")


def test_a_re_spelled_watched_path_fails(tmp_path: Path) -> None:
    _assert_refused(_scene(tmp_path, "spelled"), tmp_path, "spelled")


def test_a_symbolic_link_to_the_stand_in_fails(tmp_path: Path) -> None:
    _assert_refused(_scene(tmp_path, "symlink"), tmp_path, "symlink")


@pytest.mark.parametrize(
    "scene",
    [
        "direct_intake_helper",
        "forged_intake_entry",
        "direct_product_helper",
        "path_read_bytes",
        "pathlike_event",
    ],
)
def test_helpers_and_pathlike_reads_are_refused(tmp_path: Path, scene: str) -> None:
    _assert_refused(_scene(tmp_path, scene), tmp_path, scene)


def test_descriptor_events_are_handled_separately(tmp_path: Path) -> None:
    _assert_green(_scene(tmp_path, "descriptor_event"), tmp_path, "descriptor_event")


@pytest.mark.parametrize(
    "form", ["literal", "second_env", "joined", "spelled", "symlink"]
)
def test_supplied_setting_cannot_override_environment(
    tmp_path: Path, form: str
) -> None:
    watched = tmp_path / "guard"
    watched.mkdir()
    target = watched / "primary.json"
    target.write_bytes(FIXTURE.read_bytes())
    other = watched / "other.json"
    other.write_bytes(FIXTURE.read_bytes())
    link = watched / "alias.json"
    link.symlink_to(target)
    expressions = {
        "literal": repr(str(other)),
        "second_env": 'os.environ["SIDE_SETTING"]',
        "joined": 'os.path.join(os.environ["FOLDER"], "other.json")',
        "spelled": 'os.environ["FOLDER"] + "/./primary.json"',
        "symlink": repr(str(link)),
    }
    program = """
import os
import sys
from eii_product.register_file import RegisterRefusal, read_fc_register_rows

def forbid_open(event, args):
    if event == "open":
        raise SystemExit("unexpected-register-open")

sys.addaudithook(forbid_open)
try:
    read_fc_register_rows(%EXPRESSION%, listed_sha256="0" * 64)
except RegisterRefusal as exc:
    raise SystemExit(exc.reason) from None
print("scene-ok")
""".replace("%EXPRESSION%", expressions[form])
    result = subprocess.run(
        [sys.executable, "-c", program],
        env={
            **os.environ,
            "EII_FC_REGISTER_FILE": str(target),
            "SIDE_SETTING": str(other),
            "FOLDER": str(watched),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert result.stderr.splitlines() == ["path_refused"]
    assert result.stdout == ""
    assert str(tmp_path) not in result.stdout + result.stderr


@given(st.text())
def test_unconfigured_paths_never_reach_open(supplied: str) -> None:
    from eii_product.register_file import RegisterRefusal, read_fc_register_rows

    with pytest.MonkeyPatch.context() as patch:
        patch.delenv("EII_FC_REGISTER_FILE", raising=False)

        def forbidden(*args: object, **kwargs: object) -> None:
            pytest.fail("unconfigured path reached open")

        patch.setattr(Path, "read_text", forbidden)
        with pytest.raises(
            RegisterRefusal,
            match=r"^register_setting_invalid$"
            if supplied == ""
            else r"^path_refused$",
        ):
            read_fc_register_rows(supplied, listed_sha256="0" * 64)


def test_fresh_environment_and_omitted_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_product.register_file import RegisterRefusal, read_fc_register_rows

    target = tmp_path / "primary.json"
    target.write_bytes(FIXTURE.read_bytes())
    monkeypatch.setenv("EII_FC_REGISTER_FILE", str(target))
    listed = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert read_fc_register_rows(str(target), listed_sha256=listed) is not None
    monkeypatch.setenv("EII_FC_REGISTER_FILE", str(tmp_path / "other.json"))
    with pytest.raises(RegisterRefusal, match=r"^path_refused$"):
        read_fc_register_rows(str(target), listed_sha256=listed)
    with pytest.raises(RegisterRefusal, match=r"^path_refused$"):
        read_fc_register_rows(None, listed_sha256=listed)
    monkeypatch.delenv("EII_FC_REGISTER_FILE")
    with pytest.raises(RegisterRefusal, match=r"^path_refused$"):
        read_fc_register_rows(None, asked_path=str(target), listed_sha256=listed)
    assert read_fc_register_rows(None, listed_sha256=listed) is None


@pytest.mark.parametrize(
    "scene",
    [
        "pathlike_oserror",
        "bytes_event",
        "intake_wrong_capture",
        "bad_path_type",
        "bad_path_value",
        "product_wrong_path",
        "intake_wrong_path",
        "intake_wrong_sibling",
        "product_import_read",
        "intake_import_read",
    ],
)
def test_authorisation_is_bound_to_call_and_import(tmp_path: Path, scene: str) -> None:
    _assert_refused(_scene(tmp_path, scene), tmp_path, scene)
