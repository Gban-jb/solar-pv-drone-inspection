"""Read meter exports without inventing timestamps or replacing missing power with zero."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


TIME = "DateTime"
POWER = "Meter: power_true_kw (kW)"
ENERGY = "Meter: energy_accumulated (kWh)"
MISSING = {"", "null", "undefined", "nan", "none"}


def load_meter_exports(folder: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return readings, per-file quality and gaps between recorded timestamps."""
    files = sorted(Path(folder).expanduser().glob("*.csv"))
    if not files:
        raise ValueError("No meter CSV files found in this folder")
    frames = []
    details = []
    for path in files:
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        if not {TIME, POWER, ENERGY}.issubset(raw.columns):
            raise ValueError(f"{path.name}: required meter columns are missing")
        times = pd.to_datetime(raw[TIME], format="%Y-%m-%d %H:%M", errors="coerce")
        if times.isna().any():
            raise ValueError(f"{path.name}: {int(times.isna().sum())} invalid timestamps")
        frame = pd.DataFrame({"time": times, "source_file": path.name})
        for name, output in ((POWER, "power_kw"), (ENERGY, "energy_kwh")):
            cleaned = raw[name].str.strip()
            missing = cleaned.str.lower().isin(MISSING)
            converted = pd.to_numeric(cleaned.mask(missing), errors="coerce")
            invalid = converted.isna() & ~missing
            if invalid.any():
                raise ValueError(f"{path.name}: {int(invalid.sum())} invalid values in {name}")
            frame[output] = converted
        frames.append(frame)
        details.append({
            "File": path.name,
            "First timestamp": times.min(),
            "Last timestamp": times.max(),
            "Rows": len(frame),
            "Missing power": int(frame.power_kw.isna().sum()),
            "Missing energy": int(frame.energy_kwh.isna().sum()),
        })
    readings = pd.concat(frames, ignore_index=True).sort_values("time").reset_index(drop=True)
    if readings.time.duplicated().any():
        raise ValueError(f"Duplicate timestamps across meter files: {int(readings.time.duplicated().sum())}")
    intervals = readings.time.diff().dt.total_seconds().div(60)
    gap_rows = []
    for index in intervals[intervals > 5].index:
        gap_rows.append({
            "After": readings.at[index - 1, "time"],
            "Before": readings.at[index, "time"],
            "Gap hours": round(float(intervals.at[index]) / 60, 2),
            "Missing timestamp slots": max(0, int(round(float(intervals.at[index]) / 5)) - 1),
        })
    return readings, pd.DataFrame(details), pd.DataFrame(gap_rows)


def daily_meter_summary(readings: pd.DataFrame) -> pd.DataFrame:
    """Summarize observed samples only; an empty measurement stays missing."""
    grouped = readings.groupby(readings.time.dt.date, sort=True)
    daily = grouped.agg(
        samples=("time", "size"),
        measured_power=("power_kw", "count"),
        maximum_kw=("power_kw", "max"),
    ).reset_index(names="date")
    daily["missing_power"] = daily.samples - daily.measured_power
    return daily


def power_plot_samples(readings: pd.DataFrame, start, end) -> pd.DataFrame:
    """Use 30-minute means and distinct line segments so gaps stay visible."""
    selected = readings.loc[readings.time.dt.date.between(start, end), ["time", "power_kw"]]
    if selected.empty:
        return pd.DataFrame(columns=["time", "power_kw", "segment"])
    series = selected.set_index("time").power_kw.resample("30min").mean()
    plotted = series.dropna().reset_index()
    plotted["segment"] = plotted.time.diff().gt(pd.Timedelta(minutes=30)).cumsum()
    return plotted
