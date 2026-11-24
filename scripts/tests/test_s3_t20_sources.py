"""S3-T20 B4 and B5: hosting-off sources and the paid-assistant switch at start-up.

The closed child environment of the operations plane and the serving policy of
the product plane are checked together, so these cases live here.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from typing import Any, Literal
from unittest.mock import Mock

import s3_t28_support  # noqa: F401  (puts scripts, core and product on the path)
import test_s3_t28_controls as controls_fixture
from hypothesis import given, settings
from hypothesis import strategies as st
from s3_t28_support import IDENTITY, ROOT

from eii_product.api.area_context import AreaContextFactory
from eii_product.api.startup import ServingPolicy
from eii_product.store.startup import StartupRefusal
from eii_product.tools.public_context_tools import run_card
from operations.common import Refusal
from operations.config import (
    API_NAMES,
    ENVIRONMENT_NAMES,
    INSTALL_NAMES,
    runtime_environment,
)

FOLDER = Path("INVENTED-release")
ENVIRONMENTS: tuple[Literal["development", "staging", "live"], ...] = (
    "development",
    "staging",
    "live",
)
PAID = "remote_paid_assistant_refused"
SWITCH = "EII_REMOTE_ALLOW_PAID_ASSISTANT"
UNWANTED = "unwanted_runtime_setting"
# Setting, its single value, an enable attempt, the refusal and the policy field.
TRAFFIC = (
    "EII_TRAFFIC_PROVIDER",
    "simulated",
    "live",
    "traffic_mode_refused",
    "traffic",
)
BUSYNESS = ("EII_BUSYNESS_SOURCE", "off", "on", "busyness_mode_refused", "busyness")
WEATHER = ("EII_WEATHER_SOURCE", "off", "on", "weather_mode_refused", "weather")
SOURCES = (TRAFFIC, BUSYNESS, WEATHER)
# Empty, the single values, case, padding, fused and split text, look-alikes,
# truthy words, a control character and a long run.
EDGES = (
    "",
    "off",
    "simulated",
    "OFF",
    "Off",
    "Simulated",
    " off",
    "off ",
    "off\n",
    "\toff",
    "offoff",
    "off,on",
    "off=on",
    "o ff",
    "\u043eff",
    "\uff4f\uff46\uff46",
    "off\x00",
    "\x00",
    "on",
    "1",
    "0",
    "true",
    "false",
    "none",
    "live",
    "x" * 4096,
)
TEXT = st.one_of(st.sampled_from(EDGES), st.text())
SOURCE_DIRECTORIES = ("scripts", "core/src", "product/src", "custodian/src")


def store(engine: str = "postgres") -> Any:
    return Mock(engine=engine, release_id=IDENTITY)


def switch_reads(text: str) -> int:
    """How often a source reads or compares the switch name."""
    found = 0
    for node in ast.walk(ast.parse(text)):
        operands: list[ast.AST] = []
        if isinstance(node, ast.Call):
            operands = [*node.args, *(keyword.value for keyword in node.keywords)]
        elif isinstance(node, ast.Subscript):
            operands = [node.slice]
        elif isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
        found += sum(
            isinstance(operand, ast.Constant) and operand.value == SWITCH
            for operand in operands
        )
    return found


class Sources(unittest.TestCase):
    sensitive = controls_fixture.Controls.sensitive

    def enable_refused(self, source: tuple[str, str, str, str, str]) -> None:
        name, single, enable, reason, field = source
        verify = Mock()
        for environment in ENVIRONMENTS:
            base = {"EII_ENVIRONMENT": environment}
            with self.subTest(layer="operations", environment=environment):
                self.assertEqual(runtime_environment(base)[name], single)
                self.assertEqual(
                    runtime_environment({**base, name: single})[name], single
                )
                with self.assertRaisesRegex(Refusal, f"^{reason}$"):
                    runtime_environment({**base, name: enable})
            with self.subTest(layer="policy", environment=environment):
                ServingPolicy(environment, IDENTITY, verify).require(store(), FOLDER)
                planted: Any = {field: enable}
                with self.assertRaisesRegex(StartupRefusal, f"^{reason}$"):
                    ServingPolicy(environment, IDENTITY, verify, **planted).require(
                        store(), FOLDER
                    )
        # Only the three valid policies reached the shared verifier.
        self.assertEqual(verify.call_count, len(ENVIRONMENTS))
        self.sensitive(runtime_environment, ({name: enable},), reason)
        self.sensitive(
            ServingPolicy.require,
            (ServingPolicy("live", IDENTITY, Mock(), **planted), store(), FOLDER),
            reason,
            kind=StartupRefusal,
        )

    def test_traffic_enable_refused(self) -> None:
        self.enable_refused(TRAFFIC)

    def test_busyness_enable_refused(self) -> None:
        self.enable_refused(BUSYNESS)

    def test_weather_enable_refused(self) -> None:
        self.enable_refused(WEATHER)

    def test_child_environment_and_policy_carry_the_same_fixed_values(self) -> None:
        child = runtime_environment({})
        policy = ServingPolicy("live", IDENTITY, Mock())
        for name, single, _enable, _reason, field in SOURCES:
            with self.subTest(name=name):
                self.assertIn(name, API_NAMES)
                self.assertEqual(child[name], single)
                self.assertEqual(getattr(policy, field), single)
        self.assertEqual(
            policy.hosting_off(),
            {field for _name, single, *_rest, field in SOURCES if single == "off"},
        )
        unforced = controls_fixture.without_call(runtime_environment, "result.update")
        self.assertNotIn(BUSYNESS[0], unforced({}))
        self.assertNotIn(WEATHER[0], unforced({}))

    def test_each_edge_value_at_both_layers(self) -> None:
        for source in SOURCES:
            for value in EDGES:
                with self.subTest(name=source[0], value=value[:12]):
                    self.closed_environment(source, value)
                    self.policy(source, value)

    @settings(deadline=None)
    @given(st.sampled_from(SOURCES), TEXT)
    def test_property_only_empty_and_the_single_value_pass_the_child(
        self, source: tuple[str, str, str, str, str], value: str
    ) -> None:
        self.closed_environment(source, value)

    @settings(deadline=None)
    @given(
        st.sampled_from(SOURCES),
        st.one_of(TEXT, st.none(), st.booleans(), st.integers(), st.binary()),
    )
    def test_property_only_the_single_value_passes_the_policy(
        self, source: tuple[str, str, str, str, str], value: object
    ) -> None:
        self.policy(source, value)

    def closed_environment(
        self, source: tuple[str, str, str, str, str], value: str
    ) -> None:
        name, single, _enable, reason, _field = source
        if value in ("", single):
            self.assertEqual(runtime_environment({name: value})[name], single)
            return
        with self.assertRaises(Refusal) as refused:
            runtime_environment({name: value})
        self.assertEqual(str(refused.exception), reason)

    def policy(self, source: tuple[str, str, str, str, str], value: object) -> None:
        _name, single, _enable, reason, field = source
        verify = Mock()
        planted: Any = {field: value}
        candidate = ServingPolicy("live", IDENTITY, verify, **planted)
        if value == single:
            candidate.require(store(), FOLDER)
            verify.assert_called_once_with()
            return
        with self.assertRaises(StartupRefusal) as refused:
            candidate.require(store(), FOLDER)
        self.assertEqual(refused.exception.reason, reason)
        verify.assert_not_called()


class Switch(unittest.TestCase):
    sensitive = controls_fixture.Controls.sensitive

    def test_switch_never_set(self) -> None:
        for table in (API_NAMES, INSTALL_NAMES, *ENVIRONMENT_NAMES.values()):
            self.assertNotIn(SWITCH, table)
        for environment in ENVIRONMENTS:
            base = {"EII_ENVIRONMENT": environment}
            # Unset and empty are off, and the name never reaches the child.
            self.assertNotIn(SWITCH, runtime_environment(base))
            self.assertNotIn(SWITCH, runtime_environment({**base, SWITCH: ""}))
            for value in ("1", "0", "off", "false", " "):
                for installing in (False, True):
                    with (
                        self.subTest(
                            environment=environment, value=value, installing=installing
                        ),
                        self.assertRaisesRegex(Refusal, f"^{UNWANTED}$"),
                    ):
                        runtime_environment(
                            {**base, SWITCH: value}, installing=installing
                        )
        self.sensitive(runtime_environment, ({SWITCH: "1"},), UNWANTED)

    def test_no_source_reads_the_switch(self) -> None:
        for directory in SOURCE_DIRECTORIES:
            for path in sorted((ROOT / directory).rglob("*.py")):
                if "tests" in path.relative_to(ROOT).parts:
                    continue
                with self.subTest(path=path.relative_to(ROOT).as_posix()):
                    self.assertEqual(switch_reads(path.read_text(encoding="utf-8")), 0)

    def test_planted_switch_reads_are_counted(self) -> None:
        for text in (
            f"import os\non = os.environ.get('{SWITCH}') == '1'",
            f"import os\non = os.environ['{SWITCH}']",
            f"on = name == '{SWITCH}'",
            f"on = read(name='{SWITCH}')",
        ):
            with self.subTest(text=text):
                self.assertEqual(switch_reads(text), 1)
        # A documenting sentence or a table of refused names is not a read.
        self.assertEqual(switch_reads(f"REFUSED = frozenset({{'{SWITCH}'}})"), 0)
        self.assertEqual(switch_reads(f'"""The switch {SWITCH} is documented."""'), 0)


class Capability(unittest.TestCase):
    sensitive = controls_fixture.Controls.sensitive

    def test_assistant_key_and_opener_turn_red_without_their_refusals(self) -> None:
        policy = ServingPolicy("live", IDENTITY, Mock())
        self.sensitive(
            ServingPolicy.assistant_key, (policy,), PAID, kind=StartupRefusal
        )
        self.sensitive(
            ServingPolicy.assistant_open,
            (policy, "http://provider.invalid/v1"),
            PAID,
            kind=StartupRefusal,
        )

    def test_busyness_capability_turns_red_when_removed(self) -> None:
        class Read(Exception):
            pass

        policy = ServingPolicy("live", IDENTITY, Mock())
        context = AreaContextFactory(
            IDENTITY, None, hosting_off=policy.hosting_off()
        ).for_playbook("site_check")
        args = {"place_keys": ["INVENTED-venue-a"]}
        served = store()
        served.fetch.side_effect = Read
        result = run_card(served, "venue_busyness", args, context)
        self.assertEqual(
            (result.status, result.reason), ("OUT_OF_SCOPE", "hosting_off_source")
        )
        served.fetch.assert_not_called()
        mutant = controls_fixture.without_return(
            run_card,
            "PublicResult(tool, 'OUT_OF_SCOPE', store.release_id, "
            "reason='hosting_off_source')",
        )
        with self.assertRaises(Read):
            mutant(served, "venue_busyness", args, context)
        self.assertEqual(served.fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
