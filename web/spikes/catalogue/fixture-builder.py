"""Freeze invented fixtures using the existing S3-T07 test builders; never public data."""

import copy
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "foundations", ROOT / "product/tests/test_catalogue_foundations.py"
)
assert spec is not None and spec.loader is not None
builders = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builders)

sys.path.insert(0, str(ROOT / "product/src"))
api = builders._api()

# The production catalogue stays untouched. Every value here is an invented test input.
folder = HERE / "fixtures/catalogue"
claims = builders._claims(builders._claim(slots=builders._slot()))
for name in builders.FILES:
    value = claims if name == "claims.yaml" else (builders.SHIPPED / name).read_text()
    (folder / name).write_text(value)
loaded = api.load_catalogue(folder)
base = builders._brief(loaded.version)
base["observed"] = [{"claim_key": "area_note", "slots": {"reading": builders.FACT_A}}]
fact = vars(builders._fact(api))
other = vars(
    builders._fact(
        api,
        fact_id=builders.FACT_B,
        metric_key="night_lights_radiance",
        unit="radiance_nw_cm2_sr",
    )
)
chain = {
    "release_table": "invented_grid",
    "method": "invented_fixture",
    "version": "fixture",
    "source": "invented source, no public assertion",
    "licence": "test fixture only",
    "retrieved": "2026-11-18",
    "sha256": "ab" * 32,
}
context = {
    "facts": {builders.FACT_A: fact, builders.FACT_B: other},
    "lineage": {"lin_grid_people": chain},
    "assumptions": [],
    "scope": "area",
    "limits": ["fixture_only"],
    "companions": ["source_context"],
    "withheld": False,
}
rows = []


def add(key, rule=None, path=None, mutate=None, ctx=None, raw=None):
    brief = copy.deepcopy(base)
    context_copy = copy.deepcopy(context)
    if mutate:
        mutate(brief)
    if ctx:
        ctx(context_copy)
    rows.append(
        {
            "id": key,
            "raw": raw
            if raw is not None
            else json.dumps(brief, separators=(",", ":"), ensure_ascii=False),
            "context": context_copy,
            "expected": None
            if rule is None
            else {"rule_code": rule, "item_path": path},
        }
    )


add("valid")
add(
    "withheld",
    mutate=lambda b: b.update(observed=[]),
    ctx=lambda c: c.update(withheld=True),
)
add("malformed", "JSON", "brief", raw="{")
add(
    "unknown_component",
    "UNKNOWN_COMPONENT",
    "layout[0].component",
    lambda b: b["layout"][0].update(component="rogue"),
)
add(
    "free_prose",
    "UNKNOWN_PROPERTY",
    "layout[0].props.text",
    lambda b: b["layout"][0]["props"].update(text="Invented prose"),
)
add(
    "query",
    "UNKNOWN_PROPERTY",
    "stage[0].props.query",
    lambda b: b["stage"][0]["props"].update(query="SELECT invented"),
)
add(
    "unreturned_fact",
    "UNKNOWN_FACT",
    "observed[0].slots.reading",
    lambda b: b["observed"][0]["slots"].update(reading="f_" + "cd" * 16),
)
add(
    "unknown_action",
    "UNKNOWN_DIRECTIVE",
    "stage[0].component",
    lambda b: b["stage"][0].update(component="execute"),
)
add(
    "unknown_claim",
    "UNKNOWN_CLAIM",
    "observed[0].claim_key",
    lambda b: b["observed"][0].update(claim_key="rogue"),
)
add(
    "unknown_fragment",
    "UNKNOWN_FRAGMENT",
    "headline_key",
    lambda b: b.update(headline_key="rogue"),
)
add(
    "unknown_question",
    "UNKNOWN_QUESTION",
    "next_questions[0].question_key",
    lambda b: b["next_questions"][0].update(question_key="rogue"),
)
add(
    "unknown_directive",
    "UNKNOWN_DIRECTIVE",
    "stage[0].component",
    lambda b: b["stage"][0].update(component="rogue"),
)
add("unknown_property", "UNKNOWN_PROPERTY", "note", lambda b: b.update(note="rogue"))
add(
    "excess_components",
    "MAX_COUNT",
    "layout[1]",
    lambda b: b["layout"].append(copy.deepcopy(b["layout"][0])),
)
add(
    "swapped_valid_fact",
    "SLOT_METRIC",
    "observed[0].slots.reading",
    lambda b: b["observed"][0]["slots"].update(reading=builders.FACT_B),
)
add(
    "missing_slot",
    "SLOT_MISSING",
    "observed[0].slots.reading",
    lambda b: b["observed"][0].update(slots={}),
)
add(
    "extra_slot",
    "SLOT_EXTRA",
    "observed[0].slots.other",
    lambda b: b["observed"][0]["slots"].update(other=builders.FACT_B),
)
for key, field, value, rule in (
    ("wrong_unit", "unit", "index", "SLOT_UNIT"),
    ("wrong_geography", "geography_kind", "national", "SLOT_GEOGRAPHY"),
    ("wrong_period", "period", "2024-01", "SLOT_PERIOD"),
    ("wrong_provenance", "provenance", "synthetic", "SLOT_PROVENANCE"),
):
    add(
        key,
        rule,
        "observed[0].slots.reading",
        ctx=lambda c, f=field, v=value: c["facts"][builders.FACT_A].update({f: v}),
    )
add(
    "missing_lineage_ref",
    "LINEAGE_REF",
    "observed[0].slots.reading.lineage_ref",
    ctx=lambda c: c["facts"][builders.FACT_A].update(lineage_ref=None),
)
add(
    "missing_source_chain",
    "SOURCE_CHAIN",
    "lineage.lin_grid_people",
    ctx=lambda c: c["lineage"]["lin_grid_people"].pop("sha256"),
)
add(
    "missing_companion",
    "COMPANION",
    "companions",
    ctx=lambda c: c.update(companions=[]),
)
add(
    "unsupported_version",
    "CATALOGUE_VERSION",
    "catalogue_version",
    lambda b: b.update(catalogue_version="unsupported"),
)
add(
    "withheld_hidden_value",
    "WITHHELD",
    "observed",
    ctx=lambda c: c.update(withheld=True),
)
add(
    "assumption_invention",
    "ASSUMPTIONS",
    "assumptions",
    ctx=lambda c: c.update(assumptions=["undeclared"]),
)
add("outside_scope", "SCOPE", "scope", ctx=lambda c: c.update(scope="person"))
add("missing_limits", "LIMITS", "limits", ctx=lambda c: c.update(limits=[]))
(HERE / "fixtures/cases.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
)

# Separately frozen supplement: a real two-slot swap, plus its valid control.
paired_folder = HERE / "fixtures/catalogue-paired"
paired_folder.mkdir(exist_ok=True)
paired_slots = builders._slot() + builders._slot(
    name="light", metric="night_lights_radiance", unit="radiance_nw_cm2_sr"
)
paired_claims = builders._claims(
    builders._claim(
        slots=paired_slots,
        en="See {reading} and {light}.",
        ar="انظر {reading} و{light}.",
    )
)
for name in builders.FILES:
    value = paired_claims if name == "claims.yaml" else (folder / name).read_text()
    (paired_folder / name).write_text(value)
paired_catalogue = api.load_catalogue(paired_folder)
paired_rows = []
for swapped in (False, True):
    row = copy.deepcopy(rows[0])
    row["id"] = "paired_swap" if swapped else "paired_valid"
    row["context"]["catalogue_variant"] = "paired_slots"
    brief = json.loads(row["raw"])
    brief["catalogue_version"] = paired_catalogue.version
    brief["observed"][0]["slots"] = {
        "reading": builders.FACT_B if swapped else builders.FACT_A,
        "light": builders.FACT_A if swapped else builders.FACT_B,
    }
    row["raw"] = json.dumps(brief, separators=(",", ":"), ensure_ascii=False)
    row["expected"] = (
        {"rule_code": "SLOT_METRIC", "item_path": "observed[0].slots.reading"}
        if swapped
        else None
    )
    paired_rows.append(row)
(HERE / "fixtures/paired-cases.json").write_text(
    json.dumps(paired_rows, indent=2, ensure_ascii=False) + "\n"
)
