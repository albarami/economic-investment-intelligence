"""Task-owned documentation contract."""

from pathlib import Path


def test_scan_places_docs_hold_exact_outline_and_assumptions():
    backend = Path("docs/08_BACKEND.md").read_text()
    assert "Public places whose points lie inside the exact requested shape" in backend
    readme = Path("product/src/eii_product/tools/scan_places.README.md").read_text()
    for assumption in (
        "representative_point",
        "walking except drive",
        "origin to place",
        "release period",
    ):
        assert "ASSUMPTION: " + assumption in readme
