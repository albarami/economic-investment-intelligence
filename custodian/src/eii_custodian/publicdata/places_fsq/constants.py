"""Anonymous copy, attribution and the distances the pack states."""

from __future__ import annotations

RELEASE_POLICY = "newest_dated_at_each_refresh"
RELEASE_KEY = "places_fsq/copy"
PLACEHOLDER_KEY = "places_fsq"
COPY_ROOT = "https://data.source.coop/fused/fsq-os-places/"
METHOD = "places_fsq.v1"
COPYRIGHT_LINE = "Copyright 2024 Foursquare Labs, Inc. All rights reserved."
LICENCE_NAME = "Apache License, Version 2.0"
ATTRIBUTION = (
    "Copyright 2024 Foursquare Labs, Inc. All rights reserved. "
    "Licensed under the Apache License, Version 2.0."
)
# PUB-51: duplicate candidates lie within 50 m.
DUPLICATE_WITHIN_M = 50.0
EARTH_RADIUS_M = 6_371_000.0
TERMS_CHECKED = "2026-11-14"
HOST_TERMS_NOTE = (
    "terms to be read; checked 2026-11-14. Host terms of the copy were not found."
)
