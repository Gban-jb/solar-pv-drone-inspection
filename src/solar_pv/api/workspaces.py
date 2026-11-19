"""Local inspection workspace routes backed by the existing research models."""

from dataclasses import asdict, replace
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import re
import shutil
from tempfile import TemporaryDirectory
from threading import RLock
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field, model_validator

from solar_pv.api.observations import (
    observations_csv, observations_csv_v03, observations_json, observations_json_v03,
)
from solar_pv.domain.assets import build_design_registry
from solar_pv.domain.inspection import review_pairs
from solar_pv.domain.observations import Observation
from solar_pv.imaging.annotations import (
    load_annotations, make_annotation, revise_annotation, save_annotations,
)
from solar_pv.imaging.pairing import ImagePair, load_pairs, save_pairs
from solar_pv.imaging.thermal import (
    compare_regions, load_paired_thermal_frame, load_thermal_frame, measurement_basis,
    region_statistics, render_temperature_grid, temperature_limits_c,
)
from solar_pv.ingestion.importer import _scan_scada, init_inspection, scan_image, scan_inspection
from solar_pv.storage.site_registry import load_site_spec

ROOT = Path(__file__).resolve().parents[3]
WORKSPACES = ROOT / "data/processed/workspaces"
EXAMPLES = ROOT / "examples"
DEMO = EXAMPLES / "week10_12/inspection"
UPLOAD_LIMIT = 160 * 1024 * 1024
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
Role = Literal["rgb", "thermal", "temperature_grids", "scada"]
router = APIRouter(prefix="/api/inspections", tags=["inspections"])
writes = RLock()


class NewInspection(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sample: Literal["empty", "thermal", "import", "annotation"] = "empty"
    provenance: Literal["field_unverified", "public_research", "synthetic"] = "field_unverified"
    source: str = Field(default="", max_length=500)


class PairInput(BaseModel):
    rgb_path: str
    thermal_path: str
    temperature_path: str = ""
    alignment_reviewed: bool = False


class Bounds(BaseModel):
    box: tuple[float, float, float, float]

    @model_validator(mode="after")
    def ordered(self):
        x0, y0, x1, y1 = self.box
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("Choose a positive rectangle inside the image.")
        return self


class AnnotationInput(Bounds):
    asset_id: str = Field(min_length=1, max_length=80)
    image_path: str
    target_type: Literal["panel", "row", "region"] = "panel"
    review_status: Literal["provisional", "confirmed"] = "provisional"
    modified_at_utc: str | None = None


class RegionInput(BaseModel):
    selected: Bounds
    reference: Bounds | None = None


class FindingInput(BaseModel):
    category: Literal[
        "unclassified", "localized_heating", "uneven_appearance", "possible_shading",
        "possible_soiling_or_obstruction", "other_irregularity", "no_visible_anomaly",
    ]
    status: Literal["draft", "needs_verification", "reviewed", "resolved"]
    severity: Literal["unassigned", "low", "medium", "high"] = "unassigned"
    note: str = Field(default="", max_length=4000)
    pair_id: str | None = None
    regions: RegionInput | None = None
    modified_at_utc: str | None = None


def _root(inspection_id: str) -> Path:
    if inspection_id == "demo":
        return DEMO
    if not re.fullmatch(r"[a-f0-9]{32}", inspection_id):
        raise HTTPException(404, "Inspection not found.")
    root = WORKSPACES / inspection_id
    if not (root / "workspace.json").is_file():
        raise HTTPException(404, "Inspection not found.")
    return root


def _metadata(root: Path) -> dict:
    if root == DEMO:
        return {"id": "demo", "name": "Sample solar inspection", "provenance": "synthetic",
                "read_only": True, "source": "Student 1 synthetic thermal cases"}
    return json.loads((root / "workspace.json").read_text(encoding="utf-8"))


def _write_root(inspection_id: str) -> Path:
    root = _root(inspection_id)
    if root == DEMO:
        raise HTTPException(409, "Make a working copy to edit this example.")
    return root


def _annotations_file(root: Path) -> Path:
    if root == DEMO:
        return EXAMPLES / "week10_12/output/panel_annotations.csv"
    return root / "panel_annotations.csv"


def _pairs(root: Path) -> list[ImagePair]:
    path = root / "inspection_pairs.csv"
    return load_pairs(path, root) if path.exists() else []


def _managed_path(root: Path, path: str, roles: set[str]) -> Path:
    relative = Path(path)
    if (relative.is_absolute() or len(relative.parts) < 2 or relative.parts[0] not in roles
            or any(part == ".." or part.startswith(".") for part in relative.parts)):
        raise HTTPException(404, "File not found.")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise HTTPException(404, "File not found.")
    return resolved


def _pair(root: Path, pair_id: str) -> ImagePair:
    result = next((pair for pair in _pairs(root) if pair.pair_id == pair_id), None)
    if result is None:
        raise HTTPException(404, "Image pair not found.")
    return result


def _frame(root: Path, pair: ImagePair):
    frame = load_paired_thermal_frame(
        root, pair.thermal_path, pair.temperature_path, synthetic=pair.synthetic,
    )
    with Image.open(root / pair.thermal_path) as preview:
        if preview.size != (frame.image_width, frame.image_height):
            raise ValueError("The temperature grid and thermal preview have different dimensions.")
    return frame


@lru_cache(maxsize=1)
def _registry():
    try:
        return build_design_registry(load_site_spec(ROOT / "configs/sites/aamu_2023_review.json"))
    except (OSError, ValueError):
        return None


def _panel_masks(pair: ImagePair, frame, annotations: list) -> list:
    return [row for row in annotations
            if row.image_path == pair.rgb_path and row.target_type == "panel" and row.review_status == "confirmed"
            and (row.image_width, row.image_height) == (frame.image_width, frame.image_height)]


def _thermal_status(root: Path, pair: ImagePair, annotations: list) -> dict:
    try:
        if not pair.temperature_path:
            return {"basis": "display_only", "limits": None, "error": None}
        frame = _frame(root, pair)
        basis = measurement_basis(frame)
        return {
            "basis": basis,
            "limits": temperature_limits_c(frame, _panel_masks(pair, frame, annotations)) if basis in {"synthetic_numeric_demo", "calibrated_numeric"} else None,
            "error": None,
        }
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        return {"basis": "unavailable", "limits": None, "error": str(exc)}


def _bounds_text(region: Bounds | None) -> str:
    return ",".join(map(str, region.box)) if region else ""


def _region_results(root: Path, pair: ImagePair, payload: RegionInput) -> dict:
    frame = _frame(root, pair)
    selected = region_statistics(frame, "selected", payload.selected.box)
    reference = None
    if payload.reference:
        left, top, right, bottom = payload.selected.box
        ref_left, ref_top, ref_right, ref_bottom = payload.reference.box
        if max(left, ref_left) < min(right, ref_right) and max(top, ref_top) < min(bottom, ref_bottom):
            raise ValueError("Choose a reference region that does not overlap the selected region.")
        reference = region_statistics(frame, "reference", payload.reference.box)
    comparison = compare_regions(selected, reference) if reference else None
    return {"selected": asdict(selected), "reference": asdict(reference) if reference else None,
            "delta": comparison.delta_median if comparison else None}


def _visual_observation(root: Path, meta: dict, row, pairs: list[ImagePair]) -> Observation:
    """Export explicitly saved visible findings even without a thermal association."""
    matching = [pair for pair in pairs if pair.rgb_path == row.image_path]
    pair = matching[0] if len(matching) == 1 else None
    flags = ["thermal_measurement_unavailable"]
    captured_at = "Unknown"
    if (root / row.image_path).is_file():
        image = scan_image(root / row.image_path, root, "rgb")
        captured_at = image.get("capture_time_raw") or "Unknown"
    if captured_at == "Unknown":
        flags.append("missing_capture_time")
    if meta["provenance"] == "synthetic":
        flags.append("synthetic_data")
    if row.mapping_status != "verified":
        flags.append("asset_id_unverified")
    identity = f'{row.inspection_id or meta["id"]}|visual|{row.annotation_id}'
    return Observation(
        record_id="obs-" + sha256(identity.encode()).hexdigest()[:16],
        inspection_id=row.inspection_id or meta["id"], pair_id=pair.pair_id if pair else "",
        annotation_id=row.annotation_id, asset_id=row.asset_id, asset_level=row.target_type,
        asset_id_status="verified" if row.mapping_status == "verified" else "unverified",
        box_review_status=row.review_status, label_source="manual", captured_at=captured_at,
        rgb_image_path=row.image_path, thermal_image_path=pair.thermal_path if pair else "",
        temperature_source_path="", alignment_reviewed=bool(pair and pair.alignment_reviewed),
        radiometric_valid=False, median_temperature_c=None, reference_temperature_c=None,
        delta_t_c=None, candidate=False, candidate_threshold_c=None, comparison_method="unavailable",
        data_quality_flags=tuple(flags), synthetic=meta["provenance"] == "synthetic",
        source_image_id=row.source_image_id, linked_asset_id=row.linked_asset_id,
        linked_asset_type=row.linked_asset_type, mapping_method=row.mapping_method,
        mapping_status=row.mapping_status, mapping_evidence=row.mapping_evidence,
        reviewer_notes=row.reviewer_notes, observation_note=row.observation_note,
        possible_cause=row.possible_cause, observation_review_status=row.observation_review_status,
        source_provenance=meta["provenance"], observation_category=row.observation_category,
        finding_status=row.finding_status, severity=row.severity,
        created_at_utc=row.created_at_utc, modified_at_utc=row.modified_at_utc,
        correlation_missing=("meter scope unknown", "meter timezone unknown", "asset relationship unverified"),
    )


def _finding_rows(root: Path, pairs: list[ImagePair], annotations: list) -> tuple[list[Observation], list[dict]]:
    meta = _metadata(root)
    reviews = review_pairs(root, pairs, annotations, registry=_registry(), require_confirmed_panels=True) if pairs else []
    records = [row for review in reviews for row in review.observations]
    if meta["provenance"] == "public_research":
        records = [replace(row, source_provenance="public_research") for row in records]
    included = {row.annotation_id for row in records}
    records.extend(
        _visual_observation(root, meta, row, pairs) for row in annotations
        if row.annotation_id not in included
        and (row.observation_note or row.observation_category != "unclassified" or row.finding_status != "draft")
    )
    return records, [{"pair_id": review.pair.pair_id, "reason": review.reason}
                     for review in reviews if review.reason]


@router.get("")
def list_inspections():
    roots = sorted(WORKSPACES.glob("*/workspace.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [_metadata(path.parent) for path in roots if re.fullmatch(r"[a-f0-9]{32}", path.parent.name)] + [_metadata(DEMO)]


@router.post("", status_code=201)
def create_inspection(payload: NewInspection):
    if not payload.name.strip():
        raise HTTPException(422, "Enter an inspection name.")
    if payload.sample == "empty" and payload.provenance == "public_research" and not payload.source.strip():
        raise HTTPException(422, "Add a citation or source URL for public research files.")
    inspection_id = uuid4().hex
    provenance = "synthetic" if payload.sample != "empty" else payload.provenance
    metadata = {"id": inspection_id, "name": payload.name.strip(), "read_only": False,
                "provenance": provenance, "source": payload.source.strip()}
    samples = {
        "thermal": (DEMO, _annotations_file(DEMO)),
        "import": (EXAMPLES / "week01_03/inspection", None),
        "annotation": (EXAMPLES / "week04_06/inspection", EXAMPLES / "week04_06/output/panel_annotations.csv"),
    }
    WORKSPACES.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".workspace-", dir=WORKSPACES) as directory:
        staged = Path(directory) / "inspection"
        if payload.sample != "empty":
            source, labels = samples[payload.sample]
            shutil.copytree(source, staged)
            if labels and labels.is_file():
                shutil.copyfile(labels, _annotations_file(staged))
            metadata["source"] = f"Student 1 synthetic {payload.sample} fixture"
        init_inspection(staged)
        (staged / "workspace.json").write_text(json.dumps(metadata), encoding="utf-8")
        staged.rename(WORKSPACES / inspection_id)
    return metadata


@router.get("/{inspection_id}")
def inspection(inspection_id: str):
    root = _root(inspection_id)
    manifest = scan_inspection(root)
    pairs = _pairs(root)
    annotations = load_annotations(_annotations_file(root))
    findings, issues = _finding_rows(root, pairs, annotations)
    grids = []
    for file in sorted((root / "temperature_grids").glob("*.json")):
        grids.append(file.relative_to(root).as_posix())
    return {"inspection": _metadata(root), "files": manifest["images"] + manifest["scada"],
            "temperature_sources": grids, "pairs": [asdict(pair) | _thermal_status(root, pair, annotations) for pair in pairs],
            "annotations": annotations, "findings": findings, "pair_issues": issues}


@router.post("/{inspection_id}/files/{role}")
def upload(inspection_id: str, role: Role, file: UploadFile = File(...)):
    root = _write_root(inspection_id)
    name = Path((file.filename or "").replace("\\", "/")).name
    suffixes = {".json"} if role == "temperature_grids" else {".csv"} if role == "scada" else IMAGE_SUFFIXES
    if not name or name.startswith(".") or len(name.encode()) > 220 or Path(name).suffix.lower() not in suffixes:
        raise HTTPException(422, "This filename or format is unsupported for the selected file type.")

    with TemporaryDirectory(prefix=".upload-", dir=root) as directory:
        staged = Path(directory) / name
        with staged.open("wb") as stream:
            total = 0
            while chunk := file.file.read(1024 * 1024):
                total += len(chunk)
                if total > UPLOAD_LIMIT:
                    raise HTTPException(413, "This file exceeds the 160 MB limit.")
                stream.write(chunk)
        try:
            if role == "temperature_grids":
                frame = load_thermal_frame(staged)
                if frame.radiometric and (
                    frame.synthetic != (_metadata(root)["provenance"] == "synthetic")
                    or (not frame.synthetic and frame.calibration_status == "verified")
                ):
                    raise ValueError("Use a matching source type. Field calibration must be verified through the camera workflow.")
                record = {"status": "ok", "sha256": sha256(staged.read_bytes()).hexdigest()}
            elif role == "scada":
                record = _scan_scada(staged, root)
            else:
                record = scan_image(staged, root, role)
            if record["status"] == "error":
                raise ValueError(record["error"])
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(422, detail={"message": "We couldn't read this file.", "details": str(exc)}) from exc
        with writes:
            parent = root / role
            parent.mkdir(exist_ok=True)
            destination = parent / name
            if destination.exists():
                if _digest(destination) == record["sha256"]:
                    return {"name": name, "status": "duplicate", "message": "This file is already in the inspection."}
                raise HTTPException(409, "A different file already uses this name. Rename the file and retry.")
            if any(_digest(existing) == record["sha256"] for existing in parent.iterdir()
                   if existing.is_file() and existing.stat().st_size == total):
                return {"name": name, "status": "duplicate", "message": "This file is already in the inspection."}
            staged.rename(destination)
    return {"name": name, "status": record["status"], "missing_fields": record.get("missing_fields", [])}


def _digest(path: Path) -> str:
    from hashlib import file_digest

    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


@router.get("/{inspection_id}/image")
def image(inspection_id: str, path: str, size: Literal["thumb", "viewer", "original"] = "viewer"):
    root = _root(inspection_id)
    file = _managed_path(root, path, {"rgb", "thermal"})
    try:
        with Image.open(file) as source:
            if size != "original":
                maximum = 420 if size == "thumb" else 2560
                source.thumbnail((maximum, maximum))
            output = BytesIO()
            source.convert("RGB").save(output, "JPEG", quality=90 if size != "thumb" else 76)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "This image cannot be previewed.") from exc
    return Response(output.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.post("/{inspection_id}/pairs", status_code=201)
def save_pair(inspection_id: str, payload: PairInput):
    root = _write_root(inspection_id)
    rgb = _managed_path(root, payload.rgb_path, {"rgb"})
    thermal = _managed_path(root, payload.thermal_path, {"thermal"})
    if payload.temperature_path:
        _managed_path(root, payload.temperature_path, {"temperature_grids"})
    with writes:
        pairs = _pairs(root)
        existing = next((pair for pair in pairs if pair.thermal_path == payload.thermal_path), None)
        if existing and existing.rgb_path != payload.rgb_path:
            raise HTTPException(409, "This thermal image is already paired to a different RGB image.")
        if any(pair.rgb_path == payload.rgb_path and pair != existing for pair in pairs):
            raise HTTPException(409, "This RGB image already has a thermal pair.")
        if existing and existing.temperature_path != payload.temperature_path and any(
            row.image_path == existing.rgb_path and row.thermal_region_bounds
            for row in load_annotations(_annotations_file(root))
        ):
            raise HTTPException(409, "Clear the saved thermal regions before changing their temperature source.")
        saved = ImagePair(pairs[0].inspection_id if pairs else inspection_id,
                          existing.pair_id if existing else f"pair-{uuid4().hex[:12]}",
                          **payload.model_dump(), synthetic=_metadata(root)["provenance"] == "synthetic")
        try:
            frame = _frame(root, saved)
            if payload.alignment_reviewed:
                with Image.open(rgb) as source, Image.open(thermal) as other:
                    if source.size != other.size:
                        raise ValueError("Aligned views require identical image dimensions.")
            if existing and existing.alignment_reviewed != saved.alignment_reviewed and any(
                row.image_path == existing.rgb_path and row.thermal_region_bounds
                for row in load_annotations(_annotations_file(root))
            ):
                raise ValueError("Clear the saved thermal regions before changing the alignment status.")
            save_pairs(root / "inspection_pairs.csv", root, [p for p in pairs if p != existing] + [saved])
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc
    return asdict(saved)


def _require_current(row, timestamp: str | None) -> None:
    if timestamp != row.modified_at_utc:
        raise HTTPException(409, "This record changed. Refresh the inspection and try again.")


@router.put("/{inspection_id}/annotations/{annotation_id}")
def save_annotation(inspection_id: str, annotation_id: str, payload: AnnotationInput):
    root = _write_root(inspection_id)
    path = _managed_path(root, payload.image_path, {"rgb"})
    with writes:
        labels = load_annotations(_annotations_file(root))
        old = next((row for row in labels if row.annotation_id == annotation_id), None)
        if annotation_id != "new" and old is None:
            raise HTTPException(404, "Annotation not found.")
        if old:
            _require_current(old, payload.modified_at_utc)
            if old.image_path != payload.image_path:
                raise HTTPException(422, "An annotation belongs to its original image.")
        try:
            with Image.open(path) as source:
                width, height = source.size
            x0, y0, x1, y1 = payload.box
            if not payload.asset_id.strip():
                raise ValueError("Enter a panel or row ID.")
            values = dict(
                target_type=payload.target_type, asset_id=payload.asset_id,
                review_status=payload.review_status, box=(x0 * width, y0 * height, (x1-x0)*width, (y1-y0)*height),
                canvas_size=(width, height), image_size=(width, height),
            )
            provenance = _metadata(root)["provenance"]
            pairs = _pairs(root)
            row = revise_annotation(old, **values) if old else make_annotation(
                image_path=payload.image_path, inspection_id=pairs[0].inspection_id if pairs else inspection_id,
                source_provenance="unknown" if provenance == "public_research" else provenance, **values,
            )
            save_annotations(_annotations_file(root), [row if item == old else item for item in labels] if old else [*labels, row])
        except (OSError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
    return row


@router.delete("/{inspection_id}/annotations/{annotation_id}", status_code=204)
def delete_annotation(inspection_id: str, annotation_id: str, modified_at_utc: str):
    root = _write_root(inspection_id)
    with writes:
        rows = load_annotations(_annotations_file(root))
        row = next((item for item in rows if item.annotation_id == annotation_id), None)
        if row is None:
            raise HTTPException(404, "Annotation not found.")
        _require_current(row, modified_at_utc)
        save_annotations(_annotations_file(root), [item for item in rows if item != row])
    return Response(status_code=204)


@router.post("/{inspection_id}/pairs/{pair_id}/measure")
def measure(inspection_id: str, pair_id: str, payload: RegionInput):
    root = _root(inspection_id)
    try:
        return _region_results(root, _pair(root, pair_id), payload)
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{inspection_id}/pairs/{pair_id}/heat")
def heat(inspection_id: str, pair_id: str, low: float | None = None, high: float | None = None):
    root = _root(inspection_id)
    pair = _pair(root, pair_id)
    try:
        frame = _frame(root, pair)
        if measurement_basis(frame) not in {"synthetic_numeric_demo", "calibrated_numeric"}:
            raise ValueError("No validated numeric temperature source is available.")
        masks = _panel_masks(pair, frame, load_annotations(_annotations_file(root)))
        if not pair.alignment_reviewed or not masks:
            raise ValueError("A heat overlay requires reviewed alignment and saved panel boxes.")
        defaults = temperature_limits_c(frame, masks)
        minimum, maximum = (defaults[0] if low is None else low, defaults[1] if high is None else high)
        if not -273.15 <= minimum < maximum <= 2000:
            raise ValueError("Enter a valid increasing Celsius range.")
        output = BytesIO()
        render_temperature_grid(frame, min_c=minimum, max_c=maximum, annotations=masks).save(output, "PNG")
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(output.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.put("/{inspection_id}/findings/{annotation_id}")
def save_finding(inspection_id: str, annotation_id: str, payload: FindingInput):
    root = _write_root(inspection_id)
    with writes:
        rows = load_annotations(_annotations_file(root))
        row = next((item for item in rows if item.annotation_id == annotation_id), None)
        if row is None:
            raise HTTPException(404, "Annotation not found.")
        _require_current(row, payload.modified_at_utc)
        pair = _pair(root, payload.pair_id) if payload.pair_id else None
        if pair and pair.rgb_path != row.image_path:
            raise HTTPException(422, "The thermal pair belongs to another image.")
        try:
            if payload.regions:
                if pair is None or row.target_type != "panel":
                    raise ValueError("Choose a paired panel before saving thermal measurements.")
                if sum(item.rgb_path == row.image_path for item in _pairs(root)) != 1:
                    raise ValueError("This annotation has multiple thermal pairs. Use a unique pair before saving regions.")
                _region_results(root, pair, payload.regions)
            updated = replace(
                row, observation_category=payload.category, finding_status=payload.status,
                observation_review_status="reviewed" if payload.status in {"reviewed", "resolved"} else "pending",
                severity=payload.severity, observation_note=payload.note.strip(),
                modified_at_utc=datetime.now(timezone.utc).isoformat(),
                thermal_region_bounds=_bounds_text(payload.regions.selected) if payload.regions else row.thermal_region_bounds,
                thermal_reference_bounds=_bounds_text(payload.regions.reference) if payload.regions else row.thermal_reference_bounds,
            )
            save_annotations(_annotations_file(root), [updated if item == row else item for item in rows])
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc
    return updated


@router.get("/{inspection_id}/export/{kind}")
def export(
    inspection_id: str, kind: Literal["csv", "json", "labels"],
    schema: Literal["0.2", "0.3"] = "0.3", ids: list[str] | None = Query(default=None),
):
    root = _root(inspection_id)
    if kind == "labels":
        source = _annotations_file(root)
        if not source.is_file():
            raise HTTPException(404, "There are no saved labels.")
        content, extension = source.read_bytes(), "csv"
    else:
        records, _ = _finding_rows(root, _pairs(root), load_annotations(_annotations_file(root)))
        if ids:
            selected = set(ids)
            records = [row for row in records if row.record_id in selected]
        exporters = {"csv": (observations_csv, observations_csv_v03),
                     "json": (observations_json, observations_json_v03)}
        content, extension = exporters[kind][schema == "0.3"](records), kind
    media = "application/json" if extension == "json" else "text/csv"
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="inspection-{kind}.{extension}"'})
