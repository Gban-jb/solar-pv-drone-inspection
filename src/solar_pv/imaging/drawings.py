"""Verified references to raster previews of the AAMU engineering drawings."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from solar_pv.domain.site import SiteSpecification
from solar_pv.storage.site_registry import verify_source_document


@dataclass(frozen=True)
class DrawingView:
    sheet: str
    title: str
    pdf_page: int
    image_name: str
    image_sha256: str


DRAWING_VIEWS = (
    DrawingView(
        "WI101", "Site overview", 4, "WI101_site_plan.png",
        "79ccc96800c4d4e84a7633a658aa75761ac100fc29ec671d1363d5d2f0476894",
    ),
    DrawingView(
        "WP101.1", "Stringing · INV.05–INV.08", 7, "WP101_1_stringing.png",
        "8b074a73d034060dc8f6d5f30c3f073cafd344022ad353a2cd529c8a468124e0",
    ),
    DrawingView(
        "WP101.2", "Stringing · INV.01–INV.04", 8, "WP101_2_stringing.png",
        "85935cba06e44845efd6a15884c62452d8e92ddc796012f5dfe603e30c1f3353",
    ),
)


def drawing_view(sheet: str) -> DrawingView:
    for view in DRAWING_VIEWS:
        if view.sheet == sheet:
            return view
    raise KeyError(f"Unknown engineering drawing: {sheet}")


def load_drawing_image(
    view: DrawingView, site: SiteSpecification, project_root: Path, image_root: Path
) -> bytes:
    """Check source and packaged raster before showing a drawing in the app."""
    verify_source_document(site, project_root)
    image_path = Path(image_root) / view.image_name
    if not image_path.is_file():
        raise FileNotFoundError(f"Drawing preview missing for {view.sheet}: {image_path}")
    content = image_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != view.image_sha256:
        raise ValueError(f"Drawing preview checksum differs for {view.sheet}")
    try:
        with Image.open(image_path) as image:
            image.verify()
    except OSError as exc:
        raise ValueError(f"Drawing preview cannot be opened for {view.sheet}") from exc
    return content
