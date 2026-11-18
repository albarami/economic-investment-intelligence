"""PO-S2-32: both reviewed alias files refuse malformed CSV structure."""

from pathlib import Path

import pytest

from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.live import district_aliases

HEADER = "zone_code,layer_name,hdx_name\n"


@pytest.mark.parametrize("local", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        "zone_code,layer_name,hdx_name,hdx_name\n",
        "layer_name,zone_code,hdx_name\n",
        "zone_code,layer_name\n",
        "",
        HEADER + "1,invented\n",
        HEADER + "1,invented,invented,extra\n",
    ],
)
def test_alias_files_refuse_malformed_structure(tmp_path: Path, local: bool, body: str):
    review = tmp_path / "committed"
    cache = tmp_path / "cache"
    review.mkdir()
    (cache / "review").mkdir(parents=True)
    (review / "district_layer_aliases.csv").write_text(HEADER)
    target = cache / "review" if local else review
    (target / "district_layer_aliases.csv").write_text(body)
    with pytest.raises(FrameError, match=r"CSV (header|row width)"):
        district_aliases(review, cache)


def test_alias_files_preserve_valid_rows(tmp_path: Path):
    review = tmp_path / "committed"
    cache = tmp_path / "cache"
    review.mkdir()
    (cache / "review").mkdir(parents=True)
    (review / "district_layer_aliases.csv").write_text("# reviewed\n" + HEADER)
    (cache / "review" / "district_layer_aliases.csv").write_text(
        HEADER + '1,"invented, layer",invented target\n'
    )
    assert district_aliases(review, cache) == [
        {
            "zone_code": "1",
            "layer_name": "invented, layer",
            "hdx_name": "invented target",
        }
    ]
