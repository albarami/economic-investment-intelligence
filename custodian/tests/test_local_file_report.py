"""PO-S2-33: local-file status uses existing parsers and discloses no values."""

import json
from pathlib import Path

import pytest
from custodian.tests.support.fetch_build import run_build

from eii_custodian.publicdata.fetch.build import LOG_NAME
from eii_custodian.publicdata.fetch.transport import Response

EXPECTATIONS = "local_expectations/PUB-71.json"
ALIASES = "review/district_layer_aliases.csv"
INVENTED = {
    "national_private": "654321",
    "national_all": "765432",
    "national_1dp": "45.7",
    "zone_69_0dp": "58",
    "zone_70_0dp": "42",
}
HEADER = "zone_code,layer_name,hdx_name\n"
ALIAS_ROW = "SYN-zone,SYN-local-layer,SYN-local-target\n"


@pytest.mark.parametrize("target", [EXPECTATIONS, ALIASES])
@pytest.mark.parametrize("status", ["absent", "invalid", "present"])
def test_build_report_local_file_status_is_value_free(
    tmp_path: Path, target: str, status: str
) -> None:
    """Absent/invalid/valid invented files produce only their closed status.

    An invalid expectations record still raises the stage's existing refusal;
    its status must survive that refusal in the normal build report.
    """
    if status != "absent":
        path = tmp_path / target
        path.parent.mkdir(parents=True)
        if target == EXPECTATIONS:
            body = json.dumps(
                INVENTED if status == "present" else {**INVENTED, "SYN-extra": "9"}
            )
        else:
            body = HEADER + ALIAS_ROW
            if status == "invalid":
                body += "SYN-short,SYN-cell\n"
        path.write_text(body, encoding="utf-8")

    def unused(url: str) -> Response:
        raise AssertionError("local report must not request a URL")

    def build():
        return run_build(
            (), unused, tmp_path, lambda: "2026-11-19T00:00:00Z", lambda _: None
        )

    if target == EXPECTATIONS and status == "invalid":
        with pytest.raises(
            ValueError, match="PUB-71: local expectations record refused"
        ):
            build()
    else:
        assert build().failure is None

    text = (tmp_path / LOG_NAME).read_text(encoding="utf-8")
    report = json.loads(text)
    assert report["local_files"] == {
        EXPECTATIONS: status if target == EXPECTATIONS else "absent",
        ALIASES: status if target == ALIASES else "absent",
    }
    for marker in (*INVENTED.values(), "SYN-extra", *ALIAS_ROW.strip().split(",")):
        assert marker not in text
    assert "SYN-short" not in text
    assert "SYN-cell" not in text
    assert "CSV row width" not in text
    assert "local expectations record refused" not in text
