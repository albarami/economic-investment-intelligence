"""Stage the tracked, explicitly pending settings for unrelated CLI tests."""

import shutil
from pathlib import Path

from custodian.tests.repository_root import repository_root

from eii_custodian.publicdata.method_pin_config import CONFIG_RELATIVE


def stage_tracked_configuration(root: Path) -> None:
    destination = root / CONFIG_RELATIVE
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(repository_root(Path(__file__)) / CONFIG_RELATIVE, destination)
