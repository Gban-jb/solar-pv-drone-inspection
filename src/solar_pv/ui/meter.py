"""Meter time series with source, quality, scope and export controls."""

from __future__ import annotations

from datetime import datetime, time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from solar_pv.domain.assets import build_design_registry
from solar_pv.electrical.correlation import correlation_prerequisites
from solar_pv.electrical.scada_quality import filtered_meter_rows, inspect_meter_exports
from solar_pv.storage.meter_mapping import MeterMapping, load_meter_mapping, save_meter_mapping
from solar_pv.storage.site_registry import load_site_spec


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FOLDER = ROOT / "data/raw/marshall_2026/scada"
MAPPING_PATH = ROOT / "data/processed/meter_source_mapping.json"
SPEC_PATH = ROOT / "configs/sites/aamu_2023_review.json"


@st.cache_data(show_spinner=False)
def _read_folder(folder: str, signature: tuple[tuple[str, int, int], ...]):
    del signature
    return inspect_meter_exports(Path(folder))


st.set_page_config(page_title="Meter data | Solar PV", layout="wide")
st.title("Meter data")
st.caption("Marshall's exported meter stream. Source identity, physical scope and timestamp timezone are not documented.")
with st.expander("Data source"):
    folder = Path(st.text_input("Meter CSV folder", str(DEFAULT_FOLDER))).expanduser()
try:
    signature = tuple((path.name, path.stat().st_mtime_ns, path.stat().st_size) for path in sorted(folder.glob("*.csv")))
    inspection = _read_folder(str(folder), signature)
    mapping = load_meter_mapping(MAPPING_PATH)
except (OSError, ValueError, KeyError) as exc:
    st.error(f"Could not inspect meter data: {exc}")
    st.stop()
rows = inspection.rows
first, second, third, fourth = st.columns(4)
first.metric("CSV files", len(inspection.files))
second.metric("Rows", f"{len(rows):,}")
third.metric("Invalid timestamps", inspection.invalid_timestamps)
fourth.metric("Timestamp gaps", len(inspection.gaps))
st.caption(
    f"Recorded cadence: {inspection.nominal_cadence_minutes:g} minutes · "
    f"Duplicate timestamp rows: {inspection.duplicate_timestamps} · "
    f"Out-of-order timestamps: {inspection.out_of_order_timestamps} · "
    "Timezone: unknown; raw strings retained."
    if inspection.nominal_cadence_minutes else "Recorded cadence unavailable."
)
st.warning("The meter is not linked to an inverter, string, or panel. This page does not infer module output or faults.")

st.subheader("Available measurements")
st.dataframe([{
    "Exported column": item.column, "Label unit": item.unit,
    "Valid": item.valid_count, "Missing": item.missing_count,
    "Invalid numeric": item.invalid_count,
} for item in inspection.variables], hide_index=True, width="stretch")
available = [item for item in inspection.variables if item.valid_count > 0]
if not available:
    st.info("No valid numeric measurements are available for plotting.")
    st.stop()
preferred = next((index for index, item in enumerate(available) if "power_true_kw (kW)" in item.column), 0)
variable = st.selectbox("Measurement", available, index=preferred,
                        format_func=lambda item: f"{item.column} · {item.unit}")
valid_times = rows.time.dropna()
if valid_times.empty:
    st.info("No valid timestamps are available for filtering.")
    st.stop()
start_default, end_default = valid_times.min(), valid_times.max()
date_a, time_a, date_b, time_b = st.columns(4)
start_day = date_a.date_input("Start date", value=start_default.date())
start_clock = time_a.time_input("Start time", value=time(0, 0))
end_day = date_b.date_input("End date", value=end_default.date())
end_clock = time_b.time_input("End time", value=time(23, 59))
try:
    filtered = filtered_meter_rows(
        inspection, variable.column, pd.Timestamp(datetime.combine(start_day, start_clock)),
        pd.Timestamp(datetime.combine(end_day, end_clock)),
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()
st.caption(f"{len(filtered):,} timestamped rows in selection · {int(filtered[variable.column].isna().sum()):,} missing or invalid values · original values preserved")
st.subheader("Time series")
st.caption(f"{variable.column}. Units are taken from the exported label; physical definition is unverified. Times use the file's naive timestamp strings.")
if filtered.empty or filtered[variable.column].notna().sum() == 0:
    st.info("No numeric readings are available in this period.")
else:
    plotted = filtered.loc[filtered[variable.column].notna()].copy()
    duplicated = plotted.time.duplicated(keep=False)
    if duplicated.any():
        st.warning(f"{int(duplicated.sum())} duplicate-time rows are omitted from the plot; they remain in the export.")
        plotted = plotted.loc[~duplicated]
    if not plotted.empty:
        plotted = plotted[["time", variable.column]].set_index("time").resample("30min").mean().dropna().reset_index()
        plotted = plotted.rename(columns={variable.column: "plot_value"})
        plotted["segment"] = plotted.time.diff().gt(pd.Timedelta(minutes=30)).cumsum()
        chart = alt.Chart(plotted).mark_line(color="#356e5b", strokeWidth=2).encode(
            x=alt.X("time:T", title="Exported time (timezone unknown)"),
            y=alt.Y("plot_value:Q", title=f"{variable.column} [{variable.unit}]"),
            detail="segment:N",
            tooltip=[alt.Tooltip("time:T", title="Exported time"),
                     alt.Tooltip("plot_value:Q", title=variable.column, format=".2f")],
        ).properties(height=320)
        st.altair_chart(chart, width="stretch")
        st.caption("30-minute means use recorded samples only. Breaks indicate intervals with no valid reading.")
st.download_button("Download filtered records CSV", filtered.to_csv(index=False).encode("utf-8"),
                   file_name="meter_filtered_records.csv", mime="text/csv")
with st.expander("File and gap quality"):
    st.dataframe(inspection.files, hide_index=True, width="stretch")
    if not inspection.gaps.empty:
        st.dataframe(inspection.gaps, hide_index=True, width="stretch")
    st.caption("Missing numeric values, invalid cells, duplicate times and absent timestamps are separate conditions. No timezone is assigned.")

st.subheader("Sensor scope")
st.caption(f"Saved scope: {mapping.scope} · Asset: {mapping.asset_id or 'none'} · Status: {mapping.status} · Reference: {mapping.source_reference or 'none'}")
st.caption("A proposed mapping is stored as unverified until external documentation and review establish it.")
try:
    registry = build_design_registry(load_site_spec(SPEC_PATH))
except (OSError, ValueError) as exc:
    registry = None
    st.warning(f"Registry unavailable for scope selection: {exc}")
with st.form("meter_scope_form"):
    scopes = ["unknown", "site", "inverter", "string", "other"]
    scope = st.selectbox("Proposed scope", scopes, index=scopes.index(mapping.scope))
    candidates = [""] + [asset.asset_id for asset in registry.assets if asset.kind == scope] if registry and scope in {"site", "inverter", "string"} else [""]
    asset_id = st.selectbox("Proposed registry asset", candidates,
                            index=candidates.index(mapping.asset_id) if mapping.asset_id in candidates else 0)
    reference = st.text_input("Document or contact supporting this proposal", value=mapping.source_reference)
    submitted = st.form_submit_button("Save proposed scope")
if submitted:
    try:
        proposal = MeterMapping(scope=scope, asset_id=asset_id, source_reference=reference)
        save_meter_mapping(MAPPING_PATH, proposal)
        st.success("Proposed scope saved as unverified. No electrical correlation is enabled.")
    except (OSError, ValueError) as exc:
        st.error(f"Could not save proposed scope: {exc}")

st.subheader("Inspection comparison readiness")
selected_asset = st.session_state.get("site_map_module") or st.session_state.get("site_map_string") or st.session_state.get("site_map_inverter") or ""
check = correlation_prerequisites(
    capture_timestamp="", capture_timezone_known=False, meter_timezone_known=False,
    meter_scope=mapping.scope, meter_asset_id=mapping.asset_id, selected_asset_id=selected_asset,
    mapping_verified=False, periods_overlap=False, measurement_unit=variable.unit,
    cadence_known=inspection.nominal_cadence_minutes is not None,
)
st.caption(f"Selected map asset: {selected_asset or 'none'} · Correlation: {'permitted' if check.allowed else 'blocked'}")
for reason in check.missing:
    st.write(f"• {reason}")
