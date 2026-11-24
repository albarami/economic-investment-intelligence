"""A copied D1 plant and the actual Part-A handler inventory."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from hypothesis import given
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reason_guard import GENERIC, check, violations

ROOT = Path(__file__).resolve().parents[2]
D1 = """try:
    produce(layout.cache)
except Exception:
    raise Refusal("assembly_build_refused") from None
"""


class ReasonGuard(unittest.TestCase):
    def test_d1_plant_is_rejected(self) -> None:
        self.assertEqual(violations(D1), [3])
        self.assertEqual(
            violations(
                D1.replace("except Exception:", "except Exception as error:").replace(
                    '"assembly_build_refused"', "reason(error)"
                )
            ),
            [],
        )

    def test_part_a_modules(self) -> None:
        self.assertEqual(check(ROOT), [])

    def test_new_generic_word_cannot_evade_guard(self) -> None:
        self.assertEqual(
            violations(D1.replace("assembly_build_refused", "new_generic")), [3]
        )

    def test_projection_of_another_exception_does_not_satisfy_guard(self) -> None:
        planted = D1.replace("    raise", "    reason(other_error)\n    raise")
        self.assertEqual(violations(planted), [3])

    def test_unused_projection_does_not_satisfy_guard(self) -> None:
        planted = D1.replace("except Exception:", "except Exception as error:").replace(
            "    raise", "    reason(error)\n    raise"
        )
        self.assertEqual(violations(planted), [3])


class ReasonGuardFamily(unittest.TestCase):
    def test_d16_prefix(self) -> None:
        self.assertEqual(
            violations(
                D1.replace(
                    'raise Refusal("assembly_build_refused") from None',
                    'print("FAIL question-lab: lab_input_or_execution_failed")',
                )
            ),
            [3],
        )

    def test_d49_prefix(self) -> None:
        self.assertEqual(
            violations(
                D1.replace(
                    'raise Refusal("assembly_build_refused") from None',
                    'print("FAIL public-playbook: proof_failed")',
                )
            ),
            [3],
        )

    def test_d50_prefix(self) -> None:
        self.assertEqual(
            violations(
                D1.replace(
                    'raise Refusal("assembly_build_refused") from None',
                    'print("FAIL public-release-load: engine operation failed")',
                )
            ),
            [3],
        )

    def test_literal_shapes(self) -> None:
        for expression in (
            '"proof_failed"',
            '"proof_" "failed"',
            '"FAIL x: proof_failed"',
            'f"FAIL {command}: proof_failed"',
            'f"FAIL x: {"proof_"}failed"',
            '"FAIL x: proof_%s" % "failed"',
            '"FAIL x: " + "proof_" + "failed"',
            '"FAIL x: %s%s" % ("proof_", "failed")',
            '"FAIL x: %(head)s%(tail)s" % {"head": "proof_", "tail": "failed"}',
            '"FAIL x: {head}{tail}".format(**{"head": "proof_", "tail": "failed"})',
            '"FAIL x: {head}{tail}".format(**{"head": "safe", **{"head": "proof_"}, "tail": "failed"})',
            '"FAIL x: {}{}".format("proof_", "failed")',
            '"FAIL x: {head}{tail}".format(head="proof_", tail="failed")',
            "MESSAGE",
        ):
            with self.subTest(expression=expression):
                source = (
                    'try:\n    execute()\nexcept Exception:\n    MESSAGE = "FAIL x: proof_failed"\n    print('
                    + expression
                    + ")\n"
                )
                # The named constant is the only generic source in its case.
                if expression != "MESSAGE":
                    source = source.replace(
                        '    MESSAGE = "FAIL x: proof_failed"\n', ""
                    )
                self.assertEqual(violations(source), [3])

    def test_exception_text_leaks(self) -> None:
        for sink in (
            'print("FAIL x: " + str(error))',
            'print(f"FAIL x: {reason(error)} {error}")',
            "return str(error)",
            "raise Refusal(str(error))",
            'logger.warning("failed", extra={"error_code": str(error)})',
        ):
            with self.subTest(sink=sink):
                self.assertEqual(
                    violations(
                        "try:\n    execute()\nexcept Exception as error:\n    "
                        + sink
                        + "\n"
                    ),
                    [3],
                )

    def test_safe_projection(self) -> None:
        for expression in (
            "reason(error)",
            "error.reason",
            "error.code",
            "error.exit_code",
        ):
            with self.subTest(expression=expression):
                self.assertEqual(
                    violations(
                        "try:\n    execute()\nexcept Exception as error:\n    print("
                        + expression
                        + ")\n"
                    ),
                    [],
                )

    def test_module_constant_and_alias(self) -> None:
        for assignment in (
            'MESSAGE = "FAIL x: proof_failed"',
            'WORD = "proof_failed"\nMESSAGE: str = "FAIL x: " + WORD',
        ):
            source = (
                assignment
                + "\n"
                + D1.replace(
                    'raise Refusal("assembly_build_refused") from None',
                    "print(MESSAGE)",
                )
            )
            self.assertEqual(violations(source), [len(assignment.splitlines()) + 3])

    def test_literal_boundaries_and_cycles(self) -> None:
        for body in (
            "MESSAGE = MESSAGE\nprint(MESSAGE)",
            'print("proof_failed_extra")',
            'print("prefixproof_failed")',
            'print("PROOF_FAILED")',
            'print("")',
            'print("%d" % "x")',
            'print("%q" % "safe")',
            'print("{}{}".format("x"))',
            'print("{missing}".format())',
            'print("{".format())',
            'print("{0.no_such_attribute}".format("x"))',
            'print("{value}".format(**{"value": "safe"}))',
            'print("proof_" + dynamic + "failed")',
            'print("%(missing)s" % {"key": "safe"})',
            'print("%(head)s%(tail)s" % {"head": "proof_", "head": "safe_", "tail": "failed"})',
        ):
            self.assertEqual(
                violations(
                    "try:\n    execute()\nexcept Exception:\n    "
                    + body.replace("\n", "\n    ")
                    + "\n"
                ),
                [],
            )

    def test_constant_uses_lexical_scope_and_order(self) -> None:
        source = (
            'MESSAGE = "FAIL x: proof_failed"\ndef unrelated():\n    MESSAGE = "safe"\n'
            + D1.replace(
                'raise Refusal("assembly_build_refused") from None', "print(MESSAGE)"
            )
        )
        self.assertEqual(violations(source), [6])
        source = (
            'MESSAGE = "FAIL x: proof_failed"\n'
            + D1.replace(
                'raise Refusal("assembly_build_refused") from None', "print(MESSAGE)"
            )
            + 'MESSAGE = "safe"\n'
        )
        self.assertEqual(violations(source), [4])

    def test_parameter_shadows_module_constant(self) -> None:
        source = 'MESSAGE = "proof_failed"\ndef boundary(MESSAGE):\n    try:\n        execute()\n    except Exception:\n        print(MESSAGE)\n'
        self.assertEqual(violations(source), [])

    def test_empty_handlers_and_custom_reason_carriers(self) -> None:
        self.assertEqual(violations("try:\n    execute()\nexcept:\n    pass\n"), [3])
        self.assertEqual(
            violations(
                'try:\n    execute()\nexcept CustomRefusal:\n    raise Refusal("specific_outer")\n'
            ),
            [3],
        )
        self.assertEqual(
            violations(
                'try:\n    execute()\nexcept OSError:\n    raise Refusal("specific_outer")\n'
            ),
            [],
        )
        self.assertEqual(violations(""), [])
        self.assertEqual(violations('print("proof_failed")'), [])

    def test_deploy_guard_owns_retention_only(self) -> None:
        path = ROOT / "scripts/operations/deploy.py"
        source = 'def health_probe():\n    try:\n        execute()\n    except ValueError:\n        raise Refusal("startup_not_ready")\ndef require_retained():\n    try:\n        execute()\n    except Exception:\n        raise Refusal("rollback_retention_failed")\n'
        original = Path.read_text
        with patch.object(
            Path,
            "read_text",
            autospec=True,
            side_effect=lambda target: source if target == path else original(target),
        ):
            self.assertEqual(
                check(ROOT),
                [
                    "scripts/operations/deploy.py:9: pass the inner closed reason through reason(error)"
                ],
            )

    def test_d51_stored_generic_reasons_remain_guarded(self) -> None:
        for statement in (
            'waiting.append("fixture:unavailable")',
            'row = {"problems": ["execution:fixture_failed"]}',
        ):
            source = (
                "try:\n    execute()\nexcept Exception as error:\n    "
                + statement
                + "\n"
            )
            self.assertEqual(violations(source), [3])

    def test_unrelated_sink_cannot_satisfy_projection(self) -> None:
        source = 'try:\n    execute()\nexcept Exception as error:\n    print(reason(error))\n    print("FAIL x: proof_failed")\n'
        self.assertEqual(violations(source), [3])


@given(
    code=st.sampled_from(sorted(GENERIC)),
    split=st.integers(min_value=0, max_value=100),
    prefix=st.text(),
    shape=st.sampled_from(
        (
            "exact",
            "prefix",
            "fstring",
            "concat",
            "percent",
            "format",
            "percent_mapping",
            "format_mapping",
            "named",
        )
    ),
    sink=st.sampled_from(
        ("print({})", "return {}", "raise Refusal({})", "logger.warning({})")
    ),
)
def test_generic_construction_invariant(
    code: str, split: int, prefix: str, shape: str, sink: str
) -> None:
    cut = min(split, len(code))
    left, right = repr(code[:cut]), repr(code[cut:])
    text = repr(prefix + ": " + code)
    expressions = {
        "exact": repr(code),
        "prefix": text,
        "fstring": 'f"{command}: ' + code + '"',
        "concat": repr(prefix + ": ") + " + " + left + " + " + right,
        "percent": repr(prefix.replace("%", "%%") + ": %s%s")
        + " % ("
        + left
        + ", "
        + right
        + ")",
        "format": repr(prefix.replace("{", "{{").replace("}", "}}") + ": {}{}")
        + ".format("
        + left
        + ", "
        + right
        + ")",
        "percent_mapping": repr(prefix.replace("%", "%%") + ": %(head)s%(tail)s")
        + ' % {"head": '
        + left
        + ', "tail": '
        + right
        + "}",
        "format_mapping": repr(
            prefix.replace("{", "{{").replace("}", "}}") + ": {head}{tail}"
        )
        + '.format(**{"head": '
        + left
        + ', "tail": '
        + right
        + "})",
        "named": "MESSAGE",
    }
    source = (
        "MESSAGE = "
        + text
        + "\ntry:\n    execute()\nexcept Exception:\n    "
        + sink.format(expressions[shape])
        + "\n"
    )
    assert violations(source) == [4]


@given(
    name=st.sampled_from(("error", "fault", "caught")),
    form=st.sampled_from(("str({})", "repr({})", 'f"{{{}}}"', "{}.args", "{}.message")),
    sink=st.sampled_from(
        (
            "print({})",
            "return {}",
            "raise Refusal({})",
            'logger.warning("failed", extra={{"error_code": {}}})',
            "sys.stderr.write({})",
        )
    ),
)
def test_exception_output_invariant(name: str, form: str, sink: str) -> None:
    source = (
        "try:\n    execute()\nexcept Exception as "
        + name
        + ":\n    "
        + sink.format(form.format(name))
        + "\n"
    )
    assert violations(source) == [3]
    safe = (
        "try:\n    execute()\nexcept Exception as "
        + name
        + ":\n    "
        + sink.format("reason(" + name + ")")
        + "\n"
    )
    assert violations(safe) == []


class PartBGuard(unittest.TestCase):
    def test_d37_and_d53_planted_handlers(self) -> None:
        for handler in (
            'except ValueError:\n    return refusal(404, "NOT_FOUND")',
            'except yaml.YAMLError:\n    return Refusal("NOT_MAPPING", file_name)',
        ):
            with self.subTest(handler=handler):
                self.assertEqual(
                    violations("try:\n    execute()\n" + handler + "\n"), [3]
                )

    def test_part_b_fixed_reason_family(self) -> None:
        for code in (
            "NOT_FOUND",
            "NOT_MAPPING",
            "missing_input",
            "mount_unverified",
            "imagery_integrity",
            "imagery_manifest_integrity",
            "row_shape",
            "routing_tiles",
            "routing tiles unavailable",
            "count_unavailable",
            "detail_on_point",
            "asset_path_refused",
        ):
            with self.subTest(code=code):
                self.assertEqual(
                    violations(
                        "try:\n    execute()\nexcept ValueError:\n    return "
                        + repr(code)
                        + "\n"
                    ),
                    [3],
                )

    def test_d18_reverted(self) -> None:
        source = 'try:\n    read_layer()\nexcept Exception:\n    return refusal(500, "INTERNAL")\n'
        self.assertEqual(violations(source), [3])

    def test_part_b_inventory_cannot_disappear(self) -> None:
        from reason_guard import MODULES

        self.assertIn("product/src/eii_product/api/results.py", MODULES)
        with patch("reason_guard.violations", return_value=[1]):
            self.assertTrue(check(ROOT))


def test_actual_d18_projection_reverted() -> None:
    source = 'def error_response(error):\n    return refusal(500, "INTERNAL")\n'
    assert violations(source) == [2]
    safe = 'def error_response(error):\n    diagnostic = reason(error)\n    return refusal(500, "INTERNAL", message_key=diagnostic)\n'
    assert violations(safe) == []
