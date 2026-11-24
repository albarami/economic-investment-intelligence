"""Kills for UnregisteredShapes.find, which no earlier test calls.

make_area treats every ShapeMiss as an invalid area and does not read the
reason, so execute cannot tell these mutants apart. The port method is the
first place the refusal text exists.
"""

from eii_product.assistant.playbooks.engine import UnregisteredShapes
from eii_product.tools.make_area import ShapeMiss


def test_unregistered_shape_refusal_is_unknown() -> None:
    assert UnregisteredShapes().find("invented-shape") == ShapeMiss("unknown")
