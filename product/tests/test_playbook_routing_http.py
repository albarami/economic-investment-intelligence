"""F14 executes both real area steps; unrelated playbook tools are stand-ins."""

from types import SimpleNamespace
from unittest.mock import patch

from product.tests.test_tools_http import service as service

from eii_product.assistant.playbooks.engine import execute


def test_playbook_route_forwards_routing(service):
    client, _ledger, _store, calls = service
    bundles = []

    def record(*args, **kwargs):
        result = execute(*args, **kwargs)
        bundles.append(result)
        return result

    with (
        patch("eii_product.api.playbooks.execute", side_effect=record),
        patch(
            "eii_product.assistant.playbooks.engine.resolve",
            return_value=SimpleNamespace(status="NO_DATA", payload=None),
        ),
        patch(
            "eii_product.assistant.playbooks.engine.sector_facts",
            return_value={
                "status": "NO_DATA",
                "payload": {},
                "facts": [],
                "blocks": [],
            },
        ),
    ):
        response = client.post(
            "/api/playbooks/site_check",
            json={"activity": "INVENTED-activity", "pin": {"lat": 1, "lon": 1}},
        )
    assert response.status_code == 202
    steps = {step["key"]: step for step in bundles[0].steps}
    for key in ("near", "wider"):
        assert steps[key]["status"] == "OK"
        assert steps[key]["payload"]["area_id"].startswith("ma1/")
    assert calls == [("walk", 5), ("drive", 10), ("walk", 5), ("walk", 5)]
