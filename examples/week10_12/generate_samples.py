"""Build one aligned synthetic inspection for the combined Fall workflow."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path
from shutil import copyfile

from PIL import Image, ImageDraw

from solar_pv.api.observations import observations_csv, observations_json
from solar_pv.domain.observations import build_observations
from solar_pv.imaging.annotations import load_annotations, save_annotations
from solar_pv.imaging.pairing import PAIR_FIELDS, load_pairs
from solar_pv.ingestion.importer import scan_inspection, write_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT_ROOT / "examples/week07_09"
EXAMPLE = PROJECT_ROOT / "examples/week10_12"
INSPECTION = EXAMPLE / "inspection"
OUTPUT = EXAMPLE / "output"
CASES = ("synthetic_case_01", "synthetic_case_02", "synthetic_case_03", "nonradiometric_color_only")


def make_rgb(path: Path, boxes: list[tuple[float, float, float, float]], size: tuple[int, int]) -> None:
    image = Image.new("RGB", size, "#788478")
    draw = ImageDraw.Draw(image)
    for index, (left, top, right, bottom) in enumerate(boxes):
        x0, y0, x1, y1 = (round(left * size[0]), round(top * size[1]), round(right * size[0]), round(bottom * size[1]))
        draw.rectangle((x0 + 8, y0 + 9, x1 + 8, y1 + 9), fill="#566256")
        draw.rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), fill="#D0D7D2")
        draw.rectangle((x0, y0, x1, y1), fill=(24 + index * 4, 49 + index * 3, 68 + index * 3))
        for x in range(x0 + 32, x1, 33):
            draw.line((x, y0 + 3, x, y1 - 3), fill="#4E7183", width=1)
        for y in range(y0 + 42, y1, 43):
            draw.line((x0 + 3, y, x1 - 3, y), fill="#4E7183", width=1)
    image.save(path)


def main() -> None:
    for folder in (INSPECTION / "rgb", INSPECTION / "thermal", INSPECTION / "temperature_grids", INSPECTION / "scada", OUTPUT):
        folder.mkdir(parents=True, exist_ok=True)

    source_labels = load_annotations(SOURCE / "output/thermal_panel_annotations.csv")
    labels = []
    pair_rows = []
    for name in CASES:
        image_name = f"{name}.png"
        source_thermal = SOURCE / "inspection/thermal"
        copyfile(source_thermal / image_name, INSPECTION / "thermal" / image_name)
        record = json.loads((source_thermal / f"{name}.json").read_text(encoding="utf-8"))
        record["preview_path"] = f"../thermal/{image_name}"
        (INSPECTION / "temperature_grids" / f"{name}.json").write_text(
            json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        selected = [row for row in source_labels if row.image_path == f"thermal/{image_name}"]
        boxes = [(row.x_min, row.y_min, row.x_max, row.y_max) for row in selected]
        make_rgb(
            INSPECTION / "rgb" / image_name,
            boxes,
            (record["image_width"], record["image_height"]),
        )
        labels.extend(replace(row, image_path=f"rgb/{image_name}") for row in selected)
        pair_rows.append(
            {
                "inspection_id": "SYN-20261020-01",
                "pair_id": name,
                "rgb_path": f"rgb/{image_name}",
                "thermal_path": f"thermal/{image_name}",
                "temperature_path": f"temperature_grids/{name}.json",
                "alignment_reviewed": "true",
            }
        )

    save_annotations(OUTPUT / "panel_annotations.csv", labels)
    working_labels = PROJECT_ROOT / "data/processed/week10_12_panel_annotations.csv"
    if not working_labels.exists():
        working_labels.parent.mkdir(parents=True, exist_ok=True)
        copyfile(OUTPUT / "panel_annotations.csv", working_labels)
    with (INSPECTION / "inspection_pairs.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PAIR_FIELDS)
        writer.writeheader()
        writer.writerows(pair_rows)
    with (INSPECTION / "scada/synthetic_inverter.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("timestamp_utc", "inverter_id", "power_kw", "irradiance_w_m2"))
        for minute, power, irradiance in ((20, 83.0, 610), (25, 85.0, 626), (30, 84.5, 622), (35, 84.0, 618), (40, 82.5, 605)):
            writer.writerow((f"2026-10-20T19:{minute:02d}:00Z", "SYN-INV-01", power, irradiance))

    manifest = scan_inspection(INSPECTION)
    write_manifest(manifest, OUTPUT)
    pairs = load_pairs(INSPECTION / "inspection_pairs.csv", INSPECTION)
    observations = [
        item
        for pair in pairs
        for item in build_observations(INSPECTION, pair, labels)
    ]
    (OUTPUT / "observations.csv").write_text(observations_csv(observations), encoding="utf-8")
    (OUTPUT / "observations.json").write_text(observations_json(observations), encoding="utf-8")
    print(f"Created {len(pairs)} image pairs and {len(observations)} observations in {EXAMPLE}")


if __name__ == "__main__":
    main()
