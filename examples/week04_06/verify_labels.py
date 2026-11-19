"""Verify the Week 4-6 saved labels survive an exact CSV round trip."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from solar_pv.imaging.annotations import load_annotations, save_annotations


EXAMPLE = Path(__file__).resolve().parent
SOURCE = EXAMPLE / "output/panel_annotations.csv"
INSPECTION = EXAMPLE / "inspection"
EVIDENCE = EXAMPLE / "output/roundtrip_evidence.json"


def main() -> None:
    original = load_annotations(SOURCE)
    assert len(original) >= 20, f"Expected at least 20 labels; found {len(original)}"
    assert len({row.annotation_id for row in original}) == len(original)
    for row in original:
        with Image.open(INSPECTION / row.image_path) as image:
            assert image.size == (row.image_width, row.image_height), row.annotation_id

    with TemporaryDirectory(prefix="solar-pv-label-proof-") as directory:
        copy = Path(directory) / "labels.csv"
        save_annotations(copy, original)
        reloaded = load_annotations(copy)
    assert reloaded == original, "A saved label changed after reload"

    by_image = Counter(row.image_path for row in original)
    assert by_image["rgb/synthetic_panel_array.png"] >= 20
    result = {
        "source": SOURCE.relative_to(EXAMPLE).as_posix(),
        "saved_labels": len(original),
        "panel_labels": sum(row.target_type == "panel" for row in original),
        "row_labels": sum(row.target_type == "row" for row in original),
        "labels_by_image": dict(sorted(by_image.items())),
        "unique_annotation_ids": True,
        "image_dimensions_match": True,
        "all_fields_identical_after_save_reload": True,
        "synthetic_example": True,
    }
    EVIDENCE.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(original)} labels across {len(by_image)} synthetic images.")
    print("IDs, types, plant IDs, review states, image sizes, timestamps and all box coordinates reloaded exactly.")
    print(f"Evidence: {EVIDENCE}")


if __name__ == "__main__":
    main()
