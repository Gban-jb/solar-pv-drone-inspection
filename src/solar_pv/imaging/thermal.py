"""Read the prototype temperature-grid format and compare labeled panels."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median

from PIL import Image, ImageDraw

from solar_pv.imaging.annotations import PanelAnnotation


@dataclass(frozen=True)
class ThermalFrame:
    image_path: str
    preview_path: str
    image_width: int
    image_height: int
    unit: str
    captured_at: str
    radiometric: bool
    synthetic: bool
    temperatures: tuple[tuple[float, ...], ...] | None
    calibration_status: str = "unverified"
    calibration_reference: str = ""


@dataclass(frozen=True)
class RegionStatistics:
    region_id: str
    bounds: tuple[float, float, float, float]
    minimum: float
    maximum: float
    mean: float
    median: float
    sample_count: int
    excluded_count: int
    unit: str
    source_image: str
    measurement_basis: str
    calibration_reference: str


@dataclass(frozen=True)
class RegionComparison:
    selected: RegionStatistics
    reference: RegionStatistics
    delta_median: float
    method: str = "selected_median_minus_reference_median"


def measurement_basis(frame: ThermalFrame) -> str:
    """Separate an explicit synthetic grid from a calibrated field measurement."""
    if not frame.radiometric or frame.temperatures is None:
        return "display_only"
    if frame.synthetic:
        return "synthetic_numeric_demo"
    if frame.calibration_status == "verified" and frame.calibration_reference:
        return "calibrated_numeric"
    return "unverified_numeric"


def region_statistics(
    frame: ThermalFrame, region_id: str, bounds: tuple[float, float, float, float]
) -> RegionStatistics:
    """Measure an independently selected thermal-grid rectangle; null pixels are excluded."""
    basis = measurement_basis(frame)
    if basis not in {"synthetic_numeric_demo", "calibrated_numeric"}:
        raise ValueError("No validated numeric temperature source is available")
    if len(bounds) != 4 or any(not math.isfinite(value) for value in bounds):
        raise ValueError("Region bounds must be four finite normalized numbers")
    x0, y0, x1, y1 = bounds
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("Region bounds must lie inside the image and have positive area")
    grid = frame.temperatures
    assert grid is not None
    height, width = len(grid), len(grid[0])
    left, top = math.floor(x0 * width), math.floor(y0 * height)
    right, bottom = math.ceil(x1 * width), math.ceil(y1 * height)
    if left >= right or top >= bottom:
        raise ValueError("Selected region contains no grid pixels")
    raw = [value for row in grid[top:bottom] for value in row[left:right]]
    valid = [value for value in raw if value is not None and math.isfinite(value)]
    if not valid:
        raise ValueError("Selected region has no valid temperature samples")
    return RegionStatistics(
        region_id=region_id,
        bounds=bounds,
        minimum=min(valid), maximum=max(valid), mean=mean(valid), median=median(valid),
        sample_count=len(valid), excluded_count=len(raw) - len(valid), unit=frame.unit,
        source_image=frame.image_path, measurement_basis=basis,
        calibration_reference=frame.calibration_reference,
    )


def compare_regions(selected: RegionStatistics, reference: RegionStatistics) -> RegionComparison:
    """Only compare regions from the same source, units and measurement basis."""
    if selected.region_id == reference.region_id:
        raise ValueError("Select a distinct reference region")
    if (selected.source_image, selected.unit, selected.measurement_basis, selected.calibration_reference) != (
        reference.source_image, reference.unit, reference.measurement_basis, reference.calibration_reference
    ):
        raise ValueError("Temperature regions have incompatible measurement context")
    return RegionComparison(selected, reference, selected.median - reference.median)


@dataclass(frozen=True)
class PanelTemperature:
    annotation_id: str
    asset_id: str
    median_c: float
    reference_c: float | None
    delta_c: float | None
    candidate: bool


def load_thermal_frame(path: Path) -> ThermalFrame:
    """Load a documented prototype JSON frame, including non-radiometric metadata."""
    source = Path(path)
    with source.open("r", encoding="utf-8") as stream:
        record = json.load(stream)

    if record.get("schema_version") != 1:
        raise ValueError("Unsupported thermal sample schema")
    unit = str(record.get("unit", "")).upper()
    if unit not in {"C", "F"}:
        raise ValueError("Temperature unit must be C or F")
    width = int(record.get("image_width", 0))
    height = int(record.get("image_height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive")

    radiometric = bool(record.get("radiometric_available", False))
    grid = record.get("temperature_grid")
    temperatures = None
    if radiometric:
        if not isinstance(grid, list) or not grid or not all(isinstance(row, list) for row in grid):
            raise ValueError("Radiometric frame must include a temperature grid")
        row_width = len(grid[0])
        if row_width == 0 or any(len(row) != row_width for row in grid):
            raise ValueError("Temperature grid must be rectangular")
        if len(grid) * row_width > 10_000_000:
            raise ValueError("Temperature grid exceeds the supported size")
        try:
            temperatures = tuple(tuple(float(value) if value is not None else None for value in row) for row in grid)
        except (TypeError, ValueError) as exc:
            raise ValueError("Temperature grid contains a non-numeric value") from exc
        if any(not math.isfinite(value) for row in temperatures for value in row if value is not None):
            raise ValueError("Temperature grid contains a non-finite value")

    return ThermalFrame(
        image_path=str(record.get("image_path", "")),
        preview_path=str(record.get("preview_path", "")),
        image_width=width,
        image_height=height,
        unit=unit,
        captured_at=str(record.get("captured_at", "Unknown")),
        radiometric=radiometric,
        synthetic=bool(record.get("synthetic", False)),
        temperatures=temperatures,
        calibration_status=str(record.get("calibration_status", "unverified")),
        calibration_reference=str(record.get("calibration_reference", "")),
    )


def load_paired_thermal_frame(
    inspection_root: Path,
    thermal_path: str,
    temperature_path: str,
    *,
    synthetic: bool = False,
) -> ThermalFrame:
    """Load temperature metadata when present, otherwise treat the image as display-only."""
    root = Path(inspection_root).resolve()
    if temperature_path:
        frame = load_thermal_frame(root / temperature_path)
        if frame.image_path != thermal_path:
            raise ValueError("Temperature metadata refers to a different thermal image")
        if synthetic and not frame.synthetic:
            frame = ThermalFrame(
                image_path=frame.image_path,
                preview_path=frame.preview_path,
                image_width=frame.image_width,
                image_height=frame.image_height,
                unit=frame.unit,
                captured_at=frame.captured_at,
                radiometric=frame.radiometric,
                synthetic=True,
                temperatures=frame.temperatures,
            )
        return frame

    image_file = root / thermal_path
    with Image.open(image_file) as image:
        image.load()
        width, height = image.size
        exif = image.getexif()
        captured_at = str(exif.get(36867) or exif.get(306) or "Unknown")
    return ThermalFrame(
        image_path=thermal_path,
        preview_path=thermal_path,
        image_width=width,
        image_height=height,
        unit="C",
        captured_at=captured_at,
        radiometric=False,
        synthetic=synthetic,
        temperatures=None,
    )


def analyze_panels(
    frame: ThermalFrame,
    annotations: list[PanelAnnotation],
    *,
    image_path: str | None = None,
    threshold_c: float = 5.0,
    neighbor_count: int = 2,
) -> list[PanelTemperature]:
    """Compare labeled panels in the paired image with nearby labeled panels.

    ``image_path`` is the RGB annotation path for aligned RGB/thermal pairs. When
    omitted, annotations must refer to the thermal frame's own image path.
    """
    if measurement_basis(frame) not in {"synthetic_numeric_demo", "calibrated_numeric"}:
        raise ValueError("This image does not contain readable radiometric temperatures")
    if not math.isfinite(threshold_c) or threshold_c < 0:
        raise ValueError("Threshold must be a finite non-negative temperature difference")
    if neighbor_count < 1:
        raise ValueError("At least one comparable panel is required")

    annotation_image = image_path or frame.image_path
    panels = [
        row for row in annotations
        if row.image_path == annotation_image and row.target_type == "panel"
    ]
    if not panels:
        return []

    grid = frame.temperatures
    grid_height = len(grid)
    grid_width = len(grid[0])
    values_c: dict[str, float] = {}
    centers: dict[str, tuple[float, float]] = {}
    for panel in panels:
        x0 = max(0, min(grid_width - 1, math.floor(panel.x_min * grid_width)))
        y0 = max(0, min(grid_height - 1, math.floor(panel.y_min * grid_height)))
        x1 = max(x0 + 1, min(grid_width, math.ceil(panel.x_max * grid_width)))
        y1 = max(y0 + 1, min(grid_height, math.ceil(panel.y_max * grid_height)))
        samples = [value for row in grid[y0:y1] for value in row[x0:x1] if value is not None]
        if not samples:
            raise ValueError(f"Panel {panel.annotation_id} has no valid temperature samples")
        measured = median(samples)
        values_c[panel.annotation_id] = _to_celsius(measured, frame.unit)
        centers[panel.annotation_id] = (
            (panel.x_min + panel.x_max) / 2,
            (panel.y_min + panel.y_max) / 2,
        )

    results = []
    for panel in panels:
        neighbors = sorted(
            (other for other in panels if other.annotation_id != panel.annotation_id),
            key=lambda other: _distance(centers[panel.annotation_id], centers[other.annotation_id]),
        )[:neighbor_count]
        reference = median([values_c[other.annotation_id] for other in neighbors]) if neighbors else None
        measured = values_c[panel.annotation_id]
        delta = measured - reference if reference is not None else None
        results.append(
            PanelTemperature(
                annotation_id=panel.annotation_id,
                asset_id=panel.asset_id or panel.annotation_id,
                median_c=measured,
                reference_c=reference,
                delta_c=delta,
                candidate=delta is not None and delta >= threshold_c,
            )
        )
    return results


def temperature_limits_c(
    frame: ThermalFrame,
    annotations: list[PanelAnnotation] | None = None,
) -> tuple[float, float]:
    """Use the coolest panel median and hottest in-panel pixel as display bounds."""
    if frame.temperatures is None:
        raise ValueError("No temperature grid is available for this image")
    grid_height, grid_width = len(frame.temperatures), len(frame.temperatures[0])
    samples: list[float] = []
    panel_medians: list[float] = []
    for panel in annotations or []:
        if panel.target_type != "panel":
            continue
        x0 = max(0, min(grid_width - 1, math.floor(panel.x_min * grid_width)))
        y0 = max(0, min(grid_height - 1, math.floor(panel.y_min * grid_height)))
        x1 = max(x0 + 1, min(grid_width, math.ceil(panel.x_max * grid_width)))
        y1 = max(y0 + 1, min(grid_height, math.ceil(panel.y_max * grid_height)))
        panel_values = [value for row in frame.temperatures[y0:y1] for value in row[x0:x1] if value is not None]
        if not panel_values:
            continue
        samples.extend(panel_values)
        panel_medians.append(median(panel_values))
    if not samples:
        samples = [value for row in frame.temperatures for value in row if value is not None]
    if not samples:
        raise ValueError("No valid temperature samples are available")
    values = [_to_celsius(value, frame.unit) for value in samples]
    panel_medians_c = [_to_celsius(value, frame.unit) for value in panel_medians]
    low = math.floor(min(panel_medians_c)) if panel_medians_c else math.floor(min(values))
    high = math.ceil(max(values))
    if low == high:
        low -= 1
        high += 1
    return float(low), float(high)


def render_temperature_grid(
    frame: ThermalFrame,
    *,
    min_c: float | None = None,
    max_c: float | None = None,
    annotations: list[PanelAnnotation] | None = None,
) -> Image.Image:
    """Colorize temperatures, optionally restricting color to labeled panel boxes."""
    if frame.temperatures is None:
        raise ValueError("No temperature grid is available for this image")
    default_min, default_max = temperature_limits_c(frame)
    low = default_min if min_c is None else float(min_c)
    high = default_max if max_c is None else float(max_c)
    if not math.isfinite(low) or not math.isfinite(high) or low >= high:
        raise ValueError("Color scale maximum must be greater than its minimum")
    grid = Image.new("RGB", (len(frame.temperatures[0]), len(frame.temperatures)))
    pixels = []
    for row in frame.temperatures:
        for value in row:
            if value is None:
                pixels.append((120, 120, 120))
            else:
                value_c = _to_celsius(value, frame.unit)
                pixels.append(_heat_color((value_c - low) / (high - low)))
    grid.putdata(pixels)
    colorized = grid.resize((frame.image_width, frame.image_height), Image.Resampling.BILINEAR)
    if annotations is None:
        return colorized

    mask = Image.new("L", (frame.image_width, frame.image_height), 0)
    draw = ImageDraw.Draw(mask)
    for panel in annotations:
        if panel.target_type != "panel":
            continue
        bounds = (
            max(0, min(frame.image_width - 1, round(panel.x_min * frame.image_width))),
            max(0, min(frame.image_height - 1, round(panel.y_min * frame.image_height))),
            max(0, min(frame.image_width - 1, round(panel.x_max * frame.image_width))),
            max(0, min(frame.image_height - 1, round(panel.y_max * frame.image_height))),
        )
        draw.rectangle(bounds, fill=255)
    neutral_background = Image.new("RGB", colorized.size, (238, 241, 240))
    return Image.composite(colorized, neutral_background, mask)


def render_temperature_colorbar(min_c: float, max_c: float, *, width: int = 600, height: int = 22) -> Image.Image:
    """Render the same cool-blue to hot-red scale used by the thermal preview."""
    if not math.isfinite(min_c) or not math.isfinite(max_c) or min_c >= max_c:
        raise ValueError("Color scale maximum must be greater than its minimum")
    if width < 2 or height < 1:
        raise ValueError("Color bar dimensions must be positive")
    bar = Image.new("RGB", (width, height))
    bar.putdata([
        _heat_color(index / (width - 1))
        for _y in range(height)
        for index in range(width)
    ])
    return bar


def _to_celsius(value: float, unit: str) -> float:
    return value if unit == "C" else (value - 32) * 5 / 9


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _heat_color(position: float) -> tuple[int, int, int]:
    stops = (
        (39, 76, 119),   # cool blue
        (59, 130, 160),  # blue teal
        (112, 163, 155), # muted teal
        (217, 199, 106), # warm yellow
        (232, 146, 74),  # orange
        (201, 74, 60),   # hot red
    )
    scaled = max(0.0, min(1.0, position)) * (len(stops) - 1)
    index = min(int(scaled), len(stops) - 2)
    mix = scaled - index
    return tuple(round(stops[index][channel] * (1 - mix) + stops[index + 1][channel] * mix) for channel in range(3))
