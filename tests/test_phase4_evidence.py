"""Phase 4 measurement validity, quality and traceability regressions."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import replace
from pathlib import Path

import pytest

from solar_pv.api.observations import observations_csv, observations_csv_v03, observations_json_v03
from solar_pv.domain.observations import build_observations
from solar_pv.electrical.correlation import correlation_prerequisites
from solar_pv.electrical.scada_quality import filtered_meter_rows, inspect_meter_exports
from solar_pv.imaging.annotations import load_annotations, save_annotations
from solar_pv.imaging.pairing import load_pairs
from solar_pv.imaging.thermal import (
    ThermalFrame, analyze_panels, compare_regions, load_paired_thermal_frame, load_thermal_frame,
    measurement_basis, region_statistics,
)
from solar_pv.storage.meter_mapping import MeterMapping, load_meter_mapping, save_meter_mapping


ROOT = Path(__file__).resolve().parents[1]
INSPECTION = ROOT / "examples/week10_12/inspection"
LABELS = ROOT / "examples/week10_12/output/panel_annotations.csv"


def test_thermal_sources_and_calibrated_region_stats():
    pairs = load_pairs(INSPECTION / "inspection_pairs.csv", INSPECTION)
    synthetic = load_paired_thermal_frame(INSPECTION, pairs[0].thermal_path, pairs[0].temperature_path, synthetic=True)
    display = load_paired_thermal_frame(INSPECTION, pairs[-1].thermal_path, "", synthetic=True)
    assert measurement_basis(synthetic) == "synthetic_numeric_demo"
    assert measurement_basis(display) == "display_only"
    with pytest.raises(ValueError, match="No validated numeric"):
        region_statistics(display, "r", (0, 0, 1, 1))
    calibrated = ThermalFrame(
        "camera.raw", "camera.png", 2, 2, "F", "2026-10-20T14:00:00-05:00",
        True, False, ((68.0, None), (77.0, 86.0)), "verified", "camera-calibration-1",
    )
    assert measurement_basis(calibrated) == "calibrated_numeric"
    stats = region_statistics(calibrated, "all", (0, 0, 1, 1))
    assert (stats.minimum, stats.maximum, stats.mean, stats.median) == (68, 86, 77, 77)
    assert (stats.sample_count, stats.excluded_count, stats.unit) == (3, 1, "F")
    reference = region_statistics(calibrated, "reference", (0, 0, 0.5, 0.5))
    assert compare_regions(stats, reference).delta_median == 9
    with pytest.raises(ValueError, match="incompatible"):
        compare_regions(stats, replace(reference, unit="C"))
    with pytest.raises(ValueError, match="inside"):
        region_statistics(calibrated, "bad", (-0.1, 0, 1, 1))
    with pytest.raises(ValueError, match="no valid"):
        region_statistics(calibrated, "empty", (0.5, 0, 1, 0.5))
    assert measurement_basis(replace(calibrated, calibration_reference="")) == "unverified_numeric"


def test_invalid_numeric_grid_is_rejected(tmp_path):
    source = INSPECTION / "temperature_grids/synthetic_case_01.json"
    record = json.loads(source.read_text())
    record["temperature_grid"][0][0] = "not a number"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="non-numeric"):
        load_thermal_frame(path)


def test_week07_three_synthetic_cases_compare_rgb_labeled_panels():
    example = ROOT / "examples/week10_12/inspection"
    labels = load_annotations(ROOT / "examples/week10_12/output/panel_annotations.csv")
    pairs = load_pairs(example / "inspection_pairs.csv", example)

    expected_candidates = {
        "synthetic_case_01": {"SYN-01-P03"},
        "synthetic_case_02": set(),
        "synthetic_case_03": {"SYN-03-P03"},
    }
    for pair in pairs[:3]:
        frame = load_paired_thermal_frame(
            example, pair.thermal_path, pair.temperature_path, synthetic=pair.synthetic,
        )
        results = analyze_panels(frame, labels, image_path=pair.rgb_path, threshold_c=5.0)
        assert len(results) == 3
        assert all(result.delta_c is not None and result.reference_c is not None for result in results)
        assert {result.asset_id for result in results if result.candidate} == expected_candidates[pair.pair_id]

    display_pair = pairs[-1]
    display_frame = load_paired_thermal_frame(
        example, display_pair.thermal_path, display_pair.temperature_path, synthetic=True,
    )
    assert measurement_basis(display_frame) == "display_only"
    with pytest.raises(ValueError, match="does not contain readable radiometric temperatures"):
        analyze_panels(display_frame, labels, image_path=display_pair.rgb_path)


def test_meter_quality_preserves_raw_rows_and_unknown_scope(tmp_path):
    folder = tmp_path / "meter"
    folder.mkdir()
    header = "DateTime,Meter: power_true_kw (kW)\n"
    (folder / "a.csv").write_text(
        header + "2026-10-01 00:10,5\n2026-10-01 00:00,0\n"
        "2026-10-01 00:05,null\n2026-10-01 00:05,bad\n"
        "bad-time,8\n2026-10-01 01:05,10\n", encoding="utf-8",
    )
    report = inspect_meter_exports(folder)
    assert report.sensor_scope == report.timezone_status == "unknown"
    assert report.duplicate_timestamps == 2
    assert report.out_of_order_timestamps == 1
    assert report.invalid_timestamps == 1
    assert report.nominal_cadence_minutes == 5
    assert report.variables[0].missing_count == 1
    assert report.variables[0].invalid_count == 1
    assert report.rows.loc[report.rows.source_row == 3, "Meter: power_true_kw (kW)"].iloc[0] == 0
    assert report.rows.loc[report.rows.source_row == 5, "raw::Meter: power_true_kw (kW)"].iloc[0] == "bad"
    selected = filtered_meter_rows(report, report.variables[0].column,
                                   report.rows.time.min(), report.rows.time.max())
    assert len(selected) == 5
    (folder / "b.csv").write_text("wrong,another\n1,2\n")
    with pytest.raises(ValueError, match="DateTime"):
        inspect_meter_exports(folder)


def test_unknown_mapping_and_correlation_fail_closed(tmp_path):
    target = tmp_path / "mapping.json"
    assert load_meter_mapping(target).scope == "unknown"
    with pytest.raises(ValueError, match="source reference"):
        MeterMapping(scope="inverter", asset_id="candidate")
    with pytest.raises(ValueError, match="asset ID"):
        MeterMapping(scope="site", source_reference="manual")
    proposal = MeterMapping(scope="site", asset_id="AAMU", source_reference="unconfirmed email")
    save_meter_mapping(target, proposal)
    assert load_meter_mapping(target) == proposal
    check = correlation_prerequisites(
        capture_timestamp="2026-10-20T14:00:00-05:00", capture_timezone_known=True,
        meter_timezone_known=False, meter_scope="unknown", meter_asset_id="",
        selected_asset_id="AAMU-INV-05-STR-01-MOD-27", mapping_verified=False,
        periods_overlap=True, measurement_unit="kW", cadence_known=True,
    )
    assert not check.allowed
    assert "meter timezone documented or reconciled" in check.missing
    assert "verified asset relationship" in check.missing
    site_to_module = correlation_prerequisites(
        capture_timestamp="2026-10-20T14:00:00-05:00", capture_timezone_known=True,
        meter_timezone_known=True, meter_scope="site", meter_asset_id="AAMU",
        selected_asset_id="AAMU-INV-05-STR-01-MOD-27", mapping_verified=True,
        periods_overlap=True, measurement_unit="kW", cadence_known=True,
    )
    assert not site_to_module.allowed


def test_independent_region_review_persists_and_exports_v03(tmp_path):
    labels = load_annotations(LABELS)
    pair = load_pairs(INSPECTION / "inspection_pairs.csv", INSPECTION)[0]
    first = next(item for item in labels if item.image_path == pair.rgb_path)
    updated = replace(
        first, thermal_region_bounds="0.1,0.1,0.3,0.3",
        observation_category="localized_heating", finding_status="needs_verification",
        severity="low", observation_note="Synthetic comparison for interface review",
    )
    target = tmp_path / "labels.csv"
    save_annotations(target, [updated if item.annotation_id == first.annotation_id else item for item in labels])
    reloaded = load_annotations(target)
    assert next(item for item in reloaded if item.annotation_id == first.annotation_id).finding_status == "needs_verification"
    unaligned = replace(pair, alignment_reviewed=False)
    records = build_observations(INSPECTION, unaligned, reloaded)
    assert len(records) == 1
    record = records[0]
    assert record.annotation_id == first.annotation_id
    assert record.sample_count and record.measurement_basis == "synthetic_numeric_demo"
    assert record.finding_status == "needs_verification"
    assert "independent_thermal_region_unregistered" in record.data_quality_flags
    assert not record.candidate
    assert record.correlation_status == "blocked"
    modern = list(csv.DictReader(io.StringIO(observations_csv_v03(records))))[0]
    legacy = list(csv.DictReader(io.StringIO(observations_csv(records))))[0]
    assert modern["schema_version"] == "0.3"
    assert modern["thermal_region_bounds"] == updated.thermal_region_bounds
    assert modern["measurement_basis"] == "synthetic_numeric_demo"
    assert modern["finding_status"] == "needs_verification"
    assert legacy["schema_version"] == "0.2" and "thermal_region_bounds" not in legacy
    assert json.loads(observations_json_v03(records))["observations"][0]["synthetic"]
