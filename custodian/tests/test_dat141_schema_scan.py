"""DAT-141 and DAT-169 schema scan over the repository's structured schemas."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml
from custodian.tests.repository_root import repository_root

REPO = repository_root(Path(__file__))
SCAN_ROOTS = (
    REPO / "custodian" / "src",
    REPO / "product" / "src",
    REPO / "contracts",
)
REGISTRY = REPO / "custodian" / "publicdata" / "sources.yaml"
WORLDPOP_FILES = 40


def _names(text: str) -> frozenset[str]:
    return frozenset(text.split())


DENIED_FIELDS: dict[str, frozenset[str]] = {
    "sex": _names(
        "sex sexe sex_code sex_id sex_at_birth gender gender_code gender_id"
        " gender_identity is_female is_male female male"
    ),
    "nationality": _names(
        "nationality nationality_code nationality_id nationality_group"
        " nationality_group_code citizenship citizenship_code"
        " establishment_nationality country_of_citizenship country_of_birth"
    ),
    "ethnicity": _names("ethnicity ethnic ethnic_code ethnic_group ethnicity_group"),
    "religion": _names("religion religion_code religious_group sect"),
    "language": _names(
        "language language_code native_language mother_tongue preferred_language"
    ),
    "age": _names(
        "age age_band age_band_code age_bracket age_code age_group age_range"
        " age_years birth_year date_of_birth dob"
    ),
}
DENIED_BY_NAME = {
    name: category for category, names in DENIED_FIELDS.items() for name in names
}
SPLIT_ADMITTED_COLUMNS: dict[str, frozenset[str]] = {
    "sex": frozenset({"sex", "gender"}),
    "nationality": frozenset({"nationality"}),
}
CONTEXT_MARKERS: dict[str, frozenset[str]] = {
    "worker": _names("worker workers workforce employee employees employment payroll"),
    "residence": _names(
        "residence residences resident residents dwelling dwellings household"
        " households"
    ),
    "company": _names(
        "company companies firm firms establishment establishments employer"
        " employers business businesses"
    ),
    "protected": _names("protected privacy suppressed confidential sensitive"),
    "movement": _names(
        "movement movements mobility od trip trips visit visits visitor visitors"
    ),
    "presence": _names("presence footfall occupancy"),
    "flow": _names("flow flows origin destination"),
    "generator": _names("generator generators worldgen synthetic simulation simulated"),
    "worldpop": _names("worldpop agesex"),
}
PERSON_LEVEL_MARKERS = _names(
    "person persons individual individuals device devices trip trips microdata"
)
JOIN_KEY_MARKERS = _names(
    "worker_id resident_id residence_id company_id establishment_id"
    " registration_number person_id device_id trip_id"
)
BLOCKING_CONTEXTS = _names("protected worker residence company")
WORLDPOP_ALLOWED = _names("sex age_code age_band")
MOVEMENT_ALLOWED = _names("age_band gender nationality_group")
MOVEMENT_TABLES = _names(
    "presence_split_hourly od_split_hourly presence_split flow_split"
)
COLUMN_COLLECTION_NAMES = _names("columns fields schema header names")
SQL_CONSTRAINTS = _names("primary foreign unique check constraint key index exclude")
CREATE_TABLE = re.compile(
    r"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?([A-Za-z_][A-Za-z0-9_.$]*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Schema:
    """One discovered record, table or column collection."""

    path: str
    name: str
    fields: tuple[str, ...]
    kind: str
    context: tuple[str, ...]
    splits: tuple[str, ...] = ()


@dataclass(frozen=True)
class Violation:
    """One denied field on one discovered schema."""

    path: str
    schema: str
    field: str
    category: str


@dataclass(frozen=True)
class Scan:
    """Everything the scan discovered and everything it refused."""

    schemas: tuple[Schema, ...]
    violations: tuple[Violation, ...]
    worldpop_declarations: tuple[tuple[str, str, str], ...]


def _tokens(name: str) -> tuple[str, ...]:
    """Split camelCase and snake_case into lower-case parts."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", spaced)
    return tuple(part for part in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if part)


def _normalised(name: str) -> str:
    return "_".join(_tokens(name))


def _contexts(tokens: tuple[str, ...]) -> frozenset[str]:
    found = {
        group for group, markers in CONTEXT_MARKERS.items() if markers & set(tokens)
    }
    return frozenset(found)


def _allowed(schema: Schema, contexts: frozenset[str]) -> frozenset[str]:
    """Return only the DAT-141, decision-0022 and DAT-169 exceptions."""
    tokens = set(schema.context)
    allowed: set[str] = set()
    if "employment" in tokens and (
        "spell" in tokens or {"protected", "released"} <= tokens
    ):
        allowed.add("nationality_group")
    if "establishment" in tokens or {"register", "company"} <= tokens:
        allowed.add("establishment_nationality")
    if "protected" in contexts and "released" not in tokens:
        allowed.clear()
    if contexts & BLOCKING_CONTEXTS:
        return frozenset(allowed)
    if PERSON_LEVEL_MARKERS & tokens:
        return frozenset()
    if any(_normalised(field) in JOIN_KEY_MARKERS for field in schema.fields):
        return frozenset()
    if "worldpop" in contexts:
        allowed |= WORLDPOP_ALLOWED
    if _normalised(schema.name) in MOVEMENT_TABLES:
        allowed |= MOVEMENT_ALLOWED
    return frozenset(allowed)


def _violations(schema: Schema) -> tuple[Violation, ...]:
    contexts = _contexts(schema.context)
    if not contexts:
        return ()
    allowed = _allowed(schema, contexts)
    found: list[Violation] = []
    for field in schema.fields:
        name = _normalised(field)
        category = DENIED_BY_NAME.get(name)
        admitted = any(
            name in SPLIT_ADMITTED_COLUMNS[split]
            for split in schema.splits
            if split in SPLIT_ADMITTED_COLUMNS
        )
        if category is None or name in allowed or admitted:
            continue
        found.append(Violation(schema.path, schema.name, field, category))
    return tuple(found)


def _class_fields(node: ast.ClassDef) -> tuple[str, ...]:
    return tuple(
        item.target.id
        for item in node.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    )


def _is_schema_class(node: ast.ClassDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name) and target.id == "dataclass":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "dataclass":
            return True
    return any(isinstance(item, ast.AnnAssign) for item in node.body)


def _literal_names(value: ast.expr) -> tuple[str, ...]:
    items = list(value.keys) if isinstance(value, ast.Dict) else None
    if items is None and isinstance(value, ast.List | ast.Tuple | ast.Set):
        items = list(value.elts)
    if not items:
        return ()
    if not all(
        isinstance(item, ast.Constant) and isinstance(item.value, str) for item in items
    ):
        return ()
    return tuple(str(item.value) for item in items if isinstance(item, ast.Constant))


def _column_collection(node: ast.stmt) -> tuple[str, tuple[str, ...]] | None:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return None
    target = node.targets[0]
    if not isinstance(target, ast.Name):
        return None
    if not COLUMN_COLLECTION_NAMES & set(_tokens(target.id)):
        return None
    names = _literal_names(node.value)
    return (target.id, names) if names else None


def _python_schemas(path: Path, base: tuple[str, ...]) -> tuple[Schema, ...]:
    found: list[Schema] = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        body = node.body if isinstance(node, ast.ClassDef) else [node]
        for item in body:
            collection = _column_collection(item)
            if collection is not None:
                name, names = collection
                owner = node.name if isinstance(node, ast.ClassDef) else ""
                found.append(
                    Schema(
                        str(path),
                        f"{owner}.{name}" if owner else name,
                        names,
                        "python",
                        base + _tokens(owner) + _tokens(name),
                    )
                )
        if isinstance(node, ast.ClassDef):
            fields = _class_fields(node)
            if fields and _is_schema_class(node):
                found.append(
                    Schema(
                        str(path),
                        node.name,
                        fields,
                        "python",
                        base + _tokens(node.name),
                    )
                )
    return tuple(found)


def _parenthesised(text: str, index: int) -> str | None:
    position = index
    while position < len(text) and text[position].isspace():
        position += 1
    if position >= len(text) or text[position] != "(":
        return None
    depth = 0
    for cursor in range(position, len(text)):
        if text[cursor] == "(":
            depth += 1
        elif text[cursor] == ")":
            depth -= 1
            if depth == 0:
                return text[position + 1 : cursor]
    return None


def _sql_columns(body: str) -> tuple[str, ...]:
    names: list[str] = []
    depth = 0
    current: list[str] = []
    parts: list[str] = []
    for character in body:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(character)
    parts.append("".join(current))
    for part in parts:
        head = part.strip().split(None, 1)
        if not head:
            continue
        name = head[0].strip('"`[]')
        if not name or not re.match(r"[A-Za-z_]", name):
            continue
        if name.lower() not in SQL_CONSTRAINTS:
            names.append(name)
    return tuple(names)


def _sql_schemas(path: Path, base: tuple[str, ...]) -> tuple[Schema, ...]:
    text = path.read_text(encoding="utf-8")
    tables: dict[str, list[str]] = {}
    order: list[str] = []
    for match in CREATE_TABLE.finditer(text):
        body = _parenthesised(text, match.end())
        if body is None:
            continue
        name = match.group(1)
        if name not in tables:
            tables[name] = []
            order.append(name)
        tables[name].extend(_sql_columns(body))
    return tuple(
        Schema(str(path), name, tuple(tables[name]), "sql", base + _tokens(name))
        for name in order
    )


def _yaml_schemas(
    path: Path,
) -> tuple[tuple[Schema, ...], tuple[tuple[str, str, str], ...]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = document.get("sources") if isinstance(document, dict) else None
    schemas: list[Schema] = []
    declarations: list[tuple[str, str, str]] = []
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, dict):
            continue
        key = str(row.get("key", ""))
        tables = tuple(str(item) for item in row.get("release_tables") or ())
        context = (
            _tokens(path.name)
            + _tokens(str(row.get("source_id", "")))
            + _tokens(key)
            + tuple(token for table in tables for token in _tokens(table))
        )
        columns = tuple(
            str(column.get("name", ""))
            for column in row.get("columns") or ()
            if isinstance(column, dict)
        )
        declared = tuple(name for name in ("sex", "age_code") if name in row)
        declarations.extend((str(path), key, name) for name in declared)
        splits = tuple(
            _normalised(str(item)) for item in row.get("public_splits") or ()
        )
        if columns or declared:
            schemas.append(
                Schema(str(path), key, columns + declared, "yaml", context, splits)
            )
    return tuple(schemas), tuple(declarations)


def scan_tree(roots: tuple[Path, ...], registry: Path | None = None) -> Scan:
    """Scan the given roots, and the registry when one is named."""
    schemas: list[Schema] = []
    declarations: tuple[tuple[str, str, str], ...] = ()
    for root in roots:
        base_root = Path(root)
        if not base_root.is_dir():
            raise ValueError(f"scan root is not a folder: {base_root}")
        for path in sorted(base_root.rglob("*")):
            if not path.is_file():
                continue
            base = _tokens(str(path.relative_to(base_root)))
            if path.suffix == ".py":
                schemas.extend(_python_schemas(path, base))
            elif path.suffix == ".sql":
                schemas.extend(_sql_schemas(path, base))
    if registry is not None:
        registry_path = Path(registry)
        if not registry_path.is_file():
            raise ValueError(f"named registry is not a file: {registry_path}")
        found, declarations = _yaml_schemas(registry_path)
        schemas.extend(found)
    violations = tuple(
        violation for schema in schemas for violation in _violations(schema)
    )
    return Scan(tuple(schemas), violations, declarations)


def test_repository_schemas_carry_no_denied_field() -> None:
    """The real roots hold no denied field and no schema is silently skipped."""
    scan = scan_tree(SCAN_ROOTS, REGISTRY)
    assert scan.violations == ()
    assert scan.schemas
    assert any(schema.kind == "python" for schema in scan.schemas)


def test_worldpop_public_declarations_are_discovered() -> None:
    """The 36 per-file public sex and age declarations are seen and allowed."""
    scan = scan_tree(SCAN_ROOTS, REGISTRY)
    declarations = scan.worldpop_declarations
    assert len({key for _, key, _ in declarations}) == WORLDPOP_FILES
    assert len(declarations) == 2 * WORLDPOP_FILES
    assert {field for _, _, field in declarations} == {"sex", "age_code"}
    assert {path for path, _, _ in declarations} == {str(REGISTRY)}
    grids = [
        schema for schema in scan.schemas if "worldpop" in _contexts(schema.context)
    ]
    assert len(grids) == WORLDPOP_FILES
    assert {schema.fields for schema in grids} == {("sex", "age_code")}
    assert scan.violations == ()


def test_a_file_without_schemas_yields_no_schema(tmp_path: Path) -> None:
    """A file holding no schema is not counted as a passing schema."""
    (tmp_path / "worker_notes.py").write_text("VALUE = 1\n", encoding="utf-8")
    scan = scan_tree((tmp_path,))
    assert scan.schemas == ()
    assert scan.violations == ()


@pytest.mark.parametrize("subject", ["worker", "residence", "company"])
@pytest.mark.parametrize(
    ("field", "category"),
    [
        ("sex", "sex"),
        ("gender", "sex"),
        ("nationality_group", "nationality"),
        ("citizenship", "nationality"),
        ("ethnicity", "ethnicity"),
        ("religion", "religion"),
        ("language", "language"),
        ("age_band", "age"),
        ("age_code", "age"),
    ],
)
def test_source_record_denied_field_fails(
    tmp_path: Path, subject: str, field: str, category: str
) -> None:
    """Every denied category on a worker, residence or company record fails."""
    path = tmp_path / f"{subject}_records.py"
    path.write_text(
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\n"
        f"class {subject.title()}Record:\n"
        "    record_key: str\n"
        f"    {field}: str\n",
        encoding="utf-8",
    )
    scan = scan_tree((tmp_path,))
    assert [
        (item.path, item.schema, item.field, item.category) for item in scan.violations
    ] == [(str(path), f"{subject.title()}Record", field, category)]


PLANTED_FAILURES = (
    (
        "protected_pay.sql",
        "CREATE TABLE protected_worker_pay (worker_id text NOT NULL, pay_band text"
        " NOT NULL, nationality_group text, PRIMARY KEY (worker_id, pay_band));",
        (("protected_worker_pay", "nationality_group", "nationality"),),
    ),
    (
        "worldgen_output.py",
        "from dataclasses import dataclass\n\n\n@dataclass(frozen=True)\n"
        "class GeneratorOutput:\n    record_key: str\n    gender: str\n",
        (("GeneratorOutput", "gender", "sex"),),
    ),
    (
        "generator_output.sql",
        "CREATE TABLE generator_output (record_key text NOT NULL, age_band text);",
        (("generator_output", "age_band", "age"),),
    ),
    (
        "protected_presence.sql",
        "CREATE TABLE protected_presence_count (unit_id text, gender text);",
        (("protected_presence_count", "gender", "sex"),),
    ),
    (
        "movement_unsplit.sql",
        "CREATE TABLE presence_count (unit_id text, gender text);"
        " CREATE TABLE flow_hourly (origin_unit_id text, age_band text);",
        (
            ("presence_count", "gender", "sex"),
            ("flow_hourly", "age_band", "age"),
        ),
    ),
    (
        "employment_wrong_split.sql",
        "CREATE TABLE employment_spell (spell_key text, sex text);"
        " CREATE TABLE establishment (establishment_key text, nationality_group text);",
        (
            ("employment_spell", "sex", "sex"),
            ("establishment", "nationality_group", "nationality"),
        ),
    ),
    (
        "movement_person.sql",
        "CREATE TABLE movement_person (person_id text, sex text,"
        " nationality_group text);",
        (
            ("movement_person", "sex", "sex"),
            ("movement_person", "nationality_group", "nationality"),
        ),
    ),
    (
        "protected_employment_spell.sql",
        "CREATE TABLE protected_employment_spell (spell_key text, nationality_group text);",
        (("protected_employment_spell", "nationality_group", "nationality"),),
    ),
    (
        "company_profile.py",
        "class CompanyProfile:\n    establishment_nationality: str\n",
        (("CompanyProfile", "establishment_nationality", "nationality"),),
    ),
)


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    PLANTED_FAILURES,
    ids=[case[0] for case in PLANTED_FAILURES],
)
def test_planted_schema_fails_with_its_path_and_field(
    tmp_path: Path,
    name: str,
    text: str,
    expected: tuple[tuple[str, str, str], ...],
) -> None:
    """A derived, generator, deceptive or person-level schema fails closed."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    scan = scan_tree((tmp_path,))
    assert [
        (item.path, item.schema, item.field, item.category) for item in scan.violations
    ] == [(str(path), schema, field, category) for schema, field, category in expected]


PLANTED_PASSES = (
    (
        "worldpop_agesex.py",
        "from dataclasses import dataclass\n\n\n@dataclass(frozen=True)\n"
        "class PubPopAgesexGridCell:\n    grid_key: str\n    sex: str\n"
        "    age_code: str\n",
        ("PubPopAgesexGridCell",),
    ),
    (
        "movement_aggregates.sql",
        "CREATE TABLE presence_split_hourly (unit_id text, day_type text, hour integer,"
        " age_band text, gender text, nationality_group text);"
        " CREATE TABLE od_split_hourly (origin_unit_id text, destination_unit_id text,"
        " hour integer, age_band text, gender text, nationality_group text);"
        " CREATE TABLE presence_split (unit_id text, gender text);"
        " CREATE TABLE flow_split (origin_unit_id text, nationality_group text);",
        ("presence_split_hourly", "od_split_hourly", "presence_split", "flow_split"),
    ),
    (
        "employment_spell.py",
        "from dataclasses import dataclass\n\n\n@dataclass(frozen=True)\n"
        "class EmploymentSpell:\n    spell_key: str\n    nationality_group: str\n",
        ("EmploymentSpell",),
    ),
    (
        "business_register.sql",
        "CREATE TABLE establishment (establishment_key text,"
        " establishment_nationality text);",
        ("establishment",),
    ),
    (
        "protected_nationality_dimensions.sql",
        "CREATE TABLE protected_employment_released (dimension_key text,"
        " nationality_group text);"
        " CREATE TABLE protected_establishment_released (dimension_key text,"
        " establishment_nationality text);",
        ("protected_employment_released", "protected_establishment_released"),
    ),
)


@pytest.mark.parametrize(
    ("name", "text", "schemas"),
    PLANTED_PASSES,
    ids=[case[0] for case in PLANTED_PASSES],
)
def test_public_worldpop_and_movement_aggregates_pass(
    tmp_path: Path, name: str, text: str, schemas: tuple[str, ...]
) -> None:
    """The DAT-141 public grid and the DAT-169 movement splits are allowed."""
    (tmp_path / name).write_text(text, encoding="utf-8")
    scan = scan_tree((tmp_path,))
    assert [schema.name for schema in scan.schemas] == list(schemas)
    assert scan.violations == ()


def test_scan_refuses_a_root_that_is_not_a_folder(tmp_path: Path) -> None:
    """A missing scan root is refused instead of scanning nothing."""
    missing = tmp_path / "absent-root"
    with pytest.raises(ValueError) as caught:
        scan_tree((missing,))
    assert str(caught.value) == f"scan root is not a folder: {missing}"


def test_public_splits_allow_only_the_named_column(tmp_path: Path) -> None:
    """A public split allows the columns its name admits, and no other column."""
    bare = tmp_path / "bare.yaml"
    bare.write_text(
        "sources:\n"
        "  - key: invented-employees-bare\n"
        "    source_id: invented_employees\n"
        "    columns:\n"
        "      - name: nationality\n"
        "        type: string\n",
        encoding="utf-8",
    )
    shifted = tmp_path / "shifted.yaml"
    shifted.write_text(
        "sources:\n"
        "  - key: invented-employees-shifted\n"
        "    source_id: invented_employees\n"
        "    public_splits:\n"
        "      - nationality\n"
        "    columns:\n"
        "      - name: nationality_code\n"
        "        type: string\n",
        encoding="utf-8",
    )
    sex_word = tmp_path / "sex-word.yaml"
    sex_word.write_text(
        "sources:\n"
        "  - key: invented-employees-sex-word\n"
        "    source_id: invented_employees\n"
        "    public_splits:\n"
        "      - sex\n"
        "    columns:\n"
        "      - name: gender\n"
        "        type: string\n",
        encoding="utf-8",
    )
    nationality_only = tmp_path / "nationality-only.yaml"
    nationality_only.write_text(
        "sources:\n"
        "  - key: invented-employees-nationality-only\n"
        "    source_id: invented_employees\n"
        "    public_splits:\n"
        "      - nationality\n"
        "    columns:\n"
        "      - name: gender\n"
        "        type: string\n",
        encoding="utf-8",
    )
    bare_scan = scan_tree((tmp_path,), bare)
    shifted_scan = scan_tree((tmp_path,), shifted)
    sex_word_scan = scan_tree((tmp_path,), sex_word)
    nationality_only_scan = scan_tree((tmp_path,), nationality_only)
    assert [
        (item.schema, item.field, item.category) for item in bare_scan.violations
    ] == [("invented-employees-bare", "nationality", "nationality")]
    assert [
        (item.schema, item.field, item.category) for item in shifted_scan.violations
    ] == [("invented-employees-shifted", "nationality_code", "nationality")]
    assert [
        (item.schema, item.field, item.category) for item in sex_word_scan.violations
    ] == []
    assert [
        (item.schema, item.field, item.category)
        for item in nationality_only_scan.violations
    ] == [("invented-employees-nationality-only", "gender", "sex")]


def test_scan_refuses_a_named_registry_that_is_not_a_file(tmp_path: Path) -> None:
    """A named registry that is not a file is refused."""
    (tmp_path / "notes.py").write_text("VALUE = 1\n", encoding="utf-8")
    missing = tmp_path / "absent-registry.yaml"
    with pytest.raises(ValueError) as caught:
        scan_tree((tmp_path,), missing)
    assert str(caught.value) == f"named registry is not a file: {missing}"
