import csv
from dataclasses import replace

import pytest
import shutil
from pathlib import Path
from streamlit.testing.v1 import AppTest

from solar_pv.imaging.annotations import (
    load_annotations,
    make_annotation,
    revise_annotation,
    save_annotations,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_annotation_coordinates_are_normalized_and_clamped():
    annotation = make_annotation(
        image_path="rgb/module.jpg",
        target_type="panel",
        asset_id="",
        box=(80, 30, 40, 40),
        canvas_size=(100, 50),
        image_size=(2000, 1000),
    )

    assert annotation.x_min == 0.8
    assert annotation.y_min == 0.6
    assert annotation.x_max == 1.0
    assert annotation.y_max == 1.0
    assert annotation.image_width == 2000
    assert annotation.image_height == 1000
    assert annotation.annotation_id.startswith("ann-")


def test_annotations_round_trip_to_csv(tmp_path):
    annotation = make_annotation(
        image_path="thermal/image.tif",
        target_type="row",
        asset_id="ROW-A",
        box=(10, 8, 40, 20),
        canvas_size=(100, 50),
        image_size=(1000, 500),
    )
    target = tmp_path / "nested" / "labels.csv"

    save_annotations(target, [annotation])

    assert load_annotations(target) == [annotation]


def test_missing_annotation_file_is_empty(tmp_path):
    assert load_annotations(tmp_path / "not-created.csv") == []


def test_invalid_box_is_rejected():
    with pytest.raises(ValueError, match="at least 8 pixels"):
        make_annotation(
            image_path="rgb/image.jpg",
            target_type="panel",
            asset_id="",
            box=(3, 4, 1, 10),
            canvas_size=(100, 100),
            image_size=(100, 100),
        )


def test_duplicate_annotation_ids_are_rejected(tmp_path):
    annotation = make_annotation(
        image_path="rgb/image.jpg",
        target_type="panel",
        asset_id="",
        box=(10, 10, 20, 20),
        canvas_size=(100, 100),
        image_size=(100, 100),
    )
    target = tmp_path / "labels.csv"
    save_annotations(target, [annotation])

    with target.open("a", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerow(list(annotation.__dict__.values()))

    with pytest.raises(ValueError, match="duplicate annotation_id"):
        load_annotations(target)


def test_legacy_csv_loads_as_provisional(tmp_path):
    annotation = make_annotation(
        image_path="rgb/image.jpg",
        target_type="panel",
        asset_id="P-01",
        box=(10, 10, 30, 20),
        canvas_size=(100, 100),
        image_size=(1000, 1000),
    )
    target = tmp_path / "legacy.csv"
    fields = [field for field in annotation.__dict__ if field != "review_status"]
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({field: getattr(annotation, field) for field in fields})

    assert load_annotations(target) == [annotation]


def test_revise_annotation_preserves_identity_and_changes_review():
    original = make_annotation(
        image_path="rgb/image.jpg",
        target_type="panel",
        asset_id="P-01",
        box=(10, 10, 30, 20),
        canvas_size=(100, 100),
        image_size=(1000, 1000),
    )

    revised = revise_annotation(
        original,
        target_type="row",
        asset_id="ROW-01",
        review_status="confirmed",
        box=(20, 20, 40, 30),
        canvas_size=(100, 100),
        image_size=(1000, 1000),
    )

    assert revised.annotation_id == original.annotation_id
    assert revised.created_at_utc == original.created_at_utc
    assert revised.image_path == original.image_path
    assert revised.asset_id == "ROW-01"
    assert revised.target_type == "row"
    assert revised.review_status == "confirmed"
    assert revised.x_min == 0.2


def test_revise_review_without_new_box_keeps_geometry():
    original = make_annotation(
        image_path="rgb/image.jpg",
        target_type="panel",
        asset_id="P-01",
        box=(10, 10, 30, 20),
        canvas_size=(100, 100),
        image_size=(1000, 1000),
    )

    revised = revise_annotation(
        original,
        target_type="panel",
        asset_id="P-01",
        review_status="confirmed",
    )

    assert revised.annotation_id == original.annotation_id
    assert revised.created_at_utc == original.created_at_utc
    assert (revised.x_min, revised.y_min, revised.x_max, revised.y_max) == (
        original.x_min, original.y_min, original.x_max, original.y_max
    )
    assert revised.review_status == "confirmed"


def test_duplicate_plant_id_rejected_within_image(tmp_path):
    first = make_annotation(
        image_path="rgb/image.jpg",
        target_type="panel",
        asset_id="P-01",
        box=(10, 10, 30, 20),
        canvas_size=(100, 100),
        image_size=(1000, 1000),
    )
    second = make_annotation(
        image_path="rgb/image.jpg",
        target_type="panel",
        asset_id="p-01",
        box=(50, 50, 30, 20),
        canvas_size=(100, 100),
        image_size=(1000, 1000),
    )
    with pytest.raises(ValueError, match="duplicate plant ID in image"):
        save_annotations(tmp_path / "labels.csv", [first, second])

    save_annotations(tmp_path / "labels.csv", [first, replace(second, image_path="rgb/other.jpg")])


def test_annotator_ui_edit_saves_and_reloads_in_isolated_csv(tmp_path):
    source = PROJECT_ROOT / "examples/week04_06/output/panel_annotations.csv"
    annotations = load_annotations(source)
    label_path = tmp_path / "panel_annotations.csv"
    shutil.copy2(source, label_path)

    app = AppTest.from_file(PROJECT_ROOT / "src/solar_pv/ui/app.py")
    app.query_params["inspection"] = str(PROJECT_ROOT / "examples/week04_06/inspection")
    app.query_params["labels"] = str(label_path)
    app.query_params["image"] = "rgb/synthetic_panel_array.png"
    app.query_params["annotation"] = annotations[0].annotation_id
    app.run()
    app.switch_page("annotator.py").run()

    assert not app.exception
    assert any("20 saved" in caption.value for caption in app.caption)
    next(button for button in app.button if button.label == "Edit selected").click().run()
    next(field for field in app.text_input if field.label == "Local plant ID (legacy, optional)").set_value(
        "SYN-01-UI-TEST"
    )
    next(button for button in app.button if button.label == "Save changes").click().run()

    assert not app.exception
    reloaded = load_annotations(label_path)
    assert len(reloaded) == 22
    assert reloaded[0].annotation_id == annotations[0].annotation_id
    assert reloaded[0].asset_id == "SYN-01-UI-TEST"
    assert reloaded[0].source_provenance == annotations[0].source_provenance
    assert (reloaded[0].x_min, reloaded[0].y_min, reloaded[0].x_max, reloaded[0].y_max) == (
        annotations[0].x_min,
        annotations[0].y_min,
        annotations[0].x_max,
        annotations[0].y_max,
    )
