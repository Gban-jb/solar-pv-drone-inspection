"""Reviewed links between image annotations and provisional electrical assets."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from solar_pv.domain.assets import Asset, AssetRegistry
from solar_pv.imaging.annotations import PanelAnnotation


def asset_path(registry: AssetRegistry, asset_id: str) -> tuple[Asset, ...]:
    """Return the validated site-to-asset ancestry for display and review."""
    current = registry.get(asset_id)
    if current is None:
        raise ValueError(f"Unknown registry asset: {asset_id}")
    path = []
    while current is not None:
        path.append(current)
        current = registry.get(current.parent_id) if current.parent_id else None
    return tuple(reversed(path))


def selected_asset(
    registry: AssetRegistry, *, inverter_id: str | None, string_id: str | None,
    module_id: str | None,
) -> Asset | None:
    """Reject a mixed hierarchy even when every individual ID exists."""
    inverter = registry.get(inverter_id) if inverter_id else None
    string = registry.get(string_id) if string_id else None
    module = registry.get(module_id) if module_id else None
    if inverter_id and (inverter is None or inverter.kind != "inverter"):
        raise ValueError("Choose a valid inverter")
    if string_id and (string is None or string.kind != "string" or not inverter or string.parent_id != inverter.asset_id):
        raise ValueError("The string does not belong to the selected inverter")
    if module_id and (module is None or module.kind != "module" or not string or module.parent_id != string.asset_id):
        raise ValueError("The module does not belong to the selected string")
    return module or string or inverter


def link_annotation(
    annotation: PanelAnnotation, registry: AssetRegistry, asset_id: str,
    *, reviewer_notes: str = "",
) -> PanelAnnotation:
    asset = registry.get(asset_id)
    if asset is None or asset.kind == "site":
        raise ValueError(f"Unknown or unsupported registry asset: {asset_id}")
    return replace(
        annotation,
        linked_asset_id=asset.asset_id,
        linked_asset_type=asset.kind,
        mapping_method="manual_selection",
        mapping_status="provisional",
        mapping_evidence="",
        reviewer_notes=reviewer_notes.strip(),
        modified_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def unlink_annotation(annotation: PanelAnnotation) -> PanelAnnotation:
    return replace(
        annotation,
        linked_asset_id="",
        linked_asset_type="",
        mapping_method="",
        mapping_status="unmapped",
        mapping_evidence="",
        modified_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def verify_asset_link(
    annotation: PanelAnnotation, registry: AssetRegistry, *, approved_reference: str,
    reviewer: str,
) -> PanelAnnotation:
    if not annotation.linked_asset_id or registry.get(annotation.linked_asset_id) is None:
        raise ValueError("The linked asset must exist before verification")
    if annotation.source_provenance == "synthetic":
        raise ValueError("Synthetic image evidence cannot verify a physical asset mapping")
    if not approved_reference.strip() or not reviewer.strip():
        raise ValueError("An approved source reference and reviewer name are required")
    return replace(
        annotation,
        mapping_status="verified",
        mapping_evidence=approved_reference.strip(),
        reviewer_notes=(annotation.reviewer_notes + "\n" if annotation.reviewer_notes else "")
        + f"Mapping reviewed by {reviewer.strip()}",
        modified_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def mapping_display(annotation: PanelAnnotation, registry: AssetRegistry) -> tuple[str, str]:
    """Keep stale links visible instead of losing them during registry changes."""
    if not annotation.linked_asset_id:
        return "Unmapped", "No registry asset linked"
    asset = registry.get(annotation.linked_asset_id)
    if asset is None:
        return "Unresolved", f"Registry asset no longer found: {annotation.linked_asset_id}"
    names = [
        item.drawing_label or f"MOD-{item.sequence_number:02d}"
        if item.kind == "module" and item.sequence_number else item.drawing_label or item.asset_id
        for item in asset_path(registry, asset.asset_id)
    ]
    return annotation.mapping_status.capitalize(), " → ".join(names[1:])
