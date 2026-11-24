"""The fact model's dependency is declared by exactly its importing members."""

import ast
import tomllib

import pytest
from product.tests.sector_fixture import repository_path


def check_pydantic_declaration(sources, manifest):
    imports = set()
    for source in sources:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                imports.add(node.module.split(".")[0])
    declared = any(
        dependency.split("==")[0].lower() == "pydantic"
        for dependency in manifest["project"].get("dependencies", [])
    )
    assert declared == ("pydantic" in imports)


@pytest.mark.parametrize("member", ["core", "product", "custodian", "gateway"])
def test_member_declares_pydantic_if_and_only_if_it_imports(member):
    root = repository_path(member + "/pyproject.toml", __file__).parent.parent
    check_pydantic_declaration(
        [p.read_text() for p in (root / member / "src").rglob("*.py")],
        tomllib.loads((root / member / "pyproject.toml").read_text()),
    )


@pytest.mark.parametrize(
    "source,dependencies",
    [
        ("from pydantic import BaseModel", []),
        ("import decimal", ["pydantic==2.14.3"]),
    ],
)
def test_declaration_mismatch_plants(source, dependencies):
    with pytest.raises(AssertionError):
        check_pydantic_declaration(
            [source], {"project": {"dependencies": dependencies}}
        )
