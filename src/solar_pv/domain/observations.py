"""Inspection observations assembled from reviewed image pairs and saved labels."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image

from solar_pv.domain.assets import AssetRegistry
from solar_pv.imaging.annotations import PanelAnnotation
from solar_pv.imaging.pairing import ImagePair
from solar_pv.imaging.thermal import (
    analyze_panels, compare_regions, load_paired_thermal_frame, measurement_basis,
    region_statistics,
)


@dataclass(frozen=True)
class Observation:
    record_id: str
    inspection_id: str
    pair_id: str
    annotation_id: str
    asset_id: str
    asset_level: str
    asset_id_status: str
    box_review_status: str
    label_source: str
    captured_at: str
    rgb_image_path: str
    thermal_image_path: str
    temperature_source_path: str
    alignment_reviewed: bool
    radiometric_valid: bool
    median_temperature_c: float | None
    reference_temperature_c: float | None
    delta_t_c: float | None
    candidate: bool
    candidate_threshold_c: float | None
    comparison_method: str
    data_quality_flags: tuple[str, ...]
    synthetic: bool
    source_image_id: str = ""
    linked_asset_id: str = ""
    linked_asset_type: str = ""
    mapping_method: str = ""
    mapping_status: str = "unmapped"
    mapping_evidence: str = ""
    reviewer_notes: str = ""
    observation_note: str = ""
    possible_cause: str = ""
    observation_review_status: str = "pending"
    source_provenance: str = "unknown"
    measurement_basis: str = "display_only"
    temperature_unit: str = ""
    minimum_temperature: float | None = None
    maximum_temperature: float | None = None
    mean_temperature: float | None = None
    median_temperature: float | None = None
    reference_temperature: float | None = None
    delta_temperature: float | None = None
    sample_count: int | None = None
    excluded_sample_count: int | None = None
    thermal_region_bounds: str = ""
    thermal_reference_bounds: str = ""
    calibration_reference: str = ""
    observation_category: str = "unclassified"
    finding_status: str = "draft"
    severity: str = "unassigned"
    created_at_utc: str = ""
    modified_at_utc: str = ""
    scada_source_file: str = ""
    scada_scope: str = "unknown"
    scada_timezone_status: str = "unknown"
    correlation_status: str = "blocked"
    correlation_missing: tuple[str, ...] = ()


def build_observations(
    inspection_root: Path,
    pair: ImagePair,
    annotations: list[PanelAnnotation],
    *,
    threshold_c: float = 5.0,
    registry: AssetRegistry | None = None,
    require_confirmed_panels: bool = False,
) -> list[Observation]:
    """Transfer boxes only for a reviewed, same-size RGB/thermal image pair."""
    root = Path(inspection_root).resolve()
    frame = load_paired_thermal_frame(
        root,
        pair.thermal_path,
        pair.temperature_path,
        synthetic=pair.synthetic,
    )

    with Image.open(root / pair.rgb_path) as rgb, Image.open(root / pair.thermal_path) as thermal:
        rgb.load()
        thermal.load()
        if thermal.size != (frame.image_width, frame.image_height):
            raise ValueError("Thermal preview and temperature frame must have the same dimensions")
        if pair.alignment_reviewed and rgb.size != thermal.size:
            raise ValueError("RGB, thermal preview and temperature frame must have the same dimensions")
        image_size = rgb.size

    selected = [
        row for row in annotations
        if row.image_path == pair.rgb_path and row.target_type == "panel"
    ]
    if not pair.alignment_reviewed:
        selected = [row for row in selected if row.thermal_region_bounds]
        if not selected:
            raise ValueError("Image alignment must be reviewed before transferring panel boxes")
    if any((row.image_width, row.image_height) != image_size for row in selected):
        raise ValueError("A saved panel box has dimensions that do not match the paired images")
    comparable = [row for row in selected if not require_confirmed_panels or row.review_status == "confirmed"]
    mapped = [replace(row, image_path=pair.thermal_path) for row in comparable] if pair.alignment_reviewed else []
    findings = (
        {row.annotation_id: row for row in analyze_panels(frame, mapped, threshold_c=threshold_c)}
        if mapped and measurement_basis(frame) in {"synthetic_numeric_demo", "calibrated_numeric"} else {}
    )

    observations = []
    for row in selected:
        finding = findings.get(row.annotation_id)
        region = None
        explicit_comparison = None
        if row.thermal_region_bounds and measurement_basis(frame) in {"synthetic_numeric_demo", "calibrated_numeric"}:
            region = region_statistics(
                frame, row.annotation_id,
                tuple(float(value) for value in row.thermal_region_bounds.split(",")),
            )
            if row.thermal_reference_bounds:
                reference_region = region_statistics(
                    frame, row.annotation_id + ":reference",
                    tuple(float(value) for value in row.thermal_reference_bounds.split(",")),
                )
                explicit_comparison = compare_regions(region, reference_region)
        flags = []
        mapping_status = row.mapping_status
        if row.linked_asset_id and registry is not None and registry.get(row.linked_asset_id) is None:
            mapping_status = "unresolved"
            flags.append("asset_mapping_unresolved")
        elif row.linked_asset_id and registry is None:
            flags.append("asset_registry_not_checked")
        synthetic = frame.synthetic or row.source_provenance == "synthetic"
        if synthetic:
            flags.append("synthetic_data")
        if not pair.alignment_reviewed:
            flags.append("independent_thermal_region_unregistered")
        if not row.asset_id or synthetic:
            flags.append("asset_id_unverified")
        if row.linked_asset_id and mapping_status != "verified":
            flags.append("asset_mapping_unverified")
        if measurement_basis(frame) == "display_only":
            flags.append("non_radiometric")
        elif measurement_basis(frame) == "unverified_numeric":
            flags.append("calibration_unverified")
        elif require_confirmed_panels and row.review_status != "confirmed" and region is None:
            flags.append("box_not_confirmed")
        elif finding and finding.delta_c is None:
            flags.append("no_comparable_panel")
        if not frame.captured_at or frame.captured_at == "Unknown":
            flags.append("missing_capture_time")
        identity = f"{pair.inspection_id}|{pair.pair_id}|{row.annotation_id}"
        observations.append(
            Observation(
                record_id="obs-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16],
                inspection_id=pair.inspection_id,
                pair_id=pair.pair_id,
                annotation_id=row.annotation_id,
                asset_id=row.asset_id,
                asset_level="panel",
                asset_id_status="unverified",
                box_review_status=row.review_status,
                label_source="manual",
                captured_at=frame.captured_at,
                rgb_image_path=pair.rgb_path,
                thermal_image_path=pair.thermal_path,
                temperature_source_path=pair.temperature_path,
                alignment_reviewed=pair.alignment_reviewed,
                radiometric_valid=measurement_basis(frame) in {"synthetic_numeric_demo", "calibrated_numeric"},
                median_temperature_c=round(_celsius(region.median, region.unit), 2) if region else round(finding.median_c, 2) if finding else None,
                reference_temperature_c=round(_celsius(explicit_comparison.reference.median, region.unit), 2) if explicit_comparison else round(finding.reference_c, 2) if finding and finding.reference_c is not None else None,
                delta_t_c=round(explicit_comparison.delta_median * (5 / 9 if region.unit == "F" else 1), 2) if explicit_comparison else round(finding.delta_c, 2) if finding and finding.delta_c is not None else None,
                candidate=finding.candidate if finding and not region else False,
                candidate_threshold_c=None if region else threshold_c,
                comparison_method="selected_median_minus_reference_median" if explicit_comparison else "independent_thermal_region" if region else "median_of_nearest_two_labeled_panels" if finding else "unavailable",
                data_quality_flags=tuple(flags),
                synthetic=synthetic,
                source_image_id=row.source_image_id,
                linked_asset_id=row.linked_asset_id,
                linked_asset_type=row.linked_asset_type,
                mapping_method=row.mapping_method,
                mapping_status=mapping_status,
                mapping_evidence=row.mapping_evidence,
                reviewer_notes=row.reviewer_notes,
                observation_note=row.observation_note,
                possible_cause=row.possible_cause,
                observation_review_status=row.observation_review_status,
                source_provenance=row.source_provenance,
                measurement_basis=measurement_basis(frame),
                temperature_unit=frame.unit if frame.radiometric else "",
                minimum_temperature=round(region.minimum, 2) if region else None,
                maximum_temperature=round(region.maximum, 2) if region else None,
                mean_temperature=round(region.mean, 2) if region else None,
                median_temperature=round(region.median, 2) if region else None,
                reference_temperature=round(explicit_comparison.reference.median, 2) if explicit_comparison else None,
                delta_temperature=round(explicit_comparison.delta_median, 2) if explicit_comparison else None,
                sample_count=region.sample_count if region else None,
                excluded_sample_count=region.excluded_count if region else None,
                thermal_region_bounds=row.thermal_region_bounds,
                thermal_reference_bounds=row.thermal_reference_bounds,
                calibration_reference=frame.calibration_reference,
                observation_category=row.observation_category,
                finding_status=row.finding_status,
                severity=row.severity,
                created_at_utc=row.created_at_utc,
                modified_at_utc=row.modified_at_utc,
                correlation_missing=("meter scope unknown", "meter timezone unknown", "asset relationship unverified"),
            )
        )
    return observations


def _celsius(value: float, unit: str) -> float:
    return (value - 32) * 5 / 9 if unit == "F" else value
