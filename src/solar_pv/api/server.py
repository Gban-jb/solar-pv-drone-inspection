"""Local API for the inspection platform and historical meter context."""
from pathlib import Path

from fastapi import FastAPI
from solar_pv.api.workspaces import router as inspection_router
from solar_pv.electrical.scada_quality import inspect_meter_exports
from solar_pv.storage.site_registry import load_site_spec

ROOT = Path(__file__).resolve().parents[3]
app = FastAPI(title="AAMU Solar PV Inspection API")
app.include_router(inspection_router)

@app.get("/api/overview")
def overview():
    spec = load_site_spec(ROOT / "configs/sites/aamu_2023_review.json")
    result = {"site": {"name": spec.site_name, "modules": spec.module_count,
                       "strings": spec.string_count, "inverters": spec.inverter_count,
                       "dc_kw": spec.dc_rating_w / 1000, "status": "provisional review drawing"},
              "meter": None}
    folder = ROOT / "data/raw/marshall_2026/scada"
    if folder.is_dir() and any(folder.glob("*.csv")):
        meter = inspect_meter_exports(folder)
        power = next((v for v in meter.variables if v.column == "Meter: power_true_kw (kW)"), None)
        result["meter"] = {"rows": len(meter.rows), "files": len(meter.files),
                           "cadence_minutes": meter.nominal_cadence_minutes,
                           "missing_power": power.missing_count if power else None,
                           "scope": meter.sensor_scope, "timezone": meter.timezone_status}
    return result

# Meter endpoints use the same parser and filter as the Streamlit workspace.
from dataclasses import asdict
import pandas as pd
from fastapi import HTTPException
from fastapi.responses import Response
from solar_pv.electrical.scada_quality import filtered_meter_rows


def _meter_data():
    try:
        return inspect_meter_exports(ROOT / 'data/raw/marshall_2026/scada')
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _meter_filter(variable: str, start: str, end: str):
    try:
        start_time, end_time = pd.Timestamp(start), pd.Timestamp(end)
        if pd.isna(start_time) or pd.isna(end_time) or start_time.tzinfo or end_time.tzinfo:
            raise ValueError('Use valid timestamps without a timezone; the meter timezone is unknown.')
        inspection = _meter_data()
        return inspection, filtered_meter_rows(inspection, variable, start_time, end_time)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/api/meter')
def meter_metadata():
    data = _meter_data()
    valid = data.rows.time.dropna()
    return {'variables': [asdict(v) for v in data.variables], 'rows': len(data.rows),
            'files': len(data.files), 'gaps': len(data.gaps), 'cadence_minutes': data.nominal_cadence_minutes,
            'start': valid.min().isoformat() if not valid.empty else None,
            'end': valid.max().isoformat() if not valid.empty else None,
            'scope': 'unknown', 'timezone': 'unknown', 'correlation': 'blocked'}


@app.get('/api/meter/filtered')
def meter_filtered(variable: str, start: str, end: str):
    data, filtered = _meter_filter(variable, start, end)
    plotted = filtered.loc[filtered[variable].notna()].copy()
    plotted = plotted.loc[~plotted.time.duplicated(keep=False)]
    if not plotted.empty:
        plotted = plotted[['time', variable]].set_index('time').resample('30min').mean().dropna().reset_index()
        plotted['segment'] = plotted.time.diff().gt(pd.Timedelta(minutes=30)).cumsum()
        # Keep empty intervals in the chart axis so long gaps retain their true width.
        timeline = pd.date_range(plotted.time.iloc[0], plotted.time.iloc[-1], freq='30min')
        plotted = plotted.set_index('time').reindex(timeline).rename_axis('time').reset_index()
    points = [{'time': row.time.isoformat(), 'value': float(row.value) if pd.notna(row.value) else None,
               'segment': int(row.segment) if pd.notna(row.segment) else None}
              for row in plotted.rename(columns={variable: 'value'}).itertuples()] if not plotted.empty else []
    return {'count': len(filtered), 'missing_or_invalid': int(filtered[variable].isna().sum()),
            'points': points, 'preview': filtered.head(100).astype(object).where(filtered.head(100).notna(), '').astype(str).to_dict(orient='records')}


@app.get('/api/meter/export')
def meter_export(variable: str, start: str, end: str):
    _, filtered = _meter_filter(variable, start, end)
    return Response(filtered.to_csv(index=False), media_type='text/csv',
                    headers={'Content-Disposition': 'attachment; filename="meter_filtered_records.csv"'})
