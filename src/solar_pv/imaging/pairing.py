"""Explicit RGB/thermal associations for a single inspection."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


PAIR_FIELDS = (
    "inspection_id", "pair_id", "rgb_path", "thermal_path", "temperature_path",
    "alignment_reviewed", "synthetic",
)


@dataclass(frozen=True)
class ImagePair:
    inspection_id: str
    pair_id: str
    rgb_path: str
    thermal_path: str
    temperature_path: str
    alignment_reviewed: bool
    synthetic: bool = False


def load_pairs(path: Path, inspection_root: Path) -> list[ImagePair]:
    """Read reviewed file associations without guessing matches from filenames."""
    root = Path(inspection_root).resolve()
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required_fields = set(PAIR_FIELDS) - {"synthetic"}
        if not reader.fieldnames or not required_fields.issubset(reader.fieldnames):
            raise ValueError("Pairing CSV is missing required columns")
        pairs = []
        seen_ids = set()
        seen_thermal = set()
        inspection_id = None
        for line_number, row in enumerate(reader, start=2):
            current_inspection = (row["inspection_id"] or "").strip()
            pair_id = (row["pair_id"] or "").strip()
            aligned = (row["alignment_reviewed"] or "").strip().lower()
            if not current_inspection or (inspection_id is not None and current_inspection != inspection_id):
                raise ValueError(f"Pairing CSV row {line_number} has a missing or inconsistent inspection ID")
            if not pair_id or pair_id in seen_ids:
                raise ValueError(f"Pairing CSV row {line_number} has an empty or duplicate pair ID")
            if aligned not in {"true", "false"}:
                raise ValueError(f"Pairing CSV row {line_number} needs true or false alignment_reviewed")
            synthetic_value = (row.get("synthetic") or "").strip().lower()
            if synthetic_value not in {"", "true", "false"}:
                raise ValueError(f"Pairing CSV row {line_number} needs true or false synthetic")
            paths = {}
            for field in ("rgb_path", "thermal_path", "temperature_path"):
                raw_path = (row[field] or "").strip()
                if field == "temperature_path" and not raw_path:
                    paths[field] = ""
                    continue
                relative = Path(raw_path)
                resolved = (root / relative).resolve()
                if not relative.parts or relative.is_absolute() or not resolved.is_relative_to(root):
                    raise ValueError(f"Pairing CSV row {line_number} has an invalid {field}")
                if not resolved.is_file():
                    raise ValueError(f"Pairing CSV row {line_number} cannot find {field}: {relative}")
                paths[field] = relative.as_posix()
            if paths["thermal_path"] in seen_thermal:
                raise ValueError(f"Pairing CSV row {line_number} repeats a thermal image")
            pairs.append(
                ImagePair(
                    inspection_id=current_inspection,
                    pair_id=pair_id,
                    rgb_path=paths["rgb_path"],
                    thermal_path=paths["thermal_path"],
                    temperature_path=paths["temperature_path"],
                    alignment_reviewed=aligned == "true",
                    synthetic=synthetic_value == "true",
                )
            )
            inspection_id = current_inspection
            seen_ids.add(pair_id)
            seen_thermal.add(paths["thermal_path"])
    return pairs


def save_pairs(path: Path, inspection_root: Path, pairs: list[ImagePair]) -> Path:
    """Validate and atomically save the complete pairing list for an inspection."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=PAIR_FIELDS)
            writer.writeheader()
            for pair in pairs:
                writer.writerow({
                    "inspection_id": pair.inspection_id,
                    "pair_id": pair.pair_id,
                    "rgb_path": pair.rgb_path,
                    "thermal_path": pair.thermal_path,
                    "temperature_path": pair.temperature_path,
                    "alignment_reviewed": str(pair.alignment_reviewed).lower(),
                    "synthetic": str(pair.synthetic).lower(),
                })
        load_pairs(temporary, inspection_root)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target
