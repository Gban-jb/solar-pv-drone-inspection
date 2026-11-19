"""Draw saved panel boxes and optional temperature differences on previews."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from solar_pv.imaging.annotations import PanelAnnotation


def panel_overlay(
    source: Image.Image,
    annotations: list[PanelAnnotation],
    readings: dict[str, tuple[float | None, bool]] | None = None,
    highlight_id: str | None = None,
) -> Image.Image:
    width = min(760, source.width)
    height = max(1, round(source.height * width / source.width))
    image = source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=14)
    for number, row in enumerate(annotations, start=1):
        bounds = (
            round(row.x_min * width), round(row.y_min * height),
            round(row.x_max * width), round(row.y_max * height),
        )
        delta, candidate = (readings or {}).get(row.annotation_id, (None, False))
        highlighted = row.annotation_id == highlight_id
        color = "#E37038" if highlighted else "#E65E3C" if candidate else "#F2F0E8"
        draw.rectangle(bounds, outline=color, width=4 if highlighted else 2)
        label = f"{number:02d}  {delta:+.1f} C" if delta is not None else f"{number:02d}"
        text_width = round(draw.textlength(label, font=font))
        top = max(0, bounds[1] - 22)
        draw.rectangle((bounds[0], top, bounds[0] + text_width + 10, top + 20), fill=color)
        draw.text((bounds[0] + 5, top + 2), label, fill="#171A18", font=font)
    return image
