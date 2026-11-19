"""CSV persistence for image-based row and panel annotations."""

from __future__ import annotations

import csv
import hashlib
import shutil
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path


ANNOTATION_FIELDS = (
    "annotation_id",
    "image_path",
    "target_type",
    "asset_id",
    "x_min",
    "y_min",
    "x_max",
    "y_max",
    "image_width",
    "image_height",
    "created_at_utc",
    "review_status",
    "inspection_id",
    "source_image_id",
    "source_provenance",
    "linked_asset_id",
    "linked_asset_type",
    "mapping_method",
    "mapping_status",
    "mapping_evidence",
    "reviewer_notes",
    "observation_note",
    "possible_cause",
    "observation_review_status",
    "modified_at_utc",
    "observation_category",
    "finding_status",
    "severity",
    "thermal_region_bounds",
    "thermal_reference_bounds",
)
REVIEW_STATUSES = {"provisional", "confirmed"}
MAPPING_STATUSES = {"unmapped", "provisional", "verified", "unresolved"}
SOURCE_PROVENANCE = {"unknown", "synthetic", "field_unverified"}
MIN_BOX_PIXELS = 8


def image_identifier(inspection_id: str, image_path: str) -> str:
    """Stable within an inspection, independent of the local root directory."""
    identity = f"{inspection_id}|{Path(image_path).as_posix()}"
    return "img-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class PanelAnnotation:
    annotation_id: str
    image_path: str
    target_type: str
    asset_id: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    image_width: int
    image_height: int
    created_at_utc: str
    review_status: str = "provisional"
    inspection_id: str = ""
    source_image_id: str = ""
    source_provenance: str = "unknown"
    linked_asset_id: str = ""
    linked_asset_type: str = ""
    mapping_method: str = ""
    mapping_status: str = "unmapped"
    mapping_evidence: str = ""
    reviewer_notes: str = ""
    observation_note: str = ""
    possible_cause: str = ""
    observation_review_status: str = "pending"
    modified_at_utc: str = ""
    observation_category: str = "unclassified"
    finding_status: str = "draft"
    severity: str = "unassigned"
    thermal_region_bounds: str = ""
    thermal_reference_bounds: str = ""


def make_annotation(
    *,
    image_path: str,
    target_type: str,
    asset_id: str,
    box: tuple[float, float, float, float],
    canvas_size: tuple[int, int],
    image_size: tuple[int, int],
    review_status: str = "provisional",
    inspection_id: str = "",
    source_provenance: str = "unknown",
) -> PanelAnnotation:
    """Create one annotation from a canvas rectangle and its image dimensions."""
    if target_type not in {"panel", "row", "region"}:
        raise ValueError("target_type must be 'panel', 'row', or 'region'")
    if review_status not in REVIEW_STATUSES:
        raise ValueError("review_status must be 'provisional' or 'confirmed'")

    canvas_width, canvas_height = canvas_size
    image_width, image_height = image_size
    if min(canvas_width, canvas_height, image_width, image_height) <= 0:
        raise ValueError("Image and canvas dimensions must be positive")

    left, top, width, height = box
    x1 = min(max(left, 0.0), float(canvas_width))
    y1 = min(max(top, 0.0), float(canvas_height))
    x2 = min(max(left + width, 0.0), float(canvas_width))
    y2 = min(max(top + height, 0.0), float(canvas_height))
    if x2 - x1 < MIN_BOX_PIXELS or y2 - y1 < MIN_BOX_PIXELS:
        raise ValueError(f"Draw a box at least {MIN_BOX_PIXELS} pixels wide and high")

    now = datetime.now(timezone.utc).isoformat()
    return PanelAnnotation(
        annotation_id=f"ann-{uuid.uuid4().hex[:12]}",
        image_path=Path(image_path).as_posix(),
        target_type=target_type,
        asset_id=asset_id.strip(),
        x_min=x1 / canvas_width,
        y_min=y1 / canvas_height,
        x_max=x2 / canvas_width,
        y_max=y2 / canvas_height,
        image_width=image_width,
        image_height=image_height,
        created_at_utc=now,
        review_status=review_status,
        inspection_id=inspection_id.strip(),
        source_image_id=image_identifier(inspection_id.strip(), image_path),
        source_provenance=source_provenance,
        modified_at_utc=now,
    )


def revise_annotation(
    original: PanelAnnotation,
    *,
    target_type: str,
    asset_id: str,
    review_status: str,
    box: tuple[float, float, float, float] | None = None,
    canvas_size: tuple[int, int] | None = None,
    image_size: tuple[int, int] | None = None,
) -> PanelAnnotation:
    """Update a label while retaining its annotation ID and creation time."""
    if box is None:
        revised = replace(
            original,
            target_type=target_type,
            asset_id=asset_id.strip(),
            review_status=review_status,
            modified_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        _validate(revised)
        return revised
    if canvas_size is None or image_size is None:
        raise ValueError("Canvas and image dimensions are required for a new box")
    replacement = make_annotation(
        image_path=original.image_path,
        target_type=target_type,
        asset_id=asset_id,
        review_status=review_status,
        box=box,
        canvas_size=canvas_size,
        image_size=image_size,
        inspection_id=original.inspection_id,
        source_provenance=original.source_provenance,
    )
    return replace(
        original,
        x_min=replacement.x_min,
        y_min=replacement.y_min,
        x_max=replacement.x_max,
        y_max=replacement.y_max,
        image_width=replacement.image_width,
        image_height=replacement.image_height,
        target_type=target_type,
        asset_id=asset_id.strip(),
        review_status=review_status,
        modified_at_utc=datetime.now(timezone.utc).isoformat(),
        annotation_id=original.annotation_id,
        created_at_utc=original.created_at_utc,
    )


def load_annotations(path: Path) -> list[PanelAnnotation]:
    """Read annotations from CSV, returning an empty list when no file exists."""
    source = Path(path)
    if not source.exists():
        return []

    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required_fields = set(ANNOTATION_FIELDS[:11])
        if reader.fieldnames is None or not required_fields.issubset(reader.fieldnames):
            raise ValueError("Annotation CSV is missing required columns")

        annotations = []
        seen_ids = set()
        seen_assets = set()
        for line_number, row in enumerate(reader, start=2):
            try:
                annotation = PanelAnnotation(
                    annotation_id=row["annotation_id"],
                    image_path=row["image_path"],
                    target_type=row["target_type"],
                    asset_id=row["asset_id"],
                    x_min=float(row["x_min"]),
                    y_min=float(row["y_min"]),
                    x_max=float(row["x_max"]),
                    y_max=float(row["y_max"]),
                    image_width=int(row["image_width"]),
                    image_height=int(row["image_height"]),
                    created_at_utc=row["created_at_utc"],
                    review_status=row.get("review_status") or "provisional",
                    inspection_id=row.get("inspection_id") or "",
                    source_image_id=row.get("source_image_id") or image_identifier(
                        row.get("inspection_id") or "", row["image_path"]
                    ),
                    source_provenance=row.get("source_provenance") or "unknown",
                    linked_asset_id=row.get("linked_asset_id") or "",
                    linked_asset_type=row.get("linked_asset_type") or "",
                    mapping_method=row.get("mapping_method") or "",
                    mapping_status=row.get("mapping_status") or "unmapped",
                    mapping_evidence=row.get("mapping_evidence") or "",
                    reviewer_notes=row.get("reviewer_notes") or "",
                    observation_note=row.get("observation_note") or "",
                    possible_cause=row.get("possible_cause") or "",
                    observation_review_status=row.get("observation_review_status") or "pending",
                    modified_at_utc=row.get("modified_at_utc") or row["created_at_utc"],
                    observation_category=row.get("observation_category") or "unclassified",
                    finding_status=row.get("finding_status") or "draft",
                    severity=row.get("severity") or "unassigned",
                    thermal_region_bounds=row.get("thermal_region_bounds") or "",
                    thermal_reference_bounds=row.get("thermal_reference_bounds") or "",
                )
                _validate(annotation)
                _validate_unique(annotation, seen_ids, seen_assets)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid annotation CSV row {line_number}: {exc}") from exc
            seen_ids.add(annotation.annotation_id)
            if annotation.asset_id:
                seen_assets.add((annotation.image_path, annotation.asset_id.casefold()))
            if annotation.linked_asset_id:
                seen_assets.add((annotation.image_path, "registry:" + annotation.linked_asset_id.casefold()))
            annotations.append(annotation)
    return annotations


def save_annotations(path: Path, annotations: list[PanelAnnotation]) -> Path:
    """Write annotations to CSV using a temporary file before replacing the target."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    seen_ids = set()
    seen_assets = set()
    for annotation in annotations:
        _validate(annotation)
        _validate_unique(annotation, seen_ids, seen_assets)
        seen_ids.add(annotation.annotation_id)
        if annotation.asset_id:
            seen_assets.add((annotation.image_path, annotation.asset_id.casefold()))
        if annotation.linked_asset_id:
            seen_assets.add((annotation.image_path, "registry:" + annotation.linked_asset_id.casefold()))

    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        for annotation in annotations:
            writer.writerow(asdict(annotation))
    if target.is_file():
        with target.open("r", encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
        if not set(ANNOTATION_FIELDS).issubset(header):
            backup_suffix = ".pre_asset_link.csv" if "linked_asset_id" not in header else ".pre_phase4.csv"
            backup = target.with_name(target.name + backup_suffix)
            if not backup.exists():
                shutil.copy2(target, backup)
    temporary.replace(target)
    return target


def _validate(annotation: PanelAnnotation) -> None:
    if not annotation.annotation_id or not annotation.image_path:
        raise ValueError("annotation_id and image_path are required")
    if annotation.target_type not in {"panel", "row", "region"}:
        raise ValueError("target_type must be 'panel', 'row', or 'region'")
    if annotation.review_status not in REVIEW_STATUSES:
        raise ValueError("review_status must be 'provisional' or 'confirmed'")
    if annotation.image_width <= 0 or annotation.image_height <= 0:
        raise ValueError("image dimensions must be positive")
    if not annotation.source_image_id.startswith("img-"):
        raise ValueError("source_image_id is required")
    if annotation.source_provenance not in SOURCE_PROVENANCE:
        raise ValueError("invalid source provenance")
    if annotation.mapping_status not in MAPPING_STATUSES:
        raise ValueError("invalid mapping status")
    if annotation.linked_asset_id and annotation.mapping_status == "unmapped":
        raise ValueError("a linked asset cannot be unmapped")
    if not annotation.linked_asset_id and annotation.mapping_status != "unmapped":
        raise ValueError("an unlinked annotation must be unmapped")
    if annotation.mapping_status == "verified" and not annotation.mapping_evidence.strip():
        raise ValueError("verified mapping requires an approved evidence reference")
    if annotation.observation_review_status not in {"pending", "reviewed"}:
        raise ValueError("invalid observation review status")
    if annotation.observation_category not in {
        "unclassified", "localized_heating", "uneven_appearance", "possible_shading",
        "possible_soiling_or_obstruction", "other_irregularity", "no_visible_anomaly",
    }:
        raise ValueError("invalid observation category")
    if annotation.finding_status not in {"draft", "needs_verification", "reviewed", "resolved"}:
        raise ValueError("invalid finding status")
    if annotation.severity not in {"unassigned", "low", "medium", "high"}:
        raise ValueError("invalid reviewer severity")
    for stored_bounds in (annotation.thermal_region_bounds, annotation.thermal_reference_bounds):
        if not stored_bounds:
            continue
        try:
            bounds = tuple(float(value) for value in stored_bounds.split(","))
        except ValueError as exc:
            raise ValueError("invalid thermal region bounds") from exc
        if len(bounds) != 4 or not (
            0 <= bounds[0] < bounds[2] <= 1 and 0 <= bounds[1] < bounds[3] <= 1
        ):
            raise ValueError("invalid thermal region bounds")
    if not (
        0 <= annotation.x_min < annotation.x_max <= 1
        and 0 <= annotation.y_min < annotation.y_max <= 1
    ):
        raise ValueError("normalized box coordinates must be ordered within 0..1")


def _validate_unique(
    annotation: PanelAnnotation,
    seen_ids: set[str],
    seen_assets: set[tuple[str, str]],
) -> None:
    if annotation.annotation_id in seen_ids:
        raise ValueError(f"duplicate annotation_id: {annotation.annotation_id}")
    if annotation.asset_id and (annotation.image_path, annotation.asset_id.casefold()) in seen_assets:
        raise ValueError(f"duplicate plant ID in image: {annotation.asset_id}")
    if annotation.linked_asset_id and (
        annotation.image_path, "registry:" + annotation.linked_asset_id.casefold()
    ) in seen_assets:
        raise ValueError(f"duplicate linked asset in image: {annotation.linked_asset_id}")
