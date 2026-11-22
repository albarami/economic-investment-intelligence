"""Closed assembly diagnostics, independent of exception text and source values.

Only these reviewed names, fixed message patterns and exception classes can
supply a log word. Adding a producer reason needs a policy entry and a plant.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from csv import Error as CsvError
from decimal import InvalidOperation
from importlib.metadata import PackageNotFoundError
from json import JSONDecodeError
from types import MappingProxyType

import duckdb
import yaml

from .additions.common import AdditionError
from .assembly import PHASES, AssemblyError
from .baci.config import BaciError
from .building_inputs import BuildingError
from .busyness.build import BuildInputError
from .busyness.parse import ShapeError
from .busyness.review import ReviewError
from .comtrade.parse import ParseError
from .comtrade.policy import SafeRefusal
from .fetch.award_checks import AwardError
from .fetch.decimals import DecimalRefusal
from .fetch.page_records import PageError
from .fetch.registry import RegistryError
from .fetch.snapshots import SnapshotError
from .frame.checks import FrameError
from .gis.layers import LayerError
from .heights.model import HeightError
from .places import PlacesError
from .places.areas import AreaError
from .places_fsq.errors import PlacesFsqError
from .review.activity import SpineError
from .review.cache_fixture import CacheError
from .review.graph import GraphError
from .series.frame import MunicipalityFrameRefused
from .series.parse import SeriesRefused
from .singles.bank_credit import CreditError
from .singles.dcool import CoolingError
from .singles.families import FamilyError
from .singles.tenders import TenderError
from .singles.tenders_html import PageShapeError

STAGES = (*PHASES, "require_complete")

# Attribute names are code-owned, never chosen by an exception.
REASON_ATTRIBUTES: Mapping[type[Exception], str] = MappingProxyType(
    {
        AdditionError: "name",
        AreaError: "reason",
        BuildingError: "name",
        CacheError: "detail",
        CoolingError: "reason",
        CreditError: "reason",
        DecimalRefusal: "reason",
        FamilyError: "reason",
        FrameError: "detail",
        GraphError: "detail",
        HeightError: "name",
        MunicipalityFrameRefused: "reason",
        PageShapeError: "reason",
        ParseError: "check",
        PlacesError: "reason",
        PlacesFsqError: "reason",
        SafeRefusal: "check",
        SeriesRefused: "word",
        SpineError: "detail",
        TenderError: "reason",
    }
)

NAMED_REASONS: Mapping[type[Exception], frozenset[str]] = MappingProxyType(
    {
        AdditionError: frozenset(
            """
        activity_code_form arabic_twin_mismatch bilingual_municipality
        breakdown_unencodable bulletin_row bulletin_rows category_disagreement
        category_unlisted category_unparsed column_name country_crosswalk
        country_unreviewed crosswalk_missing district_crosswalk document_type
        duplicate_key duplicate_slug_selection export_unreadable field_map_unreadable
        geography_undeclared held_window_mismatch identifier_leak
        indicator_labels_unconfirmed key_part_missing lineage_incomplete
        measure_negative measure_not_integral measure_precision measure_unparsed
        mixed_price_basis municipality_disagreement municipality_spellings period_absent
        period_field_empty period_field_unconfirmed period_field_unreadable period_form
        period_sit period_unreadable price_as_of_mismatch price_as_of_missing
        quarter_period second_mapping selected_input_refused share_semantics_unconfirmed
        slug_absent slug_unmapped source_field_absent source_field_missing
        table_columns_mismatch table_name unknown_source_field unknown_table
        unknown_unit_type unmapped_label unmapped_municipality unmapped_unit_type
        unmapped_usage unmapped_venue_name unreviewed_venue use_map_ambiguous
        use_map_columns use_map_conflict use_map_field_empty use_map_source
        value_out_of_column venue_crosswalk venue_crosswalk_conflict venue_name_conflict
        venue_place_conflict
    """.split()
        ),
        AreaError: frozenset(
            """
        area_engine_version area_file_digest area_file_missing area_graph_unreceipted
        area_inputs_hash area_manifest_form area_manifest_missing area_polygon_form
        area_rebuild_differs area_request_mismatch area_stand_in engine_failed
        engine_package_missing engine_version places_file_digest places_file_unreceipted
        point_outside_frame road_file_missing road_file_unreceipted
    """.split()
        ),
        AssemblyError: frozenset(
            """
        assembly_additions_pending assembly_buildings_incomplete
        assembly_confirmation_invalid assembly_draw_field_unknown
        assembly_draw_lineage_ambiguous assembly_draw_table_unindexed
        assembly_draw_value_invalid assembly_family_shape_invalid assembly_fetch_refused
        assembly_fetch_unbound assembly_frame_incomplete assembly_fsq_missing
        assembly_gate_pending assembly_gis_shape_invalid assembly_graph_exists
        assembly_heights_incomplete assembly_input_refused assembly_intake_invalid
        assembly_inventory_invalid assembly_investment_refused
        assembly_investment_review_missing assembly_lineage_missing
        assembly_membership_invalid assembly_native_policy_missing
        assembly_native_source_unknown assembly_order_invalid assembly_output_invalid
        assembly_path_invalid assembly_places_incomplete assembly_regression_refused
        assembly_reports_invalid assembly_t29_refused assembly_table_duplicate
        assembly_tender_pages_incomplete assembly_tender_terms_incomplete
        assembly_tenders_shape_invalid assembly_terms_review_invalid
        assembly_value_invalid figure_seed_invalid figure_table_unreachable
        page_refusals_mismatch snapshot_selection_invalid
    """.split()
        ),
        AwardError: frozenset(
            """
        award_check_metadata_missing award_links_metadata_missing award_seed_pending
        blocked_host schema_missing
    """.split()
        ),
        BaciError: frozenset(
            """
        access_obstacle access_state archive_checksum archive_hash archive_integrity
        baci_metadata_unconfirmed blocked_host code_width configuration_bounds
        configuration_count configuration_fields configuration_type
        configuration_unreadable country_key decimal_limits dictionaries
        dictionary_count dictionary_description dictionary_key duplicate_trade_key
        header inventory iso2 iso3 licence_basis lineage manifest_complete
        manifest_configuration manifest_content manifest_hash member_bytes
        member_checksum member_kind member_name member_schema member_year
        metadata_changed_review_needed metadata_missing method_version output_hash page
        page_hash period_bounds product_key publisher qatar_key raw_bounds
        registry_policy release_contract retrieval_date revision row_schema
        rows_unconfirmed selected_manifest selected_manifest_invalid source_chain
        source_id stream_transport_missing terms_date terms_fingerprint trade_count
        write_or_stream_failed year year_coverage
    """.split()
        ),
        BuildingError: frozenset(
            """
        bldg_ovt_part_set_incomplete building_boundary_review building_frame_absent
        building_part_receipt_mismatch building_part_skipped building_part_unpinned
        building_part_unreceipted building_part_unregistered
        national_boundary_outside_frame_box national_boundary_review
        national_boundary_review_stale
    """.split()
        ),
        CoolingError: frozenset(
            """
        consumption culture_type duplicate_key sector_type unexpected_column
        unmapped_municipality year
    """.split()
        ),
        CreditError: frozenset(
            """
        activity unexpected_column value year
    """.split()
        ),
        DecimalRefusal: frozenset(
            """
        decimal_format decimal_fractional_digits decimal_total_digits missing_undeclared
    """.split()
        ),
        FamilyError: frozenset(
            """
        archive_unreadable columns_empty duplicate_member field_kind field_value
        period_label unexpected_column
    """.split()
        ),
        HeightError: frozenset(
            """
        bad_floor_count bad_footprint bad_recorded_height_m building_id
        building_manifest_absent building_manifest_boundary building_manifest_coverage
        building_manifest_inputs building_manifest_method building_manifest_pins
        building_table building_table_absent building_table_hash cache_path
        cache_receipt cache_receipt_mismatch cache_receipt_missing
        declared_reference_system declared_unit extra_property footprint_source_id
        height_value landmark_building_absent landmark_height_conflict landmark_heights
        landmark_heights_citation landmark_heights_duplicate landmark_heights_entry
        landmark_heights_height malformed_hash missing_property output_columns
        output_none output_row output_source raster_window reference_system repeated_id
        rules_class_field rules_field_or_band rules_label rules_missing_key rules_nodata
        rules_root rules_source rules_sources rules_storey rules_storey_value
        rules_unknown_key selected_input_refused snapshot_selection_invalid
        structure_mismatch switched_off wsf3d_overlap
    """.split()
        ),
        LayerError: frozenset(
            """
        area attributes cell coordinate date features geometry number spatial_reference
        text zoning_code
    """.split()
        ),
        MunicipalityFrameRefused: frozenset(
            """
        municipality_code_repeated municipality_count_mismatch municipality_field_empty
        municipality_frame_absent municipality_name_repeated
    """.split()
        ),
        PageError: frozenset(
            """
        access_failed anonymous_access_not_approved blocked_host bounds_unconfirmed
        cache_path_refused capture_evidence_missing commit_refused page_evidence_pending
        receipt_missing row_count schema_missing snapshot_date_missing
        snapshot_selection_invalid stale_period unavailable unsupported_source_claim
    """.split()
        ),
        PageShapeError: frozenset(
            """
        internal_id language page_shape pager title
    """.split()
        ),
        ParseError: frozenset(
            """
        dimension_missing duplicate_key duplicate_member measure_missing
        metadata_unreadable product_membership provider_error schema_retyped
        selection_membership short_total truncation_flag unit_mapping value_overflow
        value_type
    """.split()
        ),
        PlacesError: frozenset(
            """
        arabic_tag arabic_tag_missing attribution_header attribution_row axis_range
        axis_swapped bad_check_date building_duplicate building_id category_header
        category_row caveat_missing census_lineage crs decision_fields
        duplicate_place_date duplicate_token evidence_mismatch failed_candidate
        footprint_missing frame_boundary_missing frame_refused fsq_licence_missing
        geometry_not_bytes geometry_type geometry_wkb hand_edited link_form loader
        missing_column missing_key missing_link missing_role no_provider not_provisional
        orphan_place_id parquet passed_keys_mismatch place_id places_file_unreceipted
        pub_place_field range receipt_mismatch receipt_missing record_missing
        review_list review_row schema_versions showcase_area stale_digest stale_manifest
        stand_in_area unknown_category_class unknown_status verification_source_refused
        verification_source_unknown verified_header
    """.split()
        ),
        PlacesFsqError: frozenset(
            """
        attribution axes_swapped category_ids category_labels category_list_length
        category_unmapped cell country date_closed date_created date_refreshed
        edit_distance file_name_duplicate file_path_missing fsq_category_ids
        fsq_category_labels fsq_place_id geometry latitude longitude mapping_conflict
        mapping_header mapping_unknown_target mapping_unsigned metadata_unreadable name
        name_collision no_file_for_frame policy_disagrees receipt_mismatch
        release_invalid release_mismatch remote_path source_release statistics_missing
        summary_stale
    """.split()
        ),
        SafeRefusal: frozenset(
            """
        child_hash child_missing commit_forbidden coverage_gap dimension_missing
        duplicate_child duplicate_key duplicate_member lineage_missing manifest_hash
        manifest_incomplete manifest_missing manifest_unreadable measure_missing
        metadata_unreadable parser_identity policy_changed product_membership
        provider_error receipt_count receipt_hash receipt_missing schema_retyped
        selection_changed selection_membership short_total truncation_flag unit_mapping
        value_overflow value_type
    """.split()
        ),
        SeriesRefused: frozenset(
            """
        municipality_frame_not_supplied municipality_names_refused
        selected_input_refused unmapped_municipality_spelling
    """.split()
        ),
        ShapeError: frozenset(
            """
        schema_missing
    """.split()
        ),
        SnapshotError: frozenset(
            """
        snapshot_conflict snapshot_date_missing snapshot_hash_mismatch
        snapshot_index_invalid snapshot_missing snapshot_path_invalid
        snapshot_selection_invalid snapshot_write_failed
    """.split()
        ),
        TenderError: frozenset(
            """
        amount award_after_stop award_cutoff_invalid award_date_missing
        award_order_invalid certificate_chain_incomplete certificate_host_mismatch
        host_refused http_status internal_id language missing_buying_entity page_shape
        pager refused_path release_contact release_identifier tender_key title
    """.split()
        ),
        ValueError: frozenset(
            """
        access benchmark_metadata_unconfirmed binding binding_classification
        binding_country_dictionary binding_currency binding_direction binding_period
        binding_product binding_revision blocked_host bounds c5_parent_review_missing
        c5_parent_treatment c5_parent_visible_label_missing c5_parent_withheld_value
        c5_window_latest_2025_2026_required c5_window_latest_twelve_required
        c5_window_prior_2024_required card_sync_baseline_or_missing_value
        card_sync_block_outside_sections card_sync_encoding card_sync_malformed_block
        card_sync_missing_block card_sync_section_missing card_sync_sections_unrecorded
        card_sync_unchecked_or_duplicate card_sync_value_invalid
        card_sync_value_mismatch card_sync_wrong_anchor cause_evidence cause_schema
        comtrade_policy_required confirmation_task_duplicate confirmation_task_unknown
        data_bytes deferred_input_schema duplicate_binding duplicate_key
        figure_identity_duplicate figure_invalid figure_log_invalid
        figure_review_insufficient figure_seed_invalid format gap input_receipt
        last_period licence_metadata manifest_contract manifest_hash manifest_policy
        member_bytes member_inventory member_policy member_rows
        metadata_changed_review_needed metadata_required missing_input_evidence
        missing_tokens native_row_binding_missing native_schema native_types
        obstacle_evidence obstacle_schema output_count output_hash
        own_run_inventory_invalid owner_report pack_family_row_truncated
        pack_section_missing pack_source_duplicate page_hash pending_input_evidence
        pending_urls pin_artifact_duplicate_or_unknown pin_artifact_fields
        pin_artifact_missing pin_checked_evidence_missing pin_gate_unknown
        pin_input_unreadable pin_json_invalid pin_lineage pin_lineage_context_missing
        pin_lineage_date pin_lineage_duplicate pin_lineage_mismatch
        pin_lineage_receipt_mismatch pin_lineage_receipt_missing
        pin_lineage_source_ambiguous pin_lineage_source_unknown pin_maker_unknown
        pin_missing_or_duplicate pin_record_fields pin_record_hash pin_record_list
        pin_record_mapping pin_record_text pin_review_date pin_review_result
        pin_reviewer_missing_or_same_maker pin_schema_version pin_settings_hash_mismatch
        pin_unknown_or_anchor pin_unpinned_carries_evidence pin_unrecorded_setting
        pin_value_mismatch pin_value_type pin_yaml_invalid policy_schema precision
        price_evidence raw_bounds recomputed_output registry_policy release_contract
        reparsed_output retrieval_date retrieval_timezone review_date_format row_mapping
        row_schema schema_missing selected_bounds selected_manifest selection
        selection_flow selection_hash selection_inputs selection_pending
        selection_schema selection_scope selection_year series_policy
        series_refusal_unknown source_chain source_id source_version status_mapping
        stream_transport_missing tender_handoff_conflict tender_handoff_incomplete
        tender_handoff_invalid tender_handoff_refused tender_handoff_terms_invalid
        tender_retrieval_missing terms_fingerprint unavailable_input_binding
        unsafe_report unused_binding
    """.split()
        ),
    }
)


def _text_rules(specification: str) -> tuple[tuple[re.Pattern[str], str], ...]:
    return tuple(
        (re.compile(pattern, re.DOTALL), word)
        for row in specification.strip().splitlines()
        for word, pattern in [row.strip().split("|", 1)]
    )


# Each static record is word|full-match-pattern. Captured text is never returned.
TEXT_REASONS: Mapping[type[Exception], tuple[tuple[re.Pattern[str], str], ...]] = (
    MappingProxyType(
        {
            BuildInputError: _text_rules(r"""
        crosswalk_missing|crosswalk\ missing\ .*
        pub_place_missing|pub_place\ missing\ .*
        pub_place_missing|pub_place\ .*\ missing\ .*
    """),
            CacheError: _text_rules(r"""
        cache_body_digest_differs_from_its_sidecar|cache\ body\ digest\ differs\ from\ its\ sidecar
        cache_body_size_differs_from_its_sidecar|cache\ body\ size\ differs\ from\ its\ sidecar
        class_fixture_code_or_title_is_not_text|class\ fixture\ code\ or\ title\ is\ not\ text
        cache_json_body_is_not_a_list_of_rows|cache\ json\ body\ is\ not\ a\ list\ of\ rows
        activity_period_is_not_one_year_field|activity\ period\ is\ not\ one\ year\ field
        cache_sidecar_names_another_digest|cache\ sidecar\ names\ another\ digest
        cache_sidecar_names_another_source|cache\ sidecar\ names\ another\ source
        cache_sidecar_names_another_key|cache\ sidecar\ names\ another\ key
        cache_json_row_is_not_a_map|cache\ json\ row\ is\ not\ a\ map
        cache_sidecar_is_not_a_map|cache\ sidecar\ is\ not\ a\ map
        cache_body_is_switched_off|cache\ body\ is\ switched\ off
        cache_sidecar_is_not_json|cache\ sidecar\ is\ not\ JSON
        snapshot_extension_mismatch|snapshot\ extension\ mismatch
        activity_column_is_not_one_field|activity\ column\ is\ not\ one\ field:\ .*
        cache_body_has_no_row_reader_for|cache\ body\ has\ no\ row\ reader\ for\ .*
        snapshot_selection_invalid|.*: snapshot_selection_invalid
        snapshot_hash_mismatch|.*: snapshot_hash_mismatch
        snapshot_index_invalid|.*: snapshot_index_invalid
        snapshot_date_missing|.*: snapshot_date_missing
        snapshot_path_invalid|.*: snapshot_path_invalid
        snapshot_write_failed|.*: snapshot_write_failed
        snapshot_conflict|.*: snapshot_conflict
        snapshot_missing|.*: snapshot_missing
    """),
            CreditError: _text_rules(r"""
        value|value\ .*
    """),
            FrameError: _text_rules(r"""
        outside_greater_doha_cell_has_no_greater_doha_sibling|outside\ Greater\ Doha\ cell\ has\ no\ Greater\ Doha\ sibling
        municipality_containment_disagrees_with_key|municipality\ containment\ disagrees\ with\ key
        greater_doha_cell_must_have_resolution_9|Greater\ Doha\ cell\ must\ have\ resolution\ 9
        gazetteer_point_has_no_unique_base_cell|gazetteer:\ point\ has\ no\ unique\ base\ cell
        boundary_containment_requires_one_parent|boundary\ containment:\ requires\ one\ parent
        district_alias_csv_row_width_or_syntax|district_alias:\ CSV\ row\ width\ or\ syntax
        centre_must_be_in_exactly_one_polygon|centre\ must\ be\ in\ exactly\ one\ polygon
        unknown_district_in_reviewed_mapping|unknown\ district\ in\ reviewed\ mapping
        greater_doha_duplicate_municipality|Greater\ Doha:\ duplicate\ municipality
        greater_doha_unknown_municipality|Greater\ Doha:\ unknown\ municipality
        grid_cell_district_null_condition|grid_cell:\ district\ null\ condition
        gazetteer_missing_bilingual_name|gazetteer:\ missing\ bilingual\ name
        gazetteer_invalid_reviewed_kind|gazetteer:\ invalid\ reviewed\ kind
        gazetteer_arabic_review_status|gazetteer:\ Arabic\ review\ status
        gazetteer_duplicate_place_key|gazetteer:\ duplicate\ place\ key
        resolution_9_cell_owned_twice|resolution\-9\ cell\ owned\ twice
        district_alias_csv_row_width|district_alias:\ CSV\ row\ width
        municipality_names_unknown_key|municipality_names:\ unknown_key
        polygon_gap_or_outside_frame|polygon\ gap\ or\ outside\ frame
        review_output_overlaps_inputs|review\ output\ overlaps\ inputs
        unmapped_municipality_spelling|unmapped\ municipality\ spelling
        duplicate_district_free_zone|duplicate\ district\-free\ zone
        listed_zone_has_a_district|listed\ zone\ has\ a\ district
        unlisted_district_free_zone|unlisted\ district\-free\ zone
        matched_zone_outside_frame|matched\ zone\ outside\ frame
        municipality_names_conflict|municipality_names:\ conflict
        unknown_district_free_zone|unknown\ district\-free\ zone
        district_alias_csv_header|district_alias:\ CSV\ header
        duplicate_district_mapping|duplicate\ district\ mapping
        stored_ancestor_and_child|stored\ ancestor\ and\ child
        partial_district_coverage|partial\ district\ coverage
        gazetteer_cell_condition|gazetteer\ cell\ condition
        frame_zone_not_matched|frame\ zone\ not\ matched
        district_free_reason|district\-free\ reason
        duplicate_zone_code|duplicate\ zone\ code
        forbidden_digit_run|forbidden\ digit\ run
        invalid_zone_status|invalid\ zone\ status
        invalid_polygon|invalid\ polygon
        polygon_overlap|polygon\ overlap
        duplicate_cell|duplicate\ cell
        missing_key|missing\ key
        municipality_source_spelling_wrong_code|municipality\ source\ spelling:\ .*:\ wrong\ code
        municipality_source_spelling_unmapped|municipality\ source\ spelling:\ .*:\ unmapped
        bnd_hdx_invalid_release_source_for|bnd_hdx:\ invalid\ release\ source\ for\ .*
        required_join_source_unavailable|.*:\ required\ join\ source\ unavailable
        gazetteer_missing_source_point|gazetteer\ .*:\ missing\ source\ point
        municipality_name_disagreement|.*:\ municipality\ name\ disagreement
        pop_muni_invalid_indicator|pop_muni:\ invalid_indicator:\ .*
        no_confirmed_cache_shape|.*:\ no\ confirmed\ cache\ shape
        unsupported_source_schema|.*:\ unsupported\ source\ schema
        zone_code_no_cell_centre|zone_code\ .*:\ no\ cell\ centre
        snapshot_selection_invalid|.*: snapshot_selection_invalid
        snapshot_hash_mismatch|.*: snapshot_hash_mismatch
        snapshot_index_invalid|.*: snapshot_index_invalid
        source_switched_off|.*:\ source\ switched\ off
        snapshot_date_missing|.*: snapshot_date_missing
        snapshot_path_invalid|.*: snapshot_path_invalid
        snapshot_write_failed|.*: snapshot_write_failed
        snapshot_conflict|.*: snapshot_conflict
        expected_object|.*:\ expected\ object
        snapshot_missing|.*: snapshot_missing
        expected_list|.*:\ expected\ list
        unlisted_zone|.*:\ unlisted\ zone
        pop_muni|pop_muni:\ .*
        receipt_mismatch|.*:\ receipt\ .*\ mismatch
        missing_receipt|.*:\ missing\ receipt\ .*
        missing_fields_unknown_fields|.*:\ missing\ fields\ .*;\ unknown\ fields\ .*
        field_must_be|.*:\ field\ .*\ must\ be\ .*
    """),
            GraphError: _text_rules(r"""
        sourced_from_edge_does_not_join_a_public_node_or_table_to_source|sourced_from\ edge\ does\ not\ join\ a\ public\ node\ or\ table\ to\ source
        allow_list_category_is_not_in_the_places_cache|allow\-list\ category\ is\ not\ in\ the\ places\ cache
        mapped_edge_without_the_reviewer_approved_reason|mapped\ edge\ without\ the\ reviewer_approved\ reason
        activity_graph_has_a_duplicate_unmappable_node|activity\ graph\ has\ a\ duplicate\ UNMAPPABLE\ node
        mapped_edge_name_differs_from_the_cached_name|mapped\ edge\ name\ differs\ from\ the\ cached\ name
        activity_graph_is_missing_the_unmappable_node|activity\ graph\ is\ missing\ the\ UNMAPPABLE\ node
        edge_source_has_no_release_admitted_licence|edge\ source\ has\ no\ release\-admitted\ licence
        allow_list_header_is_not_the_fixed_header|allow\-list\ header\ is\ not\ the\ fixed\ header
        mapped_edge_class_differs_from_the_prefix|mapped\ edge\ class\ differs\ from\ the\ prefix
        spine_and_activities_name_different_codes|spine\ and\ activities\ name\ different\ codes
        allow_list_class_is_not_a_digit_string|allow\-list\ class\ is\ not\ a\ digit\ string
        lineage_edge_type_with_public_provenance|lineage\ edge\ type\ with\ public\ provenance
        mapped_edge_class_is_not_an_isic_class|mapped\ edge\ class\ is\ not\ an\ ISIC\ class
        mapped_edge_is_not_a_seven_digit_code|mapped\ edge\ is\ not\ a\ seven\-digit\ code
        mapped_edge_without_an_iso_review_date|mapped\ edge\ without\ an\ ISO\ review\ date
        sourced_from_edge_basis_is_not_lineage|sourced_from\ edge\ basis\ is\ not\ lineage
        allow_list_class_is_not_in_cls_isic4|allow\-list\ class\ is\ not\ in\ cls_isic4
        allow_list_row_with_a_malformed_date|allow\-list\ row\ with\ a\ malformed\ date
        allow_list_class_is_not_four_digits|allow\-list\ class\ is\ not\ four\ digits
        allow_list_date_is_not_an_iso_date|allow\-list\ date\ is\ not\ an\ ISO\ date
        lineage_edge_has_a_public_edge_type|lineage\ edge\ has\ a\ public\ edge\ type
        mapped_edge_without_a_reviewer_role|mapped\ edge\ without\ a\ reviewer\ role
        mapped_edge_with_a_malformed_date|mapped\ edge\ with\ a\ malformed\ date
        place_row_has_no_primary_category|place\ row\ has\ no\ primary\ category
        allow_list_sign_off_is_not_text|allow\-list\ sign\-off\ is\ not\ text
        cls_isic4_is_not_in_the_registry|cls_isic4\ is\ not\ in\ the\ registry
        public_edge_joins_a_lineage_node|public\ edge\ joins\ a\ lineage\ node
        allow_list_row_without_sign_off|allow\-list\ row\ without\ sign\-off
        allow_list_category_is_empty|allow\-list\ category\ is\ empty
        edge_value_is_not_a_decimal|edge\ value\ is\ not\ a\ decimal
        graph_output_already_exists|graph\ output\ already\ exists
        duplicate_allow_list_pair|duplicate\ allow\-list\ pair
        edge_unit_is_not_text|edge\ unit\ is\ not\ text
        unknown_edge_provenance|unknown\ edge\ provenance
        unknown_node_provenance|unknown\ node\ provenance
        node_code_is_empty|node\ code\ is\ empty
        unknown_graph_mode|unknown\ graph\ mode
        activity_without_one_classified_as_edge|activity\ without\ one\ classified_as\ edge:\ .*
        node_id_prefix_differs_from_its_type|node\ id\ prefix\ differs\ from\ its\ type:\ .*
        node_source_is_not_in_the_registry|node\ source\ is\ not\ in\ the\ registry:\ .*
        synthetic_identifier_in_the_graph|synthetic\ identifier\ in\ the\ graph:\ .*
        source_is_not_in_the_registry|source\ is\ not\ in\ the\ registry:\ .*
        edge_endpoint_is_not_a_node|edge\ endpoint\ is\ not\ a\ node:\ .*
        duplicate_activity_source|duplicate\ activity\ source:\ .*
        unknown_activity_source|unknown\ activity\ source:\ .*
        unknown_edge_basis|unknown\ edge\ basis\ .*
        unknown_edge_type|unknown\ edge\ type\ .*
        unknown_node_type|unknown\ node\ type\ .*
        conflicting_edge|conflicting\ edge\ .*
        conflicting_node|conflicting\ node\ .*
        duplicate_edge|duplicate\ edge\ .*
        duplicate_node|duplicate\ node\ .*
        edge_basis_is_not|.*\ edge\ basis\ is\ not\ .*
        edge_does_not_join_to|.*\ edge\ does\ not\ join\ .*\ to\ .*
    """),
            HeightError: _text_rules(r"""
        rules|rules_.*
        bad|bad_.*
    """),
            LayerError: _text_rules(r"""
        district_numbers_differ|district\ numbers\ differ
        feature_key_value|feature\ key\ value
        service_name_year|service\ name\ year
        health_layer|health\ layer
        layer_body|layer\ body
        layer_name|layer\ name
        rail_layer|rail\ layer
        release_column|release\ column\ .*
    """),
            RegistryError: _text_rules(r"""
        geojson_feature_polygon_is_declared_for_bnd_muni_2025_only|geojson_feature_polygon\ is\ declared\ for\ bnd_muni_2025\ only
        comtrade_policy_on_a_row_that_is_not_comtrade_api|comtrade_policy\ on\ a\ row\ that\ is\ not\ comtrade_api
        nationality_field_requires_public_splits_nationality|nationality\ field\ requires\ public_splits\ nationality
        held_table_is_not_registered_for_its_source|held\ table\ is\ not\ registered\ for\ its\ source
        cdse_backup_must_remain_optional_and_unread|CDSE\ backup\ must\ remain\ optional\ and\ unread
        variables_is_not_a_non_empty_list_of_text|variables\ is\ not\ a\ non\-empty\ list\ of\ text
        held_past_count_must_be_a_positive_integer|held\ past_count\ must\ be\ a\ positive\ integer
        chain_intermediate_sha256_is_not_a_sha_256|chain_intermediate_sha256\ is\ not\ a\ SHA\-256
        source_keys_outside_closed_series_mapping|source\ keys\ outside\ closed\ series\ mapping
        company_web_must_remain_lead_shell_only|company\ web\ must\ remain\ lead\-shell\-only
        decision_record_set_without_owner_decision|decision_record\ set\ without\ owner_decision
        layer_on_a_row_that_is_not_paged_layer|layer\ on\ a\ row\ that\ is\ not\ paged_layer
        property_series_requires_district_subject|property\ series\ requires\ district\ subject
        owner_decision_needs_a_decision_record|owner_decision\ needs\ a\ decision\ record
        held_frequency_does_not_match_series|held\ frequency\ does\ not\ match\ series
        skip_reason_names_a_licence_or_terms|skip_reason\ names\ a\ licence\ or\ terms
        traffic_provider_has_no_registry_row|traffic\ provider\ has\ no\ registry\ row
        sex_field_requires_public_splits_sex|sex\ field\ requires\ public_splits\ sex
        comtrade_api_requires_comtrade_policy|comtrade_api\ requires\ comtrade_policy
        source_keys_is_not_a_list_of_text|source_keys\ is\ not\ a\ list\ of\ text
        variables_is_not_a_recorded_value|variables\ is\ not\ a\ recorded\ value
        column_name_or_type_is_not_text|column\ name\ or\ type\ is\ not\ text
        terms_watch_set_without_basis_note|terms_watch\ set\ without\ basis_note
        point_is_not_a_pair_of_numbers|point\ is\ not\ a\ pair\ of\ numbers
        terms_watch_set_without_terms_url|terms_watch\ set\ without\ terms_url
        unknown_field_in_forecast_series|unknown\ field\ in\ forecast\ series
        forecast_series_is_not_a_map|forecast\ series\ is\ not\ a\ map
        forecast_series_is_not_a_list|forecast_series\ is\ not\ a\ list
        held_source_is_not_registered|held\ source\ is\ not\ registered
        open_series_carries_past_count|open\ series\ carries\ past_count
        public_splits_contract_mismatch|public_splits\ contract\ mismatch
        terms_watch_is_not_a_boolean|terms_watch\ is\ not\ a\ boolean
        registry_root_is_not_a_map|registry\ root\ is\ not\ a\ map
        held_reason_must_be_empty|held\ reason\ must\ be\ empty
        paged_layer_requires_layer|paged_layer\ requires\ layer
        duplicate_forecast_series|duplicate\ forecast\ series
        layer_is_not_an_integer|layer\ is\ not\ an\ integer
        register_file_declaration|register\ file\ declaration
        variables_repeats_a_name|variables\ repeats\ a\ name
        basis_note_is_not_text|basis_note\ is\ not\ text
        columns_is_not_a_list|columns\ is\ not\ a\ list
        held_period_is_missing|held\ period\ is\ missing
        open_reason_is_missing|open\ reason\ is\ missing
        unknown_forecast_state|unknown\ forecast\ state
        column_is_not_a_map|column\ is\ not\ a\ map
        entry_is_not_a_map|entry\ is\ not\ a\ map
        unknown_column_field|unknown\ column\ field
        unknown_licence_basis|unknown\ licence_basis
        cannot_be_committed|cannot\ be\ committed
        unknown_column_type|unknown\ column\ type
        layer_is_negative|layer\ is\ negative
        sources_is_empty|sources\ is\ empty
        malformed_yaml|malformed\ yaml
        duplicate_key|duplicate\ key
        unknown_kind|unknown\ kind
        file_field_on_a_row_that_does_not_use_it|file\ field\ on\ a\ row\ that\ does\ not\ use\ it:\ .*
        is_not_in_the_recorded_form|.*\ is\ not\ in\ the\ recorded\ form
        row_count_range_not_closed|.*:\ row\ count\ range\ not\ closed
        is_not_a_recorded_value|.*\ is\ not\ a\ recorded\ value
        incomplete_file_metadata|incomplete\ file\ metadata:\ .*
        is_not_a_list_of_text|.*\ is\ not\ a\ list\ of\ text
        is_not_a_decimal_code|.*\ is\ not\ a\ decimal\ code
        period_field_undeclared|.*:\ period_field_undeclared
        period_bounds_empty|.*:\ period\ bounds\ empty
        is_not_an_integer|.*\ is\ not\ an\ integer
        split_declaration|.*:\ split\ declaration
        is_not_a_boolean|.*\ is\ not\ a\ boolean
        is_not_a_date|.*\ is\ not\ a\ date
        unknown_series|unknown\ series:\ .*
        columns_empty|.*:\ columns\ empty
        missing_field|missing\ field\ .*
        unknown_field|unknown\ field\ .*
        is_not_text|.*\ is\ not\ text
        period_form|.*:\ period_form
        is_empty|.*\ is\ empty
    """),
            ReviewError: _text_rules(r"""
        source_page_expected_key_free_https_page|.*\ source_page:\ expected\ key\-free\ HTTPS\ page
        schema_expected_the_four_review_keys|.*\ schema:\ expected\ the\ four\ review\ keys
        match_expected_matched_or_no_match|.*\ match:\ expected\ matched\ or\ no_match
        schema_wrong_or_empty_cells|.*\ schema:\ wrong\ or\ empty\ cells
        schema_wrong_columns|.*\ schema:\ wrong\ columns
        place_id_duplicate|.*\ place_id:\ duplicate
        schema_unreadable|.*\ schema:\ unreadable
        expected_positive_integer|.*\ .*:\ expected\ positive\ integer
        expected_iso_date_text|.*\ .*:\ expected\ ISO\ date\ text
    """),
            ShapeError: _text_rules(r"""
        busy_besttime_changed_shape|busy_besttime\ .*\ changed_shape
        secret_in_output|.* secret_in_output
        request_failed|.* request_failed
        changed_shape|.* changed_shape
    """),
            SnapshotError: _text_rules(r"""
        snapshot_write_failed|.*:\ snapshot_write_failed
    """),
            SpineError: _text_rules(r"""
        code_system_version_differs_from_the_reviewed_version|code\-system\ version\ differs\ from\ the\ reviewed\ version
        isic_code_pattern_is_not_a_class_or_a_higher_level|isic\ code\ pattern\ is\ not\ a\ class\ or\ a\ higher\ level
        classification_title_differs_from_the_reviewed_title|classification\ title\ differs\ from\ the\ reviewed\ title
        model_audit_code_is_not_a_signed_model_decision|model\ audit\ code\ is\ not\ a\ signed\ model\ decision
        review_binding_input_fields_are_not_the_contract|review\ binding\ input\ fields\ are\ not\ the\ contract
        model_review_code_has_multiple_audited_batches|model\ review\ code\ has\ multiple\ audited\ batches
        review_code_is_not_the_reversible_dotted_form|review\ code\ is\ not\ the\ reversible\ dotted\ form
        review_binding_class_code_is_not_four_digits|review\ binding\ class\ code\ is\ not\ four\ digits
        model_audit_file_hash_differs_from_binding|model\ audit\ file\ hash\ differs\ from\ binding
        review_binding_audit_hash_is_not_a_sha256|review\ binding\ audit\ hash\ is\ not\ a\ sha256
        review_binding_fields_are_not_the_contract|review\ binding\ fields\ are\ not\ the\ contract
        review_binding_input_is_not_a_class_title|review\ binding\ input\ is\ not\ a\ class\ title
        model_audit_sample_differs_from_seed_draw|model\ audit\ sample\ differs\ from\ seed\ draw
        review_binding_has_no_code_system_version|review\ binding\ has\ no\ code\-system\ version
        model_audit_review_rows_hash_is_invalid|model\ audit\ review\ rows\ hash\ is\ invalid
        model_review_code_has_no_audited_batch|model\ review\ code\ has\ no\ audited\ batch
        model_audit_signer_differs_from_review|model\ audit\ signer\ differs\ from\ review
        review_header_is_not_the_spine_header|review\ header\ is\ not\ the\ spine\ header
        model_audit_record_fields_are_invalid|model\ audit\ record\ fields\ are\ invalid
        review_binding_inputs_are_not_a_list|review\ binding\ inputs\ are\ not\ a\ list
        model_audit_makers_are_not_different|model\ audit\ makers\ are\ not\ different
        model_audit_review_rows_hash_differs|model\ audit\ review\ rows\ hash\ differs
        review_binding_hash_is_not_a_sha256|review\ binding\ hash\ is\ not\ a\ sha256
        review_file_holds_a_bare_digit_run|review\ file\ holds\ a\ bare\ digit\ run
        model_audit_batch_id_is_duplicated|model\ audit\ batch\ id\ is\ duplicated
        model_audit_seed_is_out_of_range|model\ audit\ seed\ is\ out\ of\ range
        model_audit_file_is_not_readable|model\ audit\ file\ is\ not\ readable
        model_audit_batch_id_is_invalid|model\ audit\ batch\ id\ is\ invalid
        model_audit_errors_are_not_zero|model\ audit\ errors\ are\ not\ zero
        review_binding_is_not_an_object|review\ binding\ is\ not\ an\ object
        supplier_membership_is_incomplete|supplier\ membership\ is\ incomplete
        model_audit_sample_size_differs|model\ audit\ sample\ size\ differs
        review_binding_repeats_an_input|review\ binding\ repeats\ an\ input
        reviewed_on_is_not_a_real_date|reviewed_on\ is\ not\ a\ real\ date
        reviewed_on_is_not_an_iso_date|reviewed_on\ is\ not\ an\ ISO\ date
        isic_class_is_not_four_digits|isic\ class\ is\ not\ four\ digits
        model_audit_binding_is_missing|model\ audit\ binding\ is\ missing
        model_review_role_is_malformed|model\ review\ role\ is\ malformed
        review_binding_is_not_readable|review\ binding\ is\ not\ readable
        isic_class_is_not_four_digits|isic_class\ is\ not\ four\ digits
        model_audit_role_is_malformed|model\ audit\ role\ is\ malformed
        supplier_membership_is_missing|supplier\ membership\ is\ missing
        code_is_not_a_digit_string|code\ is\ not\ a\ digit\ string
        model_audit_date_is_invalid|model\ audit\ date\ is\ invalid
        model_audit_list_is_invalid|model\ audit\ list\ is\ invalid
        model_audit_predates_signing|model\ audit\ predates\ signing
        reason_is_not_a_closed_key|reason\ is\ not\ a\ closed\ key
        model_audit_has_no_records|model\ audit\ has\ no\ records
        isic_class_title_is_empty|isic\ class\ title\ is\ empty
        review_binding_is_missing|review\ binding\ is\ missing
        isic_field_is_not_text|isic\ field\ is\ not\ text
        duplicate_review_code|duplicate\ review\ code
        signed_name_differs_from_the_cached_name|signed\ name\ differs\ from\ the\ cached\ name:\ .*
        signed_class_differs_from_the_prefix|signed\ class\ differs\ from\ the\ prefix:\ .*
        playbook_code_absent_from_the_feeds|playbook\ code\ absent\ from\ the\ feeds:\ .*
        supplier_code_absent_from_the_feeds|supplier\ code\ absent\ from\ the\ feeds:\ .*
        decision_without_an_iso_review_date|.*\ decision\ without\ an\ ISO\ review\ date
        code_length_does_not_match_the_code|code_length\ does\ not\ match\ the\ code\ .*
        activity_column_is_not_one_field|activity\ column\ is\ not\ one\ field:\ .*
        review_status_is_not_a_decision|review\ status\ is\ not\ a\ decision:\ .*
        decision_without_a_reviewer_role|.*\ decision\ without\ a\ reviewer\ role
        decision_with_a_malformed_date|.*\ decision\ with\ a\ malformed\ date
        is_not_a_non_negative_integer|.*\ is\ not\ a\ non\-negative\ integer
        conflicting_activity_name_for|conflicting\ activity\ name\ for\ .*
        registry_key_is_not_unique|registry\ key\ is\ not\ unique:\ .*
        source_receipt_has_no_hash|source\ receipt\ has\ no\ hash:\ .*
        conflicting_isic_title_for|conflicting\ isic\ title\ for\ .*
        duplicate_activity_source|duplicate\ activity\ source\ .*
        mandatory_review_missing|mandatory\ review\ missing:\ .*
        duplicate_activity_code|duplicate\ activity\ code\ .*
        unknown_activity_source|unknown\ activity\ source\ .*
        duplicate_review_code|duplicate\ review\ code\ .*
        registry_key_missing|registry\ key\ missing:\ .*
        unknown_activity_feed|unknown\ activity\ feed\ .*
        duplicate_isic_class|duplicate\ isic\ class\ .*
        missing_isic_field|missing\ isic\ field\ .*
        unknown_class_feed|unknown\ class\ feed\ .*
        unknown_isic_field|unknown\ isic\ field\ .*
        unknown_status|unknown\ status\ .*
        is_not_text|.*\ is\ not\ text
        decision_without_the_reason|.*\ decision\ without\ the\ .*\ reason
        field_type|.*\ field\ type:\ .*
    """),
            TenderError: _text_rules(r"""
        label|.*\ label\ .*
    """),
            ValueError: _text_rules(r"""
        registry_must_record_the_disabled_source_or_evidenced_absence|registry\ must\ record\ the\ disabled\ source\ or\ evidenced\ absence
        none_found_requires_search_evidence_and_no_release_table|none_found\ requires\ search\ evidence\ and\ no\ release\ table
        weight_confirmation_is_not_the_current_area_only_choice|weight\ confirmation\ is\ not\ the\ current\ area\-only\ choice
        go_live_permission_needed_does_not_match_terms_reading|go_live_permission_needed\ does\ not\ match\ terms\ reading
        registry_and_fetched_evidence_do_not_confirm_tender|registry\ and\ fetched\ evidence\ do\ not\ confirm\ tender
        c5_parent_requires_includes_excluded_lines_or_withheld|c5_parent_requires_includes\ excluded\ lines_or_withheld
        selected_sources_must_exactly_match_owned_entries|selected\ sources\ must\ exactly\ match\ owned\ entries
        decision_record_must_be_empty_for_covering_terms|decision_record\ must\ be\ empty\ for\ covering\ terms
        sec_hr_ind_one_restaurant_indicator_row_required|sec_hr_ind:\ one\ restaurant\ indicator\ row\ required
        pub_67_target_municipality_absent_or_ambiguous|PUB\-67\ target\ municipality\ absent\ or\ ambiguous
        table_identity_comes_from_the_source_registry|table\ identity\ comes\ from\ the\ source\ registry
        basis_of_use_must_match_covering_licence_basis|basis_of_use\ must\ match\ covering\ licence_basis
        lic_cancelled_shhr_llg_integer_month_required|lic_cancelled\ shhr_llg:\ integer\ month\ required
        shown_does_not_match_recorded_visitor_source|shown\ does\ not\ match\ recorded\ visitor\ source
        r1_needs_all_hotels_and_restaurants_tables|R1\ needs\ all\ hotels\-and\-restaurants\ tables
        match_list_length_differs_from_the_choices|match\ list\ length\ differs\ from\ the\ choices
        trade_reconciliation_selected_manifest_invalid|trade_reconciliation\ selected_manifest_invalid
        unknown_outcome_or_forbidden_licence_basis|unknown\ outcome\ or\ forbidden\ licence\ basis
        country_alias_invalid_unattributed_reason|country\ alias:\ invalid\ unattributed\ reason
        lic_cancelled_sn_llg_four_digits_required|lic_cancelled\ sn_llg:\ four\ digits\ required
        sec_hr_size_restaurant_size_rows_required|sec_hr_size:\ restaurant\ size\ rows\ required
        supporting_provenance_has_no_isic_classes|supporting\ provenance\ has\ no\ ISIC\ classes
        supporting_provenance_frame_inputs_differ|supporting\ provenance\ frame\ inputs\ differ
        supporting_provenance_selections_required|supporting\ provenance\ selections\ required
        credit_limit_expected_positive_integer|credit\ limit:\ expected\ positive\ integer
        pending_confirmation_has_release_tables|pending\ confirmation\ has\ release\ tables
        request_cost_expected_positive_integer|request\ cost:\ expected\ positive\ integer
        height_source_outside_the_closed_list|height\ source\ outside\ the\ closed\ list
        recorded_source_requires_release_tables|recorded\ source\ requires\ release_tables
        supporting_provenance_registry_identity|supporting\ provenance\ registry\ identity
        trade_reconciliation_selection_unreadable|trade_reconciliation\ selection_unreadable
        pub_64_numeric_source_field_required|PUB\-64\ numeric\ source\ field\ required
        pub_67_unresolved_source_municipality|PUB\-67\ unresolved\ source\ municipality
        incomplete_or_duplicate_field_mapping|incomplete\ or\ duplicate\ field\ mapping
        one_supporting_selected_hash_required|one\ supporting\ selected\ hash\ required
        confirmation_block_is_not_an_object|confirmation\ block\ is\ not\ an\ object
        country_alias_absent_reference_code|country\ alias:\ absent\ reference\ code
        country_alias_repeated_country_name|country\ alias:\ repeated\ country\ name
        invalid_supporting_provenance_dataset|invalid\ supporting\ provenance\ dataset
        supporting_registry_identity_required|supporting\ registry\ identity\ required
        pub_64_numeric_c4_result_required|PUB\-64\ numeric\ C4\ result\ required
        basis_of_use_must_be_owner_decision|basis_of_use\ must\ be\ owner_decision
        candidate_outside_the_closed_order|candidate\ outside\ the\ closed\ order
        overlap_area_must_not_be_negative|overlap\ area\ must\ not\ be\ negative
        review_needs_bilingual_descriptions|review\ needs\ bilingual\ descriptions
        supporting_provenance_frame_differs|supporting\ provenance\ frame\ differs
        terms_read_on_must_be_a_real_date|terms_read_on\ must\ be\ a\ real\ date
        terms_read_on_must_use_yyyy_mm_dd|terms_read_on\ must\ use\ YYYY\-MM\-DD
        invalid_build_start_utc_timestamp|invalid\ build\-start\ UTC\ timestamp
        missing_review_or_search_evidence|missing\ review\ or\ search\ evidence
        missing_source_chain_release_tables|missing\ source_chain\ release_tables
        missing_source_chain_field_mapping|missing\ source_chain\ field_mapping
        a_none_choice_needs_its_reason|a\ none\ choice\ needs\ its\ reason
        benchmark_configuration_unreadable|benchmark\ configuration_unreadable
        pub_64_receipt_source_mismatch|PUB\-64\ receipt\ source\ mismatch
        pub_67_activity_entry_required|PUB\-67\ activity\ entry\ required
        pub_67_unparsed_activity_codes|PUB\-67\ unparsed\ activity\ codes
        invalid_tender_flags_or_tables|invalid\ tender\ flags\ or\ tables
        missing_covering_terms_evidence|missing\ covering\ terms\ evidence
        review_exclusion_reason_missing|review\ exclusion\ reason\ missing
        busy_besttime_registry_mismatch|busy_besttime\ registry\ mismatch
        tender_source_identity_missing|tender\ source\ identity\ missing
        zero_change_has_no_mix_share|zero\ change\ has\ no\ mix\ share
        pub_67_isic_classes_required|PUB\-67\ ISIC\ classes\ required
        incomplete_tender_confirmation|incomplete\ tender\ confirmation
        selected_fetch_lines_required|selected\ fetch\ lines\ required
        pub_67_bucket_reconciliation|PUB\-67\ bucket\ reconciliation
        decision_record_must_be_0026|decision_record\ must\ be\ 0026
        invalid_supporting_provenance|invalid\ supporting\ provenance
        read_as_visitor_must_be_true|read_as_visitor\ must\ be\ true
        basket_exceeds_eight_inputs|basket\ exceeds\ eight\ inputs
        tariff_code_must_be_dotted|tariff\ code\ must\ be\ dotted
        wrong_wage_table_identities|wrong\ wage\ table\ identities
        review_source_hash_missing|review\ source\ hash\ missing
        source_field_type_mismatch|source\ field\ type\ mismatch
        unknown_required_regression|unknown\ required\ regression
        pub_64_incomplete_receipt|PUB\-64\ incomplete\ receipt
        recorded_must_be_positive|recorded\ must\ be\ positive
        unconfirmed_source_columns|unconfirmed\ source\ columns
        pub_64_receipts_required|PUB\-64\ receipts\ required
        invalid_source_chain_hash|invalid\ source_chain\ hash
        selected_receipt_mismatch|selected\ receipt\ mismatch
        source_must_contain_rows|source\ must\ contain\ rows
        wrong_playbook_activities|wrong\ playbook\ activities
        duplicate_transit_period|duplicate\ transit\ period
        duplicate_utility_period|duplicate\ utility\ period
        incomplete_review_fields|incomplete\ review\ fields
        finite_decimal_required|finite\ Decimal\ required
        incomplete_shared_years|incomplete\ shared\ years
        missing_review_metadata|missing\ review\ metadata
        scale_must_be_positive|scale\ must\ be\ positive
        incomplete_source_chain|incomplete\ source_chain
        missing_terms_evidence|missing\ terms\ evidence
        invalid_selected_hash|invalid\ selected\ hash
        query_before_forecast|query\ before\ forecast
        review_lines_missing|review\ lines\ missing
        unknown_request_kind|unknown\ request\ kind
        unrecorded_r1_source|unrecorded\ R1\ source
        class_name_required|class\ name\ required
        missing_source_chain|missing\ source_chain
        coarse_tariff_line|coarse\ tariff\ line
        terms_words_missing|terms_words\ missing
        incomplete_receipt|incomplete\ receipt
        missing_activities|missing\ activities
        duplicate_request|duplicate\ request
        lic_cancelled_period_outside_the_c2_calendar|lic_cancelled\ period\ outside\ the\ C2\ calendar:\ .*
        unknown_or_missing_source_fields|unknown\ or\ missing\ source\ fields:\ .*
        missing_confirmed_contract_fields|.*\ missing\ confirmed\ contract\ fields
        duplicate_restaurant_source_row|.*:\ duplicate\ restaurant\ source\ row
        expected_positive_whole_number|.*:\ expected\ positive\ whole\ number
        year_four_digits_required|.*\ year:\ four\ digits\ required
        busy_besttime_request_failed|busy_besttime\ .*\ request_failed
        basket_line_source_mismatch|basket_line_source_mismatch:\ .*
        restaurant_rows_required|.*:\ restaurant\ rows\ required
        figure_table_unreachable|figure_table_unreachable:.*
        duplicate_wage_group|.*\ duplicate\ wage\ group
        basket_line_duplicate|basket_line_duplicate:\ .*
        trade_reconciliation|trade_reconciliation\ .*
        is_not_a_boolean|.*\ is\ not\ a\ boolean
        must_be_positive|.*\ must\ be\ positive
        refused_request|refused\ request:\ .*
        secret_in_output|.* secret_in_output
        request_failed|.* request_failed
        is_not_text|.*\ is\ not\ text
        changed_shape|.* changed_shape
        required|.*:\ required
        missing|missing\ .*
        expected_eight_digits_lengths_require_review|.*\ .*:\ expected\ eight\ digits;\ lengths\ require\ review
        missing_fields_unknown_fields|missing\ fields\ .*;\ unknown\ fields\ .*
        english_month_name_required|.*\ .*:\ English\ month\ name\ required
        one_component_required|.*:\ one\ component\ required:\ .*
        one_field_required_for|.*:\ one\ field\ required\ for\ .*
        unexpected_code_length|.*\ .*:\ unexpected\ code\ length
        zero_fraction_required|.*\ .*:\ zero\ fraction\ required
        integer_code_required|.*\ .*:\ integer\ code\ required
        outside_month_range|.*\ .*:\ outside\ month\ range
        integer_required|.*\ .*:\ integer\ required
        country_unmatched|.*\ country_unmatched:\ .*
        registry_fields|.*\ registry\ fields:\ .*
        source_fields|.*\ source\ fields:\ .*
        field_type|.*\ field\ type:\ .*
        unpinned|.*:unpinned:.*
        basket_line_source_mismatch|basket_line_source_mismatch:\ .*\ .*\ .*
        basket_line_unreviewed|basket_line_unreviewed:\ .*\ .*\ .*
    """),
        }
    )
)

UNEXPECTED: Mapping[type[Exception], str] = MappingProxyType(
    {
        CsvError: "csverror",
        InvalidOperation: "invalidoperation",
        PackageNotFoundError: "packagenotfounderror",
        JSONDecodeError: "jsondecodeerror",
        duckdb.Error: "duckdberror",
        yaml.YAMLError: "yamlerror",
        AttributeError: "attributeerror",
        FileNotFoundError: "filenotfounderror",
        ImportError: "importerror",
        IsADirectoryError: "isadirectoryerror",
        KeyError: "keyerror",
        NotADirectoryError: "notadirectoryerror",
        OSError: "oserror",
        PermissionError: "permissionerror",
        RuntimeError: "runtimeerror",
        StopIteration: "stopiteration",
        TypeError: "typeerror",
        UnicodeDecodeError: "unicodedecodeerror",
        UnicodeError: "unicodeerror",
        ValueError: "valueerror",
        ZeroDivisionError: "zerodivisionerror",
        AdditionError: "additionerror",
        AreaError: "areaerror",
        AssemblyError: "assemblyerror",
        AwardError: "awarderror",
        BaciError: "bacierror",
        BuildInputError: "buildinputerror",
        BuildingError: "buildingerror",
        CacheError: "cacheerror",
        CoolingError: "coolingerror",
        CreditError: "crediterror",
        DecimalRefusal: "decimalrefusal",
        FamilyError: "familyerror",
        FrameError: "frameerror",
        GraphError: "grapherror",
        HeightError: "heighterror",
        LayerError: "layererror",
        MunicipalityFrameRefused: "municipalityframerefused",
        PageError: "pageerror",
        PageShapeError: "pageshapeerror",
        ParseError: "parseerror",
        PlacesError: "placeserror",
        PlacesFsqError: "placesfsqerror",
        RegistryError: "registryerror",
        ReviewError: "reviewerror",
        SafeRefusal: "saferefusal",
        SeriesRefused: "seriesrefused",
        ShapeError: "shapeerror",
        SnapshotError: "snapshoterror",
        SpineError: "spineerror",
        TenderError: "tendererror",
    }
)

_NAMED_WORDS = frozenset(word for names in NAMED_REASONS.values() for word in names)
_TEXT_WORDS = frozenset(word for rows in TEXT_REASONS.values() for _, word in rows)
STAGE_WORDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        stage: _NAMED_WORDS
        | _TEXT_WORDS
        | frozenset({"review_unreadable"})
        | frozenset(
            [
                stage + "_unexpected",
                *(stage + "_unexpected_" + name for name in UNEXPECTED.values()),
            ]
        )
        for stage in STAGES
    }
)
