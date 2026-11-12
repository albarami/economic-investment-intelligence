"""Compose-file contract tests (K01-K04)."""

from __future__ import annotations

import errno
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import compose_rules as rules

import sandbox_check

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "infra" / "compose.yaml"


def replace_once(text: str, old: str, new: str) -> str:
    """Replace one planted text and refuse an ambiguous fixture."""
    count = text.count(old)
    if count != 1:
        raise AssertionError(f"plant occurs {count} times")
    return text.replace(old, new)


class ComposeFile(unittest.TestCase):
    """The existing Compose file and one plant per rule."""

    def test_real_file_passes(self) -> None:
        """K01: the tracked file satisfies the complete contract."""
        self.assertEqual(rules.check_compose_file(COMPOSE), [])
        self.assertEqual(
            tuple(
                str(port)
                for port in sandbox_check.BANNED_PORTS
                if str(port) in rules.FORBIDDEN_TEXT
            ),
            ("55432",),
        )

    def test_file_and_yaml_rules(self) -> None:
        """K02: one plant for env-file, file, YAML and root shape."""
        source = COMPOSE.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "infra"
            folder.mkdir()
            copy = folder / "compose.yaml"
            shutil.copy2(COMPOSE, copy)
            env_file = folder / ".env"
            env_file.write_text("", encoding="utf-8")
            self.assertEqual(
                rules.check_compose_file(copy),
                [
                    "compose: env-file: infra/.env exists beside compose.yaml; "
                    "Compose would read it",
                ],
            )
            env_file.unlink()
            self.assertEqual(
                rules.check_compose_file(folder / "absent.yaml"),
                ["compose: file: infra/compose.yaml is missing"],
            )
        self.assertEqual(
            rules.check_compose("name: [\n"),
            ["compose: yaml: cannot be parsed"],
        )
        self.assertEqual(
            rules.check_compose("- item\n"),
            ["compose: yaml: top level is not a mapping"],
        )
        self.assertEqual(rules.check_compose(source), [])

    def test_contract_rules(self) -> None:
        """K03: one plant for each structural or value rule."""
        source = COMPOSE.read_text(encoding="utf-8")
        plants = [
            (
                "\nsecrets:\n",
                "\nother:\n",
                "compose: top-level-keys: keys is "
                "['name', 'other', 'services', 'volumes'], expected "
                "['name', 'secrets', 'services', 'volumes']",
            ),
            (
                "name: eii-poc",
                "name: eii",
                "compose: name: name is 'eii', expected 'eii-poc'",
            ),
            (
                "  db:\n",
                "  other:\n",
                "compose: services: services is ['other'], expected ['db']",
            ),
            (
                "    pull_policy: never",
                "    restart: always\n    pull_policy: never",
                "compose: service-keys: db keys is "
                "['environment', 'healthcheck', 'image', 'ports', 'pull_policy', "
                "'restart', 'secrets', 'volumes'], expected "
                "['environment', 'healthcheck', 'image', 'ports', 'pull_policy', "
                "'secrets', 'volumes']",
            ),
            (
                rules.IMAGE,
                rules.IMAGE[:-1] + ("0" if rules.IMAGE[-1] != "0" else "1"),
                "compose: image: image is "
                f"{(rules.IMAGE[:-1] + ('0' if rules.IMAGE[-1] != '0' else '1'))!r}, "
                f"expected {rules.IMAGE!r}",
            ),
            (
                "pull_policy: never",
                "pull_policy: always",
                "compose: pull-policy: pull_policy is 'always', expected 'never'",
            ),
            (
                '}:5432"',
                '}:5433"',
                "compose: ports: ports is "
                "['127.0.0.1:${EII_COMPOSE_DB_PORT:?required, derived from "
                "EII_DATABASE_URL}:5433'], expected "
                f"{rules.PORTS!r}",
            ),
            (
                "/run/secrets/postgres_superuser_password",
                "/run/secrets/other",
                "compose: environment: environment is "
                "{'POSTGRES_PASSWORD_FILE': '/run/secrets/other'}, expected "
                f"{rules.ENVIRONMENT!r}",
            ),
            (
                "      - postgres_superuser_password\n    volumes:",
                "      - other\n    volumes:",
                "compose: secrets: db secrets is ['other'], expected "
                f"{rules.SERVICE_SECRETS!r}",
            ),
            (
                "eii_pgdata:/var/lib/postgresql",
                "eii_pgdata:/var/lib/postgresql/data",
                "compose: volumes: db volumes is "
                "['eii_pgdata:/var/lib/postgresql/data'], expected "
                f"{rules.SERVICE_VOLUMES!r}",
            ),
            (
                "interval: 2s",
                "interval: 3s",
                "compose: healthcheck: healthcheck is "
                "{'test': ['CMD', 'pg_isready', '-h', '127.0.0.1', '-p', "
                "'5432'], 'interval': '3s', 'retries': 30}, expected "
                f"{rules.HEALTHCHECK!r}",
            ),
            (
                "secrets:\n  postgres_superuser_password:\n",
                "secrets:\n  other:\n",
                "compose: secrets: top-level secrets is "
                "{'other': {'file': '../data/compose/postgres_superuser_password'}}, "
                f"expected {rules.TOP_SECRETS!r}",
            ),
            (
                "volumes:\n  eii_pgdata:\nsecrets:",
                "volumes:\n  other:\nsecrets:",
                "compose: volumes: top-level volumes is {'other': None}, expected "
                f"{rules.TOP_VOLUMES!r}",
            ),
        ]
        ran: list[str] = []
        for old, new, expected in plants:
            with self.subTest(expected=expected):
                ran.append(expected)
                problems = rules.check_compose(replace_once(source, old, new))
                self.assertEqual(problems, [expected])
        self.assertEqual(ran, [plant[2] for plant in plants])

    def test_read_errors_and_encoding(self) -> None:
        """K05: read errors and invalid UTF-8 retain deterministic failures."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compose.yaml"
            for error, code in (
                (OSError(errno.EACCES, "planted"), "EACCES"),
                (OSError("planted"), "OSError"),
            ):
                with (
                    self.subTest(code=code),
                    mock.patch.object(Path, "read_bytes", side_effect=error),
                ):
                    self.assertEqual(
                        rules.check_compose_file(path),
                        [f"compose: file: infra/compose.yaml cannot be read ({code})"],
                    )
            path.write_bytes(b"\xff")
            self.assertEqual(
                rules.check_compose_file(path),
                ["compose: file: infra/compose.yaml is not UTF-8"],
            )

    def test_each_forbidden_text(self) -> None:
        """K06: every forbidden token has a plant independent of structure."""
        source = COMPOSE.read_text(encoding="utf-8")
        for token in ("shared_preload_libraries", "55432", "0.0.0.0", "trust"):
            with self.subTest(token=token):
                self.assertEqual(
                    rules.check_compose(source + f"# {token}\n"),
                    [f"compose: forbidden-text: contains {token}"],
                )

    def test_unknown_service_stops_value_checks(self) -> None:
        """K07: an unknown service reports its shape before dependent values."""
        source = COMPOSE.read_text(encoding="utf-8")
        source = replace_once(source, "  db:\n", "  other:\n")
        source = replace_once(
            source, "../data/compose/postgres_superuser_password", "other-file"
        )
        self.assertEqual(
            rules.check_compose(source),
            ["compose: services: services is ['other'], expected ['db']"],
        )

    def test_text_rules(self) -> None:
        """K04: one plant for forbidden text and interpolation."""
        source = COMPOSE.read_text(encoding="utf-8")
        forbidden = rules.check_compose(source + "# trust\n")
        self.assertEqual(
            forbidden,
            ["compose: forbidden-text: contains trust"],
        )
        interpolation = rules.check_compose(source + "# ${OTHER}\n")
        self.assertEqual(
            interpolation,
            [
                "compose: interpolation: names is "
                "['EII_COMPOSE_DB_PORT', 'OTHER'], expected "
                "['EII_COMPOSE_DB_PORT']",
            ],
        )


if __name__ == "__main__":
    unittest.main()
