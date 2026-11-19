"""Cross-module checks for paired images and observation interchange."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import replace
from pathlib import Path

import pytest

from solar_pv.api.observations import observations_csv, observations_json
from solar_pv.domain.observations import build_observations
from solar_pv.domain.inspection import review_pairs
from solar_pv.imaging.annotations import load_annotations
from solar_pv.imaging.pairing import PAIR_FIELDS, load_pairs
from solar_pv.ingestion.importer import scan_inspection


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/week10_12"
INSPECTION = EXAMPLE / "inspection"


def test_combined_synthetic_inspection_exports_traceable_records():
    manifest = scan_inspection(INSPECTION)
    assert manifest["summary"]["images_opened"] == 8
    assert manifest["summary"]["scada_files_opened"] == 1

    pairs = load_pairs(INSPECTION / "inspection_pairs.csv", INSPECTION)
    labels = load_annotations(EXAMPLE / "output/panel_annotations.csv")
    records = [record for pair in pairs for record in build_observations(INSPECTION, pair, labels)]

    assert len(pairs) == 4
    assert len(records) == 12
    assert len({record.record_id for record in records}) == 12
    assert {record.inspection_id for record in records} == {"SYN-20261020-01"}
    assert all(record.rgb_image_path.startswith("rgb/") for record in records)
    assert all(record.thermal_image_path.startswith("thermal/") for record in records)
    assert all(record.alignment_reviewed and record.candidate_threshold_c == 5.0 for record in records)
    assert all("synthetic_data" in record.data_quality_flags for record in records)
    assert any(record.candidate and record.delta_t_c is not None for record in records)

    color_only = [record for record in records if record.pair_id == "nonradiometric_color_only"]
    assert len(color_only) == 3
    assert all(not record.radiometric_valid and record.delta_t_c is None for record in color_only)
    assert all("non_radiometric" in record.data_quality_flags for record in color_only)

    csv_rows = list(csv.DictReader(io.StringIO(observations_csv(records))))
    json_data = json.loads(observations_json(records))
    assert len(csv_rows) == len(json_data["observations"]) == 12
    assert csv_rows[0]["record_id"] == json_data["observations"][0]["record_id"]
    assert csv_rows[0]["schema_version"] == json_data["schema_version"] == "0.2"


def test_alignment_review_is_required_and_threshold_does_not_change_identity():
    pair = load_pairs(INSPECTION / "inspection_pairs.csv", INSPECTION)[0]
    labels = load_annotations(EXAMPLE / "output/panel_annotations.csv")
    with pytest.raises(ValueError, match="alignment must be reviewed"):
        build_observations(INSPECTION, replace(pair, alignment_reviewed=False), labels)

    default = build_observations(INSPECTION, pair, labels, threshold_c=5)
    higher_threshold = build_observations(INSPECTION, pair, labels, threshold_c=11)
    assert [record.record_id for record in default] == [record.record_id for record in higher_threshold]
    assert sum(record.candidate for record in default) == 1
    assert not any(record.candidate for record in higher_threshold)


def test_inspection_overview_keeps_valid_pairs_when_others_are_excluded():
    pairs = load_pairs(INSPECTION / "inspection_pairs.csv", INSPECTION)
    labels = load_annotations(EXAMPLE / "output/panel_annotations.csv")
    normal = review_pairs(INSPECTION, pairs, labels)
    assert len(normal) == 4
    assert all(review.included for review in normal)
    assert sum(len(review.observations) for review in normal) == 12
    assert sum(item.candidate for review in normal for item in review.observations) == 2
    assert normal[-1].thermal_status == "Display only"

    unreviewed = replace(pairs[0], alignment_reviewed=False)
    without_labels = [row for row in labels if row.image_path != pairs[1].rgb_path]
    mixed = review_pairs(INSPECTION, [unreviewed, *pairs[1:]], without_labels)
    assert [review.included for review in mixed] == [False, False, True, True]
    assert mixed[0].reason == "Alignment has not been reviewed"
    assert mixed[1].reason == "No saved panel labels for the RGB image"
    assert sum(len(review.observations) for review in mixed) == 6


def test_pairing_csv_rejects_paths_outside_inspection(tmp_path):
    path = tmp_path / "inspection_pairs.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=PAIR_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "inspection_id": "SYN-UNSAFE-01",
                "pair_id": "unsafe",
                "rgb_path": "../outside.png",
                "thermal_path": "thermal/frame.png",
                "temperature_path": "temperature_grids/frame.json",
                "alignment_reviewed": "true",
            }
        )
    with pytest.raises(ValueError, match="invalid rgb_path"):
        load_pairs(path, tmp_path)
