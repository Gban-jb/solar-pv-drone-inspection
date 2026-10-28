"""Generate deterministic, clearly synthetic importer demonstration files."""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent / "inspection"


def make_rgb(index: int) -> None:
    image = Image.new("RGB", (480, 300), (115, 151, 127))
    draw = ImageDraw.Draw(image)
    for row in range(2):
        for col in range(5):
            x = 28 + col * 86
            y = 45 + row * 107
            draw.rectangle((x, y, x + 72, y + 82), fill=(27, 57 + index * 2, 79), outline="white", width=2)
            for line in range(1, 4):
                draw.line((x + line * 18, y, x + line * 18, y + 82), fill=(93, 121, 128), width=1)
    exif = Image.Exif()
    exif[271] = "Synthetic Sample"
    exif[272] = "Drawing, not a camera"
    if index % 2:
        exif[306] = f"2026:10:22 10:{index:02d}:00"
    image.save(ROOT / "rgb" / f"synthetic_rgb_{index:02d}.jpg", exif=exif)


def make_thermal(index: int) -> None:
    image = Image.new("RGB", (480, 300), (32, 31, 40))
    draw = ImageDraw.Draw(image)
    for row in range(2):
        for col in range(5):
            x = 28 + col * 86
            y = 45 + row * 107
            tone = 75 + (index + col + row) * 8
            draw.rectangle((x, y, x + 72, y + 82), fill=(tone, 47, 108), outline=(200, 184, 193), width=2)
    draw.ellipse((205 + index * 4, 78, 235 + index * 4, 108), fill=(240, 165, 70))
    image.save(ROOT / "thermal" / f"synthetic_display_only_{index:02d}.png")


def main() -> None:
    for name in ("rgb", "thermal", "scada"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    for index in range(1, 7):
        make_rgb(index)
    for index in range(1, 5):
        make_thermal(index)
    (ROOT / "rgb" / "broken_image.jpg").write_bytes(b"not a JPEG image")

    csv_path = ROOT / "scada" / "synthetic_inverter.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("timestamp_utc", "inverter_id", "power_kw", "irradiance_w_m2"))
        for minute in range(12):
            writer.writerow((
                f"2026-10-22T10:{minute:02d}:00Z",
                "INV-DEMO-01",
                f"{78 + minute * 1.5:.1f}",
                str(560 + minute * 11),
            ))
    print(ROOT)


if __name__ == "__main__":
    main()
