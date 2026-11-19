"""Load drawing-based site specifications and export a provisional asset registry."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import fields
from pathlib import Path

from solar_pv.domain.assets import Asset, AssetRegistry, build_design_registry
from solar_pv.domain.site import DrawingSource, InverterDesign, RackGroupDesign, SiteSpecification


REGISTRY_FIELDS = tuple(field.name for field in fields(Asset))


def load_site_spec(path: Path) -> SiteSpecification:
    """Read and cross-check one versioned design snapshot from JSON."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported site specification schema_version")
    try:
        module = data["module"]
        strings = data["strings"]
        inverter = data["inverter"]
        system = data["system"]
        return SiteSpecification(
            site_id=data["site_id"],
            site_name=data["site_name"],
            address=data["address"],
            latitude_dms=data["latitude_dms"],
            longitude_dms=data["longitude_dms"],
            design_status=data["design_status"],
            source=DrawingSource(**data["source"]),
            module_model=module["model"],
            module_stc_w=module["stc_w"],
            module_count=module["count"],
            modules_per_string=strings["modules_per_string"],
            string_count=strings["count"],
            inverter_model=inverter["model"],
            inverter_ac_rating_kw=inverter["ac_rating_kw"],
            inverter_count=inverter["count"],
            dc_rating_w=system["dc_rating_w"],
            ac_rating_kw=system["ac_rating_kw"],
            array_azimuth_deg=system["array_azimuth_deg"],
            module_tilt_deg=system["module_tilt_deg"],
            interconnection_kv=system["interconnection_kv"],
            inverters=tuple(InverterDesign(**row) for row in data["inverter_strings"]),
            rack_groups=tuple(RackGroupDesign(**row) for row in data["rack_groups"]),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Incomplete site specification: {exc}") from exc


def verify_source_document(site: SiteSpecification, project_root: Path) -> Path:
    """Confirm the saved drawing is the exact PDF used for this design snapshot."""
    root = Path(project_root).resolve()
    source = (root / site.source.path).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError(f"Source drawing is missing from the project: {site.source.path}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != site.source.sha256:
        raise ValueError("Source drawing checksum differs from the site specification")
    return source


def write_registry_csv(registry: AssetRegistry, path: Path) -> Path:
    """Write generated IDs with explicit provisional status and drawing provenance."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        for asset in registry.assets:
            writer.writerow({field: getattr(asset, field) for field in REGISTRY_FIELDS})
    temporary.replace(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a provisional site asset registry")
    parser.add_argument("--spec", type=Path, required=True, help="Site specification JSON")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True, help="Generated registry CSV")
    args = parser.parse_args()
    site = load_site_spec(args.spec)
    verify_source_document(site, args.project_root)
    registry = build_design_registry(site)
    write_registry_csv(registry, args.output)
    print(
        f"{site.site_id}: {registry.count('inverter')} inverters, "
        f"{registry.count('string')} strings, {registry.count('module')} modules; "
        "all IDs provisional, no physical locations assigned"
    )
    print(args.output)


if __name__ == "__main__":
    main()
