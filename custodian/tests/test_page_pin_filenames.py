"""Named page-pin intakes use invented certificates, never lead intake bytes."""

import pytest
from custodian.tests.test_s2_t29_fix10 import config_file
from custodian.tests.test_s2_t29_fix10 import invented_certs as invented_certs

from eii_custodian.publicdata.fetch.certificate_pins import PinError, load_pin
from eii_custodian.publicdata.fetch.page_records import load_declaration

ROWS = (
    ("insurance_tables", "www.qcb.gov.qa"),
    ("monaqasat_classified", "monaqasat.mof.gov.qa"),
    ("schools_private_directory", "www.edu.gov.qa"),
    ("schools_private_directory", "myschools.edu.gov.qa"),
)
FILENAME = "digicert_g2_2020_ca1.der"


@pytest.mark.parametrize("source,host", ROWS)
def test_page_pin_named_intake_pending_then_approved(
    tmp_path, invented_certs, source, host
):
    row = next(pin for pin in load_declaration(source)["pins"] if pin["host"] == host)
    assert row["file"] == FILENAME
    assert row["security_review"] == "PENDING"
    der = invented_certs["intermediate"]
    config = config_file(tmp_path, der, host, source)
    folder = tmp_path / "intake" / source
    (folder / config["file"]).rename(folder / row["file"])
    config.update(file=row["file"], security_review=row["security_review"])
    with pytest.raises(PinError, match=r"^certificate_review_pending$"):
        load_pin(tmp_path, source, config)
    config["security_review"] = "APPROVED"
    loaded = load_pin(tmp_path, source, config)
    assert (loaded.host, loaded.der, loaded.sha256, loaded.approved) == (
        host,
        der,
        config["sha256"],
        True,
    )


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("hash", "certificate_chain_incomplete"),
        ("symlink", "intake_path_refused"),
        ("escape", "intake_path_refused"),
    ],
)
def test_page_pin_named_intake_refusals(tmp_path, invented_certs, plant, reason):
    config = config_file(tmp_path, invented_certs["intermediate"])
    folder = tmp_path / "intake" / "SYN-source"
    original = folder / config["file"]
    named = folder / FILENAME
    original.rename(named)
    config["file"] = FILENAME
    if plant == "hash":
        config["sha256"] = "0" * 64
    elif plant == "symlink":
        named.rename(original)
        named.symlink_to(original)
    else:
        config["file"] = "../" + FILENAME
        named.rename(folder.parent / FILENAME)
    with pytest.raises(PinError, match="^" + reason + "$"):
        load_pin(tmp_path, "SYN-source", config)
