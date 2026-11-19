"""Paired-image thermal inspection with independent, saved thermal regions."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from PIL import Image

from solar_pv.imaging.annotations import load_annotations, save_annotations
from solar_pv.imaging.overlays import panel_overlay
from solar_pv.imaging.pairing import load_pairs
from solar_pv.imaging.thermal import (
    analyze_panels, compare_regions, load_paired_thermal_frame, measurement_basis,
    region_statistics, render_temperature_colorbar, render_temperature_grid,
    temperature_limits_c,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = PROJECT_ROOT / "examples/week10_12/inspection"
DEFAULT_LABELS = PROJECT_ROOT / "data/processed/week10_12_panel_annotations.csv"
CATEGORIES = {
    "unclassified": "Unclassified", "localized_heating": "Apparent localized heating",
    "uneven_appearance": "Uneven thermal appearance", "possible_shading": "Possible shading influence",
    "possible_soiling_or_obstruction": "Possible soiling or obstruction",
    "other_irregularity": "Other visual irregularity", "no_visible_anomaly": "No visible anomaly",
}
STATUSES = ["draft", "needs_verification", "reviewed", "resolved"]
SEVERITIES = ["unassigned", "low", "medium", "high"]


def _zoom(image: Image.Image, factor: int, x: float, y: float) -> Image.Image:
    if factor == 1:
        return image
    width, height = image.size
    crop_width, crop_height = width / factor, height / factor
    left = min(max(x * width - crop_width / 2, 0), width - crop_width)
    top = min(max(y * height - crop_height / 2, 0), height - crop_height)
    return image.crop((round(left), round(top), round(left + crop_width), round(top + crop_height)))


def _region_inputs(label: str, values: tuple[float, ...]) -> tuple[float, ...]:
    columns = st.columns(4)
    return tuple(columns[index].number_input(
        f"{label} {side}", min_value=0.0, max_value=1.0, value=float(values[index]),
        step=0.01, format="%.2f",
    ) for index, side in enumerate(("left", "top", "right", "bottom")))


st.set_page_config(page_title="Thermal review | Solar PV", layout="wide")
st.title("Thermal review")
st.caption("Paired RGB and thermal evidence. Numerical temperatures require a valid grid and measurement basis.")
root = Path(st.session_state.get("active_inspection_root", DEFAULT_ROOT)).expanduser().resolve()
labels_path = Path(st.session_state.get("active_annotation_path", DEFAULT_LABELS)).expanduser().resolve()
with st.expander("Inspection sources"):
    root = Path(st.text_input("Inspection folder", str(root))).expanduser().resolve()
    labels_path = Path(st.text_input("Annotation CSV", str(labels_path))).expanduser().resolve()
st.session_state["active_inspection_root"] = str(root)
st.session_state["active_annotation_path"] = str(labels_path)
try:
    pairs = load_pairs(root / "inspection_pairs.csv", root)
    annotations = load_annotations(labels_path)
except (OSError, ValueError) as exc:
    st.error(f"Could not load inspection sources: {exc}")
    st.stop()
if not pairs:
    st.info("No paired thermal sources are available in this inspection.")
    st.stop()
active = st.session_state.get("active_pair_id")
pair = st.selectbox("Image pair", pairs,
                    index=next((i for i, item in enumerate(pairs) if item.pair_id == active), 0),
                    format_func=lambda item: item.pair_id.replace("_", " ").title())
st.session_state["active_pair_id"] = pair.pair_id
st.session_state["active_pair_root"] = str(root)
try:
    frame = load_paired_thermal_frame(root, pair.thermal_path, pair.temperature_path, synthetic=pair.synthetic)
    with Image.open(root / pair.rgb_path) as source:
        rgb = source.copy()
    with Image.open(root / pair.thermal_path) as source:
        thermal_preview = source.copy()
except (OSError, ValueError, json.JSONDecodeError) as exc:
    st.error(f"Could not open image pair: {exc}")
    st.stop()
basis = measurement_basis(frame)
matching = [item for item in annotations if item.image_path == pair.rgb_path and item.target_type == "panel"]
aligned = pair.alignment_reviewed and rgb.size == thermal_preview.size == (frame.image_width, frame.image_height)
temperature_source_label = (
    f"Temperature grid: {pair.temperature_path}"
    if basis in {"synthetic_numeric_demo", "calibrated_numeric", "unverified_numeric"}
    else "Temperature grid: unavailable"
)
st.caption(f"RGB: {pair.rgb_path} · Thermal: {pair.thermal_path} · {temperature_source_label}")
st.caption(f"Capture: {frame.captured_at} · {frame.image_width} × {frame.image_height} pixels · Basis: {basis} · Calibration: {frame.calibration_status}")
if basis == "display_only" and frame.synthetic:
    st.info("Synthetic visual-only preview. Colors are illustrative and are not temperature measurements.")
elif frame.synthetic:
    st.warning("Synthetic demonstration only. The temperatures and capture time are generated examples.")
elif basis == "unverified_numeric":
    st.warning("Numerical data exists, but calibration is unverified. Absolute temperatures are disabled.")
elif basis == "display_only":
    st.info("Display-only thermal image. Its colors cannot be converted to absolute temperature.")
if not aligned:
    st.warning("RGB annotations are not transferred to this thermal image. Define an independent thermal region below.")

zoom_col, x_col, y_col = st.columns(3)
zoom = zoom_col.select_slider("Zoom", options=[1, 2, 3, 4], value=1)
center_x = x_col.slider("Horizontal center", 0.0, 1.0, 0.5, disabled=zoom == 1)
center_y = y_col.slider("Vertical center", 0.0, 1.0, 0.5, disabled=zoom == 1)
left, right = st.columns(2, gap="large")
left.markdown("**RGB image**")
left.image(_zoom(panel_overlay(rgb, matching), zoom, center_x, center_y), width="stretch")
left.caption(pair.rgb_path)
right.markdown("**Thermal image**")
thermal_scale = None
if aligned and basis in {"synthetic_numeric_demo", "calibrated_numeric"}:
    scale_min, scale_max = temperature_limits_c(frame, matching)
    thermal_scale = right.slider(
        "Thermal display range (°C)", min_value=int(scale_min), max_value=int(scale_max),
        value=(int(scale_min), int(scale_max)), step=1,
        help="Blue represents cooler values and red represents warmer values within this image. This is a display scale, not a universal fault threshold.",
    )
thermal_display = (
    render_temperature_grid(
        frame, min_c=thermal_scale[0], max_c=thermal_scale[1], annotations=matching,
    ) if thermal_scale else thermal_preview
)
right.image(_zoom(thermal_display, zoom, center_x, center_y), width="stretch")
right.caption(pair.thermal_path)
if thermal_scale:
    right.image(
        render_temperature_colorbar(*thermal_scale),
        caption="Thermal temperature color scale",
        width="stretch",
    )
    cool_label, warm_label = right.columns(2)
    cool_label.caption(f"↓ At/below {thermal_scale[0]} °C · cool blue")
    warm_label.caption(f"↑ At/above {thermal_scale[1]} °C · warmer red")
    right.caption("Between these values, colors transition from blue through yellow to red. Values outside the selected range use the endpoint colors.")
st.markdown("[Open Solar Farm Map](/site-layout)")
numeric = basis in {"synthetic_numeric_demo", "calibrated_numeric"}
if numeric and aligned:
    st.subheader("Panel comparisons")
    if basis == "synthetic_numeric_demo":
        st.caption("Synthetic example values. ΔT compares each labeled panel with its two nearest labeled panels.")
    else:
        st.caption("ΔT compares each labeled panel with its two nearest labeled panels in the reviewed aligned pair.")
    threshold_c = st.slider("Candidate review threshold (ΔT °C)", 0.0, 20.0, 5.0, 0.5)
    try:
        panel_results = analyze_panels(
            frame, annotations, image_path=pair.rgb_path, threshold_c=threshold_c,
        )
    except ValueError as exc:
        st.warning(f"Panel comparison unavailable: {exc}")
    else:
        if panel_results:
            st.dataframe([{
                "Panel ID": item.asset_id,
                "Panel median (°C)": round(item.median_c, 2),
                "Nearby reference median (°C)": round(item.reference_c, 2) if item.reference_c is not None else None,
                "ΔT (°C)": round(item.delta_c, 2) if item.delta_c is not None else None,
                "Review candidate": "Review" if item.candidate else "No threshold flag",
            } for item in panel_results], hide_index=True, width="stretch")
            st.caption("A threshold flag is a review prompt, not a confirmed defect or root cause.")
        else:
            st.info("No panel labels match this paired RGB image, so no panel comparison is available.")
if not matching:
    st.info("Add a panel annotation to link an observation to this image pair.")
    st.stop()
row = st.selectbox("Linked annotation", matching,
                   format_func=lambda item: f"{item.annotation_id} · {item.linked_asset_id or item.asset_id or 'unmapped'}")
st.caption(f"Asset mapping: {row.mapping_status} · Source: {row.source_provenance} · Reviewer note: {row.reviewer_notes or 'none'}")

current = tuple(float(part) for part in row.thermal_region_bounds.split(",")) if row.thermal_region_bounds else (0.1, 0.1, 0.9, 0.9)
if numeric:
    st.subheader("Thermal region")
    st.caption("Coordinates are normalized to the thermal image. Choose independently, or copy a reviewed aligned RGB box.")
    if aligned and st.button("Copy reviewed RGB box into region controls"):
        st.session_state[f"thermal_box_{row.annotation_id}"] = (row.x_min, row.y_min, row.x_max, row.y_max)
    current = st.session_state.get(f"thermal_box_{row.annotation_id}", current)
with st.form(f"thermal_finding_{row.annotation_id}"):
    if numeric:
        selected_bounds = _region_inputs("Selected", current)
        use_reference = st.checkbox("Use separate reference region", value=bool(row.thermal_reference_bounds))
        reference_bounds = None
        if use_reference:
            previous = tuple(float(part) for part in row.thermal_reference_bounds.split(",")) if row.thermal_reference_bounds else (0.05, 0.05, 0.25, 0.25)
            reference_bounds = _region_inputs("Reference", previous)
    category = st.selectbox("Observation category", list(CATEGORIES),
                            index=list(CATEGORIES).index(row.observation_category), format_func=CATEGORIES.get)
    status = st.selectbox("Review status", STATUSES, index=STATUSES.index(row.finding_status))
    severity = st.selectbox("Reviewer severity", SEVERITIES, index=SEVERITIES.index(row.severity))
    note = st.text_area("Reviewer note", value=row.observation_note)
    save = st.form_submit_button("Save observation")
stats = None
if numeric:
    try:
        stats = region_statistics(frame, row.annotation_id, selected_bounds)
        st.dataframe([{
            "Minimum": stats.minimum, "Maximum": stats.maximum, "Mean": round(stats.mean, 2),
            "Median": stats.median, "Samples": stats.sample_count, "Excluded": stats.excluded_count,
            "Unit": stats.unit, "Measurement basis": stats.measurement_basis,
        }], hide_index=True, width="stretch")
        if reference_bounds is not None:
            comparison = compare_regions(stats, region_statistics(frame, row.annotation_id + ":reference", reference_bounds))
            st.caption(f"Selected median minus reference median: {comparison.delta_median:+.2f} {stats.unit}. No fault threshold is applied.")
    except ValueError as exc:
        st.warning(f"Region measurement unavailable: {exc}")
if save:
    if numeric and stats is None:
        st.error("Correct the thermal region before saving.")
    else:
        updated = replace(
            row, observation_category=category, finding_status=status, severity=severity,
            observation_note=note.strip(), modified_at_utc=datetime.now(timezone.utc).isoformat(),
            thermal_region_bounds=",".join(map(str, selected_bounds)) if numeric else row.thermal_region_bounds,
            thermal_reference_bounds=",".join(map(str, reference_bounds)) if numeric and reference_bounds else "",
        )
        try:
            save_annotations(labels_path, [updated if item.annotation_id == row.annotation_id else item for item in annotations])
            st.success("Observation saved. Open Inspection review for the exportable record.")
        except (OSError, ValueError) as exc:
            st.error(f"Could not save observation: {exc}")
