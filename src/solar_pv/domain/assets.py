"""Stable, provisional design IDs for site, inverter, string and module assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping

from solar_pv.domain.site import SiteSpecification


AssetKind = Literal["site", "inverter", "string", "module"]


@dataclass(frozen=True)
class Asset:
    asset_id: str
    kind: AssetKind
    parent_id: str | None
    drawing_label: str | None
    source_sheet: str
    verification_status: str = "design_provisional"
    sequence_number: int | None = None


@dataclass(frozen=True)
class AssetRegistry:
    site: SiteSpecification
    assets: tuple[Asset, ...]
    _by_id: Mapping[str, Asset] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        by_id: dict[str, Asset] = {}
        for asset in self.assets:
            if asset.asset_id in by_id:
                raise ValueError(f"Duplicate asset ID: {asset.asset_id}")
            if asset.parent_id is not None and asset.parent_id not in by_id:
                raise ValueError(f"Missing parent for {asset.asset_id}: {asset.parent_id}")
            by_id[asset.asset_id] = asset
        if not self.assets or self.assets[0].asset_id != self.site.site_id:
            raise ValueError("Registry must begin with its site asset")
        object.__setattr__(self, "_by_id", MappingProxyType(by_id))

    def get(self, asset_id: str) -> Asset | None:
        return self._by_id.get(asset_id)

    def children_of(self, asset_id: str) -> tuple[Asset, ...]:
        if asset_id not in self._by_id:
            raise KeyError(asset_id)
        return tuple(asset for asset in self.assets if asset.parent_id == asset_id)

    def count(self, kind: AssetKind) -> int:
        return sum(asset.kind == kind for asset in self.assets)


def build_design_registry(site: SiteSpecification) -> AssetRegistry:
    """Expand drawing counts into candidate IDs; physical mapping remains unknown."""
    assets = [Asset(site.site_id, "site", None, None, "WI101")]
    for inverter in sorted(site.inverters, key=lambda item: item.number):
        inverter_id = f"{site.site_id}-INV-{inverter.number:02d}"
        assets.append(
            Asset(inverter_id, "inverter", site.site_id, inverter.drawing_id, inverter.source_sheet)
        )
        for string_number in range(1, inverter.string_count + 1):
            string_id = f"{inverter_id}-STR-{string_number:02d}"
            assets.append(
                Asset(
                    string_id, "string", inverter_id,
                    f"INV-{inverter.number:02d}-{string_number:02d}",
                    inverter.source_sheet, sequence_number=string_number,
                )
            )
            for module_number in range(1, site.modules_per_string + 1):
                assets.append(
                    Asset(
                        f"{string_id}-MOD-{module_number:02d}", "module", string_id,
                        None, inverter.source_sheet, sequence_number=module_number,
                    )
                )
    return AssetRegistry(site, tuple(assets))
