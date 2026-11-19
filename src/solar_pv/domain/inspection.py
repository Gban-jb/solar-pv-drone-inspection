"""Inspection-wide readiness and export decisions for saved image pairs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from solar_pv.domain.assets import AssetRegistry
from solar_pv.domain.observations import Observation, build_observations
from solar_pv.imaging.annotations import PanelAnnotation
from solar_pv.imaging.pairing import ImagePair
from solar_pv.imaging.thermal import load_paired_thermal_frame, measurement_basis


@dataclass(frozen=True)
class PairReview:
    pair: ImagePair
    panel_count: int
    thermal_status: str
    observations: tuple[Observation, ...]
    reason: str

    @property
    def included(self) -> bool:
        return not self.reason and bool(self.observations)


def review_pairs(
    root: Path, pairs: list[ImagePair], annotations: list[PanelAnnotation],
    *, registry: AssetRegistry | None = None, require_confirmed_panels: bool = False,
) -> list[PairReview]:
    """Assess every pair independently so one bad pair cannot hide valid exports."""
    reviews = []
    for pair in pairs:
        panel_count = sum(
            row.image_path == pair.rgb_path and row.target_type == "panel"
            for row in annotations
        )
        thermal_status = "Display only" if not pair.temperature_path else "Unreadable"
        try:
            frame = load_paired_thermal_frame(
                root, pair.thermal_path, pair.temperature_path, synthetic=pair.synthetic
            )
            basis = measurement_basis(frame)
            thermal_status = {
                "calibrated_numeric": "Pixel temperatures",
                "synthetic_numeric_demo": "Pixel temperatures",
                "unverified_numeric": "Calibration unverified",
                "display_only": "Display only",
            }[basis]
            independent = any(
                row.image_path == pair.rgb_path and row.thermal_region_bounds
                for row in annotations
            )
            if not pair.alignment_reviewed and not independent:
                reason = "Alignment has not been reviewed"
                observations = ()
            elif not panel_count:
                reason = "No saved panel labels for the RGB image"
                observations = ()
            else:
                observations = tuple(build_observations(
                    root, pair, annotations, registry=registry, require_confirmed_panels=require_confirmed_panels,
                ))
                reason = "" if observations else "No panel observations were produced"
        except (OSError, ValueError) as exc:
            observations = ()
            reason = str(exc)
        reviews.append(PairReview(pair, panel_count, thermal_status, observations, reason))
    return reviews
