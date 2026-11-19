"""Combined inspection scan, paired image review, and observation export."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

import streamlit as st
from PIL import Image

from solar_pv.api.observations import observations_csv_v03, observations_json_v03
from solar_pv.domain.assets import build_design_registry
from solar_pv.domain.inspection import review_pairs
from solar_pv.imaging.annotations import load_annotations
from solar_pv.imaging.overlays import panel_overlay
from solar_pv.imaging.pairing import load_pairs
from solar_pv.imaging.thermal import (
    load_paired_thermal_frame,
    measurement_basis,
    render_temperature_grid,
    temperature_limits_c,
)
from solar_pv.ingestion.importer import scan_inspection
from solar_pv.storage.site_registry import load_site_spec


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = PROJECT_ROOT / "examples/week10_12/inspection"
DEFAULT_LABELS = PROJECT_ROOT / "data/processed/week10_12_panel_annotations.csv"
LEGACY_EXAMPLE_LABELS = PROJECT_ROOT / "examples/week10_12/output/panel_annotations.csv"
SITE_SPEC = PROJECT_ROOT / "configs/sites/aamu_2023_review.json"

if st.session_state.get("active_annotation_path") == str(LEGACY_EXAMPLE_LABELS):
    st.session_state["active_annotation_path"] = str(DEFAULT_LABELS)

st.set_page_config(page_title="Inspection review | Solar PV", layout="wide")
st.markdown(
    """
    <style>
    .block-container { max-width: 1320px; padding-bottom: 3rem; }
    h1 { font-size: 1.85rem; font-weight: 650; letter-spacing: 0; }
    h2, h3 { letter-spacing: 0; }
    div.stButton > button, div.stDownloadButton > button { border-radius: 4px; }
    div.stButton > button[kind="primary"] {
        background: #245844; border-color: #245844; color: white;
    }
    div.stButton > button[kind="primary"]:hover {
        background: #194631; border-color: #194631; color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Inspection review")
with st.expander("Files and output", expanded=False):
    root_text = st.text_input(
        "Inspection folder",
        str(st.session_state.get("active_inspection_root", DEFAULT_ROOT)),
    )
    label_text = st.text_input(
        "Panel labels CSV",
        str(st.session_state.get("active_annotation_path", DEFAULT_LABELS)),
    )
root = Path(root_text).expanduser().resolve()
label_path = Path(label_text).expanduser().resolve()
st.session_state["active_inspection_root"] = str(root)
st.session_state["active_annotation_path"] = str(label_path)

if not root.is_dir():
    st.error(f"Inspection folder not found: {root}")
    st.stop()
if root == DEFAULT_ROOT.resolve():
    st.caption("Synthetic paired images and SCADA. No site files or camera temperatures have been tested.")

if st.button("Scan inspection", type="primary"):
    try:
        st.session_state["review_manifest"] = scan_inspection(root)
    except OSError as exc:
        st.error(f"Could not scan inspection: {exc}")
manifest = st.session_state.get("review_manifest")
if manifest and manifest["source_root"] == str(root):
    summary = manifest["summary"]
    st.caption(
        f"{summary['images_opened']}/{summary['images_found']} images opened  ·  "
        f"{summary['image_errors']} errors  ·  "
        f"{summary['scada_files_opened']}/{summary['scada_files_found']} SCADA CSVs opened"
    )
    for issue in manifest["folder_issues"]:
        st.warning(issue)
    for item in (*manifest["images"], *manifest["scada"]):
        if item["status"] == "error":
            st.error(f"{item['path']}: {item['error']}")

pair_file = root / "inspection_pairs.csv"
if not pair_file.is_file():
    st.info("No image pairs have been set up for this inspection yet.")
    st.markdown("[Set up image pairs](/intake)")
    st.stop()

try:
    pairs = load_pairs(pair_file, root)
    annotations = load_annotations(label_path)
except (OSError, ValueError) as exc:
    st.error(f"Could not load inspection review files: {exc}")
    st.stop()
if not pairs:
    st.info("No image pairs are listed for this inspection.")
    st.stop()

try:
    registry = build_design_registry(load_site_spec(SITE_SPEC))
except (OSError, ValueError) as exc:
    registry = None
    st.warning(f"Could not check linked asset IDs against the site registry: {exc}")
reviews = review_pairs(root, pairs, annotations, registry=registry)
included = [review for review in reviews if review.included]
all_observations = [item for review in included for item in review.observations]
st.subheader("Inspection overview")
st.caption(
    f"{len(pairs)} image pairs  ·  {len(included)} included in export  ·  "
    f"{len(pairs) - len(included)} excluded  ·  {len(all_observations)} observations  ·  "
    f"{sum(item.candidate for item in all_observations)} candidates"
)
st.dataframe(
    [
        {
            "Image pair": review.pair.pair_id.replace("_", " ").title(),
            "Export": "Included" if review.included else "Excluded",
            "Reason": review.reason or "Ready",
            "Alignment": "Reviewed" if review.pair.alignment_reviewed else "Not reviewed",
            "Panel labels": review.panel_count,
            "Thermal data": review.thermal_status,
            "Observations": len(review.observations),
            "Candidates": sum(item.candidate for item in review.observations),
        }
        for review in reviews
    ],
    hide_index=True,
    width="stretch",
)
for review in reviews:
    if review.reason:
        st.warning(f"{review.pair.pair_id}: excluded from export because {review.reason}.")
st.caption("Display-only thermal pairs can still export panel observations; their temperatures and ΔT are unavailable.")

st.subheader("Export inspection")
if all_observations:
    if any(item.synthetic for item in all_observations):
        st.caption("The export contains synthetic records. Asset IDs and temperature values are unverified.")
    csv_col, json_col = st.columns(2)
    csv_col.download_button(
        "Download observation CSV",
        observations_csv_v03(all_observations),
        file_name=f"{root.name}_observations.csv",
        mime="text/csv",
        use_container_width=True,
    )
    json_col.download_button(
        "Download observation JSON",
        observations_json_v03(all_observations),
        file_name=f"{root.name}_observations.json",
        mime="application/json",
        use_container_width=True,
    )
else:
    st.info("No pairs have exportable panel observations yet. Review the reasons above.")

active_pair_id = (
    st.session_state.get("active_pair_id")
    if st.session_state.get("active_pair_root") == str(root)
    else None
)
initial_pair_index = next(
    (index for index, pair in enumerate(pairs) if pair.pair_id == active_pair_id),
    0,
)
st.subheader("Review image pair")
selected_review = st.selectbox(
    "Choose a pair",
    reviews,
    index=initial_pair_index,
    format_func=lambda review: review.pair.pair_id.replace("_", " ").title(),
)
selected_pair = selected_review.pair
if selected_review.reason:
    st.warning(f"Excluded from export: {selected_review.reason}")
else:
    st.caption(f"Included in export · {len(selected_review.observations)} observations")
st.session_state["active_pair_rgb_path"] = selected_pair.rgb_path
st.session_state["active_pair_id"] = selected_pair.pair_id
st.session_state["active_pair_root"] = str(root)
matching = [row for row in annotations if row.image_path == selected_pair.rgb_path and row.target_type == "panel"]
try:
    frame = load_paired_thermal_frame(
        root,
        selected_pair.thermal_path,
        selected_pair.temperature_path,
        synthetic=selected_pair.synthetic,
    )
    with Image.open(root / selected_pair.rgb_path) as rgb, Image.open(root / selected_pair.thermal_path) as thermal:
        same_dimensions = rgb.size == thermal.size == (frame.image_width, frame.image_height)
    alignment_usable = selected_pair.alignment_reviewed and same_dimensions
    current = list(selected_review.observations)
except (OSError, ValueError, json.JSONDecodeError) as exc:
    st.error(f"Could not review this pair: {exc}")
    st.stop()

if measurement_basis(frame) in {"synthetic_numeric_demo", "calibrated_numeric"}:
    with st.expander("Thermal color scale", expanded=False):
        default_min, default_max = temperature_limits_c(frame, matching if alignment_usable else [])
        range_min_col, range_max_col = st.columns(2)
        range_min = range_min_col.number_input(
            "Cool end (°C)", value=default_min, step=1.0, key="review_scale_min"
        )
        range_max = range_max_col.number_input(
            "Hot end (°C)", value=default_max, step=1.0, key="review_scale_max"
        )
    if range_min >= range_max:
        st.error("The hot end must be greater than the cool end.")
        st.stop()
else:
    range_min = range_max = None

image_area, findings_area = st.columns([2.45, 1], gap="large")
rgb_col, thermal_col = image_area.columns(2, gap="small")
rgb_col.markdown('<div class="fieldbook-image-label">RGB IMAGE</div>', unsafe_allow_html=True)
with Image.open(root / selected_pair.rgb_path) as source:
    rgb_col.image(panel_overlay(source, matching), width="stretch")
rgb_col.caption(selected_pair.rgb_path)
if measurement_basis(frame) in {"synthetic_numeric_demo", "calibrated_numeric"}:
    thermal_source = render_temperature_grid(
        frame, min_c=range_min, max_c=range_max,
        annotations=matching if alignment_usable else [],
    )
else:
    with Image.open(root / selected_pair.thermal_path) as source:
        thermal_source = source.copy()
readings = {item.annotation_id: (item.delta_t_c, item.candidate) for item in current}
thermal_labels = matching if alignment_usable else []
thermal_col.markdown(
    '<div class="fieldbook-image-label">'
    + ('THERMAL · ' + frame.unit if measurement_basis(frame) in {"synthetic_numeric_demo", "calibrated_numeric"} else 'THERMAL PREVIEW')
    + '</div>',
    unsafe_allow_html=True,
)
thermal_col.image(panel_overlay(thermal_source, thermal_labels, readings), width="stretch")
thermal_col.caption(selected_pair.thermal_path)
if measurement_basis(frame) in {"synthetic_numeric_demo", "calibrated_numeric"}:
    thermal_col.markdown(
        f'<div style="height:12px;border-radius:2px;background:linear-gradient(90deg,#274c77,#3b82a0,#70a39b,#d9c76a,#e8924a,#c94a3c)"></div>'
        f'<div style="display:flex;justify-content:space-between;font-size:0.8rem;color:#5f6b66;margin-top:3px"><span>{range_min:g} °C · cool</span><span>{(range_min + range_max) / 2:g} °C</span><span>{range_max:g} °C · hot</span></div>',
        unsafe_allow_html=True,
    )
    thermal_col.caption("Only labeled panel areas are colorized; the background stays neutral. Blue is cooler and red is hotter. This scale is for viewing, not fault classification.")

finding_rows = []
for item in sorted(current, key=lambda observation: not observation.candidate):
    identity = item.linked_asset_id or item.asset_id or "Unassigned"
    if item.linked_asset_id:
        identity += f" · {item.mapping_status}"
    displayed_value = (
        f"{item.delta_t_c:+.1f} °C ΔT"
        if item.candidate and item.delta_t_c is not None
        else f"{item.median_temperature_c:.1f} °C"
        if item.median_temperature_c is not None
        else "Unavailable"
    )
    description = (
        "Warmer than nearby panels"
        if item.candidate
        else f"Nearby reference {item.reference_temperature_c:.1f} °C"
        if item.reference_temperature_c is not None
        else "No nearby reference"
        if item.radiometric_valid
        else "No readable pixel temperatures"
    )
    finding_rows.append(
        f'<div class="fb-finding{" candidate" if item.candidate else ""}">'
        f'<div class="fb-finding-top"><span>{escape(identity)}</span>'
        f'<strong>{escape(displayed_value)}</strong></div>'
        f'<p>{description}</p></div>'
    )
findings_area.markdown(
    '<div class="fieldbook-findings">'
    f'<div class="fb-findings-head">Findings <span>{sum(item.candidate for item in current)} candidate'
    f'{"s" if sum(item.candidate for item in current) != 1 else ""} · {len(current)} panels</span></div>'
    + ("".join(finding_rows) if finding_rows else '<div class="fb-finding"><p>No reviewed panel observations for this pair.</p></div>')
    + '</div>',
    unsafe_allow_html=True,
)

if measurement_basis(frame) not in {"synthetic_numeric_demo", "calibrated_numeric"}:
    st.warning("This image has no readable pixel temperatures. ΔT is unavailable.")
if not same_dimensions:
    st.warning("The RGB and thermal image dimensions differ. Panel overlays and temperature comparisons are disabled.")
elif not selected_pair.alignment_reviewed:
    st.warning("Image alignment has not been reviewed. Confirm the match in New inspection before transferring panel boxes.")
if not matching:
    st.info("No saved panel labels match this RGB image.")

st.caption(f"{len(current)} labeled panels  ·  {sum(item.candidate for item in current)} review candidates")
if current:
    st.subheader("Observations")
    st.dataframe(
        [
            {
                "Panel ID": item.asset_id or "Unassigned",
                "Registry asset": item.linked_asset_id or "Unmapped",
                "Mapping": item.mapping_status.capitalize(),
                "Observation": item.observation_note or "None entered",
                "Category": item.observation_category.replace("_", " "),
                "Finding status": item.finding_status.replace("_", " "),
                "Reviewer severity": item.severity,
                "Box review": item.box_review_status.capitalize(),
                "Median °C": round(item.median_temperature_c, 1) if item.median_temperature_c is not None else "Unavailable",
                "Nearby °C": round(item.reference_temperature_c, 1) if item.reference_temperature_c is not None else "Unavailable",
                "ΔT °C": round(item.delta_t_c, 1) if item.delta_t_c is not None else "Unavailable",
                "Thermal minimum": item.minimum_temperature if item.minimum_temperature is not None else "Unavailable",
                "Thermal maximum": item.maximum_temperature if item.maximum_temperature is not None else "Unavailable",
                "Thermal mean": item.mean_temperature if item.mean_temperature is not None else "Unavailable",
                "Pixel samples": item.sample_count if item.sample_count is not None else "Unavailable",
                "Measurement basis": item.measurement_basis,
                "Electrical comparison": item.correlation_status,
                "Flag": "Candidate" if item.candidate else "None",
                "Data quality": ", ".join(item.data_quality_flags),
            }
            for item in current
        ],
        hide_index=True,
        width="stretch",
    )

st.subheader("Electrical evidence relationship")
st.caption("Marshall's meter exports are available on Meter data. Their scope and timezone are not verified, so no panel-level reading or time correlation is attached to these findings.")
st.markdown("[Inspect meter data and quality](/meter)")
st.markdown("[Open thermal region review](/thermal)")
