import csv
import json

from PIL import Image

from solar_pv.ingestion.cli import main
from solar_pv.ingestion.importer import init_inspection, scan_inspection, write_manifest


def test_init_creates_expected_folders(tmp_path):
    root = init_inspection(tmp_path / "visit")
    assert all((root / name).is_dir() for name in ("rgb", "thermal", "scada"))


def test_scan_reports_bad_image_without_stopping(tmp_path):
    root = init_inspection(tmp_path / "visit")
    for index in range(10):
        role = "rgb" if index < 6 else "thermal"
        Image.new("RGB", (32, 24), "white").save(root / role / f"{index:02d}.png")
    (root / "rgb" / "broken.jpg").write_bytes(b"not a jpeg")
    with (root / "scada" / "readings.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("timestamp_utc", "inverter_id", "power_kw"))
        writer.writerow(("2026-10-22T10:00:00Z", "INV-1", "17.0"))

    manifest = scan_inspection(root)
    assert manifest["summary"] == {
        "images_found": 11,
        "images_opened": 10,
        "image_errors": 1,
        "scada_files_found": 1,
        "scada_files_opened": 1,
    }
    assert next(row for row in manifest["images"] if row["path"].endswith("broken.jpg"))["status"] == "error"
    assert all(row["status"] == "warning" for row in manifest["images"] if row["status"] != "error")
    assert all(row["temperature_status"] == "not_checked" for row in manifest["images"] if row["kind"] == "thermal")
    assert manifest["scada"][0]["row_count"] == 1

    json_path, csv_path = write_manifest(manifest, tmp_path / "out")
    assert json.loads(json_path.read_text())["summary"]["images_opened"] == 10
    with csv_path.open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 12


def test_bad_csv_is_reported(tmp_path):
    root = init_inspection(tmp_path / "visit")
    (root / "scada" / "broken.csv").write_text("a,b\n1,2,3\n", encoding="utf-8")
    manifest = scan_inspection(root)
    assert manifest["summary"]["scada_files_opened"] == 0
    assert manifest["scada"][0]["status"] == "error"
    assert "row 2 has 3 values" in manifest["scada"][0]["error"]
    assert "No readable SCADA CSV found" in manifest["folder_issues"]


def test_cli_scan_writes_output_for_partial_failure(tmp_path, capsys):
    root = init_inspection(tmp_path / "visit")
    (root / "rgb" / "broken.jpg").write_bytes(b"bad")
    output = tmp_path / "out"
    assert main(["scan", str(root), "--output", str(output)]) == 0
    assert (output / "inspection_manifest.json").is_file()
    assert "ERROR" in capsys.readouterr().out
