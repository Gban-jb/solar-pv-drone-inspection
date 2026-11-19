"""Engineering drawing viewport and registry-backed electrical asset navigation."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from PIL import Image

from solar_pv.domain.assets import AssetRegistry, build_design_registry
from solar_pv.imaging.drawings import DRAWING_VIEWS, drawing_view, load_drawing_image
from solar_pv.imaging.overlays import panel_overlay
from solar_pv.storage.asset_evidence import find_asset_evidence
from solar_pv.storage.site_registry import load_site_spec, verify_source_document
from solar_pv.ui.drawing_viewer import drawing_viewer_html


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = PROJECT_ROOT / "configs/sites/aamu_2023_review.json"
IMAGE_ROOT = Path(__file__).resolve().parent / "assets/drawings"
EVIDENCE_INDEX = Path(os.environ.get(
    "SOLAR_PV_EVIDENCE_INDEX", str(PROJECT_ROOT / "data/processed/asset_evidence_index.json")
))


@st.cache_resource(show_spinner=False)
def _registry(spec_mtime_ns: int) -> AssetRegistry:
    del spec_mtime_ns
    return build_design_registry(load_site_spec(SPEC_PATH))


@st.cache_data(show_spinner=False)
def _image_bytes(sheet: str, image_mtime_ns: int) -> bytes:
    del image_mtime_ns
    return load_drawing_image(drawing_view(sheet), load_site_spec(SPEC_PATH), PROJECT_ROOT, IMAGE_ROOT)


def _on_inverter_change() -> None:
    st.session_state["site_map_string"] = None
    st.session_state["site_map_module"] = None
    chosen = st.session_state.get("site_map_inverter")
    if chosen:
        st.session_state["site_map_drawing"] = "WP101.2" if chosen.endswith(("01", "02", "03", "04")) else "WP101.1"


def _on_string_change() -> None:
    st.session_state["site_map_module"] = None


def _asset_label(registry: AssetRegistry, asset_id: str | None) -> str:
    if asset_id is None:
        return "Select an asset"
    asset = registry.get(asset_id)
    if asset is None:
        return asset_id
    short_label = (
        f"MOD-{asset.sequence_number:02d}" if asset.kind == "module" and asset.sequence_number
        else asset.drawing_label or asset.asset_id
    )
    return f"{short_label} · {asset.asset_id}"


st.set_page_config(page_title="Solar Farm Map | Solar PV", layout="wide")
st.title("Solar Farm Map")
st.caption("Alabama A&M Solar Project · engineering design reference")
st.markdown(
    """
    <style>
    .site-layout-notice {
        border: 1px solid var(--fb-rule); border-left: 3px solid var(--fb-green);
        border-radius: 5px; padding: .75rem .9rem; margin: .6rem 0 1.25rem;
        background: var(--fb-surface); color: var(--fb-ink); font-size: .88rem;
        line-height: 1.5;
    }
    .site-layout-notice strong { display: block; margin-bottom: .15rem; }
    .st-key-site-asset-card { border-left: 3px solid var(--fb-green) !important; }
    .site-layout-empty {
        border-top: 1px solid var(--fb-rule); margin-top: .8rem;
        padding-top: .8rem; color: var(--fb-muted); font-size: .88rem;
    }
    .st-key-site-layout-workspace button[data-variant="segmented_control"][data-selected="true"] {
        border-color: var(--fb-green) !important; color: var(--fb-green) !important;
        background: var(--fb-hover) !important;
    }
    @media (max-width: 950px) {
        .st-key-site-layout-workspace [data-testid="stHorizontalBlock"] {
            flex-direction: column !important; gap: 1.4rem !important;
        }
        .st-key-site-layout-workspace [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            width: 100% !important; flex: 1 1 auto !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    registry = _registry(SPEC_PATH.stat().st_mtime_ns)
    verify_source_document(registry.site, PROJECT_ROOT)
except (OSError, ValueError) as exc:
    st.error(f"Site layout is unavailable: {exc}")
    st.stop()

st.markdown(
    '<div class="site-layout-notice"><strong>Design reference only</strong>'
    '2023 review drawings. Asset IDs are design candidates without surveyed or '
    'field-verified locations. Use the electrical list to navigate; no physical '
    'module or inverter markers are placed on the drawing.</div>',
    unsafe_allow_html=True,
)

if "site_map_drawing" not in st.session_state:
    st.session_state["site_map_drawing"] = "WI101"
if st.session_state["site_map_drawing"] not in {view.sheet for view in DRAWING_VIEWS}:
    st.session_state["site_map_drawing"] = "WI101"

workspace = st.container(key="site-layout-workspace")
drawing_col, asset_col = workspace.columns([2.3, 1], gap="large")
with drawing_col:
    st.segmented_control(
        "Drawing",
        [view.sheet for view in DRAWING_VIEWS],
        format_func=lambda sheet: drawing_view(sheet).title,
        key="site_map_drawing",
    )
    view = drawing_view(st.session_state["site_map_drawing"])
    image_path = IMAGE_ROOT / view.image_name
    if not image_path.is_file():
        st.error(f"Drawing preview missing for {view.sheet}: {image_path}")
    else:
        try:
            content = _image_bytes(view.sheet, image_path.stat().st_mtime_ns)
        except (OSError, ValueError) as exc:
            st.error(f"Could not load {view.sheet}: {exc}")
        else:
            viewer_height = 480 if view.sheet == "WP101.1" else 620
            st.iframe(
                drawing_viewer_html(view, content, height_px=viewer_height),
                height=viewer_height + 5,
                alt=f"Zoomable engineering drawing {view.sheet}, PDF page {view.pdf_page}",
            )
            st.caption(
                f"{view.sheet} · PDF page {view.pdf_page} · cropped drawing preview. "
                "Zoom and pan explore the drawing; they do not establish site coordinates."
            )

with asset_col:
    st.subheader("Electrical assets")
    st.caption("Type in a selector to search the registry.")
    inverter_ids = [asset.asset_id for asset in registry.children_of(registry.site.site_id)]
    if st.session_state.get("site_map_inverter") not in [None, *inverter_ids]:
        st.session_state["site_map_inverter"] = None
    inverter_id = st.selectbox(
        "Inverter", [None, *inverter_ids],
        format_func=lambda item: _asset_label(registry, item),
        key="site_map_inverter", on_change=_on_inverter_change,
    )
    string_ids = [asset.asset_id for asset in registry.children_of(inverter_id)] if inverter_id else []
    if st.session_state.get("site_map_string") not in [None, *string_ids]:
        st.session_state["site_map_string"] = None
    st.caption(f"{len(string_ids)} expected strings" if inverter_id else "Choose an inverter to see its strings")
    string_id = st.selectbox(
        "String", [None, *string_ids],
        format_func=lambda item: _asset_label(registry, item),
        key="site_map_string", on_change=_on_string_change,
        disabled=not inverter_id,
    )
    module_ids = [asset.asset_id for asset in registry.children_of(string_id)] if string_id else []
    if st.session_state.get("site_map_module") not in [None, *module_ids]:
        st.session_state["site_map_module"] = None
    st.caption(f"{len(module_ids)} expected modules" if string_id else "Choose a string to see its modules")
    module_id = st.selectbox(
        "Module", [None, *module_ids],
        format_func=lambda item: _asset_label(registry, item),
        key="site_map_module", disabled=not string_id,
    )

    selected = registry.get(module_id or string_id or inverter_id or registry.site.site_id)
    try:
        linked_evidence, evidence_warnings = find_asset_evidence(
            EVIDENCE_INDEX, registry, selected.asset_id
        )
    except (OSError, ValueError) as exc:
        linked_evidence, evidence_warnings = [], [f"Evidence index unavailable: {exc}"]
    st.subheader("Asset information")
    with st.container(border=True, key="site-asset-card"):
        st.markdown(f"**{selected.asset_id}**")
        st.caption(f"{selected.kind.title()} · {selected.drawing_label or 'Generated design ID'}")
        st.write(f"Source drawing: **{selected.source_sheet}**")
        st.write("Mapping status: **Design candidate · physical position unverified**")
        if selected.kind == "inverter":
            st.write(f"Expected strings: **{len(string_ids)}**")
        elif selected.kind == "string":
            st.write(f"Expected modules: **{len(module_ids)}**")
        elif selected.kind == "module":
            st.caption("Module number is an electrical sequence, not a mapped panel position.")
        else:
            st.write("Design scope: **8 inverters · 94 strings · 2,538 modules**")
        if not linked_evidence:
            st.markdown(
                '<div class="site-layout-empty">No linked inspection evidence for this asset.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption(f"{len(linked_evidence)} linked image annotation(s) · review status below")
    for warning in evidence_warnings:
        st.warning(warning)
    if linked_evidence:
        st.subheader(f"Linked image evidence ({len(linked_evidence)})")
        st.caption("Manual links are provisional unless reviewed against an approved source.")
        for evidence in linked_evidence:
            row = evidence.annotation
            with st.expander(f"{row.annotation_id} · {row.image_path}"):
                st.write(f"Linked asset: **{row.linked_asset_id}**")
                method = row.mapping_method.replace("_", " ").capitalize() if row.mapping_method else "Unknown method"
                st.write(f"Mapping: **{row.mapping_status.capitalize()}** · {method}")
                if row.mapping_evidence:
                    st.caption(f"Approved mapping source: {row.mapping_evidence}")
                synthetic = row.source_provenance == "synthetic" or bool(evidence.pair and evidence.pair.synthetic)
                st.caption("SYNTHETIC PRACTICE" if synthetic else f"Source provenance: {row.source_provenance}")
                st.caption(f"Image ID: {row.source_image_id} · Box coordinates: normalized 0–1")
                metadata = evidence.image_metadata
                if metadata.get("status") != "error":
                    st.caption(
                        f"Capture time: {metadata.get('capture_time_raw') or 'Unavailable'} · "
                        f"Camera: {metadata.get('camera_model') or 'Unavailable'} · "
                        f"Size: {metadata.get('width')} × {metadata.get('height')} px"
                    )
                    latitude, longitude = metadata.get("gps_latitude"), metadata.get("gps_longitude")
                    st.caption(
                        f"Image GPS: {latitude}, {longitude} (accuracy unverified)"
                        if latitude is not None and longitude is not None else "Image GPS unavailable"
                    )
                    st.caption(
                        "Altitude, camera pose, calibration, RTK status and coordinate "
                        "reference system: not established from this image."
                    )
                    try:
                        with Image.open(evidence.source.inspection_root / row.image_path) as image:
                            st.image(panel_overlay(image, [row], highlight_id=row.annotation_id), width="stretch")
                    except OSError as exc:
                        st.warning(f"Could not preview the RGB image: {exc}")
                if evidence.pair:
                    st.caption(f"Thermal pair: {evidence.pair.thermal_path}")
                    if evidence.observation and evidence.observation.radiometric_valid:
                        st.caption("Readable pixel temperatures are available in the paired source; see Inspection review.")
                    elif evidence.observation and not evidence.observation.radiometric_valid:
                        st.caption("Thermal preview only · no readable pixel temperatures")
                    elif evidence.pair.temperature_path:
                        st.caption("Temperature source is paired, but its validity is not established here.")
                    else:
                        st.caption("Thermal preview only · no readable pixel temperatures")
                    try:
                        with Image.open(evidence.source.inspection_root / evidence.pair.thermal_path) as thermal:
                            st.image(thermal, width="stretch")
                    except OSError as exc:
                        st.warning(f"Could not preview the thermal image: {exc}")
                else:
                    st.caption("No explicit RGB/thermal pair is linked to this image.")
                if row.observation_note:
                    st.write(f"Observation: **{row.observation_note}**")
                    st.caption(f"Possible cause: {row.possible_cause or 'Unknown'} · Review: {row.observation_review_status}")
                if evidence.observation:
                    st.caption(
                        f"Inspection observation {evidence.observation.record_id} · "
                        f"ΔT: {evidence.observation.delta_t_c if evidence.observation.delta_t_c is not None else 'Unavailable'} °C"
                    )
                for issue in evidence.warnings:
                    st.warning(issue)
                if st.button(
                    "Open highlighted annotation", key=f"open-evidence:{row.annotation_id}",
                    disabled=metadata.get("status") == "error",
                ):
                    st.session_state["active_inspection_root"] = str(evidence.source.inspection_root)
                    st.session_state["active_annotation_path"] = str(evidence.source.annotation_file)
                    st.session_state["active_pair_rgb_path"] = row.image_path
                    st.session_state["week04_image"] = evidence.source.inspection_root / row.image_path
                    st.session_state["week04_selected_id"] = row.annotation_id
                    st.session_state["week04_edit_id"] = row.annotation_id
                    st.session_state["week04_asset_id"] = row.asset_id
                    st.session_state["week04_target_type"] = row.target_type
                    st.session_state["week04_review_status"] = row.review_status
                    st.session_state["week04_reset_editor"] = False
                    st.session_state["week04_canvas_revision"] = st.session_state.get("week04_canvas_revision", 0) + 1
                    st.switch_page("annotator.py")

    if module_ids:
        with st.expander(f"All {len(module_ids)} module records"):
            st.dataframe(
                [
                    {"Sequence": registry.get(item).sequence_number, "Candidate ID": item,
                     "Mapping": "Unverified"}
                    for item in module_ids
                ],
                hide_index=True, width="stretch", height=240,
            )
    with st.expander("Array block types in WI101"):
        groups = registry.site.rack_groups
        selected_group = st.selectbox(
            "Rack block type",
            [None, *range(len(groups))],
            format_func=lambda index: (
                "Choose a block type" if index is None else
                f"{groups[index].count} blocks · {groups[index].modules_high} high × {groups[index].modules_wide} wide"
            ),
        )
        if selected_group is not None:
            group = groups[selected_group]
            st.write(f"Expected modules in this group: **{group.module_count:,}**")
            st.caption("WI101 gives group counts, not individual rack IDs or a string-to-rack mapping.")
