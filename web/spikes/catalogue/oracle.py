"""Offline bridge to S3-T07; supplementary accounting is spike-only, not production."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "product/src"))


def load_api():
    from eii_product.assistant import catalogue

    return catalogue


api = load_api()

CATALOGUES = {
    "base": api.load_catalogue(HERE / "fixtures/catalogue"),
    "paired_slots": api.load_catalogue(HERE / "fixtures/catalogue-paired"),
}


def answer(row):
    checks = []
    try:
        brief = json.loads(row["raw"])
    except (ValueError, TypeError):
        return {"refusal": {"rule_code": "JSON", "item_path": "brief"}, "checks": []}
    context = row["context"]
    facts = {key: api.ReturnedFact(**value) for key, value in context["facts"].items()}
    catalogue = CATALOGUES[context.get("catalogue_variant", "base")]
    refusal = api.check_brief(catalogue, brief, facts)
    if refusal is not None:
        return {"refusal": asdict(refusal), "checks": checks}
    checks.append("schema_and_invention")
    for item in brief["observed"] + brief["inferred"]:
        for fact_id in item["slots"].values():
            ref = facts[fact_id].lineage_ref
            source = context["lineage"].get(ref, {})
            fields = {
                "release_table",
                "method",
                "version",
                "source",
                "licence",
                "retrieved",
                "sha256",
            }
            if (
                set(source) != fields
                or not all(
                    isinstance(value, str) and value for value in source.values()
                )
                or len(source["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in source["sha256"])
            ):
                return {
                    "refusal": {
                        "rule_code": "SOURCE_CHAIN",
                        "item_path": f"lineage.{ref}",
                    },
                    "checks": checks,
                }
    checks.append("sources")
    if context["assumptions"] != []:
        return {
            "refusal": {"rule_code": "ASSUMPTIONS", "item_path": "assumptions"},
            "checks": checks,
        }
    checks.append("assumptions")
    if context["scope"] != "area":
        return {
            "refusal": {"rule_code": "SCOPE", "item_path": "scope"},
            "checks": checks,
        }
    checks.append("scope")
    if context["limits"] != ["fixture_only"]:
        return {
            "refusal": {"rule_code": "LIMITS", "item_path": "limits"},
            "checks": checks,
        }
    if context["companions"] != ["source_context"]:
        return {
            "refusal": {"rule_code": "COMPANION", "item_path": "companions"},
            "checks": checks,
        }
    if context["withheld"] and (brief["observed"] or brief["inferred"]):
        return {
            "refusal": {"rule_code": "WITHHELD", "item_path": "observed"},
            "checks": checks,
        }
    checks.append("limits_and_companions")
    return {"refusal": None, "checks": checks}


print(json.dumps([answer(row) for row in json.load(sys.stdin)]))
