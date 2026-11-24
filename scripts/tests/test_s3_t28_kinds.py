"""Public-only operational kinds and associations, without engine imports."""

import json

from s3_t28_support import IDENTITY, WorkspaceCase

from operations.common import Refusal
from operations.install import public_kind


class PublicKinds(WorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        (self.root / "manifest.json").write_text(
            json.dumps(dict(release_kind="public_only", release_id=IDENTITY))
        )

    def test_unfrozen_unregistered_public_succeeds(self) -> None:
        self.assertEqual(public_kind(self.root)["release_id"], IDENTITY)

    def test_each_parameter_selection(self) -> None:
        for choice in ("A", "B"):
            with (
                self.subTest(choice=choice),
                self.assertRaisesRegex(Refusal, "public_only_parameter_selection"),
            ):
                public_kind(self.root, parameter_set=choice)

    def test_descriptor_only(self) -> None:
        (self.root / "freeze.json").write_text("{}")
        with self.assertRaisesRegex(Refusal, "public_only_freeze_forbidden"):
            public_kind(self.root)

    def test_register_association_only(self) -> None:
        register = self.root / "register.jsonl"
        register.write_text(json.dumps(dict(release_id=IDENTITY)) + "\n")
        with self.assertRaisesRegex(Refusal, "public_only_register_forbidden"):
            public_kind(self.root, register)

    def test_supported_protected_kind_gets_own_refusal(self) -> None:
        (self.root / "manifest.json").write_text(
            json.dumps(dict(release_kind="protected", release_id=IDENTITY))
        )
        with self.assertRaisesRegex(Refusal, "protected_release_requires_s11_t09"):
            public_kind(self.root)
