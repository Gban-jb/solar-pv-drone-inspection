from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src/solar_pv/ui/app.py"


def test_inventory_and_annotations_share_one_app():
    app = AppTest.from_file(APP).run()

    assert not app.exception
    assert app.header[0].value == "Inspection inventory"

    app.button[0].click().run()
    assert not app.exception
    assert [metric.value for metric in app.metric] == ["10 / 11", "1", "1 / 1"]

    example = ROOT / "examples/week04_06"
    app.session_state["active_inspection_root"] = str(example / "inspection")
    app.session_state["active_annotation_path"] = str(example / "output/panel_annotations.csv")
    app.switch_page("annotator.py").run()
    assert not app.exception
    assert app.title[0].value == "Panel annotations"
    assert any("20 saved" in caption.value for caption in app.caption)

    app.switch_page("inventory.py").run()
    assert not app.exception
    assert app.header[0].value == "Inspection inventory"
