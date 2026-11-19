"""Missing meter readings and missing timestamps must remain distinct."""

from datetime import date

from solar_pv.electrical.scada import load_meter_exports, power_plot_samples
from solar_pv.ingestion.importer import _scan_scada


def test_meter_quality_preserves_zero_null_and_file_gap(tmp_path):
    folder = tmp_path / "scada"
    folder.mkdir()
    header = "DateTime,Meter: power_true_kw (kW),Meter: energy_accumulated (kWh)\n"
    (folder / "first.csv").write_text(
        header + "2026-10-01 00:00,0,100\n"
        "2026-10-01 00:05,null,100\n"
        "2026-10-01 00:10,undefined,100\n",
        encoding="utf-8",
    )
    (folder / "second.csv").write_text(
        header + "2026-10-01 01:10,10,101\n", encoding="utf-8"
    )
    readings, files, gaps = load_meter_exports(folder)
    assert len(readings) == 4
    assert readings.power_kw.iloc[0] == 0
    assert readings.power_kw.isna().sum() == 2
    assert files["Missing power"].sum() == 2
    assert len(gaps) == 1
    assert gaps.iloc[0]["Missing timestamp slots"] == 11
    chart = power_plot_samples(readings, date(2026, 10, 1), date(2026, 10, 1))
    assert list(chart.power_kw) == [0, 10]
    assert list(chart.segment) == [0, 1]
    inventory = _scan_scada(folder / "first.csv", tmp_path)
    assert inventory["status"] == "warning"
    assert inventory["empty_cells"]["Meter: power_true_kw (kW)"] == 2
