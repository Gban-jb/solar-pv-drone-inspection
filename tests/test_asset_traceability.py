"""Persistent image-to-asset links without claiming a physical site mapping."""

from dataclasses import replace
from pathlib import Path
import csv
import io
import shutil

import pytest
from PIL import Image

from solar_pv.api.observations import observations_csv, observations_json
from solar_pv.domain.assets import build_design_registry
from solar_pv.domain.asset_mapping import (
    link_annotation, mapping_display, selected_asset, unlink_annotation, verify_asset_link,
)
from solar_pv.domain.observations import build_observations
from solar_pv.imaging.annotations import load_annotations, make_annotation, revise_annotation, save_annotations
from solar_pv.imaging.pairing import ImagePair, save_pairs
from solar_pv.storage.asset_evidence import find_asset_evidence, register_evidence_source
from solar_pv.storage.site_registry import load_site_spec


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = build_design_registry(load_site_spec(ROOT / "configs/sites/aamu_2023_review.json"))
MODULE = "AAMU-INV-05-STR-01-MOD-27"


def _source(tmp_path):
    root = tmp_path / "inspection"
    (root / "rgb").mkdir(parents=True)
    (root / "thermal").mkdir()
    Image.new("RGB", (64, 48), "#768e72").save(root / "rgb/frame.png")
    Image.new("RGB", (64, 48), "#555577").save(root / "thermal/frame.png")
    pair = ImagePair("SYN-TRACE", "pair-1", "rgb/frame.png", "thermal/frame.png", "", True, True)
    save_pairs(root / "inspection_pairs.csv", root, [pair])
    annotation = make_annotation(
        image_path=pair.rgb_path, target_type="panel", asset_id="LOCAL-01",
        box=(10, 10, 20, 20), canvas_size=(64, 48), image_size=(64, 48),
        inspection_id=pair.inspection_id, source_provenance="synthetic",
    )
    return root, pair, annotation


def test_valid_hierarchy_link_edit_remove_and_explicit_verification(tmp_path):
    root, _, annotation = _source(tmp_path)
    assert selected_asset(
        REGISTRY, inverter_id="AAMU-INV-05", string_id="AAMU-INV-05-STR-01",
        module_id=MODULE,
    ).asset_id == MODULE
    with pytest.raises(ValueError, match="does not belong"):
        selected_asset(
            REGISTRY, inverter_id="AAMU-INV-04", string_id="AAMU-INV-05-STR-01",
            module_id=None,
        )
    with pytest.raises(ValueError, match="Unknown"):
        link_annotation(annotation, REGISTRY, "AAMU-NOT-REAL")

    linked = link_annotation(annotation, REGISTRY, MODULE, reviewer_notes="Drawing candidate only")
    assert linked.linked_asset_type == "module" and linked.mapping_status == "provisional"
    assert linked.asset_id == "LOCAL-01"
    assert "INV.05" in mapping_display(linked, REGISTRY)[1]
    assert "MOD-27" in mapping_display(linked, REGISTRY)[1] or MODULE in mapping_display(linked, REGISTRY)[1]
    revised_box = revise_annotation(
        linked, target_type="region", asset_id="LOCAL-01", review_status="confirmed",
        box=(11, 11, 18, 18), canvas_size=(64, 48), image_size=(64, 48),
    )
    assert revised_box.linked_asset_id == MODULE and revised_box.source_image_id == linked.source_image_id
    with pytest.raises(ValueError, match="Synthetic"):
        verify_asset_link(linked, REGISTRY, approved_reference="as-built", reviewer="Reviewer")
    non_synthetic = replace(linked, source_provenance="field_unverified")
    with pytest.raises(ValueError, match="source reference"):
        verify_asset_link(non_synthetic, REGISTRY, approved_reference="", reviewer="Reviewer")
    verified = verify_asset_link(non_synthetic, REGISTRY, approved_reference="Approved schedule A", reviewer="Reviewer")
    assert verified.mapping_status == "verified" and verified.mapping_evidence == "Approved schedule A"
    edited = link_annotation(verified, REGISTRY, "AAMU-INV-05-STR-01")
    assert edited.mapping_status == "provisional" and edited.mapping_evidence == ""
    unlinked = unlink_annotation(edited)
    assert unlinked.annotation_id == annotation.annotation_id
    assert unlinked.asset_id == annotation.asset_id
    assert unlinked.linked_asset_id == "" and unlinked.mapping_status == "unmapped"


def test_legacy_22_labels_survive_migration_without_renumbering(tmp_path):
    original = ROOT / "examples/week04_06/output/panel_annotations.csv"
    target = tmp_path / "labels.csv"
    shutil.copyfile(original, target)
    before_bytes = target.read_bytes()
    before = load_annotations(target)
    assert len(before) == 22
    linked = link_annotation(before[0], REGISTRY, MODULE)
    save_annotations(target, [linked, *before[1:]])
    after = load_annotations(target)
    assert [row.annotation_id for row in after] == [row.annotation_id for row in before]
    assert [(row.image_path, row.asset_id, row.x_min, row.y_min) for row in after] == [
        (row.image_path, row.asset_id, row.x_min, row.y_min) for row in before
    ]
    assert after[0].linked_asset_id == MODULE
    assert target.with_name("labels.csv.pre_asset_link.csv").read_bytes() == before_bytes
    assert all(not row.linked_asset_id for row in after[1:])


def test_source_index_persists_evidence_and_exports_provisional_synthetic_note(tmp_path):
    root, pair, annotation = _source(tmp_path)
    label_file = tmp_path / "labels.csv"
    linked = replace(
        link_annotation(annotation, REGISTRY, MODULE),
        observation_note="Visible discoloration", possible_cause="",
    )
    save_annotations(label_file, [linked])
    index = tmp_path / "evidence_index.json"
    register_evidence_source(index, label_file, root)
    register_evidence_source(index, label_file, root)

    # A new lookup using only files on disk is the restart boundary.
    found, warnings = find_asset_evidence(index, REGISTRY, MODULE)
    assert not warnings and len(found) == 1
    assert found[0].annotation.annotation_id == annotation.annotation_id
    assert found[0].image_metadata["width"] == 64
    assert found[0].pair.thermal_path == pair.thermal_path
    assert found[0].observation is not None
    parent_found, _ = find_asset_evidence(index, REGISTRY, "AAMU-INV-05")
    assert len(parent_found) == 1

    record = build_observations(root, pair, load_annotations(label_file))[0]
    assert record.linked_asset_id == MODULE
    assert record.mapping_status == "provisional"
    assert record.observation_note == "Visible discoloration"
    assert record.synthetic and not record.radiometric_valid and record.delta_t_c is None
    assert "asset_mapping_unverified" in record.data_quality_flags
    assert "non_radiometric" in record.data_quality_flags
    csv_row = next(csv.DictReader(io.StringIO(observations_csv([record]))))
    assert csv_row["linked_asset_id"] == MODULE and csv_row["source_image_id"] == linked.source_image_id
    assert '"mapping_status": "provisional"' in observations_json([record])


def test_missing_and_corrupt_sources_remain_visible_as_warnings(tmp_path):
    root, _, annotation = _source(tmp_path)
    label_file = tmp_path / "labels.csv"
    save_annotations(label_file, [link_annotation(annotation, REGISTRY, MODULE)])
    index = tmp_path / "evidence_index.json"
    register_evidence_source(index, label_file, root)

    (root / "rgb/frame.png").write_bytes(b"broken image")
    found, _ = find_asset_evidence(index, REGISTRY, MODULE)
    assert len(found) == 1
    assert found[0].image_metadata["status"] == "error"
    assert found[0].warnings

    (root / "rgb/frame.png").unlink()
    found, warnings = find_asset_evidence(index, REGISTRY, MODULE)
    assert len(found) == 1 and found[0].warnings
    assert warnings  # The pairing file cannot validate a missing source.


def test_stale_registry_reference_is_preserved_as_unresolved(tmp_path):
    root, pair, annotation = _source(tmp_path)
    stale = replace(
        annotation, linked_asset_id="OLD-ASSET", linked_asset_type="module",
        mapping_method="manual_selection", mapping_status="provisional",
    )
    label_file = tmp_path / "labels.csv"
    save_annotations(label_file, [stale])
    loaded = load_annotations(label_file)[0]
    assert loaded.linked_asset_id == "OLD-ASSET"
    assert mapping_display(loaded, REGISTRY)[0] == "Unresolved"
    record = build_observations(root, pair, [loaded], registry=REGISTRY)[0]
    assert record.mapping_status == "unresolved"
    assert "asset_mapping_unresolved" in record.data_quality_flags
    index = tmp_path / "evidence_index.json"
    register_evidence_source(index, label_file, root)
    found, _ = find_asset_evidence(index, REGISTRY, MODULE)
    assert found == []


def test_duplicate_link_to_same_asset_in_one_image_is_rejected(tmp_path):
    _, _, first = _source(tmp_path)
    second = make_annotation(
        image_path=first.image_path, target_type="panel", asset_id="LOCAL-02",
        box=(35, 10, 18, 20), canvas_size=(64, 48), image_size=(64, 48),
        inspection_id="SYN-TRACE", source_provenance="synthetic",
    )
    with pytest.raises(ValueError, match="duplicate linked asset"):
        save_annotations(
            tmp_path / "labels.csv",
            [link_annotation(first, REGISTRY, MODULE), link_annotation(second, REGISTRY, MODULE)],
        )


def test_evidence_index_uses_paths_that_survive_moving_project_folder(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    root, _, annotation = _source(project)
    label_file = project / "data/processed/labels.csv"
    save_annotations(label_file, [link_annotation(annotation, REGISTRY, MODULE)])
    index = project / "data/processed/asset_evidence_index.json"
    register_evidence_source(index, label_file, root)
    assert '"annotation_file": "labels.csv"' in index.read_text()

    moved = tmp_path / "moved_project"
    shutil.move(str(project), str(moved))
    found, warnings = find_asset_evidence(moved / "data/processed/asset_evidence_index.json", REGISTRY, MODULE)
    assert not warnings and len(found) == 1
    assert found[0].annotation.annotation_id == annotation.annotation_id
