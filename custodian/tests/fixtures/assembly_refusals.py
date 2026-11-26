"""Invented refusal delivery cases preserved from the approved S2-P56 inventory."""

INVENTORY_CASES = [
    {
        "anchor": "places/area_files.py:_load_road; places/integrate.py:areas_before_stage",
        "plants": [["AreaError", "road_file_missing", "road_file_missing"]],
        "row": "frame:01",
        "stage": "frame",
    },
    {
        "anchor": "places/area_files.py:_load_road",
        "plants": [
            ["AreaError", "road_file_unreceipted", "road_file_unreceipted"],
            [
                "SnapshotError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_snapshoterror",
            ],
        ],
        "row": "frame:02",
        "stage": "frame",
    },
    {
        "anchor": "places/area_files.py:_load_road; fetch/snapshots.py:reviewed_selections",
        "plants": [
            [
                "SnapshotError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_snapshoterror",
            ],
            [
                "AreaError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_areaerror",
            ],
            ["SnapshotError", "snapshot_index_invalid", "snapshot_index_invalid"],
            [
                "SnapshotError",
                "snapshot_selection_invalid",
                "snapshot_selection_invalid",
            ],
        ],
        "row": "frame:03",
        "stage": "frame",
    },
    {
        "anchor": "places/integrate.py:_opened_place, areas_before_stage",
        "plants": [["AreaError", "places_file_unreceipted", "places_file_unreceipted"]],
        "row": "frame:04",
        "stage": "frame",
    },
    {
        "anchor": "places/integrate.py:_opened_place, _receipt_of",
        "plants": [["AreaError", "places_file_digest", "places_file_digest"]],
        "row": "frame:05",
        "stage": "frame",
    },
    {
        "anchor": "places/area_requests.py:area_requests; places/review.py:_yaml_list, _keys, _area",
        "plants": [
            ["PlacesError", "missing_key", "missing_key"],
            ["PlacesError", "review_list", "review_list"],
            ["PlacesError", "review_row", "review_row"],
            ["PlacesError", "showcase_area", "showcase_area"],
        ],
        "row": "frame:06",
        "stage": "frame",
    },
    {
        "anchor": "places/integrate.py:areas_before_stage (_READER_ERRORS)",
        "plants": [
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_oserror",
            ],
            [
                "TypeError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_typeerror",
            ],
            [
                "SnapshotError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_snapshoterror",
            ],
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_valueerror",
            ],
            [
                "UnicodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_unicodeerror",
            ],
            [
                "YAMLError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_yamlerror",
            ],
        ],
        "row": "frame:07",
        "stage": "frame",
    },
    {
        "anchor": "places/integrate.py:_cache_points",
        "plants": [
            ["PlacesError", "axis_swapped", "axis_swapped"],
            ["PlacesError", "missing_column", "missing_column"],
            ["PlacesError", "schema_versions", "schema_versions"],
            [
                "DuckDBError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_duckdberror",
            ],
        ],
        "row": "frame:08",
        "stage": "frame",
    },
    {
        "anchor": "places/area_files.py:open_pinned_engine",
        "plants": [
            ["AreaError", "engine_package_missing", "engine_package_missing"],
            [
                "ImportError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_importerror",
            ],
        ],
        "row": "frame:09",
        "stage": "frame",
    },
    {
        "anchor": "places/area_engine.py:PinnedEngine.__init__; places/area_files.py:open_pinned_engine",
        "plants": [
            [
                "PackageNotFoundError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_packagenotfounderror",
            ],
            [
                "AreaError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_areaerror",
            ],
            [
                "ImportError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_importerror",
            ],
        ],
        "row": "frame:10",
        "stage": "frame",
    },
    {
        "anchor": "places/area_files.py:produce_areas, _call_engine, _prepare, _require_polygon",
        "plants": [
            ["AreaError", "area_polygon_form", "area_polygon_form"],
            ["AreaError", "engine_failed", "engine_failed"],
            ["AreaError", "engine_version", "engine_version"],
            ["AreaError", "point_outside_frame", "point_outside_frame"],
            ["AreaError", "road_file_missing", "road_file_missing"],
            ["AreaError", "road_file_unreceipted", "road_file_unreceipted"],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_keyerror",
            ],
            [
                "TypeError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_typeerror",
            ],
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_valueerror",
            ],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_oserror",
            ],
        ],
        "row": "frame:11",
        "stage": "frame",
    },
    {
        "anchor": "places/area_files.py:manifest_agrees, produce_areas",
        "plants": [
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_oserror",
            ]
        ],
        "row": "frame:12",
        "stage": "frame",
    },
    {
        "anchor": "places/integrate.py:run_places_before_gazetteer, _tag, _note",
        "plants": [
            ["PlacesError", "arabic_tag", "arabic_tag"],
            ["PlacesError", "arabic_tag_missing", "arabic_tag_missing"],
        ],
        "row": "frame:13",
        "stage": "frame",
    },
    {
        "anchor": "places/integrate.py:_place_from_registry, run_places_before_gazetteer",
        "plants": [
            ["PlacesError", "parquet", "parquet"],
            ["PlacesError", "places_file_unreceipted", "places_file_unreceipted"],
        ],
        "row": "frame:14",
        "stage": "frame",
    },
    {
        "anchor": "places/integrate.py:_boundary, run_places_before_gazetteer",
        "plants": [["PlacesError", "frame_boundary_missing", "frame_boundary_missing"]],
        "row": "frame:15",
        "stage": "frame",
    },
    {
        "anchor": "places/integrate.py:_tag",
        "plants": [
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_oserror",
            ],
            [
                "UnicodeDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_unicodedecodeerror",
            ],
        ],
        "row": "frame:16",
        "stage": "frame",
    },
    {
        "anchor": "places/stage.py:run_places_stage; places/review.py:load_* , _checked; places/integrate.py:_refuse_stage",
        "plants": [
            ["PlacesError", "attribution_header", "attribution_header"],
            ["PlacesError", "attribution_row", "attribution_row"],
            ["PlacesError", "bad_check_date", "bad_check_date"],
            ["PlacesError", "category_header", "category_header"],
            ["PlacesError", "category_row", "category_row"],
            ["PlacesError", "duplicate_place_date", "duplicate_place_date"],
            ["PlacesError", "duplicate_token", "duplicate_token"],
            ["PlacesError", "link_form", "link_form"],
            ["PlacesError", "missing_key", "missing_key"],
            ["PlacesError", "missing_link", "missing_link"],
            ["PlacesError", "missing_role", "missing_role"],
            ["PlacesError", "orphan_place_id", "orphan_place_id"],
            ["PlacesError", "review_list", "review_list"],
            ["PlacesError", "review_row", "review_row"],
            ["PlacesError", "showcase_area", "showcase_area"],
            ["PlacesError", "unknown_category_class", "unknown_category_class"],
            ["PlacesError", "unknown_status", "unknown_status"],
            [
                "PlacesError",
                "verification_source_refused",
                "verification_source_refused",
            ],
            [
                "PlacesError",
                "verification_source_unknown",
                "verification_source_unknown",
            ],
            ["PlacesError", "verified_header", "verified_header"],
        ],
        "row": "frame:17",
        "stage": "frame",
    },
    {
        "anchor": "places/read.py:require_receipt, load_boundary_buildings",
        "plants": [
            ["PlacesError", "receipt_mismatch", "receipt_mismatch"],
            ["PlacesError", "receipt_missing", "receipt_missing"],
        ],
        "row": "frame:18",
        "stage": "frame",
    },
    {
        "anchor": "places/read.py:read_place_file, _require_schema, _place_row, stored_confidence; places/stage.py:_source_points",
        "plants": [
            ["PlacesError", "arabic_tag", "arabic_tag"],
            ["PlacesError", "axis_range", "axis_range"],
            ["PlacesError", "axis_swapped", "axis_swapped"],
            ["PlacesError", "geometry_not_bytes", "geometry_not_bytes"],
            ["PlacesError", "geometry_type", "geometry_type"],
            ["PlacesError", "geometry_wkb", "geometry_wkb"],
            ["PlacesError", "missing_column", "missing_column"],
            ["PlacesError", "place_id", "place_id"],
            ["PlacesError", "range", "range"],
            ["PlacesError", "schema_versions", "schema_versions"],
        ],
        "row": "frame:19",
        "stage": "frame",
    },
    {
        "anchor": "places/read.py:read_building_file, _building_row, load_boundary_buildings",
        "plants": [
            ["PlacesError", "axis_range", "axis_range"],
            ["PlacesError", "axis_swapped", "axis_swapped"],
            ["PlacesError", "building_duplicate", "building_duplicate"],
            ["PlacesError", "building_id", "building_id"],
            ["PlacesError", "geometry_not_bytes", "geometry_not_bytes"],
            ["PlacesError", "geometry_type", "geometry_type"],
            ["PlacesError", "geometry_wkb", "geometry_wkb"],
            ["PlacesError", "missing_column", "missing_column"],
            ["PlacesError", "schema_versions", "schema_versions"],
        ],
        "row": "frame:20",
        "stage": "frame",
    },
    {
        "anchor": "places/build.py:_require_fields; places/stage.py:_place_row",
        "plants": [["PlacesError", "pub_place_field", "pub_place_field"]],
        "row": "frame:21",
        "stage": "frame",
    },
    {
        "anchor": "places/build.py:_flagship",
        "plants": [["PlacesError", "footprint_missing", "footprint_missing"]],
        "row": "frame:22",
        "stage": "frame",
    },
    {
        "anchor": "places/stage.py:resolve_review",
        "plants": [
            ["PlacesError", "record_missing", "record_missing"],
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_frameerror",
            ],
        ],
        "row": "frame:23",
        "stage": "frame",
    },
    {
        "anchor": "places/stage.py:render_verification_rows, _verification_row",
        "plants": [
            ["PlacesError", "orphan_place_id", "orphan_place_id"],
            ["PlacesError", "unknown_status", "unknown_status"],
        ],
        "row": "frame:24",
        "stage": "frame",
    },
    {
        "anchor": "places/stage.py:commit_files",
        "plants": [["PlacesError", "caveat_missing", "caveat_missing"]],
        "row": "frame:25",
        "stage": "frame",
    },
    {
        "anchor": "places/build.py:_fsq, _table; places/display.py:census_figure; places/stage.py:run_places_stage",
        "plants": [
            ["PlacesError", "arabic_tag_missing", "arabic_tag_missing"],
            ["PlacesError", "census_lineage", "census_lineage"],
            ["PlacesError", "fsq_licence_missing", "fsq_licence_missing"],
            ["PlacesError", "loader", "loader"],
        ],
        "row": "frame:26",
        "stage": "frame",
    },
    {
        "anchor": "places/stage.py:resolve_review; places/build.py:_keep",
        "plants": [
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_frameerror",
            ],
            [
                "FrameError",
                "gazetteer: point has no unique base cell",
                "gazetteer_point_has_no_unique_base_cell",
            ],
            ["FrameError", "missing key", "missing_key"],
            ["FrameError", "forbidden digit run", "forbidden_digit_run"],
            [
                "FrameError",
                "gazetteer: duplicate place key",
                "gazetteer_duplicate_place_key",
            ],
            [
                "FrameError",
                "gazetteer: invalid reviewed kind",
                "gazetteer_invalid_reviewed_kind",
            ],
            [
                "FrameError",
                "gazetteer: Arabic review status",
                "gazetteer_arabic_review_status",
            ],
            [
                "PlacesError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_placeserror",
            ],
        ],
        "row": "frame:27",
        "stage": "frame",
    },
    {
        "anchor": "places/stage.py:run_places_stage, _decision_against_file; places/review.py:_csv, _yaml_list; places/read.py:_connect",
        "plants": [
            [
                "FileNotFoundError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_filenotfounderror",
            ],
            [
                "CsvError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_csverror",
            ],
            [
                "UnicodeDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_unicodedecodeerror",
            ],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_oserror",
            ],
            [
                "DuckDBError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_duckdberror",
            ],
            [
                "YAMLError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_yamlerror",
            ],
        ],
        "row": "frame:28",
        "stage": "frame",
    },
    {
        "anchor": "frame/live.py:_place_points, resolve_reviewed_specs; frame/gazetteer.py:reviewed_points",
        "plants": [
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_jsondecodeerror",
            ],
            [
                "FrameError",
                "gazetteer SYN: missing source point",
                "gazetteer_missing_source_point",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_keyerror",
            ],
        ],
        "row": "frame:29",
        "stage": "frame",
    },
    {
        "anchor": "assembly_adapters.py:Production.frame",
        "plants": [
            [
                "AssemblyError",
                "assembly_places_incomplete",
                "assembly_places_incomplete",
            ]
        ],
        "row": "frame:30",
        "stage": "frame",
    },
    {
        "anchor": "assembly_io.py:local",
        "plants": [["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"]],
        "row": "frame:31",
        "stage": "frame",
    },
    {
        "anchor": "assembly_adapters.py:Production.frame",
        "plants": [
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_jsondecodeerror",
            ]
        ],
        "row": "frame:32",
        "stage": "frame",
    },
    {
        "anchor": "assembly_adapters.py:Production.table",
        "plants": [
            ["AssemblyError", "assembly_lineage_missing", "assembly_lineage_missing"],
            ["AssemblyError", "assembly_table_duplicate", "assembly_table_duplicate"],
        ],
        "row": "frame:33",
        "stage": "frame",
    },
    {
        "anchor": "assembly_adapters.py:Production.read_places",
        "plants": [
            [
                "AssemblyError",
                "assembly_places_incomplete",
                "assembly_places_incomplete",
            ]
        ],
        "row": "frame:34",
        "stage": "frame",
    },
    {
        "anchor": "assembly_io.py:bound_files; Production.read_places",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_oserror",
            ],
        ],
        "row": "frame:35",
        "stage": "frame",
    },
    {
        "anchor": "assembly_adapters.py:Production.read_places",
        "plants": [
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "frame_unexpected_jsondecodeerror",
            ]
        ],
        "row": "frame:36",
        "stage": "frame",
    },
    {
        "anchor": "assembly_io.py:read_object",
        "plants": [
            ["AssemblyError", "assembly_input_refused", "assembly_input_refused"]
        ],
        "row": "spine_graph:01",
        "stage": "spine_graph",
    },
    {
        "anchor": "assembly_adapters.py:Production.spine_graph",
        "plants": [
            [
                "AssemblyError",
                "assembly_membership_invalid",
                "assembly_membership_invalid",
            ]
        ],
        "row": "spine_graph:02",
        "stage": "spine_graph",
    },
    {
        "anchor": "assembly_io.py:local",
        "plants": [["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"]],
        "row": "spine_graph:03",
        "stage": "spine_graph",
    },
    {
        "anchor": "assembly_adapters.py:Production.read_places",
        "plants": [
            [
                "AssemblyError",
                "assembly_places_incomplete",
                "assembly_places_incomplete",
            ]
        ],
        "row": "spine_graph:04",
        "stage": "spine_graph",
    },
    {
        "anchor": "assembly_io.py:bound_files; assembly.py:run_steps",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"]
        ],
        "row": "spine_graph:05",
        "stage": "spine_graph",
    },
    {
        "anchor": "assembly_adapters.py:Production.read_places",
        "plants": [
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_jsondecodeerror",
            ],
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_valueerror",
            ],
        ],
        "row": "spine_graph:06",
        "stage": "spine_graph",
    },
    {
        "anchor": "assembly_adapters.py:Production.spine_graph",
        "plants": [["AssemblyError", "assembly_graph_exists", "assembly_graph_exists"]],
        "row": "spine_graph:07",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:decode_review_code",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            ["SpineError", "code is not a digit string", "code_is_not_a_digit_string"],
            [
                "SpineError",
                "review file holds a bare digit run",
                "review_file_holds_a_bare_digit_run",
            ],
            [
                "SpineError",
                "review code is not the reversible dotted form",
                "review_code_is_not_the_reversible_dotted_form",
            ],
        ],
        "row": "spine_graph:08",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:entry_by_key",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            ["SpineError", "registry key missing: SYN", "registry_key_missing"],
            [
                "SpineError",
                "registry key is not unique: SYN",
                "registry_key_is_not_unique",
            ],
        ],
        "row": "spine_graph:09",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/cache_fixture.py:read_cached \u2190 fetch/snapshots.py:read_snapshot",
        "plants": [
            [
                "CacheError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_cacheerror",
            ],
            ["CacheError", "SYN: snapshot_path_invalid", "snapshot_path_invalid"],
            ["CacheError", "SYN: snapshot_index_invalid", "snapshot_index_invalid"],
            ["CacheError", "SYN: snapshot_missing", "snapshot_missing"],
            ["CacheError", "SYN: snapshot_hash_mismatch", "snapshot_hash_mismatch"],
            ["CacheError", "SYN: snapshot_date_missing", "snapshot_date_missing"],
            ["SnapshotError", "snapshot_date_missing", "snapshot_date_missing"],
            ["SnapshotError", "snapshot_hash_mismatch", "snapshot_hash_mismatch"],
            ["SnapshotError", "snapshot_index_invalid", "snapshot_index_invalid"],
            ["SnapshotError", "snapshot_missing", "snapshot_missing"],
            ["SnapshotError", "snapshot_path_invalid", "snapshot_path_invalid"],
        ],
        "row": "spine_graph:10",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/cache_fixture.py:read_cached",
        "plants": [
            [
                "CacheError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_cacheerror",
            ],
            [
                "CacheError",
                "snapshot extension mismatch",
                "snapshot_extension_mismatch",
            ],
            [
                "CacheError",
                "cache sidecar names another digest",
                "cache_sidecar_names_another_digest",
            ],
            [
                "CacheError",
                "cache body digest differs from its sidecar",
                "cache_body_digest_differs_from_its_sidecar",
            ],
            [
                "CacheError",
                "cache body size differs from its sidecar",
                "cache_body_size_differs_from_its_sidecar",
            ],
            [
                "CacheError",
                "cache sidecar names another key",
                "cache_sidecar_names_another_key",
            ],
            [
                "CacheError",
                "cache sidecar names another source",
                "cache_sidecar_names_another_source",
            ],
            ["CacheError", "cache body is switched off", "cache_body_is_switched_off"],
        ],
        "row": "spine_graph:11",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/cache_fixture.py:read_rows, _json_rows, read_csv",
        "plants": [
            [
                "CacheError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_cacheerror",
            ],
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_jsondecodeerror",
            ],
            [
                "CacheError",
                "cache body has no row reader for SYN",
                "cache_body_has_no_row_reader_for",
            ],
            [
                "CacheError",
                "cache json body is not a list of rows",
                "cache_json_body_is_not_a_list_of_rows",
            ],
            [
                "CacheError",
                "cache json row is not a map",
                "cache_json_row_is_not_a_map",
            ],
            [
                "UnicodeDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_unicodedecodeerror",
            ],
        ],
        "row": "spine_graph:12",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:parse_feed_rows \u2190 series/parse.py:confirmed_rows",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            ["SpineError", "SYN field type: SYN", "field_type"],
            ["ValueError", "SYN registry fields: \u2026", "registry_fields"],
            ["ValueError", "SYN source fields: \u2026", "source_fields"],
            ["ValueError", "SYN field type: SYN", "field_type"],
        ],
        "row": "spine_graph:13",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:parse_feed_rows, merge_feed_rows, release_field",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            ["SpineError", "unknown activity feed SYN", "unknown_activity_feed"],
            [
                "SpineError",
                "activity column is not one field: SYN",
                "activity_column_is_not_one_field",
            ],
            ["SpineError", "activity_name_ar is not text", "is_not_text"],
            [
                "SpineError",
                "active_count is not a non-negative integer",
                "is_not_a_non_negative_integer",
            ],
            ["SpineError", "SYN field type: SYN", "field_type"],
            [
                "SpineError",
                "conflicting activity name for SYN",
                "conflicting_activity_name_for",
            ],
        ],
        "row": "spine_graph:14",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:parse_isic_rows",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            ["SpineError", "unknown isic field \u2026", "unknown_isic_field"],
            ["SpineError", "missing isic field \u2026", "missing_isic_field"],
            ["SpineError", "isic field is not text", "isic_field_is_not_text"],
            ["SpineError", "isic class title is empty", "isic_class_title_is_empty"],
            [
                "SpineError",
                "conflicting isic title for SYN",
                "conflicting_isic_title_for",
            ],
            [
                "SpineError",
                "isic code pattern is not a class or a higher level",
                "isic_code_pattern_is_not_a_class_or_a_higher_level",
            ],
        ],
        "row": "spine_graph:15",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:read_review_csv, _review_row",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            [
                "SpineError",
                "review header is not the spine header",
                "review_header_is_not_the_spine_header",
            ],
            ["SpineError", "duplicate review code", "duplicate_review_code"],
            [
                "SpineError",
                "code_length does not match the code \u2026",
                "code_length_does_not_match_the_code",
            ],
            ["SpineError", "unknown status \u2026", "unknown_status"],
            ["SpineError", "reason is not a closed key", "reason_is_not_a_closed_key"],
            [
                "SpineError",
                "isic_class is not four digits",
                "isic_class_is_not_four_digits",
            ],
            [
                "SpineError",
                "reviewed_on is not an ISO date",
                "reviewed_on_is_not_an_iso_date",
            ],
            ["SpineError", "\u2026 is not text", "is_not_text"],
            [
                "FileNotFoundError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_filenotfounderror",
            ],
        ],
        "row": "spine_graph:16",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:load_recorded_binding, read_review_binding, _require_reviewed_binding",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            ["SpineError", "review binding is missing", "review_binding_is_missing"],
            [
                "SpineError",
                "code-system version differs from the reviewed version",
                "code_system_version_differs_from_the_reviewed_version",
            ],
            [
                "SpineError",
                "classification title differs from the reviewed title",
                "classification_title_differs_from_the_reviewed_title",
            ],
        ],
        "row": "spine_graph:17",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:_require_model_audits, _audit_record",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            [
                "SpineError",
                "model review role is malformed",
                "model_review_role_is_malformed",
            ],
            [
                "SpineError",
                "model audit binding is missing",
                "model_audit_binding_is_missing",
            ],
            [
                "SpineError",
                "model audit file is not readable",
                "model_audit_file_is_not_readable",
            ],
            [
                "SpineError",
                "model audit list is invalid",
                "model_audit_list_is_invalid",
            ],
            ["SpineError", "model audit has no records", "model_audit_has_no_records"],
            [
                "SpineError",
                "model review code has no audited batch",
                "model_review_code_has_no_audited_batch",
            ],
            [
                "SpineError",
                "model audit code is not a signed model decision",
                "model_audit_code_is_not_a_signed_model_decision",
            ],
            [
                "SpineError",
                "model audit predates signing",
                "model_audit_predates_signing",
            ],
        ],
        "row": "spine_graph:18",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:build_spine, _derive, _require_sign_off, _require_decision",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            [
                "SpineError",
                "supplier membership is missing",
                "supplier_membership_is_missing",
            ],
            [
                "SpineError",
                "playbook code absent from the feeds: SYN",
                "playbook_code_absent_from_the_feeds",
            ],
            [
                "SpineError",
                "supplier code absent from the feeds: SYN",
                "supplier_code_absent_from_the_feeds",
            ],
            ["SpineError", "duplicate activity code \u2026", "duplicate_activity_code"],
            ["SpineError", "unknown activity source \u2026", "unknown_activity_source"],
            [
                "SpineError",
                "isic class is not four digits",
                "isic_class_is_not_four_digits",
            ],
            [
                "SpineError",
                "mapped decision without a reviewer role",
                "decision_without_a_reviewer_role",
            ],
            [
                "SpineError",
                "SYN decision without the SYN reason",
                "decision_without_the_reason",
            ],
        ],
        "row": "spine_graph:19",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/activity.py:_source_hash",
        "plants": [
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_spineerror",
            ],
            [
                "SpineError",
                "source receipt has no hash: SYN",
                "source_receipt_has_no_hash",
            ],
        ],
        "row": "spine_graph:20",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/graph.py:read_allowlist, _allowlist_row",
        "plants": [
            [
                "GraphError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_grapherror",
            ],
            [
                "GraphError",
                "allow-list header is not the fixed header",
                "allow_list_header_is_not_the_fixed_header",
            ],
            ["GraphError", "duplicate allow-list pair", "duplicate_allow_list_pair"],
            [
                "GraphError",
                "allow-list class is not a digit string",
                "allow_list_class_is_not_a_digit_string",
            ],
            [
                "GraphError",
                "allow-list category is empty",
                "allow_list_category_is_empty",
            ],
            [
                "GraphError",
                "allow-list sign-off is not text",
                "allow_list_sign_off_is_not_text",
            ],
            [
                "GraphError",
                "allow-list date is not an ISO date",
                "allow_list_date_is_not_an_iso_date",
            ],
            [
                "FileNotFoundError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_filenotfounderror",
            ],
        ],
        "row": "spine_graph:21",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/graph.py:build_graph, _require_mapped_row, _require_sign_off, _add_node, _add_edge",
        "plants": [
            [
                "GraphError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_grapherror",
            ],
            ["GraphError", "unknown graph mode", "unknown_graph_mode"],
            [
                "GraphError",
                "cls_isic4 is not in the registry",
                "cls_isic4_is_not_in_the_registry",
            ],
            [
                "GraphError",
                "spine and activities name different codes",
                "spine_and_activities_name_different_codes",
            ],
            [
                "GraphError",
                "mapped edge is not a seven-digit code",
                "mapped_edge_is_not_a_seven_digit_code",
            ],
            [
                "GraphError",
                "allow-list class is not in cls_isic4",
                "allow_list_class_is_not_in_cls_isic4",
            ],
            [
                "GraphError",
                "allow-list category is not in the places cache",
                "allow_list_category_is_not_in_the_places_cache",
            ],
            [
                "GraphError",
                "allow-list row without sign-off",
                "allow_list_row_without_sign_off",
            ],
            [
                "GraphError",
                "source is not in the registry: SYN",
                "source_is_not_in_the_registry",
            ],
            ["GraphError", "conflicting node \u2026", "conflicting_node"],
            ["GraphError", "conflicting edge \u2026", "conflicting_edge"],
        ],
        "row": "spine_graph:22",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/graph.py:validate_graph, _check_node, _check_edge, _check_edge_ends, _require_unmappable",
        "plants": [
            [
                "GraphError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_grapherror",
            ],
            ["GraphError", "node code is empty", "node_code_is_empty"],
            ["GraphError", "unknown node provenance", "unknown_node_provenance"],
            [
                "GraphError",
                "edge source has no release-admitted licence",
                "edge_source_has_no_release_admitted_licence",
            ],
            [
                "GraphError",
                "activity graph is missing the UNMAPPABLE node",
                "activity_graph_is_missing_the_unmappable_node",
            ],
        ],
        "row": "spine_graph:23",
        "stage": "spine_graph",
    },
    {
        "anchor": "review/graph.py:write_graph, _write_parquet",
        "plants": [
            [
                "GraphError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_grapherror",
            ],
            [
                "GraphError",
                "graph output already exists",
                "graph_output_already_exists",
            ],
            [
                "DuckDBError",
                "SYN opaque fault /syn/no-output 999999999",
                "spine_graph_unexpected_duckdberror",
            ],
        ],
        "row": "spine_graph:24",
        "stage": "spine_graph",
    },
    {
        "anchor": "assembly_adapters.py:Production.additions",
        "plants": [
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "additions_unexpected_keyerror",
            ]
        ],
        "row": "additions:02",
        "stage": "additions",
    },
    {
        "anchor": "additions/build.py:build_additions, checked_selection",
        "plants": [
            ["AdditionError", "duplicate_slug_selection", "duplicate_slug_selection"],
            ["AdditionError", "slug_absent", "slug_absent"],
        ],
        "row": "additions:03",
        "stage": "additions",
    },
    {
        "anchor": "additions/build.py:_field_map; industry.py:_review/_spec/_measures\u2026; municipal.py:_rules/_geography\u2026; splits.py:_spec/_role/_vocab\u2026; property_venues.py:_unit_types/_missing_measure",
        "plants": [["AdditionError", "field_map_unreadable", "field_map_unreadable"]],
        "row": "additions:04",
        "stage": "additions",
    },
    {
        "anchor": "additions/build.py:_cached_export",
        "plants": [
            ["AdditionError", "selected_input_refused", "selected_input_refused"],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "additions_unexpected_oserror",
            ],
            [
                "SnapshotError",
                "SYN opaque fault /syn/no-output 999999999",
                "additions_unexpected_snapshoterror",
            ],
        ],
        "row": "additions:05",
        "stage": "additions",
    },
    {
        "anchor": "additions/build.py:_cached_export",
        "plants": [["AdditionError", "export_unreadable", "export_unreadable"]],
        "row": "additions:06",
        "stage": "additions",
    },
    {
        "anchor": "property_venues.py:load_venue_crosswalk, _venue, _museum_rows, _one_place",
        "plants": [
            ["AdditionError", "unmapped_venue_name", "unmapped_venue_name"],
            ["AdditionError", "unreviewed_venue", "unreviewed_venue"],
            ["AdditionError", "venue_crosswalk", "venue_crosswalk"],
            ["AdditionError", "venue_crosswalk_conflict", "venue_crosswalk_conflict"],
            ["AdditionError", "venue_name_conflict", "venue_name_conflict"],
            ["AdditionError", "venue_place_conflict", "venue_place_conflict"],
        ],
        "row": "additions:07",
        "stage": "additions",
    },
    {
        "anchor": "property_venues.py; municipal.py; splits.py; industry.py (family parsers)",
        "plants": [
            ["AdditionError", "activity_code_form", "activity_code_form"],
            ["AdditionError", "arabic_twin_mismatch", "arabic_twin_mismatch"],
            ["AdditionError", "bilingual_municipality", "bilingual_municipality"],
            ["AdditionError", "breakdown_unencodable", "breakdown_unencodable"],
            ["AdditionError", "category_disagreement", "category_disagreement"],
            ["AdditionError", "category_unlisted", "category_unlisted"],
            ["AdditionError", "category_unparsed", "category_unparsed"],
            ["AdditionError", "country_crosswalk", "country_crosswalk"],
            ["AdditionError", "country_unreviewed", "country_unreviewed"],
            ["AdditionError", "crosswalk_missing", "crosswalk_missing"],
            ["AdditionError", "district_crosswalk", "district_crosswalk"],
            ["AdditionError", "document_type", "document_type"],
            ["AdditionError", "geography_undeclared", "geography_undeclared"],
            ["AdditionError", "identifier_leak", "identifier_leak"],
            [
                "AdditionError",
                "indicator_labels_unconfirmed",
                "indicator_labels_unconfirmed",
            ],
            ["AdditionError", "municipality_disagreement", "municipality_disagreement"],
            ["AdditionError", "municipality_spellings", "municipality_spellings"],
            ["AdditionError", "second_mapping", "second_mapping"],
            ["AdditionError", "slug_unmapped", "slug_unmapped"],
            ["AdditionError", "source_field_absent", "source_field_absent"],
            ["AdditionError", "unknown_source_field", "unknown_source_field"],
            ["AdditionError", "unmapped_municipality", "unmapped_municipality"],
            ["AdditionError", "unmapped_unit_type", "unmapped_unit_type"],
        ],
        "row": "additions:08",
        "stage": "additions",
    },
    {
        "anchor": "additions/common.py:parse_period_rule, parse_period_value, observe_period_bounds",
        "plants": [
            ["AdditionError", "period_absent", "period_absent"],
            ["AdditionError", "period_field_empty", "period_field_empty"],
            ["AdditionError", "period_field_unconfirmed", "period_field_unconfirmed"],
            ["AdditionError", "period_field_unreadable", "period_field_unreadable"],
            ["AdditionError", "period_form", "period_form"],
            ["AdditionError", "period_sit", "period_sit"],
            ["AdditionError", "period_unreadable", "period_unreadable"],
        ],
        "row": "additions:09",
        "stage": "additions",
    },
    {
        "anchor": "additions/common.py:read_measure; municipal.py:_whole/_scaled; industry.py:_number",
        "plants": [
            ["AdditionError", "measure_negative", "measure_negative"],
            ["AdditionError", "measure_not_integral", "measure_not_integral"],
            ["AdditionError", "measure_precision", "measure_precision"],
            ["AdditionError", "measure_unparsed", "measure_unparsed"],
        ],
        "row": "additions:10",
        "stage": "additions",
    },
    {
        "anchor": "additions/build.py:_tables, _refuse_row, _refuse_value; common.py:require_lineage, refuse_duplicate_keys, require_closed; storage.py:publish, _definition",
        "plants": [
            ["AdditionError", "column_name", "column_name"],
            ["AdditionError", "duplicate_key", "duplicate_key"],
            ["AdditionError", "key_part_missing", "key_part_missing"],
            ["AdditionError", "lineage_incomplete", "lineage_incomplete"],
            ["AdditionError", "table_columns_mismatch", "table_columns_mismatch"],
            ["AdditionError", "table_name", "table_name"],
            ["AdditionError", "unknown_table", "unknown_table"],
            ["AdditionError", "value_out_of_column", "value_out_of_column"],
        ],
        "row": "additions:11",
        "stage": "additions",
    },
    {
        "anchor": "frame/crosswalk.py; additions/municipal.py:_codes/_names; splits.py:_names; property_venues.py:_municipality_rows",
        "plants": [
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "additions_unexpected_frameerror",
            ],
            [
                "MunicipalityFrameRefused",
                "SYN opaque fault /syn/no-output 999999999",
                "additions_unexpected_municipalityframerefused",
            ],
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "additions_unexpected_valueerror",
            ],
            [
                "FrameError",
                "municipality_names: unknown_key",
                "municipality_names_unknown_key",
            ],
            [
                "FrameError",
                "unmapped municipality spelling",
                "unmapped_municipality_spelling",
            ],
            ["FrameError", "district_alias: CSV header", "district_alias_csv_header"],
        ],
        "row": "additions:12",
        "stage": "additions",
    },
    {
        "anchor": "assembly_io.py:read_object",
        "plants": [
            ["AssemblyError", "assembly_input_refused", "assembly_input_refused"]
        ],
        "row": "additions:13",
        "stage": "additions",
    },
    {
        "anchor": "assembly_io.py:bound_files",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"]
        ],
        "row": "additions:14",
        "stage": "additions",
    },
    {
        "anchor": "assembly_adapters.py:Production.additions",
        "plants": [
            [
                "AssemblyError",
                "assembly_additions_pending",
                "assembly_additions_pending",
            ]
        ],
        "row": "additions:15",
        "stage": "additions",
    },
    {
        "anchor": "assembly_adapters.py:Production.table",
        "plants": [
            ["AssemblyError", "assembly_lineage_missing", "assembly_lineage_missing"],
            ["AssemblyError", "assembly_table_duplicate", "assembly_table_duplicate"],
        ],
        "row": "additions:16",
        "stage": "additions",
    },
    {
        "anchor": "assembly_io.py:local",
        "plants": [["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"]],
        "row": "additions:17",
        "stage": "additions",
    },
    {
        "anchor": "additions/storage.py:write_parquet; review/cache_fixture.py:read_parquet",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "additions_unexpected_valueerror",
            ],
            [
                "DuckDBError",
                "SYN opaque fault /syn/no-output 999999999",
                "additions_unexpected_duckdberror",
            ],
        ],
        "row": "additions:18",
        "stage": "additions",
    },
    {
        "anchor": "assembly_adapters.py:Production.needed_frame",
        "plants": [
            ["AssemblyError", "assembly_frame_incomplete", "assembly_frame_incomplete"]
        ],
        "row": "gis_property_singles:01",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly_layers.py:build_layers, _features",
        "plants": [
            [
                "AssemblyError",
                "assembly_gis_shape_invalid",
                "assembly_gis_shape_invalid",
            ]
        ],
        "row": "gis_property_singles:02",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly_layers.py:build_layers; assembly_adapters.py:Production.table",
        "plants": [
            ["AssemblyError", "assembly_table_duplicate", "assembly_table_duplicate"]
        ],
        "row": "gis_property_singles:03",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly_adapters.py:Production.table",
        "plants": [
            ["AssemblyError", "assembly_lineage_missing", "assembly_lineage_missing"]
        ],
        "row": "gis_property_singles:04",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly_layers.py:build_layers",
        "plants": [
            [
                "AssemblyError",
                "assembly_family_shape_invalid",
                "assembly_family_shape_invalid",
            ]
        ],
        "row": "gis_property_singles:05",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly_layers.py:build_layers; assembly_adapters.py:Production.raw",
        "plants": [
            [
                "AssemblyError",
                "snapshot_selection_invalid",
                "snapshot_selection_invalid",
            ]
        ],
        "row": "gis_property_singles:06",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly_layers.py:build_layers",
        "plants": [
            [
                "AssemblyError",
                "assembly_tenders_shape_invalid",
                "assembly_tenders_shape_invalid",
            ]
        ],
        "row": "gis_property_singles:07",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly_io.py:local",
        "plants": [["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"]],
        "row": "gis_property_singles:08",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly.py:_output_path, run_steps; assembly_io.py:json_value",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"],
            ["AssemblyError", "assembly_value_invalid", "assembly_value_invalid"],
        ],
        "row": "gis_property_singles:09",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "frame/build.py:read_cached; fetch/snapshots.py:read_snapshot",
        "plants": [
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_frameerror",
            ],
            ["SnapshotError", "snapshot_date_missing", "snapshot_date_missing"],
            ["SnapshotError", "snapshot_hash_mismatch", "snapshot_hash_mismatch"],
            ["SnapshotError", "snapshot_index_invalid", "snapshot_index_invalid"],
            ["SnapshotError", "snapshot_missing", "snapshot_missing"],
            ["SnapshotError", "snapshot_path_invalid", "snapshot_path_invalid"],
        ],
        "row": "gis_property_singles:10",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "frame/build.py:read_cached",
        "plants": [
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_frameerror",
            ],
            [
                "FrameError",
                "SYN: receipt {source_id\\|key\\|licence_id\\|licence_basis} mismatch",
                "receipt_mismatch",
            ],
            [
                "FrameError",
                "SYN: missing receipt {publisher\\|title_en\\|fetch_url\\|retrieved_utc\\|sha256}",
                "missing_receipt",
            ],
            ["FrameError", "SYN: source switched off", "source_switched_off"],
        ],
        "row": "gis_property_singles:11",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly_adapters.py:Production.raw; fetch/snapshots.py:Snapshot.body",
        "plants": [
            ["SnapshotError", "snapshot_hash_mismatch", "snapshot_hash_mismatch"]
        ],
        "row": "gis_property_singles:12",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "frame/build.py:read_cached; assembly_adapters.py:Production.raw",
        "plants": [
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_jsondecodeerror",
            ]
        ],
        "row": "gis_property_singles:13",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "gis/layers.py (address_rows, parcel_rows, zoning_rows, rail_rows, health_rows, poi_rows, landmark_rows, land_price_rows and helpers)",
        "plants": [
            ["LayerError", "area", "area"],
            ["LayerError", "attributes", "attributes"],
            ["LayerError", "cell", "cell"],
            ["LayerError", "coordinate", "coordinate"],
            ["LayerError", "date", "date"],
            ["LayerError", "features", "features"],
            ["LayerError", "geometry", "geometry"],
            ["LayerError", "number", "number"],
            ["LayerError", "spatial_reference", "spatial_reference"],
            ["LayerError", "text", "text"],
            ["LayerError", "zoning_code", "zoning_code"],
            ["LayerError", "layer name", "layer_name"],
            ["LayerError", "rail layer", "rail_layer"],
            ["LayerError", "health layer", "health_layer"],
            ["LayerError", "district numbers differ", "district_numbers_differ"],
            ["LayerError", "service name year", "service_name_year"],
            ["LayerError", "feature key value", "feature_key_value"],
            ["LayerError", "release column SYN", "release_column"],
        ],
        "row": "gis_property_singles:14",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "frame/grid.py:point_cell; frame/gazetteer.py:reviewed_points, make_row; frame/checks.py:safe_key",
        "plants": [
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_frameerror",
            ],
            [
                "FrameError",
                "gazetteer: point has no unique base cell",
                "gazetteer_point_has_no_unique_base_cell",
            ],
            [
                "FrameError",
                "gazetteer: missing bilingual name",
                "gazetteer_missing_bilingual_name",
            ],
            [
                "FrameError",
                "gazetteer: duplicate place key",
                "gazetteer_duplicate_place_key",
            ],
            ["FrameError", "missing key", "missing_key"],
            ["FrameError", "forbidden digit run", "forbidden_digit_run"],
        ],
        "row": "gis_property_singles:15",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "gis/layers.py:geometry_shape; assembly_layers.py:build_layers",
        "plants": [
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_keyerror",
            ]
        ],
        "row": "gis_property_singles:16",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "singles/bank_credit.py:parse_bank_credit, _value",
        "plants": [
            ["CreditError", "activity", "activity"],
            ["CreditError", "unexpected_column", "unexpected_column"],
            ["CreditError", "value", "value"],
            ["CreditError", "year", "year"],
            ["CreditError", "value SYN", "value"],
        ],
        "row": "gis_property_singles:17",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "singles/dcool.py:parse_dcool, _sector_value, _status_indicator",
        "plants": [
            ["CoolingError", "consumption", "consumption"],
            ["CoolingError", "culture_type", "culture_type"],
            ["CoolingError", "duplicate_key", "duplicate_key"],
            ["CoolingError", "project_status", "project_status"],
            ["CoolingError", "sector_type", "sector_type"],
            ["CoolingError", "unexpected_column", "unexpected_column"],
            ["CoolingError", "unmapped_municipality", "unmapped_municipality"],
            ["CoolingError", "year", "year"],
        ],
        "row": "gis_property_singles:18",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "frame/crosswalk.py:load_municipality_names, read_csv",
        "plants": [
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_frameerror",
            ],
            [
                "FrameError",
                "municipality_names: unknown_key",
                "municipality_names_unknown_key",
            ],
            [
                "FrameError",
                "municipality_names: conflict",
                "municipality_names_conflict",
            ],
            [
                "FileNotFoundError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_filenotfounderror",
            ],
        ],
        "row": "gis_property_singles:19",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "property/bulletin.py:sales_export_rows",
        "plants": [
            ["AdditionError", "bulletin_row", "bulletin_row"],
            ["AdditionError", "bulletin_rows", "bulletin_rows"],
            [
                "AdditionError",
                "no_whole_property_deals",
                "no_whole_property_deals",
            ],
            ["AdditionError", "source_field_missing", "source_field_missing"],
            ["AdditionError", "unknown_source_field", "unknown_source_field"],
        ],
        "row": "gis_property_singles:20",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "property/use_map.py:load_use_map",
        "plants": [
            ["AdditionError", "period_form", "period_form"],
            ["AdditionError", "unknown_unit_type", "unknown_unit_type"],
            ["AdditionError", "use_map_columns", "use_map_columns"],
            ["AdditionError", "use_map_conflict", "use_map_conflict"],
            ["AdditionError", "use_map_field_empty", "use_map_field_empty"],
            ["AdditionError", "use_map_source", "use_map_source"],
        ],
        "row": "gis_property_singles:21",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "property/bulletin.py:parse_bulletin, _deal; additions/property_venues.py:_municipality, _district, _text; property/use_map.py:use_lookup; additions/common.py:read_measure",
        "plants": [
            ["AdditionError", "bulletin_row", "bulletin_row"],
            ["AdditionError", "bulletin_rows", "bulletin_rows"],
            ["AdditionError", "crosswalk_missing", "crosswalk_missing"],
            ["AdditionError", "district_crosswalk", "district_crosswalk"],
            ["AdditionError", "measure_not_integral", "measure_not_integral"],
            ["AdditionError", "measure_unparsed", "measure_unparsed"],
            ["AdditionError", "municipality_disagreement", "municipality_disagreement"],
            ["AdditionError", "period_form", "period_form"],
            ["AdditionError", "unknown_source_field", "unknown_source_field"],
            ["AdditionError", "unmapped_label", "unmapped_label"],
            ["AdditionError", "unmapped_municipality", "unmapped_municipality"],
            ["AdditionError", "unmapped_usage", "unmapped_usage"],
            ["AdditionError", "use_map_ambiguous", "use_map_ambiguous"],
            ["AdditionError", "use_map_source", "use_map_source"],
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_frameerror",
            ],
        ],
        "row": "gis_property_singles:22",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "property/bulletin.py:refuse_release_identifiers; property/quarter.py:quarter_aggregates, expected_as_of; property/price_as_of.py:group_as_of, require_price_as_of",
        "plants": [
            ["AdditionError", "identifier_leak", "identifier_leak"],
            ["AdditionError", "mixed_price_basis", "mixed_price_basis"],
            ["AdditionError", "price_as_of_mismatch", "price_as_of_mismatch"],
            ["AdditionError", "price_as_of_missing", "price_as_of_missing"],
        ],
        "row": "gis_property_singles:23",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "singles/families.py:decode_family_archive, parse_family_rows, _encode, _period_label; additions/common.py:parse_period_rule",
        "plants": [
            ["FamilyError", "archive_unreadable", "archive_unreadable"],
            ["FamilyError", "columns_empty", "columns_empty"],
            ["FamilyError", "duplicate_member", "duplicate_member"],
            ["FamilyError", "field_kind", "field_kind"],
            ["FamilyError", "field_value", "field_value"],
            ["FamilyError", "period_label", "period_label"],
            ["FamilyError", "unexpected_column", "unexpected_column"],
            ["AdditionError", "period_field_empty", "period_field_empty"],
            ["AdditionError", "period_field_unreadable", "period_field_unreadable"],
            ["AdditionError", "period_form", "period_form"],
            ["AdditionError", "period_sit", "period_sit"],
        ],
        "row": "gis_property_singles:24",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "confirm_s2_t13.py:load_confirmation, _block, _validate_tender",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_valueerror",
            ],
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_jsondecodeerror",
            ],
            [
                "ValueError",
                "confirmation block is not an object",
                "confirmation_block_is_not_an_object",
            ],
            [
                "ValueError",
                "missing fields ['syn_missing']; unknown fields ['syn_unknown']",
                "missing_fields_unknown_fields",
            ],
            ["ValueError", "SYN is not text", "is_not_text"],
            ["ValueError", "SYN is not a boolean", "is_not_a_boolean"],
            [
                "ValueError",
                "invalid tender flags or tables",
                "invalid_tender_flags_or_tables",
            ],
            [
                "ValueError",
                "weight confirmation is not the current area-only choice",
                "weight_confirmation_is_not_the_current_area_only_choice",
            ],
            [
                "FileNotFoundError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_filenotfounderror",
            ],
        ],
        "row": "gis_property_singles:25",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "confirm_s2_t13.py:completion_evidence",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_valueerror",
            ],
            [
                "ValueError",
                "incomplete tender confirmation",
                "incomplete_tender_confirmation",
            ],
            [
                "ValueError",
                "registry and fetched evidence do not confirm tender",
                "registry_and_fetched_evidence_do_not_confirm_tender",
            ],
            [
                "ValueError",
                "registry must record the disabled source or evidenced absence",
                "registry_must_record_the_disabled_source_or_evidenced_absence",
            ],
        ],
        "row": "gis_property_singles:26",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "singles/tenders.py:rows_from_pages, _interpret, _merge, _row_for, _pick, publish_tenders, reject_release; singles/tenders_html.py:read_raw_page",
        "plants": [
            ["TenderError", "amount", "amount"],
            ["TenderError", "language", "language"],
            ["TenderError", "missing_buying_entity", "missing_buying_entity"],
            ["TenderError", "release_contact", "release_contact"],
            ["TenderError", "release_identifier", "release_identifier"],
            ["TenderError", "tender_key", "tender_key"],
            ["TenderError", "internal_id", "internal_id"],
            ["TenderError", "page_shape", "page_shape"],
            ["TenderError", "pager", "pager"],
            ["TenderError", "title", "title"],
            ["TenderError", "SYN label SYN", "label"],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "gis_property_singles_unexpected_keyerror",
            ],
            ["PageShapeError", "internal_id", "internal_id"],
            ["PageShapeError", "language", "language"],
            ["PageShapeError", "page_shape", "page_shape"],
            ["PageShapeError", "pager", "pager"],
            ["PageShapeError", "title", "title"],
        ],
        "row": "gis_property_singles:27",
        "stage": "gis_property_singles",
    },
    {
        "anchor": "assembly_adapters.py:Production.fsq",
        "plants": [["AssemblyError", "assembly_fsq_missing", "assembly_fsq_missing"]],
        "row": "fsq:01",
        "stage": "fsq",
    },
    {
        "anchor": "assembly_adapters.py:_fsq_manifest, Production.table",
        "plants": [
            ["AssemblyError", "assembly_lineage_missing", "assembly_lineage_missing"],
            ["PlacesFsqError", "release_invalid", "release_invalid"],
        ],
        "row": "fsq:02",
        "stage": "fsq",
    },
    {
        "anchor": "assembly_adapters.py:Production.fsq; assembly_io.py:bound_files; assembly.py:run_steps",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"]
        ],
        "row": "fsq:03",
        "stage": "fsq",
    },
    {
        "anchor": "assembly_io.py:local",
        "plants": [["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"]],
        "row": "fsq:04",
        "stage": "fsq",
    },
    {
        "anchor": "assembly_adapters.py:Production.read_places",
        "plants": [
            [
                "AssemblyError",
                "assembly_places_incomplete",
                "assembly_places_incomplete",
            ]
        ],
        "row": "fsq:05",
        "stage": "fsq",
    },
    {
        "anchor": "assembly_adapters.py:Production.needed_frame",
        "plants": [
            ["AssemblyError", "assembly_frame_incomplete", "assembly_frame_incomplete"]
        ],
        "row": "fsq:06",
        "stage": "fsq",
    },
    {
        "anchor": "assembly_adapters.py:Production.table",
        "plants": [
            ["AssemblyError", "assembly_table_duplicate", "assembly_table_duplicate"]
        ],
        "row": "fsq:07",
        "stage": "fsq",
    },
    {
        "anchor": "assembly_io.py:write_record, json_value",
        "plants": [
            ["AssemblyError", "assembly_value_invalid", "assembly_value_invalid"]
        ],
        "row": "fsq:08",
        "stage": "fsq",
    },
    {
        "anchor": "fetch/snapshots.py:read_snapshot, Snapshot.body",
        "plants": [
            ["SnapshotError", "snapshot_date_missing", "snapshot_date_missing"],
            ["SnapshotError", "snapshot_hash_mismatch", "snapshot_hash_mismatch"],
            ["SnapshotError", "snapshot_missing", "snapshot_missing"],
            ["SnapshotError", "snapshot_index_invalid", "snapshot_index_invalid"],
            ["SnapshotError", "snapshot_path_invalid", "snapshot_path_invalid"],
        ],
        "row": "fsq:09",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/policy.py:assert_policy",
        "plants": [["PlacesFsqError", "policy_disagrees", "policy_disagrees"]],
        "row": "fsq:10",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/policy.py:load_mapping",
        "plants": [["PlacesFsqError", "mapping_header", "mapping_header"]],
        "row": "fsq:11",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/policy.py:_mapping_row",
        "plants": [["PlacesFsqError", "mapping_unsigned", "mapping_unsigned"]],
        "row": "fsq:12",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/policy.py:_mapping_row",
        "plants": [
            ["PlacesFsqError", "mapping_unknown_target", "mapping_unknown_target"]
        ],
        "row": "fsq:13",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/policy.py:load_mapping",
        "plants": [["PlacesFsqError", "mapping_conflict", "mapping_conflict"]],
        "row": "fsq:14",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/policy.py:product_categories (via assemble.py:build_places)",
        "plants": [["PlacesFsqError", "category_unmapped", "category_unmapped"]],
        "row": "fsq:15",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/assemble.py:build_places",
        "plants": [
            ["PlacesFsqError", "name", "name"],
            ["PlacesFsqError", "release_invalid", "release_invalid"],
            ["PlacesFsqError", "release_mismatch", "release_mismatch"],
            ["PlacesFsqError", "source_release", "source_release"],
        ],
        "row": "fsq:16",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/assemble.py:build_places",
        "plants": [["PlacesFsqError", "attribution", "attribution"]],
        "row": "fsq:17",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/assemble.py:_parsed",
        "plants": [
            ["PlacesFsqError", "name", "name"],
            ["PlacesFsqError", "receipt_mismatch", "receipt_mismatch"],
        ],
        "row": "fsq:18",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/parse.py:_local",
        "plants": [["PlacesFsqError", "remote_path", "remote_path"]],
        "row": "fsq:19",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/parse.py:_schema",
        "plants": [["PlacesFsqError", "name", "name"]],
        "row": "fsq:20",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/parse.py:_schema, _row, _float, _range, _wkb_point, _date",
        "plants": [
            ["PlacesFsqError", "date_closed", "date_closed"],
            ["PlacesFsqError", "date_created", "date_created"],
            ["PlacesFsqError", "date_refreshed", "date_refreshed"],
            ["PlacesFsqError", "fsq_category_ids", "fsq_category_ids"],
            ["PlacesFsqError", "fsq_category_labels", "fsq_category_labels"],
            ["PlacesFsqError", "geometry", "geometry"],
            ["PlacesFsqError", "latitude", "latitude"],
            ["PlacesFsqError", "longitude", "longitude"],
        ],
        "row": "fsq:21",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/parse.py:_row",
        "plants": [["PlacesFsqError", "axes_swapped", "axes_swapped"]],
        "row": "fsq:22",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/parse.py:_categories, _members",
        "plants": [
            ["PlacesFsqError", "category_ids", "category_ids"],
            ["PlacesFsqError", "category_labels", "category_labels"],
            ["PlacesFsqError", "category_list_length", "category_list_length"],
        ],
        "row": "fsq:23",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/parse.py:_row",
        "plants": [
            ["PlacesFsqError", "country", "country"],
            ["PlacesFsqError", "fsq_place_id", "fsq_place_id"],
            ["PlacesFsqError", "name", "name"],
        ],
        "row": "fsq:24",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/assemble.py:_table_row",
        "plants": [
            ["PlacesFsqError", "cell", "cell"],
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "fsq_unexpected_frameerror",
            ],
        ],
        "row": "fsq:25",
        "stage": "fsq",
    },
    {
        "anchor": "places_fsq/names.py:check_labels; assemble.py:build_places",
        "plants": [
            ["PlacesFsqError", "edit_distance", "edit_distance"],
            ["PlacesFsqError", "name_collision", "name_collision"],
        ],
        "row": "fsq:26",
        "stage": "fsq",
    },
    {
        "anchor": "assembly_adapters.py:Production.fsq, read_places; policy.py; parse.py",
        "plants": [
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "fsq_unexpected_jsondecodeerror",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "fsq_unexpected_keyerror",
            ],
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "fsq_unexpected_valueerror",
            ],
            [
                "DuckDBError",
                "SYN opaque fault /syn/no-output 999999999",
                "fsq_unexpected_duckdberror",
            ],
            [
                "FileNotFoundError",
                "SYN opaque fault /syn/no-output 999999999",
                "fsq_unexpected_filenotfounderror",
            ],
            [
                "YAMLError",
                "SYN opaque fault /syn/no-output 999999999",
                "fsq_unexpected_yamlerror",
            ],
        ],
        "row": "fsq:27",
        "stage": "fsq",
    },
    {
        "anchor": "assembly_adapters.py:Production.series_stage",
        "plants": [
            [
                "AssemblyError",
                "assembly_regression_refused",
                "assembly_regression_refused",
            ]
        ],
        "row": "series_stage:01",
        "stage": "series_stage",
    },
    {
        "anchor": "series/frame.py:frame_municipalities, parse_frame_municipalities",
        "plants": [
            [
                "MunicipalityFrameRefused",
                "municipality_code_repeated",
                "municipality_code_repeated",
            ],
            [
                "MunicipalityFrameRefused",
                "municipality_count_mismatch",
                "municipality_count_mismatch",
            ],
            [
                "MunicipalityFrameRefused",
                "municipality_field_empty",
                "municipality_field_empty",
            ],
            [
                "MunicipalityFrameRefused",
                "municipality_frame_absent",
                "municipality_frame_absent",
            ],
            [
                "MunicipalityFrameRefused",
                "municipality_name_repeated",
                "municipality_name_repeated",
            ],
        ],
        "row": "series_stage:02",
        "stage": "series_stage",
    },
    {
        "anchor": "series/parse.py:municipality_names, _bind",
        "plants": [
            [
                "SeriesRefused",
                "municipality_names_refused",
                "municipality_names_refused",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_keyerror",
            ],
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_frameerror",
            ],
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_oserror",
            ],
        ],
        "row": "series_stage:03",
        "stage": "series_stage",
    },
    {
        "anchor": "series/figures.py:build_series",
        "plants": [
            [
                "SeriesRefused",
                "unmapped_municipality_spelling",
                "unmapped_municipality_spelling",
            ]
        ],
        "row": "series_stage:04",
        "stage": "series_stage",
    },
    {
        "anchor": "series/figures.py:build_series, finish_build, _refused",
        "plants": [
            [
                "SeriesRefused",
                "municipality_frame_not_supplied",
                "municipality_frame_not_supplied",
            ],
            ["SeriesRefused", "selected_input_refused", "selected_input_refused"],
        ],
        "row": "series_stage:05",
        "stage": "series_stage",
    },
    {
        "anchor": "series/figures.py:build_series",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            [
                "ValueError",
                "selected sources must exactly match owned entries",
                "selected_sources_must_exactly_match_owned_entries",
            ],
        ],
        "row": "series_stage:06",
        "stage": "series_stage",
    },
    {
        "anchor": "assembly_adapters.py:Production.series_stage",
        "plants": [
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_keyerror",
            ]
        ],
        "row": "series_stage:07",
        "stage": "series_stage",
    },
    {
        "anchor": "series/parse.py:selected_body, selected_source",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            ["ValueError", "invalid selected hash", "invalid_selected_hash"],
            ["ValueError", "selected receipt mismatch", "selected_receipt_mismatch"],
            ["ValueError", "incomplete receipt", "incomplete_receipt"],
            ["ValueError", "source must contain rows", "source_must_contain_rows"],
        ],
        "row": "series_stage:08",
        "stage": "series_stage",
    },
    {
        "anchor": "fetch/snapshots.py:read_snapshot (via selected_body and Production.series_stage)",
        "plants": [
            ["SnapshotError", "snapshot_date_missing", "snapshot_date_missing"],
            ["SnapshotError", "snapshot_hash_mismatch", "snapshot_hash_mismatch"],
            ["SnapshotError", "snapshot_missing", "snapshot_missing"],
            ["SnapshotError", "snapshot_index_invalid", "snapshot_index_invalid"],
            ["SnapshotError", "snapshot_path_invalid", "snapshot_path_invalid"],
        ],
        "row": "series_stage:09",
        "stage": "series_stage",
    },
    {
        "anchor": "series/parse.py:confirmed_rows",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            ["ValueError", "SYN registry fields: ...", "registry_fields"],
            ["ValueError", "SYN source fields: ...", "source_fields"],
            ["ValueError", "SYN field type: SYN", "field_type"],
        ],
        "row": "series_stage:10",
        "stage": "series_stage",
    },
    {
        "anchor": "series/parse.py:source_period, customs_code; series/figures.py:contract_rows",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            [
                "ValueError",
                "SYN year: four digits required",
                "year_four_digits_required",
            ],
            [
                "ValueError",
                "SYN missing confirmed contract fields",
                "missing_confirmed_contract_fields",
            ],
        ],
        "row": "series_stage:11",
        "stage": "series_stage",
    },
    {
        "anchor": "series/parse.py:country_crosswalk",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            [
                "ValueError",
                "country alias: invalid unattributed reason",
                "country_alias_invalid_unattributed_reason",
            ],
            [
                "ValueError",
                "country alias: absent reference code",
                "country_alias_absent_reference_code",
            ],
            [
                "ValueError",
                "country alias: repeated country name",
                "country_alias_repeated_country_name",
            ],
        ],
        "row": "series_stage:12",
        "stage": "series_stage",
    },
    {
        "anchor": "series/figures.py:build_series",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            ["ValueError", "SYN country_unmatched: [...]", "country_unmatched"],
        ],
        "row": "series_stage:13",
        "stage": "series_stage",
    },
    {
        "anchor": "series/baskets.py:reviewed_inputs, _validate_review, validate_source_review, tariff_digits; series/figures.py:basket_exclusion_review",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_jsondecodeerror",
            ],
            ["ValueError", "missing activities", "missing_activities"],
            ["ValueError", "wrong playbook activities", "wrong_playbook_activities"],
            [
                "ValueError",
                "basket exceeds eight inputs",
                "basket_exceeds_eight_inputs",
            ],
            ["ValueError", "incomplete review fields", "incomplete_review_fields"],
            ["ValueError", "missing review metadata", "missing_review_metadata"],
            ["ValueError", "review source hash missing", "review_source_hash_missing"],
            ["ValueError", "review lines missing", "review_lines_missing"],
            [
                "ValueError",
                "review needs bilingual descriptions",
                "review_needs_bilingual_descriptions",
            ],
            [
                "ValueError",
                "review exclusion reason missing",
                "review_exclusion_reason_missing",
            ],
            ["ValueError", "tariff code must be dotted", "tariff_code_must_be_dotted"],
            ["ValueError", "coarse tariff line", "coarse_tariff_line"],
            ["ValueError", "basket_line_duplicate: ...", "basket_line_duplicate"],
            [
                "ValueError",
                "basket_line_source_mismatch: ...",
                "basket_line_source_mismatch",
            ],
        ],
        "row": "series_stage:14",
        "stage": "series_stage",
    },
    {
        "anchor": "series/figures.py:validate_figure, _envelope; assembly_adapters.py:Production.series_stage",
        "plants": [
            ["ValueError", "source_chain", "source_chain"],
            ["ValueError", "missing method", "missing"],
            ["ValueError", "missing method_version", "missing"],
            ["ValueError", "missing source_chain", "missing_source_chain"],
            ["ValueError", "incomplete source_chain", "incomplete_source_chain"],
            ["ValueError", "invalid source_chain hash", "invalid_source_chain_hash"],
            [
                "ValueError",
                "missing source_chain release_tables",
                "missing_source_chain_release_tables",
            ],
            [
                "ValueError",
                "missing source_chain field_mapping",
                "missing_source_chain_field_mapping",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_keyerror",
            ],
        ],
        "row": "series_stage:15",
        "stage": "series_stage",
    },
    {
        "anchor": "series/figures.py:_groups, build_series; series/reconcile.py:wage_evidence",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            ["ValueError", "SYN duplicate wage group", "duplicate_wage_group"],
            [
                "ValueError",
                "wrong wage table identities",
                "wrong_wage_table_identities",
            ],
            ["ValueError", "incomplete shared years", "incomplete_shared_years"],
            [
                "InvalidOperation",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_invalidoperation",
            ],
        ],
        "row": "series_stage:16",
        "stage": "series_stage",
    },
    {
        "anchor": "series/figures.py:build_series, compute_checks; series/support.py:load_support",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_oserror",
            ],
            [
                "SpineError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_spineerror",
            ],
            [
                "ValueError",
                "supporting provenance selections required",
                "supporting_provenance_selections_required",
            ],
            [
                "ValueError",
                "supporting provenance registry identity",
                "supporting_provenance_registry_identity",
            ],
            [
                "ValueError",
                "invalid supporting provenance dataset",
                "invalid_supporting_provenance_dataset",
            ],
            [
                "ValueError",
                "supporting provenance has no ISIC classes",
                "supporting_provenance_has_no_isic_classes",
            ],
            [
                "ValueError",
                "supporting provenance frame inputs differ",
                "supporting_provenance_frame_inputs_differ",
            ],
            [
                "ValueError",
                "supporting provenance frame differs",
                "supporting_provenance_frame_differs",
            ],
            [
                "ValueError",
                "invalid supporting provenance",
                "invalid_supporting_provenance",
            ],
            ["ValueError", "duplicate utility period", "duplicate_utility_period"],
            [
                "ValueError",
                "zero change has no mix share",
                "zero_change_has_no_mix_share",
            ],
            [
                "ValueError",
                "lic_cancelled period outside the C2 calendar: ...",
                "lic_cancelled_period_outside_the_c2_calendar",
            ],
            ["ValueError", "duplicate transit period", "duplicate_transit_period"],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_keyerror",
            ],
        ],
        "row": "series_stage:17",
        "stage": "series_stage",
    },
    {
        "anchor": "series/figures.py:build_series, compute_checks",
        "plants": [
            [
                "ZeroDivisionError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_zerodivisionerror",
            ],
            [
                "InvalidOperation",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_invalidoperation",
            ],
            [
                "TypeError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_typeerror",
            ],
        ],
        "row": "series_stage:18",
        "stage": "series_stage",
    },
    {
        "anchor": "stage.py:_local_expected",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "series_stage_unexpected_valueerror",
            ]
        ],
        "row": "series_stage:19",
        "stage": "series_stage",
    },
    {
        "anchor": "assembly_adapters.py:Production.series_stage, Production.table",
        "plants": [
            ["AssemblyError", "assembly_lineage_missing", "assembly_lineage_missing"]
        ],
        "row": "series_stage:20",
        "stage": "series_stage",
    },
    {
        "anchor": "assembly_io.py:read_object",
        "plants": [
            ["AssemblyError", "assembly_input_refused", "assembly_input_refused"]
        ],
        "row": "series_stage:21",
        "stage": "series_stage",
    },
    {
        "anchor": "assembly_adapters.py:Production.table",
        "plants": [
            ["AssemblyError", "assembly_table_duplicate", "assembly_table_duplicate"]
        ],
        "row": "series_stage:22",
        "stage": "series_stage",
    },
    {
        "anchor": "assembly_io.py:local; assembly.py:run_steps",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"],
            ["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"],
        ],
        "row": "series_stage:23",
        "stage": "series_stage",
    },
    {
        "anchor": "assembly_io.py:local via Production.heights",
        "plants": [["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"]],
        "row": "heights:01",
        "stage": "heights",
    },
    {
        "anchor": "heights/step.py:build_heights",
        "plants": [["HeightError", "building_table_absent", "building_table_absent"]],
        "row": "heights:02",
        "stage": "heights",
    },
    {
        "anchor": "building_inputs.py:verify_building_manifest",
        "plants": [
            ["HeightError", "building_manifest_absent", "building_manifest_absent"]
        ],
        "row": "heights:03",
        "stage": "heights",
    },
    {
        "anchor": "building_inputs.py:verify_building_manifest",
        "plants": [
            ["HeightError", "building_manifest_method", "building_manifest_method"]
        ],
        "row": "heights:04",
        "stage": "heights",
    },
    {
        "anchor": "building_inputs.py:verify_building_manifest",
        "plants": [["HeightError", "building_table_hash", "building_table_hash"]],
        "row": "heights:05",
        "stage": "heights",
    },
    {
        "anchor": "building_inputs.py:verify_building_manifest",
        "plants": [
            ["HeightError", "building_manifest_coverage", "building_manifest_coverage"]
        ],
        "row": "heights:06",
        "stage": "heights",
    },
    {
        "anchor": "building_inputs.py:verify_building_manifest, pinned",
        "plants": [
            ["HeightError", "building_manifest_inputs", "building_manifest_inputs"],
            [
                "BuildingError",
                "building_part_receipt_mismatch",
                "building_part_receipt_mismatch",
            ],
            ["BuildingError", "building_part_skipped", "building_part_skipped"],
            ["BuildingError", "building_part_unpinned", "building_part_unpinned"],
            ["BuildingError", "building_part_unreceipted", "building_part_unreceipted"],
            [
                "BuildingError",
                "building_part_unregistered",
                "building_part_unregistered",
            ],
        ],
        "row": "heights:07",
        "stage": "heights",
    },
    {
        "anchor": "building_inputs.py:verify_building_manifest",
        "plants": [
            ["HeightError", "building_manifest_boundary", "building_manifest_boundary"]
        ],
        "row": "heights:08",
        "stage": "heights",
    },
    {
        "anchor": "building_inputs.py:verify_building_manifest",
        "plants": [["HeightError", "building_manifest_pins", "building_manifest_pins"]],
        "row": "heights:09",
        "stage": "heights",
    },
    {
        "anchor": "heights/model.py:load_rules, _structure, _require_text",
        "plants": [
            ["HeightError", "rules_class_field", "rules_class_field"],
            ["HeightError", "rules_field_or_band", "rules_field_or_band"],
            ["HeightError", "rules_label", "rules_label"],
            ["HeightError", "rules_missing_key", "rules_missing_key"],
            ["HeightError", "rules_nodata", "rules_nodata"],
            ["HeightError", "rules_root", "rules_root"],
            ["HeightError", "rules_source", "rules_source"],
            ["HeightError", "rules_sources", "rules_sources"],
            ["HeightError", "rules_storey", "rules_storey"],
            ["HeightError", "rules_storey_value", "rules_storey_value"],
            ["HeightError", "rules_unknown_key", "rules_unknown_key"],
        ],
        "row": "heights:10",
        "stage": "heights",
    },
    {
        "anchor": "heights/landmarks.py:load_landmark_heights, _registry_entry, verify_landmark_receipts",
        "plants": [
            ["HeightError", "landmark_heights", "landmark_heights"],
            ["HeightError", "landmark_heights_citation", "landmark_heights_citation"],
            ["HeightError", "landmark_heights_duplicate", "landmark_heights_duplicate"],
            ["HeightError", "landmark_heights_entry", "landmark_heights_entry"],
            ["HeightError", "landmark_heights_height", "landmark_heights_height"],
        ],
        "row": "heights:11",
        "stage": "heights",
    },
    {
        "anchor": "heights/landmarks.py:apply_landmark_heights",
        "plants": [
            ["HeightError", "landmark_building_absent", "landmark_building_absent"],
            ["HeightError", "landmark_height_conflict", "landmark_height_conflict"],
        ],
        "row": "heights:12",
        "stage": "heights",
    },
    {
        "anchor": "heights/model.py:load_buildings, _number, _footprint",
        "plants": [
            ["HeightError", "bad_floor_count", "bad_floor_count"],
            ["HeightError", "bad_footprint", "bad_footprint"],
            ["HeightError", "bad_recorded_height_m", "bad_recorded_height_m"],
            ["HeightError", "building_id", "building_id"],
            ["HeightError", "building_table", "building_table"],
            ["HeightError", "extra_property", "extra_property"],
            ["HeightError", "footprint_source_id", "footprint_source_id"],
            ["HeightError", "missing_property", "missing_property"],
            ["HeightError", "repeated_id", "repeated_id"],
        ],
        "row": "heights:13",
        "stage": "heights",
    },
    {
        "anchor": "heights/read.py:_verified_body",
        "plants": [
            ["HeightError", "snapshot_selection_invalid", "snapshot_selection_invalid"]
        ],
        "row": "heights:14",
        "stage": "heights",
    },
    {
        "anchor": "heights/read.py:_verified_body",
        "plants": [
            ["HeightError", "selected_input_refused", "selected_input_refused"],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "heights_unexpected_oserror",
            ],
            [
                "SnapshotError",
                "SYN opaque fault /syn/no-output 999999999",
                "heights_unexpected_snapshoterror",
            ],
        ],
        "row": "heights:15",
        "stage": "heights",
    },
    {
        "anchor": "heights/read.py:_verified_body",
        "plants": [
            ["HeightError", "cache_receipt", "cache_receipt"],
            ["HeightError", "cache_receipt_mismatch", "cache_receipt_mismatch"],
            ["HeightError", "cache_receipt_missing", "cache_receipt_missing"],
            ["HeightError", "malformed_hash", "malformed_hash"],
            ["HeightError", "switched_off", "switched_off"],
        ],
        "row": "heights:16",
        "stage": "heights",
    },
    {
        "anchor": "heights/read.py:_declared_check",
        "plants": [
            ["HeightError", "declared_reference_system", "declared_reference_system"],
            ["HeightError", "declared_unit", "declared_unit"],
        ],
        "row": "heights:17",
        "stage": "heights",
    },
    {
        "anchor": "heights/read.py:_parse_globfp, _zip_members, _dbf_heights, _dbf_text_field, _parse_wsf, _local_file",
        "plants": [
            ["HeightError", "cache_path", "cache_path"],
            ["HeightError", "height_value", "height_value"],
            ["HeightError", "raster_window", "raster_window"],
            ["HeightError", "reference_system", "reference_system"],
            ["HeightError", "structure_mismatch", "structure_mismatch"],
        ],
        "row": "heights:18",
        "stage": "heights",
    },
    {
        "anchor": "heights/match.py:wsf3d_height",
        "plants": [["HeightError", "wsf3d_overlap", "wsf3d_overlap"]],
        "row": "heights:19",
        "stage": "heights",
    },
    {
        "anchor": "heights/step.py:_resolve",
        "plants": [["HeightError", "bad_floor_count", "bad_floor_count"]],
        "row": "heights:20",
        "stage": "heights",
    },
    {
        "anchor": "heights/manifest.py:check_row",
        "plants": [
            ["HeightError", "output_columns", "output_columns"],
            ["HeightError", "output_none", "output_none"],
            ["HeightError", "output_row", "output_row"],
            ["HeightError", "output_source", "output_source"],
        ],
        "row": "heights:21",
        "stage": "heights",
    },
    {
        "anchor": "core/src/eii_core/calc/building_heights.py (choose_height, height_counts, fallback_errors, floor_height)",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "heights_unexpected_valueerror",
            ],
            [
                "ValueError",
                "candidate outside the closed order",
                "candidate_outside_the_closed_order",
            ],
            [
                "ValueError",
                "match list length differs from the choices",
                "match_list_length_differs_from_the_choices",
            ],
        ],
        "row": "heights:22",
        "stage": "heights",
    },
    {
        "anchor": "assembly_adapters.py:Production.heights",
        "plants": [
            [
                "AssemblyError",
                "assembly_heights_incomplete",
                "assembly_heights_incomplete",
            ]
        ],
        "row": "heights:23",
        "stage": "heights",
    },
    {
        "anchor": "assembly.py:run_steps; assembly_io.py:write_record",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"],
            ["AssemblyError", "assembly_value_invalid", "assembly_value_invalid"],
        ],
        "row": "heights:24",
        "stage": "heights",
    },
    {
        "anchor": "trade_reconciliation.py:load_selection",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_valueerror",
            ],
            [
                "ValueError",
                "trade_reconciliation selection_unreadable",
                "trade_reconciliation_selection_unreadable",
            ],
            [
                "TypeError",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_typeerror",
            ],
        ],
        "row": "trade_reconciliation:01",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "trade_reconciliation.py:Selection.from_mapping",
        "plants": [
            ["ValueError", "binding", "binding"],
            ["ValueError", "cause_evidence", "cause_evidence"],
            ["ValueError", "cause_schema", "cause_schema"],
            ["ValueError", "deferred_input_schema", "deferred_input_schema"],
            ["ValueError", "duplicate_binding", "duplicate_binding"],
            ["ValueError", "missing_input_evidence", "missing_input_evidence"],
            ["ValueError", "obstacle_evidence", "obstacle_evidence"],
            ["ValueError", "obstacle_schema", "obstacle_schema"],
            ["ValueError", "pending_input_evidence", "pending_input_evidence"],
            ["ValueError", "price_evidence", "price_evidence"],
            ["ValueError", "selection_flow", "selection_flow"],
            ["ValueError", "selection_inputs", "selection_inputs"],
            ["ValueError", "selection_pending", "selection_pending"],
            ["ValueError", "selection_schema", "selection_schema"],
            ["ValueError", "selection_scope", "selection_scope"],
            ["ValueError", "selection_year", "selection_year"],
            ["ValueError", "unavailable_input_binding", "unavailable_input_binding"],
        ],
        "row": "trade_reconciliation:02",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "trade_reconciliation.py:_materialize, owner_report",
        "plants": [["ValueError", "owner_report", "owner_report"]],
        "row": "trade_reconciliation:03",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "trade_reconciliation.py:read_comtrade, read_baci, read_portal, _materialize",
        "plants": [
            ["ValueError", "comtrade_policy_required", "comtrade_policy_required"],
            ["ValueError", "selection", "selection"],
        ],
        "row": "trade_reconciliation:04",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "series/parse.py:selected_body, selected_source, confirmed_rows; fetch/snapshots.py:read_snapshot; trade_reconciliation.py:read_portal",
        "plants": [
            ["ValueError", "source_id", "source_id"],
            ["ValueError", "invalid selected hash", "invalid_selected_hash"],
            ["ValueError", "selected receipt mismatch", "selected_receipt_mismatch"],
            ["ValueError", "incomplete receipt", "incomplete_receipt"],
            ["ValueError", "source must contain rows", "source_must_contain_rows"],
            ["ValueError", "SYN registry fields: ...", "registry_fields"],
            ["ValueError", "SYN source fields: ...", "source_fields"],
            ["ValueError", "SYN field type: SYN", "field_type"],
            [
                "StopIteration",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_stopiteration",
            ],
            ["SnapshotError", "snapshot_date_missing", "snapshot_date_missing"],
            ["SnapshotError", "snapshot_hash_mismatch", "snapshot_hash_mismatch"],
            ["SnapshotError", "snapshot_index_invalid", "snapshot_index_invalid"],
            ["SnapshotError", "snapshot_missing", "snapshot_missing"],
            ["SnapshotError", "snapshot_path_invalid", "snapshot_path_invalid"],
        ],
        "row": "trade_reconciliation:05",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "series/parse.py:country_crosswalk",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_valueerror",
            ],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_oserror",
            ],
        ],
        "row": "trade_reconciliation:06",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "series/parse.py:municipality_names (from series/figures.py:contract_rows)",
        "plants": [
            [
                "SeriesRefused",
                "municipality_names_refused",
                "municipality_names_refused",
            ]
        ],
        "row": "trade_reconciliation:07",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "baci/contracts.py:read_selected",
        "plants": [
            ["BaciError", "archive_hash", "archive_hash"],
            ["BaciError", "lineage", "lineage"],
            ["BaciError", "manifest_complete", "manifest_complete"],
            ["BaciError", "manifest_configuration", "manifest_configuration"],
            ["BaciError", "manifest_hash", "manifest_hash"],
            ["BaciError", "retrieval_date", "retrieval_date"],
            ["BaciError", "selected_manifest", "selected_manifest"],
            ["BaciError", "terms_fingerprint", "terms_fingerprint"],
        ],
        "row": "trade_reconciliation:08",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "comtrade/assemble.py:assemble, verify_child",
        "plants": [
            ["SafeRefusal", "child_hash", "child_hash"],
            ["SafeRefusal", "child_missing", "child_missing"],
            ["SafeRefusal", "coverage_gap", "coverage_gap"],
            ["SafeRefusal", "duplicate_child", "duplicate_child"],
            ["SafeRefusal", "lineage_missing", "lineage_missing"],
            ["SafeRefusal", "manifest_hash", "manifest_hash"],
            ["SafeRefusal", "manifest_incomplete", "manifest_incomplete"],
            ["SafeRefusal", "manifest_missing", "manifest_missing"],
            ["SafeRefusal", "manifest_unreadable", "manifest_unreadable"],
            ["SafeRefusal", "parser_identity", "parser_identity"],
            ["SafeRefusal", "policy_changed", "policy_changed"],
            ["SafeRefusal", "receipt_count", "receipt_count"],
            ["SafeRefusal", "receipt_hash", "receipt_hash"],
            ["SafeRefusal", "receipt_missing", "receipt_missing"],
            ["SafeRefusal", "selection_changed", "selection_changed"],
            [
                "ParseError",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_parseerror",
            ],
        ],
        "row": "trade_reconciliation:09",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "trade_reconciliation.py:_materialize",
        "plants": [
            ["ValueError", "binding_classification", "binding_classification"],
            ["ValueError", "binding_country_dictionary", "binding_country_dictionary"],
            ["ValueError", "binding_currency", "binding_currency"],
            ["ValueError", "binding_direction", "binding_direction"],
            ["ValueError", "binding_period", "binding_period"],
            ["ValueError", "binding_product", "binding_product"],
            ["ValueError", "binding_revision", "binding_revision"],
            ["ValueError", "input_receipt", "input_receipt"],
            ["ValueError", "native_row_binding_missing", "native_row_binding_missing"],
            ["ValueError", "unused_binding", "unused_binding"],
            [
                "DecimalRefusal",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_decimalrefusal",
            ],
        ],
        "row": "trade_reconciliation:10",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "core eii_core.calc.trade_reconciliation",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_valueerror",
            ]
        ],
        "row": "trade_reconciliation:11",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "trade_reconciliation.py:build_reconciliation",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_valueerror",
            ],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_oserror",
            ],
            ["ValueError", "trade_reconciliation SYN", "trade_reconciliation"],
        ],
        "row": "trade_reconciliation:12",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "assembly_adapters.py:Production.trade_reconciliation; assembly_io.py:read_object, bound_files",
        "plants": [
            ["AssemblyError", "assembly_input_refused", "assembly_input_refused"],
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"],
            ["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "trade_reconciliation_unexpected_keyerror",
            ],
        ],
        "row": "trade_reconciliation:13",
        "stage": "trade_reconciliation",
    },
    {
        "anchor": "busyness/build.py:build_busyness",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_valueerror",
            ],
            [
                "ValueError",
                "busy_besttime registry mismatch",
                "busy_besttime_registry_mismatch",
            ],
        ],
        "row": "busyness:01",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/review.py:load_venues, _rows, _date",
        "plants": [
            [
                "ReviewError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_reviewerror",
            ],
            [
                "ReviewError",
                "busy_besttime_venues.csv schema: wrong columns",
                "schema_wrong_columns",
            ],
        ],
        "row": "busyness:02",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/review.py:load_requests",
        "plants": [
            [
                "ReviewError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_reviewerror",
            ],
            [
                "ReviewError",
                "busy_besttime_requests.yaml schema: unreadable",
                "schema_unreadable",
            ],
        ],
        "row": "busyness:03",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/review.py:load_crosswalk",
        "plants": [
            [
                "ReviewError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_reviewerror",
            ],
            [
                "ReviewError",
                "venue_busyness_crosswalk.csv match: expected matched or no_match",
                "match_expected_matched_or_no_match",
            ],
        ],
        "row": "busyness:04",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/policy.py:run_limit",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_valueerror",
            ],
            [
                "ValueError",
                "EII_BESTTIME_RUN_CREDIT_LIMIT: expected positive whole number",
                "expected_positive_whole_number",
            ],
        ],
        "row": "busyness:05",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/build.py:build_busyness",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_valueerror",
            ],
            ["ValueError", "BESTTIME_API_KEY_PRIVATE: required", "required"],
            ["ValueError", "BESTTIME_API_KEY_PUBLIC: required", "required"],
        ],
        "row": "busyness:06",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/build.py:_inputs",
        "plants": [
            [
                "BuildInputError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_buildinputerror",
            ],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_oserror",
            ],
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_jsondecodeerror",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_keyerror",
            ],
            ["BuildInputError", "pub_place missing SYN", "pub_place_missing"],
            ["BuildInputError", "crosswalk missing SYN", "crosswalk_missing"],
            ["BuildInputError", "pub_place name missing SYN", "pub_place_missing"],
        ],
        "row": "busyness:07",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/address.py:read_addresses; places/integrate.py:_opened_place; places/read.py:require_receipt",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_valueerror",
            ],
            ["AreaError", "places_file_digest", "places_file_digest"],
            ["AreaError", "places_file_unreceipted", "places_file_unreceipted"],
            [
                "DuckDBError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_duckdberror",
            ],
            ["PlacesError", "places_file_unreceipted", "places_file_unreceipted"],
            ["PlacesError", "receipt_mismatch", "receipt_mismatch"],
            ["PlacesError", "receipt_missing", "receipt_missing"],
        ],
        "row": "busyness:08",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/build.py:_request",
        "plants": [
            ["ValueError", "blocked_host", "blocked_host"],
            [
                "ValueError",
                "busy_besttime https://syn.invalid/opaque request_failed",
                "busy_besttime_request_failed",
            ],
            ["ValueError", "... /forecasts/week/raw request_failed", "request_failed"],
        ],
        "row": "busyness:09",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/parse.py:parse_forecast, parse_query",
        "plants": [
            [
                "ShapeError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_shapeerror",
            ],
            [
                "ShapeError",
                "busy_besttime SYN changed_shape",
                "busy_besttime_changed_shape",
            ],
        ],
        "row": "busyness:10",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/policy.py:CreditBudget",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_valueerror",
            ],
            [
                "ValueError",
                "credit limit: expected positive integer",
                "credit_limit_expected_positive_integer",
            ],
            [
                "ValueError",
                "request cost: expected positive integer",
                "request_cost_expected_positive_integer",
            ],
            ["ValueError", "unknown request kind", "unknown_request_kind"],
            ["ValueError", "duplicate request", "duplicate_request"],
            ["ValueError", "query before forecast", "query_before_forecast"],
        ],
        "row": "busyness:11",
        "stage": "busyness",
    },
    {
        "anchor": "busyness/security.py:assert_clean (from build_busyness and Production.busyness)",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_valueerror",
            ],
            [
                "ValueError",
                "busy_besttime https://syn.invalid/opaque secret_in_output",
                "secret_in_output",
            ],
        ],
        "row": "busyness:12",
        "stage": "busyness",
    },
    {
        "anchor": "fetch/receipts.py:commit_pair; fetch/snapshots.py:publish_snapshot, _publish_file; busyness/build.py:build_busyness",
        "plants": [
            ["SnapshotError", "snapshot_date_missing", "snapshot_date_missing"],
            ["SnapshotError", "snapshot_hash_mismatch", "snapshot_hash_mismatch"],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_oserror",
            ],
            ["SnapshotError", "snapshot_conflict", "snapshot_conflict"],
            ["SnapshotError", "snapshot_index_invalid", "snapshot_index_invalid"],
            ["SnapshotError", "snapshot_path_invalid", "snapshot_path_invalid"],
            ["SnapshotError", "snapshot_write_failed", "snapshot_write_failed"],
            [
                "SnapshotError",
                "busy_besttime: snapshot_write_failed",
                "snapshot_write_failed",
            ],
        ],
        "row": "busyness:13",
        "stage": "busyness",
    },
    {
        "anchor": "assembly_adapters.py:Production.busyness, Production.table; assembly_io.py:local, read_object",
        "plants": [
            ["AssemblyError", "assembly_input_refused", "assembly_input_refused"],
            ["AssemblyError", "assembly_lineage_missing", "assembly_lineage_missing"],
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"],
            ["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"],
            ["AssemblyError", "assembly_table_duplicate", "assembly_table_duplicate"],
            [
                "JSONDecodeError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_jsondecodeerror",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_keyerror",
            ],
            [
                "SnapshotError",
                "SYN opaque fault /syn/no-output 999999999",
                "busyness_unexpected_snapshoterror",
            ],
        ],
        "row": "busyness:14",
        "stage": "busyness",
    },
    {
        "anchor": "assembly_adapters.py:Production.run",
        "plants": [["AssemblyError", "figure_seed_invalid", "figure_seed_invalid"]],
        "row": "require_complete:01",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly_inventory.py:validate_inventory",
        "plants": [
            [
                "AssemblyError",
                "assembly_inventory_invalid",
                "assembly_inventory_invalid",
            ]
        ],
        "row": "require_complete:02",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly_adapters.py:Production.run",
        "plants": [
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "require_complete_unexpected_oserror",
            ]
        ],
        "row": "require_complete:03",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly.py:run_steps",
        "plants": [
            ["AssemblyError", "assembly_order_invalid", "assembly_order_invalid"]
        ],
        "row": "require_complete:04",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly.py:_output_path; assembly.py:run_steps",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"]
        ],
        "row": "require_complete:05",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly.py:run_steps",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "require_complete_unexpected_oserror",
            ],
        ],
        "row": "require_complete:06",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly_io.py:local",
        "plants": [["AssemblyError", "assembly_path_invalid", "assembly_path_invalid"]],
        "row": "require_complete:07",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly_adapters.py:Production.record",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"]
        ],
        "row": "require_complete:08",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly_io.py:json_value (via write_record)",
        "plants": [
            ["AssemblyError", "assembly_value_invalid", "assembly_value_invalid"]
        ],
        "row": "require_complete:09",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly_io.py:write_record",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "require_complete_unexpected_valueerror",
            ]
        ],
        "row": "require_complete:10",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly_adapters.py:Production.table",
        "plants": [
            ["AssemblyError", "assembly_table_duplicate", "assembly_table_duplicate"]
        ],
        "row": "require_complete:11",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly_adapters.py:Production.table",
        "plants": [
            ["AssemblyError", "assembly_lineage_missing", "assembly_lineage_missing"]
        ],
        "row": "require_complete:12",
        "stage": "require_complete",
    },
    {
        "anchor": "assembly_io.py:bound_files",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_oserror",
            ],
        ],
        "row": "final_audit:01",
        "stage": "final_audit",
    },
    {
        "anchor": "completeness.py:pack_sources",
        "plants": [["ValueError", "pack_section_missing", "pack_section_missing"]],
        "row": "final_audit:02",
        "stage": "final_audit",
    },
    {
        "anchor": "completeness.py:pack_sources",
        "plants": [
            ["ValueError", "pack_family_row_truncated", "pack_family_row_truncated"]
        ],
        "row": "final_audit:03",
        "stage": "final_audit",
    },
    {
        "anchor": "completeness.py:pack_sources",
        "plants": [["ValueError", "pack_source_duplicate", "pack_source_duplicate"]],
        "row": "final_audit:04",
        "stage": "final_audit",
    },
    {
        "anchor": "completeness.py:section",
        "plants": [
            ["ValueError", "pack_section_missing", "pack_section_missing"],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_oserror",
            ],
        ],
        "row": "final_audit:05",
        "stage": "final_audit",
    },
    {
        "anchor": "confirm_s2_t13.py:load_confirmation; assembly_reports.py:gather_audit",
        "plants": [
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_oserror",
            ],
            [
                "ValueError",
                "confirmation block is not an object",
                "confirmation_block_is_not_an_object",
            ],
            [
                "ValueError",
                "missing fields ['syn_missing']; unknown fields ['syn_unknown']",
                "missing_fields_unknown_fields",
            ],
            ["ValueError", "SYN is not text", "is_not_text"],
            ["ValueError", "SYN is not a boolean", "is_not_a_boolean"],
            [
                "ValueError",
                "invalid tender flags or tables",
                "invalid_tender_flags_or_tables",
            ],
            [
                "ValueError",
                "weight confirmation is not the current area-only choice",
                "weight_confirmation_is_not_the_current_area_only_choice",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_keyerror",
            ],
        ],
        "row": "final_audit:06",
        "stage": "final_audit",
    },
    {
        "anchor": "confirm_s2_t13.py:own_run_pending; assembly_reports.py:gather_audit",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_valueerror",
            ],
            [
                "ValueError",
                "unknown outcome or forbidden licence basis",
                "unknown_outcome_or_forbidden_licence_basis",
            ],
            ["ValueError", "terms_words missing", "terms_words_missing"],
            [
                "ValueError",
                "terms_read_on must be a real date",
                "terms_read_on_must_be_a_real_date",
            ],
            ["ValueError", "missing terms evidence", "missing_terms_evidence"],
        ],
        "row": "final_audit:07",
        "stage": "final_audit",
    },
    {
        "anchor": "fetch/registry.py:read_yaml",
        "plants": [
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_oserror",
            ],
            ["RegistryError", "malformed yaml", "malformed_yaml"],
        ],
        "row": "final_audit:08",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_adapters.py:Production.raw",
        "plants": [
            [
                "AssemblyError",
                "snapshot_selection_invalid",
                "snapshot_selection_invalid",
            ]
        ],
        "row": "final_audit:09",
        "stage": "final_audit",
    },
    {
        "anchor": "frame/build.py:read_cached",
        "plants": [
            [
                "FrameError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_frameerror",
            ],
            ["ValueError", "source_id", "source_id"],
            ["ValueError", "missing receipt SYN", "missing"],
        ],
        "row": "final_audit:10",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_reports.py:gather_audit; fetch/registry.py:read_yaml",
        "plants": [
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_oserror",
            ],
            ["RegistryError", "malformed yaml", "malformed_yaml"],
        ],
        "row": "final_audit:11",
        "stage": "final_audit",
    },
    {
        "anchor": "fetch/forecast_series.py:load_forecast_series; fetch/forecast_series.py:_series",
        "plants": [
            [
                "RegistryError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_registryerror",
            ],
            [
                "RegistryError",
                "forecast_series is not a list",
                "forecast_series_is_not_a_list",
            ],
            ["RegistryError", "duplicate forecast series", "duplicate_forecast_series"],
            [
                "RegistryError",
                "forecast series is not a map",
                "forecast_series_is_not_a_map",
            ],
            [
                "RegistryError",
                "unknown field in forecast series",
                "unknown_field_in_forecast_series",
            ],
            ["RegistryError", "unknown series: SYN", "unknown_series"],
            ["RegistryError", "unknown forecast state", "unknown_forecast_state"],
            [
                "RegistryError",
                "source keys outside closed series mapping",
                "source_keys_outside_closed_series_mapping",
            ],
        ],
        "row": "final_audit:12",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_reports.py:gather_audit",
        "plants": [
            [
                "AssemblyError",
                "assembly_confirmation_invalid",
                "assembly_confirmation_invalid",
            ]
        ],
        "row": "final_audit:13",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_reports.py:gather_audit",
        "plants": [
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_oserror",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_keyerror",
            ],
            ["RegistryError", "malformed yaml", "malformed_yaml"],
        ],
        "row": "final_audit:14",
        "stage": "final_audit",
    },
    {
        "anchor": "heights/model.py:load_rules",
        "plants": [
            ["HeightError", "rules_missing_key", "rules_missing_key"],
            ["HeightError", "rules_root", "rules_root"],
            ["HeightError", "rules_storey", "rules_storey"],
            ["HeightError", "rules_unknown_key", "rules_unknown_key"],
        ],
        "row": "final_audit:15",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_reports.py:gather_audit; assembly_io.py:bound_files",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"]
        ],
        "row": "final_audit:16",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_io.py:read_object",
        "plants": [
            ["AssemblyError", "assembly_input_refused", "assembly_input_refused"]
        ],
        "row": "final_audit:17",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_reports.py:gather_audit",
        "plants": [
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "final_audit_unexpected_oserror",
            ]
        ],
        "row": "final_audit:18",
        "stage": "final_audit",
    },
    {
        "anchor": "fetch/page_records.py:selected_page; fetch/snapshots.py:reviewed_selections; fetch/snapshots.py:read_snapshot",
        "plants": [
            ["PageError", "cache_path_refused", "cache_path_refused"],
            ["PageError", "receipt_missing", "receipt_missing"],
            ["PageError", "snapshot_date_missing", "snapshot_date_missing"],
            ["PageError", "snapshot_selection_invalid", "snapshot_selection_invalid"],
            [
                "AssemblyError",
                "snapshot_selection_invalid",
                "snapshot_selection_invalid",
            ],
            ["SnapshotError", "snapshot_date_missing", "snapshot_date_missing"],
            ["SnapshotError", "snapshot_index_invalid", "snapshot_index_invalid"],
            ["SnapshotError", "snapshot_path_invalid", "snapshot_path_invalid"],
            [
                "SnapshotError",
                "snapshot_selection_invalid",
                "snapshot_selection_invalid",
            ],
        ],
        "row": "final_audit:19",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_reports.py:gather_audit",
        "plants": [["AssemblyError", "assembly_t29_refused", "assembly_t29_refused"]],
        "row": "final_audit:20",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_reports.py:awards_evidence",
        "plants": [
            ["AssemblyError", "assembly_t29_refused", "assembly_t29_refused"],
            [
                "AwardError",
                "award_links_metadata_missing",
                "award_links_metadata_missing",
            ],
            ["AwardError", "award_seed_pending", "award_seed_pending"],
            ["AwardError", "schema_missing", "schema_missing"],
        ],
        "row": "final_audit:21",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_reports.py:own_words_confirmed",
        "plants": [
            [
                "AssemblyError",
                "assembly_terms_review_invalid",
                "assembly_terms_review_invalid",
            ]
        ],
        "row": "final_audit:22",
        "stage": "final_audit",
    },
    {
        "anchor": "gate_report.py:confirmations",
        "plants": [
            [
                "ValueError",
                "confirmation_task_duplicate",
                "confirmation_task_duplicate",
            ],
            ["ValueError", "confirmation_task_unknown", "confirmation_task_unknown"],
        ],
        "row": "final_audit:23",
        "stage": "final_audit",
    },
    {
        "anchor": "assembly_io.py:read_object",
        "plants": [
            ["AssemblyError", "assembly_input_refused", "assembly_input_refused"]
        ],
        "row": "draw:01",
        "stage": "draw",
    },
    {
        "anchor": "assembly_reports.py:draw_tables; assembly_reports.py:_draw_row_sources",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"]
        ],
        "row": "draw:02",
        "stage": "draw",
    },
    {
        "anchor": "assembly_reports.py:draw_tables",
        "plants": [
            [
                "AssemblyError",
                "assembly_draw_table_unindexed",
                "assembly_draw_table_unindexed",
            ]
        ],
        "row": "draw:03",
        "stage": "draw",
    },
    {
        "anchor": "assembly_reports.py:draw_tables",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"],
            ["AssemblyError", "assembly_table_duplicate", "assembly_table_duplicate"],
        ],
        "row": "draw:04",
        "stage": "draw",
    },
    {
        "anchor": "assembly_reports.py:draw_tables",
        "plants": [
            ["AssemblyError", "figure_table_unreachable", "figure_table_unreachable"]
        ],
        "row": "draw:05",
        "stage": "draw",
    },
    {
        "anchor": "assembly_reports.py:_draw_row_sources; draw_tables reader",
        "plants": [
            ["AssemblyError", "assembly_lineage_missing", "assembly_lineage_missing"]
        ],
        "row": "draw:06",
        "stage": "draw",
    },
    {
        "anchor": "assembly_reports.py:_draw_row_sources",
        "plants": [
            [
                "AssemblyError",
                "assembly_draw_lineage_ambiguous",
                "assembly_draw_lineage_ambiguous",
            ]
        ],
        "row": "draw:07",
        "stage": "draw",
    },
    {
        "anchor": "assembly_reports.py:_draw_row_sources; draw_tables reader",
        "plants": [
            [
                "AttributeError",
                "SYN opaque fault /syn/no-output 999999999",
                "draw_unexpected_attributeerror",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "draw_unexpected_keyerror",
            ],
        ],
        "row": "draw:08",
        "stage": "draw",
    },
    {
        "anchor": "assembly_reports.py:draw_tables reader",
        "plants": [
            [
                "AssemblyError",
                "assembly_draw_field_unknown",
                "assembly_draw_field_unknown",
            ]
        ],
        "row": "draw:09",
        "stage": "draw",
    },
    {
        "anchor": "assembly_reports.py:draw_tables reader",
        "plants": [
            [
                "AssemblyError",
                "assembly_draw_value_invalid",
                "assembly_draw_value_invalid",
            ]
        ],
        "row": "draw:10",
        "stage": "draw",
    },
    {
        "anchor": "draw.py:draw",
        "plants": [["ValueError", "figure_log_invalid", "figure_log_invalid"]],
        "row": "draw:11",
        "stage": "draw",
    },
    {
        "anchor": "draw.py:draw; draw.py:sample",
        "plants": [["ValueError", "figure_seed_invalid", "figure_seed_invalid"]],
        "row": "draw:12",
        "stage": "draw",
    },
    {
        "anchor": "draw.py:draw",
        "plants": [
            [
                "ValueError",
                "SYN opaque fault /syn/no-output 999999999",
                "draw_unexpected_valueerror",
            ],
            [
                "OSError",
                "SYN opaque fault /syn/no-output 999999999",
                "draw_unexpected_oserror",
            ],
            ["AssemblyError", "figure_table_unreachable", "figure_table_unreachable"],
            ["ValueError", "figure_table_unreachable:SYN", "figure_table_unreachable"],
        ],
        "row": "draw:13",
        "stage": "draw",
    },
    {
        "anchor": "draw.py:validate_figure",
        "plants": [
            ["ValueError", "figure_invalid", "figure_invalid"],
            ["ValueError", "source_id", "source_id"],
        ],
        "row": "draw:14",
        "stage": "draw",
    },
    {
        "anchor": "draw.py:draw; draw.py:sample",
        "plants": [
            ["ValueError", "figure_identity_duplicate", "figure_identity_duplicate"]
        ],
        "row": "draw:15",
        "stage": "draw",
    },
    {
        "anchor": "draw.py:sample",
        "plants": [
            ["ValueError", "figure_review_insufficient", "figure_review_insufficient"]
        ],
        "row": "draw:16",
        "stage": "draw",
    },
    {
        "anchor": "assembly_io.py:bound_files",
        "plants": [
            ["AssemblyError", "assembly_output_invalid", "assembly_output_invalid"]
        ],
        "row": "reports:01",
        "stage": "reports",
    },
    {
        "anchor": "assembly_io.py:read_object",
        "plants": [
            ["AssemblyError", "assembly_input_refused", "assembly_input_refused"]
        ],
        "row": "reports:02",
        "stage": "reports",
    },
    {
        "anchor": "assembly_reports.py:write_reports",
        "plants": [
            ["AssemblyError", "assembly_reports_invalid", "assembly_reports_invalid"]
        ],
        "row": "reports:03",
        "stage": "reports",
    },
    {
        "anchor": "assembly_reports.py:write_reports",
        "plants": [
            [
                "TypeError",
                "SYN opaque fault /syn/no-output 999999999",
                "reports_unexpected_typeerror",
            ],
            [
                "KeyError",
                "SYN opaque fault /syn/no-output 999999999",
                "reports_unexpected_keyerror",
            ],
        ],
        "row": "reports:04",
        "stage": "reports",
    },
    {
        "anchor": "draw.py:reviewer_sheet; draw.py:validate_figure",
        "plants": [["ValueError", "figure_invalid", "figure_invalid"]],
        "row": "reports:05",
        "stage": "reports",
    },
    {
        "anchor": "assembly_reports.py:require_complete",
        "plants": [["AssemblyError", "assembly_gate_pending", "assembly_gate_pending"]],
        "row": "require_complete:13",
        "stage": "require_complete",
    },
]


# S2-P76 extends the inventory without changing the approved S2-P56 payload.
REVIEW_DATA_GUARD_CASES = [
    {
        "anchor": "places/review.py:load_categories, load_showcase_areas, _area; places/stage.py:run_places_stage; places/area_requests.py:area_requests",
        "plants": [
            ["PlacesError", "duplicate_category", "duplicate_category"],
            ["PlacesError", "showcase_area_duplicate", "showcase_area_duplicate"],
            ["PlacesError", "showcase_area_source", "showcase_area_source"],
            [
                "PlacesError",
                "showcase_area_gazetteer_mismatch",
                "showcase_area_gazetteer_mismatch",
            ],
        ],
        "row": "frame:S2-P76",
        "stage": "frame",
    },
    {
        "anchor": "additions/property_venues.py:load_venue_crosswalk",
        "plants": [
            ["AdditionError", "venue_key_form", "venue_key_form"],
            ["AdditionError", "venue_key_digit_run", "venue_key_digit_run"],
        ],
        "row": "additions:S2-P76",
        "stage": "additions",
    },
    {
        "anchor": "busyness/build.py:_inputs; heights/landmarks.py:checked_cache_path",
        "plants": [["BuildInputError", "cache_path_refused", "cache_path_refused"]],
        "row": "busyness:S2-P76",
        "stage": "busyness",
    },
    {
        "anchor": "places/review.py:_district_members; places/stage.py:_district_points, _district_member",
        "plants": [
            ["PlacesError", "landmark_member_duplicate", "landmark_member_duplicate"],
            ["PlacesError", "landmark_member_outside", "landmark_member_outside"],
            ["PlacesError", "landmark_member_unknown", "landmark_member_unknown"],
            ["PlacesError", "landmark_members_empty", "landmark_members_empty"],
            ["PlacesError", "landmark_point_outside", "landmark_point_outside"],
            ["PlacesError", "landmark_reason_missing", "landmark_reason_missing"],
            ["PlacesError", "landmark_record_ref", "landmark_record_ref"],
            ["PlacesError", "landmark_source_refused", "landmark_source_refused"],
        ],
        "row": "frame:S2-LMK2",
        "stage": "frame",
    },
]
