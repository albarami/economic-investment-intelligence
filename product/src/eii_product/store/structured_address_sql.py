"""Unchanged fixed structured-address reads and index from S2-T51.

Kept in the store layer so API modules contain no inline SQL (S3-T22).
"""

_COLUMNS = "feature_key, zone_number, street_number, building_number, building_subtype, lon, lat"
_POSTGRES = f"SELECT {_COLUMNS} FROM app.pub_address_point WHERE zone_number = %s AND street_number = %s AND building_number = %s ORDER BY feature_key LIMIT 6"
_EMBEDDED = f"SELECT {_COLUMNS} FROM app.pub_address_point WHERE zone_number = ? AND street_number = ? AND building_number = ? ORDER BY feature_key LIMIT 6"
INDEX_DDL = "CREATE INDEX pub_address_point_structured ON app.pub_address_point (zone_number, street_number, building_number, feature_key)"
