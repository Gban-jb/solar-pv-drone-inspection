"""Create three deterministic synthetic practice images for panel and row marking."""

from pathlib import Path
from random import Random

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = PROJECT_ROOT / "examples/week04_06/inspection/rgb/synthetic_panel_array.png"
ROW_OUTPUT = OUTPUT.with_name("synthetic_panel_array_rows.png")
CLOSEUP_OUTPUT = OUTPUT.with_name("synthetic_panel_array_closeup.png")


def make_ground(size: tuple[int, int], seed: int) -> Image.Image:
    image = Image.new("RGB", size, "#747F72")
    draw = ImageDraw.Draw(image)
    rng = Random(seed)
    for _ in range(size[0] * size[1] // 67):
        x = rng.randrange(image.width)
        y = rng.randrange(image.height)
        tone = rng.choice(("#69766A", "#808A7C", "#778274", "#879084"))
        draw.point((x, y), fill=tone)
    return image


def draw_module(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int, row: int, column: int) -> None:
    draw.rounded_rectangle(
        (x + 8, y + 8, x + width + 9, y + height + 9),
        radius=3,
        fill="#59645B",
    )
    draw.rectangle((x, y, x + width, y + height), fill="#B6C0BC")
    draw.rectangle((x + 3, y + 3, x + width - 3, y + height - 3), fill="#173348")

    for stripe in range(y + 4, y + height - 3):
        mix = (stripe - y) / height
        red = round(19 + mix * 11 + row * 2)
        green = round(46 + mix * 10 + column * 2)
        blue = round(65 + mix * 13)
        draw.line((x + 4, stripe, x + width - 4, stripe), fill=(red, green, blue))

    draw.polygon(
        (
            (x + round(width * .13), y + 5),
            (x + round(width * .26), y + 5),
            (x + round(width * .65), y + height - 5),
            (x + round(width * .52), y + height - 5),
        ),
        fill=(50, 75, 93),
    )
    draw.line((x + 4, y + 4, x + width - 4, y + 4), fill="#DAE1DA", width=2)
    draw.line((x + 4, y + 4, x + 4, y + height - 4), fill="#D1DAD2", width=2)


def main() -> None:
    image = make_ground((1280, 840), 41)
    draw = ImageDraw.Draw(image)

    panel_width, panel_height = 172, 112
    start_x, start_y = 99, 96
    column_pitch, row_pitch = 231, 184
    for row in range(4):
        for column in range(5):
            x = start_x + column * column_pitch
            y = start_y + row * row_pitch
            draw_module(draw, x, y, panel_width, panel_height, row, column)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT)

    rows = make_ground((1280, 840), 57)
    row_draw = ImageDraw.Draw(rows)
    for row in range(3):
        for column in range(6):
            draw_module(row_draw, 85 + column * 185, 120 + row * 230, 145, 88, row, column)
    rows.save(ROW_OUTPUT)

    closeup = make_ground((960, 640), 73)
    closeup_draw = ImageDraw.Draw(closeup)
    for row in range(2):
        for column in range(3):
            draw_module(closeup_draw, 65 + column * 290, 120 + row * 240, 250, 160, row, column)
    closeup.save(CLOSEUP_OUTPUT)
    print(f"Created synthetic practice images: {OUTPUT.parent}")


if __name__ == "__main__":
    main()
