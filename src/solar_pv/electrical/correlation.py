"""Explicit prerequisites for an inspection-to-electrical comparison."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CorrelationCheck:
    allowed: bool
    satisfied: tuple[str, ...]
    missing: tuple[str, ...]


def correlation_prerequisites(
    *, capture_timestamp: str, capture_timezone_known: bool,
    meter_timezone_known: bool, meter_scope: str,
    meter_asset_id: str, selected_asset_id: str,
    mapping_verified: bool, periods_overlap: bool,
    measurement_unit: str, cadence_known: bool,
) -> CorrelationCheck:
    """Fail closed; a site stream cannot become a module measurement."""
    checks = {
        "parseable capture timestamp": _parseable(capture_timestamp),
        "capture timezone documented": capture_timezone_known,
        "meter timezone documented or reconciled": meter_timezone_known,
        "compatible measurement periods": periods_overlap,
        "documented meter scope": meter_scope in {"site", "inverter", "string"},
        "verified asset relationship": mapping_verified and bool(meter_asset_id)
            and meter_asset_id == selected_asset_id,
        "documented measurement unit": bool(measurement_unit) and measurement_unit != "not documented",
        "known sampling cadence": cadence_known,
    }
    return CorrelationCheck(
        allowed=all(checks.values()),
        satisfied=tuple(name for name, passed in checks.items() if passed),
        missing=tuple(name for name, passed in checks.items() if not passed),
    )


def _parseable(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True
