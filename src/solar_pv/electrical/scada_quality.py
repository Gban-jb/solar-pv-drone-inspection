"""Lossless inspection of local meter CSV exports and their quality."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


TIME_COLUMN = "DateTime"
MISSING = {"", "null", "undefined", "nan", "none"}
UNIT_PATTERN = re.compile(r"\(([^()]*)\)\s*$")


@dataclass(frozen=True)
class MeterVariable:
    column: str
    unit: str
    valid_count: int
    missing_count: int
    invalid_count: int


@dataclass(frozen=True)
class MeterInspection:
    rows: pd.DataFrame
    files: pd.DataFrame
    gaps: pd.DataFrame
    variables: tuple[MeterVariable, ...]
    duplicate_timestamps: int
    out_of_order_timestamps: int
    invalid_timestamps: int
    nominal_cadence_minutes: float | None
    sensor_scope: str = "unknown"
    sensor_id: str = "undocumented"
    timezone_status: str = "unknown"


def inspect_meter_exports(folder: Path) -> MeterInspection:
    """Retain raw cells, parsed values, row identity and invalid-row indicators."""
    paths = sorted(Path(folder).expanduser().glob("*.csv"))
    if not paths:
        raise ValueError("No meter CSV files found in this folder")
    all_rows = []
    details = []
    columns: set[str] | None = None
    out_of_order = 0
    for path in paths:
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        if TIME_COLUMN not in raw or len(raw.columns) < 2:
            raise ValueError(f"{path.name}: DateTime and a measurement column are required")
        data_columns = set(raw.columns) - {TIME_COLUMN}
        if columns is None:
            columns = data_columns
        elif data_columns != columns:
            raise ValueError(f"{path.name}: measurement columns differ from the other files")
        times = pd.to_datetime(raw[TIME_COLUMN].str.strip(), format="%Y-%m-%d %H:%M", errors="coerce")
        out_of_order += int((times.diff().dt.total_seconds() < 0).sum())
        frame = pd.DataFrame({
            "source_file": path.name,
            "source_row": raw.index + 2,
            "raw_timestamp": raw[TIME_COLUMN],
            "time": times,
            "invalid_timestamp": times.isna(),
        })
        invalid_values = 0
        for column in raw.columns:
            if column == TIME_COLUMN:
                continue
            value = raw[column].str.strip()
            missing = value.str.lower().isin(MISSING)
            numeric = pd.to_numeric(value.mask(missing), errors="coerce")
            invalid = numeric.isna() & ~missing
            frame[f"raw::{column}"] = raw[column]
            frame[column] = numeric
            frame[f"invalid::{column}"] = invalid
            invalid_values += int(invalid.sum())
        all_rows.append(frame)
        details.append({
            "File": path.name, "Rows": len(frame),
            "First timestamp": times.min(), "Last timestamp": times.max(),
            "Invalid timestamps": int(times.isna().sum()),
            "Out of order": int((times.diff().dt.total_seconds() < 0).sum()),
            "Invalid numeric cells": invalid_values,
        })
    rows = pd.concat(all_rows, ignore_index=True)
    valid_times = rows.loc[rows.time.notna(), "time"]
    duplicates = int(valid_times.duplicated(keep=False).sum())
    distinct = valid_times.drop_duplicates().sort_values().reset_index(drop=True)
    intervals = distinct.diff().dt.total_seconds().div(60)
    positives = intervals[intervals > 0]
    cadence = float(positives.mode().iloc[0]) if not positives.empty else None
    gap_rows = []
    if cadence:
        for index in intervals[intervals > cadence].index:
            gap_rows.append({
                "After": distinct.iloc[index - 1], "Before": distinct.iloc[index],
                "Gap hours": round(float(intervals.iloc[index]) / 60, 2),
                "Missing timestamp slots": max(0, int(round(float(intervals.iloc[index]) / cadence)) - 1),
            })
    variables = []
    for column in sorted(columns or ()):
        unit_match = UNIT_PATTERN.search(column)
        variables.append(MeterVariable(
            column=column, unit=unit_match.group(1) if unit_match else "not documented",
            valid_count=int(rows[column].notna().sum()),
            missing_count=int(rows[f"raw::{column}"].str.strip().str.lower().isin(MISSING).sum()),
            invalid_count=int(rows[f"invalid::{column}"].sum()),
        ))
    return MeterInspection(
        rows=rows, files=pd.DataFrame(details), gaps=pd.DataFrame(gap_rows),
        variables=tuple(variables), duplicate_timestamps=duplicates,
        out_of_order_timestamps=out_of_order,
        invalid_timestamps=int(rows.invalid_timestamp.sum()),
        nominal_cadence_minutes=cadence,
    )


def filtered_meter_rows(
    inspection: MeterInspection, variable: str, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """Return original and parsed cells in an inclusive, naive timestamp window."""
    if variable not in {item.column for item in inspection.variables}:
        raise ValueError("Unknown meter variable")
    if start > end:
        raise ValueError("Start time must not exceed end time")
    rows = inspection.rows
    selected = rows.loc[rows.time.between(start, end), [
        "source_file", "source_row", "raw_timestamp", "time",
        f"raw::{variable}", variable, f"invalid::{variable}",
    ]].copy()
    return selected.sort_values("time", kind="stable").reset_index(drop=True)
