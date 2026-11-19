"""Provisional, documented sensor scope; never implies a verified electrical link."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MeterMapping:
    scope: str = "unknown"
    asset_id: str = ""
    source_reference: str = ""
    status: str = "unverified"

    def __post_init__(self) -> None:
        if self.scope not in {"unknown", "site", "inverter", "string", "other"}:
            raise ValueError("Unsupported meter scope")
        if self.status != "unverified":
            raise ValueError("This prototype cannot verify a physical meter mapping")
        if self.scope == "unknown" and self.asset_id:
            raise ValueError("Unknown scope cannot have an asset link")
        if self.scope in {"site", "inverter", "string"} and not self.asset_id:
            raise ValueError("A scoped mapping requires an asset ID")
        if self.scope != "unknown" and not self.source_reference.strip():
            raise ValueError("A proposed meter scope needs a source reference")


def load_meter_mapping(path: Path) -> MeterMapping:
    if not Path(path).is_file():
        return MeterMapping()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported meter mapping schema")
    return MeterMapping(**{key: data[key] for key in ("scope", "asset_id", "source_reference", "status")})


def save_meter_mapping(path: Path, mapping: MeterMapping) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(json.dumps({"schema_version": 1, **asdict(mapping)}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
