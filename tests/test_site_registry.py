"""Cross-sheet design arithmetic and provisional asset-registry checks."""

import csv
import json
from pathlib import Path

import pytest

from solar_pv.domain.assets import build_design_registry
from solar_pv.storage.site_registry import (
    load_site_spec,
    verify_source_document,
    write_registry_csv,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "configs/sites/aamu_2023_review.json"


def test_aamu_design_facts_reconcile_across_drawings():
    site = load_site_spec(SPEC_PATH)
    assert site.design_status == "review_drawing_unverified"
    assert site.source.not_for_construction
    assert site.module_count == 2538
    assert site.module_count * site.module_stc_w == 1_383_210
    assert site.string_count == 94
    assert site.modules_per_string == 27
    assert [inverter.string_count for inverter in site.inverters] == [12] * 6 + [11] * 2
    assert sum(group.module_count for group in site.rack_groups) == 2538
    assert site.inverter_count * site.inverter_ac_rating_kw == 1000
    assert site.longitude_dms is None


def test_registry_has_unique_parented_provisional_ids():
    site = load_site_spec(SPEC_PATH)
    registry = build_design_registry(site)
    assert len(registry.assets) == 1 + 8 + 94 + 2538
    assert registry.count("site") == 1
    assert registry.count("inverter") == 8
    assert registry.count("string") == 94
    assert registry.count("module") == 2538
    assert all(asset.verification_status == "design_provisional" for asset in registry.assets)
    assert registry.get("AAMU-INV-07-STR-11-MOD-27").parent_id == "AAMU-INV-07-STR-11"
    assert registry.get("AAMU-INV-07-STR-12") is None
    assert registry.get("AAMU-INV-01-STR-01-MOD-01").drawing_label is None
    assert len(registry.children_of("AAMU-INV-08")) == 11
    assert len(registry.children_of("AAMU-INV-08-STR-11")) == 27


def test_registry_csv_preserves_hierarchy_and_status(tmp_path):
    registry = build_design_registry(load_site_spec(SPEC_PATH))
    target = write_registry_csv(registry, tmp_path / "nested/registry.csv")
    with target.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2641
    assert rows[0]["asset_id"] == "AAMU"
    assert rows[-1]["asset_id"] == "AAMU-INV-08-STR-11-MOD-27"
    assert rows[-1]["parent_id"] == "AAMU-INV-08-STR-11"
    assert {row["verification_status"] for row in rows} == {"design_provisional"}


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda data: data["strings"].update(modules_per_string=18), "Module count disagrees"),
        (lambda data: data["module"].update(stc_w=540), "DC rating disagrees"),
        (lambda data: data["inverter_strings"][6].update(string_count=12), "String count disagrees"),
        (lambda data: data["rack_groups"][0].update(count=4), "site-plan rack groups"),
        (lambda data: data.update(design_status="field_verified"), "review drawing cannot"),
    ],
)
def test_conflicting_or_unverified_specs_are_rejected(tmp_path, change, message):
    data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_site_spec(path)


def test_changed_source_checksum_is_rejected(tmp_path):
    site = load_site_spec(SPEC_PATH)
    changed = tmp_path / site.source.path
    changed.parent.mkdir(parents=True)
    changed.write_bytes(b"changed drawing contents")
    with pytest.raises(ValueError, match="checksum differs"):
        verify_source_document(site, tmp_path)
