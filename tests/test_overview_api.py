from pathlib import Path
from shutil import copyfile

from fastapi.testclient import TestClient
from solar_pv.api import server


def test_overview_reports_provisional_design_and_missing_meter(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / 'configs/sites/aamu_2023_review.json'
    target = tmp_path / 'configs/sites/aamu_2023_review.json'
    target.parent.mkdir(parents=True)
    copyfile(source, target)
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    response = TestClient(server.app).get('/api/overview')
    assert response.status_code == 200
    data = response.json()
    assert data['site']['modules'] == 2538
    assert data['site']['status'] == 'provisional review drawing'
    assert data['meter'] is None


def test_overview_preserves_unknown_scope_and_reports_missing_readings(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / 'configs/sites/aamu_2023_review.json'
    target = tmp_path / 'configs/sites/aamu_2023_review.json'
    target.parent.mkdir(parents=True)
    copyfile(source, target)
    folder = tmp_path / 'data/raw/marshall_2026/scada'
    folder.mkdir(parents=True)
    (folder / 'synthetic.csv').write_text(
        'DateTime,Meter: power_true_kw (kW)\n'
        '2026-08-01 12:00,1.2\n2026-08-01 12:05,null\n'
    )
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    meter = TestClient(server.app).get('/api/overview').json()['meter']
    assert meter['rows'] == 2
    assert meter['missing_power'] == 1
    assert meter['cadence_minutes'] == 5
    assert meter['scope'] == meter['timezone'] == 'unknown'


def test_meter_filter_and_export_preserve_missing_values(tmp_path, monkeypatch):
    folder = tmp_path / 'data/raw/marshall_2026/scada'
    folder.mkdir(parents=True)
    (folder / 'synthetic.csv').write_text(
        'DateTime,Meter: power_true_kw (kW)\n'
        '2026-08-01 12:00,1.2\n2026-08-01 12:05,null\n2026-08-01 12:10,3.4\n'
    )
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    client = TestClient(server.app)
    params = {'variable': 'Meter: power_true_kw (kW)',
              'start': '2026-08-01T12:00', 'end': '2026-08-01T12:05'}
    result = client.get('/api/meter/filtered', params=params)
    assert result.status_code == 200
    assert result.json()['count'] == 2
    assert result.json()['missing_or_invalid'] == 1
    export = client.get('/api/meter/export', params=params)
    assert export.status_code == 200
    import csv, io
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert len(rows) == 2
    assert rows[1]['raw::Meter: power_true_kw (kW)'] == 'null'
    assert rows[1]['Meter: power_true_kw (kW)'] == ''
    assert client.get('/api/meter/filtered', params={**params, 'variable': 'invalid'}).status_code == 422
    assert client.get('/api/meter/filtered', params={**params, 'start': '2026-08-01T12:00Z'}).status_code == 422


def test_meter_chart_preserves_empty_half_hour_intervals(tmp_path, monkeypatch):
    folder = tmp_path / 'data/raw/marshall_2026/scada'
    folder.mkdir(parents=True)
    (folder / 'synthetic.csv').write_text(
        'DateTime,Meter: power_true_kw (kW)\n'
        '2026-08-01 12:00,1\n2026-08-01 13:00,2\n'
    )
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    response = TestClient(server.app).get('/api/meter/filtered', params={
        'variable': 'Meter: power_true_kw (kW)', 'start': '2026-08-01T12:00',
        'end': '2026-08-01T13:00',
    })
    points = response.json()['points']
    assert len(points) == 3
    assert points[1]['time'] == '2026-08-01T12:30:00'
    assert points[1]['value'] is None
    assert points[0]['segment'] != points[2]['segment']
