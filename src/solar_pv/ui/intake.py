"""Guided inspection file scan and RGB/thermal pairing setup."""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

from solar_pv.imaging.pairing import ImagePair, load_pairs, save_pairs
from solar_pv.imaging.thermal import load_thermal_frame
from solar_pv.ingestion.importer import scan_inspection


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INSPECTION = PROJECT_ROOT / "examples/week10_12/inspection"

st.set_page_config(page_title="New inspection | Solar PV", layout="wide")
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


def _pair_id(rgb_path: str, thermal_path: str) -> str:
    joined = f"{Path(rgb_path).stem}_{Path(thermal_path).stem}".lower()
    return re.sub(r"[^a-z0-9_-]+", "_", joined).strip("_-")[:64] or "image_pair"


def _show_preview(column, root: Path, record: dict, title: str) -> None:
    path = root / record["path"]
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((900, 640), Image.Resampling.LANCZOS)
        column.image(image, width="stretch")
        column.caption(f"{title}: {record['path']} · {record['width']} × {record['height']} px")
    except OSError as exc:
        column.error(f"Could not preview {record['path']}: {exc}")


st.title("New inspection")
st.caption("Scan a folder, choose an RGB and thermal pair, review the match, and save it for Inspection Review.")

with st.expander("Inspection folder", expanded=True):
    folder_text = st.text_input(
        "Folder containing rgb/, thermal/, and optional scada/ folders",
        str(st.session_state.get("active_inspection_root", DEFAULT_INSPECTION)),
    )
root = Path(folder_text).expanduser().resolve()
if root != DEFAULT_INSPECTION.resolve() or "active_inspection_root" in st.session_state:
    st.session_state["active_inspection_root"] = str(root)

if st.button("Scan inspection folder", type="primary"):
    try:
        st.session_state["intake_manifest"] = scan_inspection(root)
        st.session_state["intake_root"] = str(root)
        st.session_state["active_inspection_root"] = str(root)
    except (OSError, ValueError) as exc:
        st.error(f"Could not scan the inspection folder: {exc}")

manifest = st.session_state.get("intake_manifest")
if not manifest or st.session_state.get("intake_root") != str(root):
    st.info("Scan the folder to review available files and create an image pair.")
    st.stop()

summary = manifest["summary"]
metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Images opened", f"{summary['images_opened']} / {summary['images_found']}")
metric_b.metric("Image errors", summary["image_errors"])
metric_c.metric("SCADA CSVs opened", f"{summary['scada_files_opened']} / {summary['scada_files_found']}")

for issue in manifest["folder_issues"]:
    st.warning(issue)
for record in manifest["images"]:
    if record["status"] == "error":
        st.error(f"{record['path']}: {record['error']}")

usable = [record for record in manifest["images"] if record["status"] != "error"]
rgb_records = [record for record in usable if record["kind"] == "rgb"]
thermal_records = [record for record in usable if record["kind"] == "thermal"]
if not rgb_records or not thermal_records:
    st.warning("A pair needs at least one readable image in both rgb/ and thermal/.")
    st.stop()

st.subheader("Choose images")
rgb_record = st.selectbox(
    "RGB image",
    rgb_records,
    format_func=lambda row: f"{row['path']}  ·  {row['width']} × {row['height']} px",
    key="intake_rgb_choice",
)
thermal_record = st.selectbox(
    "Thermal image",
    thermal_records,
    format_func=lambda row: f"{row['path']}  ·  {row['width']} × {row['height']} px",
    key="intake_thermal_choice",
)

rgb_path = rgb_record["path"]
thermal_path = thermal_record["path"]
same_dimensions = (rgb_record["width"], rgb_record["height"]) == (
    thermal_record["width"], thermal_record["height"]
)
existing_path = root / "inspection_pairs.csv"
try:
    existing_pairs = load_pairs(existing_path, root) if existing_path.is_file() else []
except (OSError, ValueError) as exc:
    st.error(f"The existing pairing file needs attention before more pairs can be saved: {exc}")
    st.stop()
existing_match = next(
    (pair for pair in existing_pairs if pair.rgb_path == rgb_path and pair.thermal_path == thermal_path),
    None,
)
for role, record in (("RGB", rgb_record), ("Thermal", thermal_record)):
    if record["missing_fields"]:
        st.caption(f"{role} metadata not found: {', '.join(record['missing_fields'])}")

temperature_files = sorted(
    path for path in root.rglob("*.json")
    if "temperature_grids" in path.relative_to(root).parts
)
temperature_options = [""] + [path.relative_to(root).as_posix() for path in temperature_files]
temperature_default = existing_match.temperature_path if existing_match else ""
temperature_index = temperature_options.index(temperature_default) if temperature_default in temperature_options else 0
temperature_path = st.selectbox(
    "Pixel-temperature data (optional)",
    temperature_options,
    index=temperature_index,
    format_func=lambda value: value or "No temperature file",
    help="Choose a prototype temperature JSON file when it belongs to this thermal image. Without one, the pair is treated as display-only.",
    key=f"intake_temperature:{rgb_path}:{thermal_path}",
)

preview_rgb, preview_thermal = st.columns(2, gap="large")
_show_preview(preview_rgb, root, rgb_record, "RGB")
_show_preview(preview_thermal, root, thermal_record, "Thermal")

if same_dimensions:
    st.caption("Image dimensions match. Check the previews to decide whether panel boxes can transfer between them.")
else:
    st.warning(
        "The image dimensions differ. This pair can be saved for reference, but panel overlays and "
        "temperature comparisons will remain blocked."
    )

temperature_problem = None
if temperature_path:
    try:
        temperature_frame = load_thermal_frame(root / temperature_path)
        if temperature_frame.image_path != thermal_path:
            temperature_problem = "The selected temperature file refers to a different thermal image."
        elif (temperature_frame.image_width, temperature_frame.image_height) != (
            thermal_record["width"], thermal_record["height"]
        ):
            temperature_problem = "Temperature-grid dimensions do not match the thermal image."
        elif not temperature_frame.radiometric:
            st.warning("This temperature file is marked non-radiometric. No temperature comparison will be available.")
    except (OSError, ValueError) as exc:
        temperature_problem = f"Could not read the selected temperature file: {exc}"
    if temperature_problem:
        st.error(temperature_problem)
else:
    st.warning("No pixel-temperature file is selected. The thermal image will be displayed without ΔT analysis.")

thermal_in_use = next(
    (pair for pair in existing_pairs if pair.thermal_path == thermal_path and pair != existing_match),
    None,
)
if thermal_in_use:
    st.error(f"This thermal image is already paired with {thermal_in_use.rgb_path}.")

pair_id_default = existing_match.pair_id if existing_match else _pair_id(rgb_path, thermal_path)
pair_id = st.text_input(
    "Pair ID",
    value=pair_id_default,
    key=f"intake_pair_id:{rgb_path}:{thermal_path}",
)
alignment_reviewed = st.checkbox(
    "I reviewed these images and confirmed panel boxes can transfer between them",
    value=existing_match.alignment_reviewed if existing_match else False,
    disabled=not same_dimensions,
    key=f"intake_alignment:{rgb_path}:{thermal_path}",
)
synthetic = st.checkbox(
    "These are synthetic practice files",
    value=existing_match.synthetic if existing_match else False,
    help="Mark generated or fabricated inputs so the exported observations retain that data-quality flag.",
    key=f"intake_synthetic:{rgb_path}:{thermal_path}",
)

if st.button("Save image pair", type="primary", disabled=bool(temperature_problem or thermal_in_use)):
    clean_pair_id = pair_id.strip()
    if not clean_pair_id:
        st.error("Enter a pair ID.")
    elif any(pair.pair_id == clean_pair_id and pair != existing_match for pair in existing_pairs):
        st.error("That pair ID is already in use for this inspection.")
    else:
        updated_pair = ImagePair(
            inspection_id=manifest["inspection_id"],
            pair_id=clean_pair_id,
            rgb_path=rgb_path,
            thermal_path=thermal_path,
            temperature_path=temperature_path,
            alignment_reviewed=alignment_reviewed and same_dimensions,
            synthetic=synthetic,
        )
        updated_pairs = [
            pair for pair in existing_pairs
            if not (pair.rgb_path == rgb_path and pair.thermal_path == thermal_path)
        ]
        updated_pairs.append(updated_pair)
        try:
            saved_path = save_pairs(existing_path, root, updated_pairs)
        except (OSError, ValueError) as exc:
            st.error(f"Could not save the image pair: {exc}")
        else:
            st.session_state["active_inspection_root"] = str(root)
            st.session_state["active_pair_rgb_path"] = rgb_path
            st.session_state["active_pair_id"] = clean_pair_id
            st.session_state["active_pair_root"] = str(root)
            existing_pairs = updated_pairs
            st.success(f"Saved {clean_pair_id} to {saved_path.name}. Open Inspection Review to view it.")

if existing_pairs:
    st.subheader("Saved image pairs")
    st.dataframe(
        [
            {
                "Pair ID": pair.pair_id,
                "RGB": pair.rgb_path,
                "Thermal": pair.thermal_path,
                "Temperatures": pair.temperature_path or "Unavailable",
                "Alignment": "Reviewed" if pair.alignment_reviewed else "Needs review",
                "Synthetic": pair.synthetic,
            }
            for pair in existing_pairs
        ],
        hide_index=True,
        width="stretch",
    )
