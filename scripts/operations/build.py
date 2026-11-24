"""Custodian build orchestrator: sandbox, delete owned vault, then publish."""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eii_core.reasons import closed_code, reason
from operations.common import Refusal, read_json


def fc_register_sha256() -> str | None:
    """Hash the file EII_FC_REGISTER_FILE names, from the lead's shell (L-1509).

    Unset lists nothing. The bytes come from the product's one register read
    (a regular file, no symlink); an unreadable file or value refuses with a
    fixed reason that carries neither the value nor the path.
    """
    from eii_product.config import ConfigError, read_fc_register_file
    from eii_product.register_file import RegisterRefusal, read_register_bytes

    with contextlib.suppress(ConfigError, RegisterRefusal):
        setting = read_fc_register_file()
        if setting is None:
            return None
        return hashlib.sha256(read_register_bytes(setting)).hexdigest()
    raise Refusal("fc_register_unreadable") from None


def build_release(
    root: Path,
    *,
    code_root: Path | None = None,
    cache: Path | None = None,
    extensions: Path | None = None,
    sandbox: Callable[..., Any] | None = None,
    cleanup: Callable[[Path], None] = shutil.rmtree,
    validate: Callable[[Path], object] | None = None,
    parameter_set: str | None = None,
) -> Path:
    if parameter_set is not None:
        raise Refusal("public_only_parameter_selection")
    import sandbox_launch

    code_root = root if code_root is None else code_root
    if sandbox is None:
        sandbox = sandbox_launch.run_in_sandbox
    if validate is None:
        sys.path.insert(0, str(code_root / "product/src"))
        from eii_product.store.release_check import check_release

        validate = check_release
    work = root / ".operations/build"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work, prefix="public-") as scratch:
        temporary = Path(scratch)
        vault, stage = temporary / "vault", temporary / "release"
        vault.mkdir()
        stage.mkdir()
        layout = sandbox_launch.Layout(
            code_root,
            root / "data/public_cache" if cache is None else cache,
            vault,
            root / "data/engine_extensions" if extensions is None else extensions,
            staging=stage,
        )
        try:
            # Adapt stored Public outputs before the read-only sandbox mount.
            # Older independently reviewed envelopes keep their existing path.
            spec = layout.cache / "review/release_spec.json"
            if spec.exists() or spec.is_symlink():
                from eii_custodian.release.producer import produce

                listed = fc_register_sha256()
                try:
                    produce(layout.cache, fc_register_sha256=listed)
                except Exception as error:
                    code = reason(error)
                    raise Refusal(
                        code, 8 if code == "candidate_written_approval_missing" else 4
                    ) from None
            result = sandbox(
                "build-release",
                layout,
                (
                    sys.executable,
                    "-I",
                    "-B",
                    str(code_root / "scripts/sandbox_inside/public_release.py"),
                    str(code_root),
                    str(layout.cache),
                    str(stage),
                ),
            )
            if result.returncode != 0:
                if (
                    result.returncode == 1
                    and getattr(result, "stderr", "").strip()
                    == "protected_release_not_built"
                ):
                    raise Refusal("protected_release_not_built", 1)
                raise Refusal(
                    closed_code(
                        getattr(result, "stderr", "").strip(), "operation_failed"
                    )
                )
        except sandbox_launch.SandboxError:
            raise Refusal("sandbox_enforcement_failed", 1) from None
        finally:
            try:
                cleanup(vault)
                if vault.exists():
                    raise OSError
            except OSError:
                raise Refusal("vault_cleanup_failed", 1) from None
        validate(stage)
        manifest = read_json(stage / "manifest.json", "release_missing")
        identity = str(manifest["release_id"])
        from operations.install import HASH, file_inventory, public_kind

        public_kind(stage)
        if HASH.fullmatch(identity) is None:
            raise Refusal("release_folder_identity_mismatch")
        exports = root / "data/releases"
        exports.mkdir(parents=True, exist_ok=True)
        target = exports / identity
        if target.exists():
            if file_inventory(target) != file_inventory(stage):
                raise Refusal("install_byte_mismatch")
        else:
            os.rename(stage, target)
        return target
