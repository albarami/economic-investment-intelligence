"""Checksummed immutable applications and exact release copies on local fixtures."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch

from s3_t28_support import COMMIT, IDENTITY, WorkspaceCase

from operations.common import Refusal, encoded, sha
from operations.config import Environment
from operations.install import (
    archive_manifest,
    file_inventory,
    install_application,
    install_release,
    verify_application,
)


def archive_fixture(root: Path) -> Path:
    files = {
        name: b"INVENTED-offline-input"
        for name in (
            "product/src/eii_product/api/app.py",
            "core/src/eii_core/__init__.py",
            "web/dist/index.html",
            "runtime/dependencies.json",
            "runtime/site-packages/INVENTED.py",
            "scripts/operations/serve.py",
        )
    }
    document = dict(
        code_version=COMMIT,
        files={k: hashlib.sha256(v).hexdigest() for k, v in files.items()},
        features=["INVENTED-finished"],
        python_version="3.14.1",
    )
    archive = root / "application.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        for name, body in {**files, "application.json": encoded(document)}.items():
            stream.writestr(name, body)
    archive.with_suffix(".zip.sha256").write_text(sha(archive))
    return archive


class Install(WorkspaceCase):
    def test_identical_leaf_application_symlink_is_still_mutable(self) -> None:
        archive = archive_fixture(self.root)
        stage, digest = install_application(archive, self.env("staging"), COMMIT)
        live, _ = install_application(archive, self.env("live"), COMMIT)
        shutil.rmtree(live)
        live.symlink_to(stage, target_is_directory=True)
        with self.assertRaisesRegex(Refusal, "mutable_application_refused"):
            verify_application(live, code_version=COMMIT, application_sha256=digest)

    def test_untracked_executable_or_web_source_cannot_enter_committed_archive(
        self,
    ) -> None:
        from operations.package import source_files

        def git(root: Path, *args: str) -> bytes:
            if args[0] == "rev-parse":
                return COMMIT.encode()
            if args[0] == "ls-tree":
                return b"scripts/operations/serve.py\nscripts/operations/entry.py\nuv.lock\n"
            if args[0] == "ls-files":
                return b"web/src/INVENTED-unreviewed.tsx\0"
            return b"INVENTED-committed-source" if args[0] == "show" else b""

        with patch("operations.package._git", side_effect=git):
            with self.assertRaisesRegex(Refusal, "application_source_unavailable"):
                source_files(self.root, COMMIT)

    def setUp(self) -> None:
        super().setUp()
        runtime = patch("operations.install.verify_runtime")
        runtime.start()
        self.addCleanup(runtime.stop)

    def env(self, name: str) -> Environment:
        home = self.root / name
        return Environment(
            name,
            home / "releases" / IDENTITY,
            home / "state",
            8088 if name == "live" else 8089,
            ("127.0.0.1", 5432, "INVENTED_" + name),
        )

    def test_identical_archive_reused_and_each_input_tamper(self) -> None:
        archive = archive_fixture(self.root)
        staged, digest = install_application(archive, self.env("staging"), COMMIT)
        live, same = install_application(archive, self.env("live"), COMMIT)
        self.assertEqual(digest, same)
        self.assertEqual(file_inventory(staged), file_inventory(live))
        self.assertEqual(
            install_application(archive, self.env("live"), COMMIT), (live, digest)
        )
        for name in (
            "product/src/eii_product/api/app.py",
            "web/dist/index.html",
            "runtime/site-packages/INVENTED.py",
        ):
            path = live / name
            original = path.read_bytes()
            path.write_bytes(original + b"INVENTED-tamper")
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(Refusal, "application_verification_failed"),
            ):
                verify_application(live, code_version=COMMIT, application_sha256=digest)
            path.write_bytes(original)

    def test_archive_checksum_and_mutable_folder(self) -> None:
        archive = archive_fixture(self.root)
        archive.with_suffix(".zip.sha256").write_text("aa" * 32)
        with self.assertRaisesRegex(Refusal, "application_checksum_mismatch"):
            archive_manifest(archive)
        with self.assertRaisesRegex(Refusal, "mutable_application_refused"):
            verify_application(
                self.root, code_version=COMMIT, application_sha256="aa" * 32
            )

    def test_release_bytes_never_rebuilt_or_rewritten(self) -> None:
        source = self.root / "exports" / IDENTITY
        source.mkdir(parents=True)
        (source / "manifest.json").write_bytes(
            encoded(
                dict(
                    release_kind="public_only",
                    release_id=IDENTITY,
                    tables=[dict(file="table.parquet")],
                )
            )
        )
        (source / "table.parquet").write_bytes(b"INVENTED-original-table")
        original = file_inventory(source)
        application = self.root / "INVENTED-application"
        with patch(
            "eii_product.store.release_check.check_release",
            return_value=type(
                "Checked",
                (),
                {
                    "document": dict(
                        release_id=IDENTITY, tables=[dict(file="table.parquet")]
                    ),
                    "folder": source,
                },
            )(),
        ):
            for env in (self.env("staging"), self.env("live")):
                install_release(source, env, application)
                self.assertEqual(file_inventory(env.release), original)
                install_release(source, env, application)
            live = self.env("live")
            (live.release / "table.parquet").write_bytes(b"INVENTED-altered-table")
            with self.assertRaisesRegex(Refusal, "install_byte_mismatch"):
                install_release(source, live, application)
        self.assertEqual(file_inventory(source), original)

    def test_metadata_rewrite_cannot_rebind_corrupted_source(self) -> None:
        archive = archive_fixture(self.root)
        folder, digest = install_application(archive, self.env("live"), COMMIT)
        metadata = json.loads((folder / "application.json").read_bytes())
        name = "web/dist/index.html"
        (folder / name).write_bytes(b"INVENTED-replacement")
        metadata["files"][name] = sha(folder / name)
        (folder / "application.json").write_bytes(encoded(metadata))
        with self.assertRaisesRegex(Refusal, "application_verification_failed"):
            verify_application(folder, code_version=COMMIT, application_sha256=digest)
