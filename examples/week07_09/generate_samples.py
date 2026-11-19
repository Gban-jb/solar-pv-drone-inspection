"""Generate fabricated temperature grids for the Week 7-9 viewer prototype."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from solar_pv.imaging.thermal import load_thermal_frame, render_temperature_grid


PROJECT_ROOT = Path(__file__).resolve().parents[2]
THERMAL_DIR = PROJECT_ROOT / "examples/week07_09/inspection/thermal"
OUTPUT_DIR = PROJECT_ROOT / "examples/week07_09/output"
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 840
GRID_WIDTH = 72
GRID_HEIGHT = 48
PANEL_BOXES = ((0.08, 0.20, 0.30, 0.80), (0.39, 0.20, 0.61, 0.80), (0.70, 0.20, 0.92, 0.80))
CASES = (
    ("synthetic_case_01", (42.0, 42.5, 51.0), 2),
    ("synthetic_case_02", (44.0, 45.0, 44.5), None),
    ("synthetic_case_03", (39.0, 43.0, 48.0), 2),
)


def make_grid(baselines: tuple[float, float, float], warm_panel: int | None) -> list[list[float]]:
    grid = []
    for y in range(GRID_HEIGHT):
        row = []
        for x in range(GRID_WIDTH):
            value = 27.0 + (x / GRID_WIDTH) * 0.4 + (y / GRID_HEIGHT) * 0.3
            for panel_index, (left, top, right, bottom) in enumerate(PANEL_BOXES):
                inside = left <= (x + 0.5) / GRID_WIDTH <= right and top <= (y + 0.5) / GRID_HEIGHT <= bottom
                if inside:
                    value = baselines[panel_index] + ((x % 7) * 0.08) + ((y % 5) * 0.05)
                    if panel_index == warm_panel:
                        value += 1.2
                        hot_center_x = (left + right) / 2
                        hot_center_y = (top + bottom) / 2
                        if abs((x + 0.5) / GRID_WIDTH - hot_center_x) < 0.055 and abs((y + 0.5) / GRID_HEIGHT - hot_center_y) < 0.20:
                            value += 7.0
                    break
            row.append(round(value, 2))
        grid.append(row)
    return grid


def write_frame(name: str, baselines: tuple[float, float, float], warm_panel: int | None) -> None:
    image_name = f"{name}.png"
    metadata = {
        "schema_version": 1,
        "image_path": f"thermal/{image_name}",
        "preview_path": image_name,
        "image_width": IMAGE_WIDTH,
        "image_height": IMAGE_HEIGHT,
        "unit": "C",
        "captured_at": "2026-10-20T14:30:00-05:00",
        "radiometric_available": True,
        "synthetic": True,
        "temperature_grid": make_grid(baselines, warm_panel),
    }
    data_path = THERMAL_DIR / f"{name}.json"
    data_path.write_text(json.dumps(metadata, separators=(",", ":")) + "\n", encoding="utf-8")
    preview = render_temperature_grid(load_thermal_frame(data_path))
    preview.save(THERMAL_DIR / image_name)


def write_nonradiometric_example() -> None:
    image_name = "nonradiometric_color_only.png"
    metadata = {
        "schema_version": 1,
        "image_path": f"thermal/{image_name}",
        "preview_path": image_name,
        "image_width": IMAGE_WIDTH,
        "image_height": IMAGE_HEIGHT,
        "unit": "C",
        "captured_at": "2026-10-20T14:35:00-05:00",
        "radiometric_available": False,
        "synthetic": True,
        "temperature_grid": None,
    }
    (THERMAL_DIR / "nonradiometric_color_only.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    image = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT), "#242334")
    draw = ImageDraw.Draw(image)
    for row, box in enumerate(PANEL_BOXES):
        x0, y0, x1, y1 = (round(box[0] * IMAGE_WIDTH), round(box[1] * IMAGE_HEIGHT), round(box[2] * IMAGE_WIDTH), round(box[3] * IMAGE_HEIGHT))
        draw.rectangle((x0, y0, x1, y1), fill=(100 + row * 35, 44 + row * 12, 110 + row * 18), outline="#D8D8D2", width=3)
    image.save(THERMAL_DIR / image_name)


def write_annotations() -> None:
    fields = (
        "annotation_id", "image_path", "target_type", "asset_id", "x_min", "y_min", "x_max", "y_max",
        "image_width", "image_height", "created_at_utc", "review_status",
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / "thermal_panel_annotations.csv"
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name, _, _ in CASES:
            for panel_index, box in enumerate(PANEL_BOXES, start=1):
                writer.writerow(
                    {
                        "annotation_id": f"syn-{name[-2:]}-{panel_index}",
                        "image_path": f"thermal/{name}.png",
                        "target_type": "panel",
                        "asset_id": f"SYN-{name[-2:]}-P{panel_index:02d}",
                        "x_min": box[0], "y_min": box[1], "x_max": box[2], "y_max": box[3],
                        "image_width": IMAGE_WIDTH, "image_height": IMAGE_HEIGHT,
                        "created_at_utc": datetime(2026, 10, 28, tzinfo=timezone.utc).isoformat(),
                        "review_status": "confirmed",
                    }
                )
        for panel_index, box in enumerate(PANEL_BOXES, start=1):
            writer.writerow(
                {
                    "annotation_id": f"syn-color-{panel_index}",
                    "image_path": "thermal/nonradiometric_color_only.png",
                    "target_type": "panel",
                    "asset_id": f"SYN-COLOR-P{panel_index:02d}",
                    "x_min": box[0], "y_min": box[1], "x_max": box[2], "y_max": box[3],
                    "image_width": IMAGE_WIDTH, "image_height": IMAGE_HEIGHT,
                    "created_at_utc": datetime(2026, 10, 28, tzinfo=timezone.utc).isoformat(),
                    "review_status": "confirmed",
                }
            )


def main() -> None:
    THERMAL_DIR.mkdir(parents=True, exist_ok=True)
    for name, baselines, warm_panel in CASES:
        write_frame(name, baselines, warm_panel)
    write_nonradiometric_example()
    write_annotations()
    print(f"Created synthetic thermal review examples in {THERMAL_DIR.parent}")


if __name__ == "__main__":
    main()
