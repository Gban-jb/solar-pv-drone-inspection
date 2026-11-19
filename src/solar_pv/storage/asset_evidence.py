"""Persistent annotation-source index and registry-to-image evidence lookup."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from solar_pv.domain.assets import AssetRegistry
from solar_pv.domain.asset_mapping import asset_path
from solar_pv.domain.observations import Observation, build_observations
from solar_pv.imaging.annotations import PanelAnnotation, load_annotations
from solar_pv.imaging.pairing import ImagePair, load_pairs
from solar_pv.ingestion.importer import scan_image


@dataclass(frozen=True)
class EvidenceSource:
    annotation_file: Path
    inspection_root: Path


@dataclass(frozen=True)
class LinkedEvidence:
    annotation: PanelAnnotation
    source: EvidenceSource
    image_metadata: dict
    pair: ImagePair | None
    observation: Observation | None
    warnings: tuple[str, ...]


def load_evidence_sources(index_path: Path) -> list[EvidenceSource]:
    path = Path(index_path)
    if not path.exists():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema_version") != 1 or not isinstance(document.get("sources"), list):
            raise ValueError("Unsupported evidence index format")
        sources = []
        for row in document["sources"]:
            if not isinstance(row, dict) or not row.get("annotation_file") or not row.get("inspection_root"):
                raise ValueError("Evidence index has an incomplete source")
            annotation_file = Path(row["annotation_file"])
            inspection_root = Path(row["inspection_root"])
            sources.append(EvidenceSource(
                (path.parent / annotation_file).resolve(),
                (path.parent / inspection_root).resolve(),
            ))
        return sources
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Could not load evidence index: {exc}") from exc


def register_evidence_source(index_path: Path, annotation_file: Path, inspection_root: Path) -> None:
    """Remember where saved links live so a restarted app can find them."""
    source = EvidenceSource(Path(annotation_file).resolve(), Path(inspection_root).resolve())
    if not source.annotation_file.is_file() or not source.inspection_root.is_dir():
        raise ValueError("Saved labels and inspection folder are required to register evidence")
    sources = load_evidence_sources(index_path)
    if source not in sources:
        sources.append(source)
    target = Path(index_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    payload = {
        "schema_version": 1,
        "sources": [
            {
                "annotation_file": os.path.relpath(item.annotation_file, target.parent),
                "inspection_root": os.path.relpath(item.inspection_root, target.parent),
            }
            for item in sources
        ],
    }
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def _image_path(root: Path, relative_text: str) -> Path | None:
    relative = Path(relative_text)
    source = (root / relative).resolve()
    if relative.is_absolute() or not source.is_relative_to(root):
        return None
    return source


def find_asset_evidence(
    index_path: Path, registry: AssetRegistry, asset_id: str,
) -> tuple[list[LinkedEvidence], list[str]]:
    """Find direct and descendant links, retaining broken-source warnings."""
    if registry.get(asset_id) is None:
        raise ValueError(f"Unknown registry asset: {asset_id}")
    matches: list[LinkedEvidence] = []
    warnings: list[str] = []
    for source in load_evidence_sources(index_path):
        if not source.annotation_file.is_file():
            warnings.append(f"Saved annotation file is missing: {source.annotation_file}")
            continue
        try:
            annotations = load_annotations(source.annotation_file)
        except (OSError, ValueError) as exc:
            warnings.append(f"Could not read {source.annotation_file}: {exc}")
            continue
        linked = [
            row for row in annotations
            if row.linked_asset_id and registry.get(row.linked_asset_id)
            and asset_id in {asset.asset_id for asset in asset_path(registry, row.linked_asset_id)}
        ]
        if not linked:
            continue
        pair_file = source.inspection_root / "inspection_pairs.csv"
        try:
            pairs = load_pairs(pair_file, source.inspection_root) if pair_file.is_file() else []
        except (OSError, ValueError) as exc:
            pairs = []
            warnings.append(f"Pairing information unavailable for {source.inspection_root}: {exc}")
        for row in linked:
            issues = []
            image = _image_path(source.inspection_root, row.image_path)
            if image is None or not image.is_file():
                metadata = {"status": "error", "error": "Source image is missing or outside the inspection folder"}
                issues.append(metadata["error"])
            else:
                role = "thermal" if row.image_path.startswith("thermal/") else "rgb"
                metadata = scan_image(image, source.inspection_root, role)
                if metadata["status"] == "error":
                    issues.append(f"Image cannot be opened: {metadata['error']}")
            pair = next((item for item in pairs if item.rgb_path == row.image_path), None)
            observation = None
            if pair and row.target_type == "panel" and pair.alignment_reviewed:
                try:
                    observation = next(
                        (item for item in build_observations(source.inspection_root, pair, annotations, registry=registry)
                         if item.annotation_id == row.annotation_id), None
                    )
                except (OSError, ValueError) as exc:
                    issues.append(f"Observation unavailable: {exc}")
            if pair and not pair.temperature_path:
                issues.append("Thermal preview has no readable pixel temperatures")
            matches.append(LinkedEvidence(row, source, metadata, pair, observation, tuple(issues)))
    return matches, warnings
