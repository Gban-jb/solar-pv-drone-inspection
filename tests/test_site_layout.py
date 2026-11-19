"""Drawing provenance and registry navigation for the Site Layout workspace."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from solar_pv.imaging.drawings import DRAWING_VIEWS, drawing_view, load_drawing_image
from solar_pv.storage.site_registry import load_site_spec
from solar_pv.ui.drawing_viewer import drawing_viewer_html


ROOT = Path(__file__).resolve().parents[1]
SPEC = load_site_spec(ROOT / "configs/sites/aamu_2023_review.json")
IMAGES = ROOT / "src/solar_pv/ui/assets/drawings"
APP = ROOT / "src/solar_pv/ui/app.py"


@pytest.fixture
def local_drawings():
    if not (ROOT / SPEC.source.path).is_file() or not all(
        (IMAGES / view.image_name).is_file() for view in DRAWING_VIEWS
    ):
        pytest.skip("The optional AAMU drawing and preview files are not supplied with the app.")
    return IMAGES


@pytest.fixture
def synthetic_drawing(tmp_path):
    data = b"%PDF-1.7\n%%EOF\n"
    source = tmp_path / "reference.pdf"
    source.write_bytes(data)
    return replace(SPEC, source=replace(SPEC.source, path=source.name, sha256=sha256(data).hexdigest()))


def test_three_previews_match_source_sheets_and_load(local_drawings):
    assert [(view.sheet, view.pdf_page) for view in DRAWING_VIEWS] == [
        ("WI101", 4), ("WP101.1", 7), ("WP101.2", 8),
    ]
    for view in DRAWING_VIEWS:
        assert load_drawing_image(view, SPEC, ROOT, local_drawings).startswith(b"\x89PNG")
    assert drawing_view("WP101.1").title.startswith("Stringing")


def test_missing_reference_pdf_and_preview_are_reported(tmp_path, synthetic_drawing):
    with pytest.raises(ValueError, match="Source drawing is missing"):
        load_drawing_image(DRAWING_VIEWS[0], SPEC, tmp_path, IMAGES)
    with pytest.raises(FileNotFoundError, match="Drawing preview missing for WI101"):
        load_drawing_image(DRAWING_VIEWS[0], synthetic_drawing, tmp_path, tmp_path)


def test_preview_checksum_rejects_wrong_page(tmp_path, synthetic_drawing):
    view = DRAWING_VIEWS[0]
    (tmp_path / view.image_name).write_bytes(b"unexpected preview contents")
    with pytest.raises(ValueError, match="checksum differs"):
        load_drawing_image(view, synthetic_drawing, tmp_path, tmp_path)


def test_viewer_has_keyboard_and_fit_controls_without_external_services():
    html = drawing_viewer_html(DRAWING_VIEWS[0], b"test")
    assert 'aria-label="Fit drawing to screen"' in html
    assert 'aria-label="Reset to original size"' in html
    assert "pointermove" in html and "wheel" in html and "ArrowLeft" in html
    assert "data:image/png;base64," in html
    assert "https://" not in html and "http://" not in html


def test_inverter_string_module_workflow_has_no_fabricated_evidence(tmp_path, monkeypatch, local_drawings):
    monkeypatch.setenv("SOLAR_PV_EVIDENCE_INDEX", str(tmp_path / "empty_evidence.json"))
    app = AppTest.from_file(APP).run().switch_page("site_layout.py").run()
    assert not app.exception
    assert app.title[0].value == "Solar Farm Map"
    assert app.get("segmented_control")[0].value == "WI101"
    assert any("PDF page 4" in item.value for item in app.caption)

    app.selectbox[0].select("AAMU-INV-05").run()
    assert not app.exception
    assert app.get("segmented_control")[0].value == "WP101.1"
    assert any("12 expected strings" in item.value for item in app.caption)

    app.selectbox[1].select("AAMU-INV-05-STR-01").run()
    assert not app.exception
    assert any("27 expected modules" in item.value for item in app.caption)
    assert len(app.dataframe[0].value) == 27

    app.selectbox[2].select("AAMU-INV-05-STR-01-MOD-27").run()
    assert not app.exception
    assert app.selectbox[2].value == "AAMU-INV-05-STR-01-MOD-27"
    assert any("No linked inspection evidence" in item.value for item in app.markdown)
    assert not any("synthetic" in item.value.lower() for item in app.markdown)
