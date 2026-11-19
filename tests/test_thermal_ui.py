from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THERMAL_PAGE = PROJECT_ROOT / "src/solar_pv/ui/thermal.py"


def test_visual_only_thermal_preview_never_shows_numeric_temperature_output():
    app = AppTest.from_file(THERMAL_PAGE).run()
    app.selectbox[0].select("Nonradiometric Color Only").run()

    assert not app.exception
    assert app.selectbox[0].value.pair_id == "nonradiometric_color_only"
    assert any(
        "colors are illustrative and are not temperature measurements" in message.value.lower()
        for message in app.info
    )
    assert any("Temperature grid: unavailable" in caption.value for caption in app.caption)
    assert not app.subheader
    assert not app.dataframe
