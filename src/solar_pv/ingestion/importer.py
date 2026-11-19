"""Folder-based inspection import with per-file diagnostics."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image


IMAGE_ROLES = ("rgb", "thermal")
INVENTORY_FIELDS = (
    "kind", "path", "status", "format", "width", "height", "capture_time_raw",
    "gps_latitude", "gps_longitude", "gps_datum_raw", "coordinate_reference_system",
    "altitude_m", "camera_pose", "calibration_status", "rtk_status",
    "camera_make", "camera_model",
    "temperature_status", "row_count", "columns", "size_bytes", "sha256",
    "missing_fields", "error",
)


def init_inspection(path: Path) -> Path:
    root = Path(path).expanduser().resolve()
    for name in (*IMAGE_ROLES, "scada"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _base_record(path: Path, root: Path, kind: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "kind": kind,
        "path": path.relative_to(root).as_posix(),
        "status": "ok",
        "size_bytes": None,
        "sha256": None,
        "missing_fields": [],
        "error": None,
    }
    try:
        record["size_bytes"] = path.stat().st_size
        record["sha256"] = _hash_file(path)
    except OSError as exc:
        record["status"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def _gps_component(values: Any, direction: Any) -> float:
    degrees, minutes, seconds = (float(value) for value in values)
    number = degrees + minutes / 60 + seconds / 3600
    if isinstance(direction, bytes):
        direction = direction.decode("ascii")
    if direction in ("S", "W"):
        number = -number
    return number


def _read_gps(exif: Any) -> tuple[float | None, float | None]:
    try:
        gps = exif.get_ifd(34853)
        if not gps:
            return None, None
        latitude = _gps_component(gps[2], gps[1])
        longitude = _gps_component(gps[4], gps[3])
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return None, None
        return round(latitude, 7), round(longitude, 7)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, UnicodeDecodeError):
        return None, None


def _csv_shape(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, None)
        if not header or any(not name.strip() for name in header):
            raise ValueError("CSV header is empty or has an unnamed column")
        if len(set(header)) != len(header):
            raise ValueError("CSV header contains duplicate columns")
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(
                    f"CSV row {line_number} has {len(row)} values; expected {len(header)}"
                )


def _scan_image(path: Path, root: Path, role: str) -> dict[str, Any]:
    record = _base_record(path, root, role)
    record.update({
        "format": None,
        "width": None,
        "height": None,
        "capture_time_raw": None,
        "gps_latitude": None,
        "gps_longitude": None,
        "gps_datum_raw": None,
        "coordinate_reference_system": None,
        "altitude_m": None,
        "camera_pose": None,
        "calibration_status": None,
        "rtk_status": None,
        "camera_make": None,
        "camera_model": None,
        "temperature_status": "not_checked" if role == "thermal" else None,
    })
    if record["status"] == "error":
        return record

    try:
        with Image.open(path) as image:
            record["format"] = image.format
            record["width"], record["height"] = image.size
            exif = image.getexif()
            exif_details = exif.get_ifd(34665) if exif else {}
            capture_time = (
                exif_details.get(36867) or exif.get(36867) or exif.get(306)
            )
            record["capture_time_raw"] = str(capture_time) if capture_time else None
            record["camera_make"] = str(exif.get(271)) if exif.get(271) else None
            record["camera_model"] = str(exif.get(272)) if exif.get(272) else None
            record["gps_latitude"], record["gps_longitude"] = _read_gps(exif)
            try:
                gps_ifd = exif.get_ifd(34853) if exif else {}
                record["gps_datum_raw"] = str(gps_ifd.get(18)) if gps_ifd.get(18) else None
            except (KeyError, TypeError, ValueError):
                pass
            image.load()
        if not record["capture_time_raw"]:
            record["missing_fields"].append("capture_timestamp")
        if record["gps_latitude"] is None:
            record["missing_fields"].append("gps")
        if not record["camera_model"]:
            record["missing_fields"].append("camera_model")
        if record["missing_fields"]:
            record["status"] = "warning"
    except Exception as exc:
        record["status"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def scan_image(path: Path, inspection_root: Path, role: str) -> dict[str, Any]:
    """Read one source image's metadata without altering the original file."""
    root = Path(inspection_root).resolve()
    source = Path(path).resolve()
    if role not in IMAGE_ROLES or not source.is_relative_to(root):
        raise ValueError("Image must be inside the inspection folder with a valid role")
    return _scan_image(source, root, role)


def _scan_scada(path: Path, root: Path) -> dict[str, Any]:
    record = _base_record(path, root, "scada")
    record.update({"columns": [], "row_count": None, "empty_cells": {}, "preview_rows": []})
    if record["status"] == "error":
        return record

    try:
        _csv_shape(path)
        table = pd.read_csv(
            path, dtype=str, keep_default_na=False, encoding="utf-8-sig",
            on_bad_lines="error",
        )
        record["columns"] = [str(column) for column in table.columns]
        record["row_count"] = len(table)
        record["empty_cells"] = {
            column: int(table[column].str.strip().str.lower().isin(
                {"", "null", "undefined", "nan", "none"}
            ).sum())
            for column in table.columns
        }
        record["preview_rows"] = table.head(3).to_dict(orient="records")
        if not any("time" in name.lower() or "date" in name.lower()
                   for name in record["columns"]):
            record["missing_fields"].append("timestamp_column")
        if table.empty:
            record["missing_fields"].append("data_rows")
        if any(record["empty_cells"].values()):
            record["missing_fields"].append("missing_values")
        if record["missing_fields"]:
            record["status"] = "warning"
    except Exception as exc:
        record["status"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def scan_inspection(path: Path) -> dict[str, Any]:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Inspection folder not found: {root}")

    images = []
    scada = []
    folder_issues = []
    for role in IMAGE_ROLES:
        folder = root / role
        if not folder.is_dir():
            folder_issues.append(f"Missing folder: {role}/")
            continue
        for item in sorted(folder.rglob("*")):
            if item.is_file() and not item.name.startswith("."):
                images.append(_scan_image(item, root, role))

    scada_folder = root / "scada"
    if not scada_folder.is_dir():
        folder_issues.append("Missing folder: scada/")
    else:
        for item in sorted(scada_folder.rglob("*")):
            if item.is_file() and not item.name.startswith("."):
                record = _scan_scada(item, root) if item.suffix.lower() == ".csv" else _base_record(item, root, "scada")
                if item.suffix.lower() != ".csv":
                    record["status"] = "error"
                    record["error"] = "Unsupported SCADA file; expected CSV"
                scada.append(record)
        if not any(record["status"] != "error" for record in scada):
            folder_issues.append("No readable SCADA CSV found")

    return {
        "schema_version": "0.1",
        "inspection_id": root.name,
        "source_root": str(root),
        "scanned_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "images_found": len(images),
            "images_opened": sum(row["status"] != "error" for row in images),
            "image_errors": sum(row["status"] == "error" for row in images),
            "scada_files_found": len(scada),
            "scada_files_opened": sum(row["status"] != "error" for row in scada),
        },
        "folder_issues": folder_issues,
        "images": images,
        "scada": scada,
    }


def inventory_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for record in (*manifest["images"], *manifest["scada"]):
        row = {field: record.get(field) for field in INVENTORY_FIELDS}
        for field in ("missing_fields", "columns"):
            value = row[field]
            row[field] = "; ".join(value) if isinstance(value, list) else value
        rows.append(row)
    return rows


def write_manifest(manifest: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "inspection_manifest.json"
    csv_path = output / "file_inventory.csv"
    with json_path.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=INVENTORY_FIELDS)
        writer.writeheader()
        writer.writerows(inventory_rows(manifest))
    return json_path, csv_path
