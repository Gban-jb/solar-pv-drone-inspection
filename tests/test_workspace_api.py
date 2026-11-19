"""The workspace API preserves data and the existing observation interchange."""

import csv
from io import BytesIO, StringIO

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from solar_pv.api import workspaces
from solar_pv.api.server import app

BASE = "/api/inspections"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(workspaces, "WORKSPACES", tmp_path / "workspaces")
    return TestClient(app)


def _inspection(client, sample="empty"):
    response = client.post(BASE, json={"name": "Test inspection", "sample": sample})
    assert response.status_code == 201, response.text
    return BASE + "/" + response.json()["id"]


def _image(width=200, height=160):
    output = BytesIO()
    Image.new("RGB", (width, height), "#304053").save(output, "PNG")
    return output.getvalue()


def _upload(client, root, role, name, content):
    return client.post(f"{root}/files/{role}", files={"file": (name, content)})


def test_import_creates_isolated_inspection_and_keeps_good_files(client):
    root = _inspection(client, "import")
    files = client.get(root).json()["files"]
    assert len([file for file in files if file["kind"] != "scada" and file["status"] != "error"]) == 10
    assert len([file for file in files if file["status"] == "error"]) == 1
    assert len([file for file in files if file["kind"] == "scada" and file["status"] != "error"]) == 1

    evidence = _image()
    assert _upload(client, root, "rgb", "new.png", evidence).status_code == 200
    assert _upload(client, root, "rgb", "second-name.png", evidence).json()["status"] == "duplicate"
    assert _upload(client, root, "rgb", "new.png", _image(210)).status_code == 409
    assert _upload(client, root, "rgb", "broken.png", b"not a picture").status_code == 422
    assert _upload(client, root, "scada", "bad.csv", b"a,b\n1,2,3").status_code == 422
    assert client.get(root + "/image", params={"path": "rgb/new.png"}).headers["content-type"] == "image/jpeg"
    assert client.get(root + "/image", params={"path": "rgb/../workspace.json"}).status_code == 404
    assert not (workspaces.EXAMPLES / "week01_03/inspection/rgb/new.png").exists()


def test_thermal_working_copy_saves_regions_checks_revisions_and_exports(client):
    demo = client.get(BASE + "/demo").json()
    assert len(demo["findings"]) == 12
    assert sum(row["candidate"] for row in demo["findings"]) == 2
    assert client.post(BASE + "/demo/files/rgb", files={"file": ("source.png", _image())}).status_code == 409
    root = _inspection(client, "thermal")
    workspace = client.get(root).json()
    cases = {pair["pair_id"]: pair for pair in workspace["pairs"]}
    assert [cases[f"synthetic_case_0{n}"]["basis"] for n in range(1, 4)] == ["synthetic_numeric_demo"] * 3
    boxes = {"selected": {"box": [.7, .2, .92, .8]}, "reference": {"box": [.08, .2, .3, .8]}}
    for number in range(1, 4):
        response = client.post(f"{root}/pairs/synthetic_case_0{number}/measure", json=boxes)
        assert response.status_code == 200, response.text
        stats = response.json()
        assert stats["selected"]["sample_count"] > 0
        assert stats["delta"] == pytest.approx(stats["selected"]["median"] - stats["reference"]["median"])
    assert client.post(root + "/pairs/nonradiometric_color_only/measure", json=boxes).status_code == 422
    assert client.post(root + "/pairs/synthetic_case_01/measure", json={
        "selected": boxes["selected"], "reference": boxes["selected"],
    }).status_code == 422
    assert client.get(root + "/pairs/synthetic_case_01/heat").headers["content-type"] == "image/png"

    draft = {"image_path": "rgb/synthetic_case_01.png", "asset_id": "Draft box",
             "box": [.07, .07, .26, .16], "review_status": "provisional"}
    assert client.put(root + "/annotations/new", json=draft).status_code == 200
    after_draft = client.get(root).json()["findings"]
    assert sum(row["candidate"] for row in after_draft) == 2
    draft_row = next(row for row in after_draft if row["asset_id"] == "Draft box")
    assert draft_row["delta_t_c"] is None and "box_not_confirmed" in draft_row["data_quality_flags"]

    original = next(row for row in workspace["annotations"] if row["asset_id"] == "SYN-01-P03")
    annotation = original["annotation_id"]
    finding = {"category": "localized_heating", "status": "needs_verification", "severity": "medium",
               "note": "Saved via the workspace", "pair_id": "synthetic_case_01", "regions": boxes,
               "modified_at_utc": original["modified_at_utc"]}
    saved = client.put(f"{root}/findings/{annotation}", json=finding)
    assert saved.status_code == 200, saved.text
    assert client.put(f"{root}/findings/{annotation}", json=finding).status_code == 409
    reloaded = client.get(root).json()
    selected = next(row for row in reloaded["findings"] if row["annotation_id"] == annotation)
    assert selected["observation_note"] == finding["note"]
    assert selected["delta_t_c"] > 0
    filtered = {"ids": selected["record_id"]}
    json_file = client.get(root + "/export/json", params=filtered)
    csv_file = client.get(root + "/export/csv", params=filtered)
    assert json_file.json()["observations"] == [selected]
    assert "attachment" in csv_file.headers["content-disposition"]
    assert list(csv.DictReader(StringIO(csv_file.text)))[0]["observation_note"] == finding["note"]
    assert client.get(root + "/export/json?schema=0.2").json()["schema_version"] == "0.2"
    before = next(row for row in client.get(BASE + "/demo").json()["findings"] if row["annotation_id"] == annotation)
    assert before["observation_note"] != finding["note"]
    assert all(row["delta_t_c"] is None for row in reloaded["findings"] if row["measurement_basis"] == "display_only")


def test_edit_twenty_labels_and_export_an_unpaired_visible_finding(client):
    root = _inspection(client, "annotation")
    rows = client.get(root).json()["annotations"]
    image_path = "rgb/synthetic_panel_array.png"
    labels = [row for row in rows if row["image_path"] == image_path]
    assert len(labels) == 20
    initial = labels[0]
    payload = {"box": [initial[key] for key in ("x_min", "y_min", "x_max", "y_max")],
               "asset_id": "CHECK-01", "image_path": image_path, "target_type": "panel",
               "review_status": "confirmed", "modified_at_utc": initial["modified_at_utc"]}
    endpoint = root + "/annotations/" + initial["annotation_id"]
    changed = client.put(endpoint, json=payload)
    assert changed.status_code == 200, changed.text
    assert changed.json()["annotation_id"] == initial["annotation_id"]
    assert changed.json()["created_at_utc"] == initial["created_at_utc"]
    assert client.put(endpoint, json=payload).status_code == 409

    finding = {"category": "possible_shading", "status": "reviewed", "note": "Visible only",
               "modified_at_utc": changed.json()["modified_at_utc"]}
    saved = client.put(root + "/findings/" + initial["annotation_id"], json=finding)
    assert saved.status_code == 200, saved.text
    records = client.get(root + "/export/json").json()["observations"]
    assert len(records) == 1 and records[0]["asset_id"] == "CHECK-01"
    assert records[0]["thermal_image_path"] == "" and records[0]["delta_t_c"] is None
    assert len(list(csv.DictReader(StringIO(client.get(root + "/export/labels").text)))) == len(rows)
    assert client.delete(endpoint, params={"modified_at_utc": saved.json()["modified_at_utc"]}).status_code == 204
    assert client.get(root + "/export/json").json()["observations"] == []


def test_different_image_dimensions_block_box_transfer_but_allow_review(client):
    root = _inspection(client)
    assert _upload(client, root, "rgb", "capture.png", _image()).status_code == 200
    assert _upload(client, root, "thermal", "capture.png", _image(210)).status_code == 200
    pair = {"rgb_path": "rgb/capture.png", "thermal_path": "thermal/capture.png", "alignment_reviewed": True}
    assert client.post(root + "/pairs", json=pair).status_code == 422
    pair["alignment_reviewed"] = False
    assert client.post(root + "/pairs", json=pair).status_code == 201
    saved = client.get(root).json()["pairs"][0]
    assert saved["basis"] == "display_only" and not saved["alignment_reviewed"]
