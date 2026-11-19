"""Small local inventory viewer for the first milestone."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

from solar_pv.ingestion.importer import inventory_rows, scan_inspection, write_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = PROJECT_ROOT / "examples/week01_03/inspection"

st.set_page_config(page_title="Solar PV inspection", layout="wide")
st.header("Inspection inventory")

folder_text = st.text_input("Inspection folder", value=str(st.session_state.get("active_inspection_root", EXAMPLE)))
folder = Path(folder_text).expanduser()
if folder.resolve() != EXAMPLE.resolve() or "active_inspection_root" in st.session_state:
    st.session_state["active_inspection_root"] = str(folder.resolve())
if folder.resolve() == EXAMPLE.resolve():
    st.caption("Synthetic demonstration files. No site or radiometric measurements.")

if st.button("Scan folder", type="primary"):
    try:
        st.session_state["manifest"] = scan_inspection(folder)
    except OSError as exc:
        st.error(str(exc))

manifest = st.session_state.get("manifest")
if manifest:
    summary = manifest["summary"]
    first, second, third = st.columns(3)
    first.metric("Images opened", f"{summary['images_opened']} / {summary['images_found']}")
    second.metric("Image errors", summary["image_errors"])
    third.metric("SCADA CSVs opened", f"{summary['scada_files_opened']} / {summary['scada_files_found']}")

    for issue in manifest["folder_issues"]:
        st.warning(issue)
    for row in (*manifest["images"], *manifest["scada"]):
        if row["status"] == "error":
            st.error(f"{row['path']}: {row['error']}")

    st.subheader("Files")
    rows = inventory_rows(manifest)
    st.dataframe(
        pd.DataFrame(rows)[["status", "kind", "path", "missing_fields"]],
        width="stretch",
        hide_index=True,
    )
    selected_path = st.selectbox("File details", [row["path"] for row in rows])
    if selected_path:
        selected = next(row for row in rows if row["path"] == selected_path)
        st.json(selected, expanded=False)

    st.subheader("Image previews")
    valid_images = [row for row in manifest["images"] if row["status"] != "error"]
    for start in range(0, len(valid_images), 4):
        for column, row in zip(st.columns(4), valid_images[start:start + 4]):
            image_path = Path(manifest["source_root"]) / row["path"]
            try:
                with Image.open(image_path) as source:
                    preview = ImageOps.exif_transpose(source)
                    preview.thumbnail((360, 240))
                    column.image(preview.copy(), width="stretch")
                column.caption(row["path"])
            except OSError as exc:
                column.error(f"{row['path']}: {exc}")

    if manifest["scada"]:
        st.subheader("SCADA summary")
        for row in manifest["scada"]:
            st.write(f"{row['path']}: {row['status']} | {row.get('row_count')} rows")
            if row.get("preview_rows"):
                st.dataframe(pd.DataFrame(row["preview_rows"]), width="stretch", hide_index=True)

    if st.button("Save inventory"):
        output = folder.resolve().parent / f"{folder.name}_output"
        json_path, csv_path = write_manifest(manifest, output)
        st.success(f"Saved {json_path.name} and {csv_path.name} in {output}")

    st.download_button(
        "Download manifest",
        data=json.dumps(manifest, indent=2),
        file_name="inspection_manifest.json",
        mime="application/json",
    )
