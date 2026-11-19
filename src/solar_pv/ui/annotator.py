"""Streamlit panel and row annotation tool."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
from streamlit_drawable_canvas import st_canvas

from solar_pv.domain.assets import build_design_registry
from solar_pv.domain.asset_mapping import (
    asset_path, link_annotation, mapping_display, selected_asset, unlink_annotation,
    verify_asset_link,
)
from solar_pv.imaging.annotations import (
    load_annotations,
    make_annotation,
    revise_annotation,
    save_annotations,
)
from solar_pv.imaging.pairing import load_pairs
from solar_pv.storage.asset_evidence import register_evidence_source
from solar_pv.storage.site_registry import load_site_spec


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INSPECTION = PROJECT_ROOT / "examples/week04_06/inspection"
DEFAULT_ANNOTATION_FILE = PROJECT_ROOT / "data/processed/panel_annotations.csv"
IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff"}
VIEW_WIDTHS = {"Compact": 420, "Wide": 760, "Detail": 1100}
SITE_SPEC = PROJECT_ROOT / "configs/sites/aamu_2023_review.json"
EVIDENCE_INDEX = PROJECT_ROOT / "data/processed/asset_evidence_index.json"


@st.cache_resource(show_spinner=False)
def _asset_registry(spec_mtime_ns: int):
    del spec_mtime_ns
    return build_design_registry(load_site_spec(SITE_SPEC))


def _reset_link_children(annotation_id: str) -> None:
    st.session_state[f"link_string:{annotation_id}"] = None
    st.session_state[f"link_module:{annotation_id}"] = None


def _reset_link_module(annotation_id: str) -> None:
    st.session_state[f"link_module:{annotation_id}"] = None


def _save_annotation_update(path: Path, rows: list, original, revised) -> None:
    save_annotations(path, [revised if row.annotation_id == original.annotation_id else row for row in rows])


def reset_editor() -> None:
    st.session_state["week04_edit_id"] = None
    st.session_state["week04_asset_id"] = ""
    st.session_state["week04_target_type"] = "panel"
    st.session_state["week04_review_status"] = "provisional"
    st.session_state["week04_canvas_revision"] = st.session_state.get("week04_canvas_revision", 0) + 1


def begin_edit(annotation) -> None:
    st.session_state["week04_edit_id"] = annotation.annotation_id
    st.session_state["week04_asset_id"] = annotation.asset_id
    st.session_state["week04_target_type"] = annotation.target_type
    st.session_state["week04_review_status"] = annotation.review_status
    st.session_state["week04_canvas_revision"] = st.session_state.get("week04_canvas_revision", 0) + 1


st.set_page_config(page_title="Panel annotations | Solar PV", layout="wide")
st.markdown(
    """
    <style>
    .block-container { max-width: 1320px; padding-bottom: 3rem; }
    h1 { font-size: 1.85rem; font-weight: 650; letter-spacing: 0; }
    h2, h3 { letter-spacing: 0; }
    div[data-testid="stExpander"] { border-radius: 4px; }
    div.stButton > button, div.stDownloadButton > button { border-radius: 4px; }
    div.stButton > button[kind="primary"] {
        background: #245844; border-color: #245844; color: white;
    }
    div.stButton > button[kind="primary"]:hover {
        background: #194631; border-color: #194631; color: white;
    }
    button[data-variant="segmented_control"][data-selected="true"] {
        background: rgba(36, 88, 68, 0.1) !important;
        border-color: #245844 !important; color: #245844 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Panel annotations")
with st.expander("Files and output", expanded=False):
    inspection_text = st.text_input(
        "Inspection folder",
        str(st.session_state.get("active_inspection_root", st.query_params.get("inspection", DEFAULT_INSPECTION))),
    )
    annotation_text = st.text_input(
        "Label CSV",
        str(st.session_state.get("active_annotation_path", st.query_params.get("labels", DEFAULT_ANNOTATION_FILE))),
    )
inspection_root = Path(inspection_text).expanduser().resolve()
annotation_path = Path(annotation_text).expanduser()
if st.query_params.get("inspection") != str(inspection_root):
    st.query_params["inspection"] = str(inspection_root)
if st.query_params.get("labels") != str(annotation_path.resolve()):
    st.query_params["labels"] = str(annotation_path.resolve())
if inspection_root != DEFAULT_INSPECTION.resolve() or "active_inspection_root" in st.session_state:
    st.session_state["active_inspection_root"] = str(inspection_root)
if annotation_path.resolve() != DEFAULT_ANNOTATION_FILE.resolve() or "active_annotation_path" in st.session_state:
    st.session_state["active_annotation_path"] = str(annotation_path.resolve())

if not inspection_root.is_dir():
    st.error(f"Inspection folder not found: {inspection_root}")
    st.stop()

image_paths = sorted(
    path
    for folder_name in ("rgb", "thermal")
    for path in (inspection_root / folder_name).rglob("*")
    if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
)
if not image_paths:
    st.info("No supported images found in the inspection's rgb/ or thermal/ folders.")
    st.stop()

try:
    all_annotations = load_annotations(annotation_path)
except (OSError, ValueError) as exc:
    st.error(f"Could not load annotation CSV: {exc}")
    st.stop()

relative_paths = {path: path.relative_to(inspection_root).as_posix() for path in image_paths}
pair_file = inspection_root / "inspection_pairs.csv"
try:
    saved_pairs = load_pairs(pair_file, inspection_root) if pair_file.is_file() else []
except (OSError, ValueError) as exc:
    saved_pairs = []
    st.warning(f"Image pairing information is unavailable: {exc}")
toolbar = st.columns([3, 2], gap="medium")
with toolbar[0]:
    active_path = st.session_state.get("active_pair_rgb_path") or st.query_params.get("image")
    initial_index = next((index for index, path in enumerate(image_paths) if relative_paths[path] == active_path), 0)
    if st.session_state.get("week04_image") not in [None, *image_paths]:
        st.session_state["week04_image"] = image_paths[initial_index]
    selected_path = st.selectbox(
        "Image", image_paths, index=initial_index,
        format_func=lambda path: relative_paths[path], key="week04_image",
    )
with toolbar[1]:
    view_size = st.segmented_control("View size", list(VIEW_WIDTHS), default="Compact")
image_rel = relative_paths[selected_path]
if st.query_params.get("image") != image_rel:
    st.query_params["image"] = image_rel
image_pair = next((pair for pair in saved_pairs if pair.rgb_path == image_rel), None)
inspection_id = image_pair.inspection_id if image_pair else inspection_root.name
source_provenance = (
    "synthetic" if (image_pair and image_pair.synthetic)
    or inspection_root in {DEFAULT_INSPECTION.resolve(), (PROJECT_ROOT / "examples/week10_12/inspection").resolve()}
    else "field_unverified" if image_pair else "unknown"
)
image_annotations = [row for row in all_annotations if row.image_path == image_rel]
if st.session_state.pop("week04_reset_editor", False):
    reset_editor()
edit_id = st.session_state.get("week04_edit_id")
edit_annotation = next((row for row in image_annotations if row.annotation_id == edit_id), None)
if edit_id and edit_annotation is None:
    reset_editor()

try:
    with Image.open(selected_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
except OSError as exc:
    st.error(f"Could not open image: {exc}")
    st.stop()

if inspection_root == DEFAULT_INSPECTION.resolve():
    st.caption(f"SYNTHETIC PRACTICE  ·  {image.width} × {image.height} px  ·  {len(image_annotations)} saved")
else:
    st.caption(f"{image_rel}  ·  {image.width} × {image.height} px  ·  {len(image_annotations)} saved")

scale = min(
    VIEW_WIDTHS[view_size or "Compact"] / image.width,
    720 / image.height,
    1.0,
)
canvas_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
display_image = image.resize(canvas_size, Image.Resampling.LANCZOS)
background = display_image.copy()
draw = ImageDraw.Draw(background)
font = ImageFont.load_default(size=12 if canvas_size[0] <= 420 else 14)
for number, row in enumerate(image_annotations, start=1):
    x1 = round(row.x_min * canvas_size[0])
    y1 = round(row.y_min * canvas_size[1])
    x2 = round(row.x_max * canvas_size[0])
    y2 = round(row.y_max * canvas_size[1])
    editing = row.annotation_id == st.session_state.get("week04_edit_id")
    color = "#E37038" if editing else ("#23A36F" if row.review_status == "confirmed" else "#5D8A77")
    draw.rectangle((x1, y1, x2, y2), outline=color, width=2)
    tag = f"{number:02d}" if canvas_size[0] <= 420 else (row.asset_id or f"{number:02d}")
    tag_width = round(draw.textlength(tag, font=font))
    draw.rectangle((x1, y1, x1 + tag_width + 10, y1 + 17), fill=color)
    draw.text((x1 + 5, y1 + 1), tag, fill="white", font=font)

if "week04_canvas_revision" not in st.session_state:
    st.session_state["week04_canvas_revision"] = 0
canvas_key = (
    f"annotation:{inspection_root}:{image_rel}:"
    f"{canvas_size}:{len(image_annotations)}:{edit_id}:{st.session_state['week04_canvas_revision']}"
)

workspace, controls = st.columns([2.15, 1], gap="large")
with workspace:
    canvas_result = st_canvas(
        background_image=background,
        background_image_fit="stretch",
        drawing_mode="rect",
        fill_color="rgba(227, 112, 56, 0.14)",
        stroke_color="#E37038",
        stroke_width=2,
        update_streamlit=False,
        width=canvas_size[0],
        height=canvas_size[1],
        key=canvas_key,
    )

with controls:
    st.subheader("Edit label" if edit_annotation else "New label")
    target_type = st.selectbox("Type", ("panel", "row", "region"), key="week04_target_type")
    asset_id = st.text_input("Local plant ID (legacy, optional)", key="week04_asset_id")
    st.caption("Use Link to Solar Asset below for a validated design-registry ID.")
    review_status = st.selectbox(
        "Box review",
        ("provisional", "confirmed"),
        format_func=str.capitalize,
        key="week04_review_status",
    )
    objects = (canvas_result.json_data or {}).get("objects", [])
    if len(objects) == 1:
        st.caption("1 replacement box ready" if edit_annotation else "1 box ready")
    elif len(objects) > 1:
        st.caption(f"{len(objects)} boxes on canvas · keep one before saving")
    elif edit_annotation:
        st.caption("Current box shown in orange")
    else:
        st.caption("No box applied")

    if st.button("Save changes" if edit_annotation else "Save label", type="primary", use_container_width=True):
        if len(objects) > 1 or (not edit_annotation and not objects):
            st.error("Draw one box, then use the canvas update button before saving.")
        else:
            box = objects[0] if objects else None
            angle = float(box.get("angle", 0) or 0) if box else 0.0
            if abs(angle) > 0.5:
                st.error("Rotated boxes are not supported. Draw an axis-aligned rectangle.")
            else:
                try:
                    box_values = (
                        (
                            float(box["left"]),
                            float(box["top"]),
                            float(box["width"]) * float(box.get("scaleX", 1) or 1),
                            float(box["height"]) * float(box.get("scaleY", 1) or 1),
                        )
                        if box else None
                    )
                    if edit_annotation:
                        annotation = revise_annotation(
                            edit_annotation,
                            target_type=target_type,
                            asset_id=asset_id,
                            review_status=review_status,
                            box=box_values,
                            canvas_size=canvas_size,
                            image_size=image.size,
                        )
                        updated = [
                            annotation if row.annotation_id == edit_annotation.annotation_id else row
                            for row in all_annotations
                        ]
                    else:
                        annotation = make_annotation(
                            image_path=image_rel,
                            target_type=target_type,
                            asset_id=asset_id,
                            review_status=review_status,
                            box=box_values,
                            canvas_size=canvas_size,
                            image_size=image.size,
                        )
                        updated = [*all_annotations, annotation]
                    save_annotations(annotation_path, updated)
                except (KeyError, OSError, TypeError, ValueError) as exc:
                    st.error(f"Could not save annotation: {exc}")
                else:
                    st.session_state["week04_reset_editor"] = True
                    st.rerun()
    if edit_annotation:
        st.button("Cancel edit", on_click=reset_editor, use_container_width=True)

    st.divider()
    st.subheader(f"Saved labels ({len(image_annotations)})")
    if image_annotations:
        annotation_ids = [row.annotation_id for row in image_annotations]
        if "week04_selected_id" not in st.session_state:
            requested_id = st.query_params.get("annotation")
            st.session_state["week04_selected_id"] = requested_id if requested_id in annotation_ids else annotation_ids[0]
        if st.session_state.get("week04_selected_id") not in [None, *annotation_ids]:
            st.session_state["week04_selected_id"] = annotation_ids[0]
        selected_id = st.selectbox(
            "Select label",
            annotation_ids,
            format_func=lambda annotation_id: next(
                (row.asset_id or row.annotation_id)
                for row in image_annotations
                if row.annotation_id == annotation_id
            ),
            key="week04_selected_id",
        )
        if st.query_params.get("annotation") != selected_id:
            st.query_params["annotation"] = selected_id
        selected_annotation = next(row for row in image_annotations if row.annotation_id == selected_id)
        edit_button, remove_button = st.columns(2)
        with edit_button:
            st.button("Edit selected", on_click=begin_edit, args=(selected_annotation,), use_container_width=True)
        with remove_button:
            remove = st.button("Remove label", use_container_width=True)
        if remove:
            try:
                save_annotations(
                    annotation_path,
                    [row for row in all_annotations if row.annotation_id != selected_id],
                )
            except (OSError, ValueError) as exc:
                st.error(f"Could not remove annotation: {exc}")
            else:
                st.session_state["week04_reset_editor"] = True
                st.rerun()

        st.subheader("Link to Solar Asset")
        try:
            registry = _asset_registry(SITE_SPEC.stat().st_mtime_ns)
        except (OSError, ValueError) as exc:
            registry = None
            st.warning(f"Asset registry unavailable: {exc}")
        if registry is not None:
            status, path_label = mapping_display(selected_annotation, registry)
            st.caption(f"Mapping: {status} · {path_label}")
            if selected_annotation.source_provenance == "synthetic" or source_provenance == "synthetic":
                st.caption("Synthetic practice image · this cannot verify a physical asset position.")
            elif selected_annotation.source_provenance == "unknown":
                st.caption("Source provenance is unknown. Check the original image before using this link.")
            existing_path = (
                asset_path(registry, selected_annotation.linked_asset_id)
                if selected_annotation.linked_asset_id and registry.get(selected_annotation.linked_asset_id)
                else ()
            )
            existing_by_kind = {item.kind: item.asset_id for item in existing_path}
            inverter_ids = [item.asset_id for item in registry.children_of(registry.site.site_id)]
            inverter_key = f"link_inverter:{selected_id}"
            string_key = f"link_string:{selected_id}"
            module_key = f"link_module:{selected_id}"
            if inverter_key not in st.session_state:
                st.session_state[inverter_key] = existing_by_kind.get("inverter")
            if st.session_state[inverter_key] not in [None, *inverter_ids]:
                st.session_state[inverter_key] = None
            inverter_id = st.selectbox(
                "Inverter", [None, *inverter_ids],
                format_func=lambda item: registry.get(item).drawing_label if item else "Unmapped",
                key=inverter_key, on_change=_reset_link_children, args=(selected_id,),
            )
            string_ids = [item.asset_id for item in registry.children_of(inverter_id)] if inverter_id else []
            if string_key not in st.session_state:
                st.session_state[string_key] = existing_by_kind.get("string")
            if st.session_state[string_key] not in [None, *string_ids]:
                st.session_state[string_key] = None
            string_id = st.selectbox(
                "String", [None, *string_ids],
                format_func=lambda item: registry.get(item).drawing_label if item else "Inverter only",
                key=string_key, disabled=not inverter_id,
                on_change=_reset_link_module, args=(selected_id,),
            )
            module_ids = [item.asset_id for item in registry.children_of(string_id)] if string_id else []
            if module_key not in st.session_state:
                st.session_state[module_key] = existing_by_kind.get("module")
            if st.session_state[module_key] not in [None, *module_ids]:
                st.session_state[module_key] = None
            module_id = st.selectbox(
                "Module candidate", [None, *module_ids],
                format_func=lambda item: f"MOD-{registry.get(item).sequence_number:02d}" if item else "String only",
                key=module_key, disabled=not string_id,
            )
            notes = st.text_area(
                "Mapping notes (optional)", value=selected_annotation.reviewer_notes,
                key=f"link_notes:{selected_id}", height=72,
            )
            link_col, unlink_col = st.columns(2)
            if link_col.button("Save asset link", use_container_width=True):
                try:
                    asset = selected_asset(
                        registry, inverter_id=inverter_id, string_id=string_id, module_id=module_id
                    )
                    if asset is None:
                        raise ValueError("Choose an inverter, string or module candidate")
                    revised = link_annotation(selected_annotation, registry, asset.asset_id, reviewer_notes=notes)
                    if source_provenance == "synthetic":
                        revised = replace(revised, source_provenance="synthetic")
                    _save_annotation_update(annotation_path, all_annotations, selected_annotation, revised)
                    register_evidence_source(EVIDENCE_INDEX, annotation_path, inspection_root)
                except (OSError, ValueError) as exc:
                    st.error(f"Could not save asset link: {exc}")
                else:
                    st.rerun()
            if unlink_col.button("Remove asset link", disabled=not selected_annotation.linked_asset_id, use_container_width=True):
                try:
                    revised = unlink_annotation(selected_annotation)
                    _save_annotation_update(annotation_path, all_annotations, selected_annotation, revised)
                except (OSError, ValueError) as exc:
                    st.error(f"Could not remove asset link: {exc}")
                else:
                    for key in (inverter_key, string_key, module_key):
                        st.session_state[key] = None
                    st.rerun()
            with st.expander("Verify mapping against approved records"):
                st.caption("Box review and manual selection do not verify physical identity.")
                reference = st.text_input("Approved source reference", key=f"verify_reference:{selected_id}")
                reviewer = st.text_input("Reviewer name", key=f"verify_reviewer:{selected_id}")
                attested = st.checkbox(
                    "I checked this ID against the referenced approved record",
                    key=f"verify_attested:{selected_id}",
                )
                if st.button("Mark mapping verified", disabled=not attested or not selected_annotation.linked_asset_id):
                    try:
                        revised = verify_asset_link(
                            selected_annotation, registry,
                            approved_reference=reference, reviewer=reviewer,
                        )
                        _save_annotation_update(annotation_path, all_annotations, selected_annotation, revised)
                    except (OSError, ValueError) as exc:
                        st.error(f"Could not verify mapping: {exc}")
                    else:
                        st.rerun()

        with st.expander("Inspection note", expanded=bool(selected_annotation.observation_note)):
            st.caption("Record what is visible. A note does not diagnose a fault.")
            observation_note = st.text_area(
                "Observation", value=selected_annotation.observation_note,
                key=f"observation_note:{selected_id}", height=80,
            )
            possible_cause = st.text_input(
                "Possible cause (optional)", value=selected_annotation.possible_cause,
                key=f"possible_cause:{selected_id}",
            )
            note_review = st.selectbox(
                "Note review", ("pending", "reviewed"),
                index=0 if selected_annotation.observation_review_status == "pending" else 1,
                key=f"observation_review:{selected_id}",
            )
            if st.button("Save inspection note"):
                try:
                    revised = replace(
                        selected_annotation,
                        observation_note=observation_note.strip(),
                        possible_cause=possible_cause.strip(),
                        observation_review_status=note_review,
                        modified_at_utc=datetime.now(timezone.utc).isoformat(),
                    )
                    _save_annotation_update(annotation_path, all_annotations, selected_annotation, revised)
                except (OSError, ValueError) as exc:
                    st.error(f"Could not save inspection note: {exc}")
                else:
                    st.rerun()
    if annotation_path.is_file():
        st.download_button(
            "Download CSV",
            data=annotation_path.read_bytes(),
            file_name=annotation_path.name,
            mime="text/csv",
            use_container_width=True,
        )

st.divider()
if image_annotations:
    st.dataframe(
        [
            {
                "No.": number,
                "Annotation ID": row.annotation_id,
                "Type": row.target_type,
                "Plant ID": row.asset_id or "Unassigned",
                "Registry asset": row.linked_asset_id or "Unmapped",
                "Mapping": row.mapping_status.capitalize(),
                "Box review": row.review_status.capitalize(),
                "Bounds (0-1)": (
                    f"{row.x_min:.3f}, {row.y_min:.3f}, "
                    f"{row.x_max:.3f}, {row.y_max:.3f}"
                ),
            }
            for number, row in enumerate(image_annotations, start=1)
        ],
        hide_index=True,
        width="stretch",
    )
else:
    st.caption("No saved labels for this image.")

image_word = "image" if len(image_paths) == 1 else "images"
label_word = "label" if len(all_annotations) == 1 else "labels"
st.caption(f"{len(image_paths)} {image_word} in inspection  ·  {len(all_annotations)} {label_word} in CSV")
