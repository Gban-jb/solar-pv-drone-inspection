"""Drawing-derived site design facts, separate from verified installed assets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


def _positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class DrawingSource:
    path: str
    sha256: str
    issue_date: str
    issue_label: str
    not_for_construction: bool

    def __post_init__(self) -> None:
        if not self.path or not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("Drawing source requires a path and SHA-256 checksum")
        date.fromisoformat(self.issue_date)
        if not self.issue_label or not isinstance(self.not_for_construction, bool):
            raise ValueError("Drawing issue label and construction status are required")


@dataclass(frozen=True)
class InverterDesign:
    drawing_id: str
    string_count: int
    source_sheet: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"INV\.\d{2}", self.drawing_id):
            raise ValueError(f"Unexpected inverter drawing ID: {self.drawing_id}")
        _positive_int(self.string_count, "string_count")
        if not self.source_sheet:
            raise ValueError("Inverter string count requires a source sheet")

    @property
    def number(self) -> int:
        return int(self.drawing_id[-2:])


@dataclass(frozen=True)
class RackGroupDesign:
    modules_high: int
    modules_wide: int
    count: int
    source_sheet: str

    def __post_init__(self) -> None:
        for name in ("modules_high", "modules_wide", "count"):
            _positive_int(getattr(self, name), name)
        if not self.source_sheet:
            raise ValueError("Rack count requires a source sheet")

    @property
    def module_count(self) -> int:
        return self.modules_high * self.modules_wide * self.count


@dataclass(frozen=True)
class SiteSpecification:
    site_id: str
    site_name: str
    address: str
    latitude_dms: str | None
    longitude_dms: str | None
    design_status: str
    source: DrawingSource
    module_model: str
    module_stc_w: int
    module_count: int
    modules_per_string: int
    string_count: int
    inverter_model: str
    inverter_ac_rating_kw: int
    inverter_count: int
    dc_rating_w: int
    ac_rating_kw: int
    array_azimuth_deg: int
    module_tilt_deg: int
    interconnection_kv: float
    inverters: tuple[InverterDesign, ...]
    rack_groups: tuple[RackGroupDesign, ...]

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Z][A-Z0-9_-]*", self.site_id):
            raise ValueError("site_id must be an uppercase stable code")
        if not self.site_name or not self.address or not self.module_model or not self.inverter_model:
            raise ValueError("Site name, address and equipment models are required")
        if self.design_status != "review_drawing_unverified" or not self.source.not_for_construction:
            raise ValueError("A review drawing cannot establish installed or field-verified status")
        for name in (
            "module_stc_w", "module_count", "modules_per_string", "string_count",
            "inverter_ac_rating_kw", "inverter_count", "dc_rating_w", "ac_rating_kw",
        ):
            _positive_int(getattr(self, name), name)
        if not (0 <= self.array_azimuth_deg < 360 and 0 <= self.module_tilt_deg <= 90):
            raise ValueError("Array azimuth or module tilt is outside its expected range")
        if self.interconnection_kv <= 0:
            raise ValueError("Interconnection voltage must be positive")
        if self.module_count != self.string_count * self.modules_per_string:
            raise ValueError("Module count disagrees with string count and length")
        if self.dc_rating_w != self.module_count * self.module_stc_w:
            raise ValueError("DC rating disagrees with module count and STC watts")
        if self.inverter_count != len(self.inverters):
            raise ValueError("Inverter count disagrees with listed inverters")
        numbers = [inverter.number for inverter in self.inverters]
        if sorted(numbers) != list(range(1, self.inverter_count + 1)):
            raise ValueError("Inverter drawing IDs must be unique and consecutive")
        if self.string_count != sum(inverter.string_count for inverter in self.inverters):
            raise ValueError("String count disagrees with inverter assignments")
        if self.ac_rating_kw != self.inverter_count * self.inverter_ac_rating_kw:
            raise ValueError("AC rating disagrees with inverter count and rating")
        if self.module_count != sum(group.module_count for group in self.rack_groups):
            raise ValueError("Module count disagrees with site-plan rack groups")
