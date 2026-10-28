# Student 1 Project Plan (Revised Assignment)

Student: Sudin Pokharel  
Source: `research/source/project_description_v3.docx`  
Plan date: 2026-10-22  
Status: implementation plan; milestone dates and site data access are not yet confirmed

## Outcome and scope

Build a reproducible Python inspection prototype. It imports drone RGB and radiometric thermal files, keeps stable row or panel labels, highlights suspected hot or visibly affected areas, shows inverter-level SCADA context where available, and exports evidence-backed inspection records for Student 2. The final product is a runnable application and demonstration, not a report alone. A thermal anomaly is a reason to inspect, not a confirmed electrical root cause.

The revised assignment explicitly allows manually confirmed IDs and a simple baseline. It does not require deep learning, microcrack detection, per-panel electrical loss from inverter data, a production API, or a deployed cloud platform. Student 2 owns long-term asset history; Student 3 owns cost scenarios; Student 4 owns a separate RF survey kit.

## System architecture

```text
Inspection folder
  rgb/ + thermal/ + scada/
             |
      Ingest and validate
      metadata, decode, errors, provenance
             |
      Inspection manifest (JSON/CSV)
             |
       Reviewer-assigned row/panel IDs
             |
       Thermal observations + RGB labels
             |
       Inspection-time inverter context
             |
       Reviewed findings + simple severity
             |
       Streamlit layout/map and CSV/JSON export
             |
             Student 2
```

Core processing lives in `src/solar_pv/` and is callable without the user interface. `ingestion/` reads files and builds the manifest; `domain/` defines IDs and observation records; `imaging/` holds annotation, thermal decoding and visual overlays; `electrical/` handles inverter-level time series; `diagnosis/` holds transparent candidate/severity rules; `storage/` saves local inspection work; `api/` owns file-export schemas, not necessarily an HTTP server; `ui/` presents the review screen and map. Keep original files unchanged in `data/raw/`; derived data belong in `data/processed/`. A file manifest and CSV/JSON are enough for the first prototype. Student 2's separate database is the historical source of truth.

## Technology decisions

| Need | Choice and boundary |
| --- | --- |
| Runtime and distribution | Python 3.12, isolated virtual environment, `pyproject.toml`, documented installation on a second computer. Verify the eventual camera SDK supports the chosen Python/platform. |
| Week 1-3 image import | Pillow for supported JPEG/PNG/TIFF decoding, dimensions, EXIF and thumbnails. Decoding a picture does not prove it contains temperatures. |
| Week 1-3 SCADA import | pandas for CSV inspection; preserve raw column names and values. Confirm field names, units and timezone before applying plant-specific mappings. |
| Command and tests | Standard-library `argparse` CLI; pytest for file failures, missing metadata, CSV parsing and export invariants. |
| Reviewer interface | A small Streamlit inventory screen first, growing into the final review/map screen. Prototype a narrow rectangle-drawing interaction in Weeks 4-6 and confirm it saves stable coordinates and IDs. Use a small Streamlit component only if built-in controls are insufficient. |
| Thermal measurements | Camera-vendor-supported decoder/SDK after obtaining original radiometric samples. Keep conversion parameters and decoder version. Never derive degrees C from a color-rendered image. NumPy/OpenCV can support later pixel operations if the camera data warrants them. |
| SCADA context and map | pandas time-series plots at inverter level. Streamlit with PyDeck for selectable mapped findings when reliable GPS/site coordinates exist; otherwise use a clearly labeled layout/list. |
| Persistence/integration | Local CSV/JSON, original-file references, schema version and data-quality flags. Add SQLite only if local editing/history actually needs transactions; do not duplicate Student 2's database. No PostGIS, custom API server or deep-learning infrastructure unless later evidence changes the scope. |

## Build order and acceptance gates

| Weeks | Build | Demonstration gate |
| --- | --- | --- |
| Fall 1-3 | Folder template and importer for RGB, thermal and SCADA CSV; manifest and preview. | Open 10 images and one CSV, show metadata/missing fields, and report a bad file without crashing. |
| Fall 4-6 | Draw/confirm panel or row boxes; persistent IDs saved to CSV. | Label 20 examples, save and reload exactly. |
| Fall 7-9 | Read radiometric temperatures where supported and mark relative hot regions. | Annotated image and delta T for at least three test cases; reject non-radiometric temperature claims. |
| Fall 10-12 | Combine importer, IDs, thermal overlays and observation CSV in one runnable app. | Supervisor opens a new test image and exports an observation. Supply source, setup, five-minute recording and limitations. |
| Spring 13-15 | Manual-assisted or simple visible labels for shade, dirt and obvious obstruction. | Show original/annotated views and label provenance. |
| Spring 16-18 | Timestamped inverter output vs irradiance/comparable baseline. | Show one linked graph and explain the inverter-level attribution limit. |
| Spring 19-22 | Inspection map/layout, transparent severity rules, CSV/JSON contract for Student 2. | Click a finding to view image, delta T and data source. |
| Spring 23-25 | Ten-case test set, clean install, end-to-end import/review/export. | Ten-minute supervisor-selected demo, setup guide, sample input/output and tests. |

Work in small vertical slices so each milestone is runnable. Freeze shared IDs and file schema with Student 2 by Week 12; exchange sample files among Students 1-3 by Week 18. A case with uncertain asset location or no radiometric data must remain explicitly uncertain. Do not turn unavailable inputs into zero or confirmed faults.

## Immediate Week 1-3 implementation

1. Obtain the camera model, ten representative original images, a SCADA CSV and the expected folder naming from the supervisor. Until these arrive, use clearly labeled synthetic sample images and CSV only for software testing.
2. Provide `init` and `scan` commands. `init` creates `rgb/`, `thermal/` and `scada/` folders. `scan` decodes files individually, captures dimensions, format, file size, available capture time/GPS, checksums, CSV columns/row count and missing-field warnings. Keep processing after a per-file error.
3. Save JSON and flat CSV inventories, present previews/status in the UI, write tests, and repeat the run from a clean install. The demo must separate real site data from synthetic fixtures.

## Feasibility questions

Confirm the actual milestone calendar, who procures/builds the drone and radiometric camera, supported raw export, Marshall's SCADA columns and sampling interval, written site/flight access, site layout, and a shared panel/row ID convention. The project-wide instruction about a populated database and physical device at every milestone conflicts with the specific software-only Week 1-3 test; ask the supervisor how it is applied. If field access is unavailable, the final result must be labeled a lab-validated prototype rather than a validated site service.

## Sources checked

- Revised Student 1 assignment: `research/source/project_description_v3.docx`.
- Pillow image lifecycle and formats: https://pillow.readthedocs.io/en/stable/reference/open_files.html
- pandas CSV parser: https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_csv.html
- Streamlit components and selectable PyDeck charts: https://docs.streamlit.io/develop/concepts/custom-components/components-v2 and https://docs.streamlit.io/develop/api-reference/charts/st.pydeck_chart
- pytest temporary-file testing: https://docs.pytest.org/en/stable/how-to/tmp_path.html
- Example of model-dependent radiometric support: https://flir.custhelp.com/app/answers/detail/a_id/3084/
