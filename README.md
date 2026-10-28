# Solar PV Drone Fault Mapping - Student 1

Sudin Pokharel's revised assignment is to build a Python prototype that imports drone RGB and radiometric thermal images, marks panels or rows, highlights suspected anomalies, adds inverter-level context when available, and exports reviewable inspection records. The actual milestone week is awaiting confirmation. The first importer milestone is implemented with synthetic demonstration files; real camera and SCADA data have not been tested. Read `project_context.md` for scope and current progress.

## Project layout

| Area | Purpose |
| --- | --- |
| `AGENTS.md`, `project_context.md` | Instructions and concise handoff context for future work. |
| `reports/style.md` | Locked format for project reports and documents. |
| `reports/builders/` | Reusable PDF layout and report-specific source scripts. |
| `reports/submissions/` | Professor-facing PDFs; the current Week 1-3 summary is here. |
| `research/source/` | The current v3 assignment and the superseded original, both preserved. |
| `research/literature/`, `research/requirements/` | Reading notes and verified requirements. |
| `research/requirements/project_plan_v3.md` | Current architecture, stack, build order and open questions. |
| `src/solar_pv/` | Application package; the first importer and inventory view are implemented. |
| `tests/`, `configs/` | Software tests and site/application configuration. |
| `data/`, `artifacts/` | Local datasets and generated outputs; their contents are excluded from Git. |
| `examples/week01_03/` | Clearly synthetic input and output files for the first milestone. |

`src/solar_pv/` is the base package for technical work. Its subpackages have distinct responsibilities:

| Package | Responsibility |
| --- | --- |
| `domain/` | Persistent panel/row IDs, observations, and export contracts. |
| `ingestion/` | Folder setup, image/CSV validation, metadata inventory, and later synchronization. |
| `imaging/` | Panel marks, RGB labels, thermal decoding, and hotspot overlays. |
| `electrical/` | Inverter-level SCADA context and inspection-time graphs. |
| `diagnosis/` | Transparent candidate and severity rules, not confirmed root causes. |
| `storage/` | Saved labels, inspection records, and local persistence if needed. |
| `api/` | CSV/JSON export contract for Student 2; a server is not yet required. |
| `ui/` | Inspection viewer and map/layout. |

Use `data/raw/` for original inputs, `data/interim/` for conversions, and `data/processed/` for analysis-ready data. Put model files in `artifacts/models/` and experiment outputs in `artifacts/runs/`. The `README.md` files in those areas explain what belongs there. No real site dataset or trained model is present yet.

Place each new file in the area that owns it. Keep the root for project-wide entry points and update this map when the structure changes.

## Week 1-3 importer

Use Python 3.12. From the project root on macOS/Linux:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[ui,dev]"
.venv/bin/python examples/week01_03/generate_samples.py
.venv/bin/solar-pv-import scan examples/week01_03/inspection --output examples/week01_03/output
.venv/bin/python -m pytest -q
.venv/bin/python -m streamlit run src/solar_pv/ui/inventory.py
```

On Windows, use `py -3.12 -m venv .venv` and replace `.venv/bin/python` with `.venv\Scripts\python`. Run the installed `solar-pv-import` command from `.venv\Scripts\solar-pv-import.exe`.

For a new inspection, run `solar-pv-import init data/raw/<inspection-name>` and place original files in the created `rgb/`, `thermal/`, and `scada/` folders. Then use `solar-pv-import scan data/raw/<inspection-name> --output data/processed/<inspection-name>`. The output includes a JSON manifest and a flat CSV inventory. The importer reports unreadable files individually, keeps processing, and marks absent capture time/GPS/camera model as warnings. It does **not** calculate temperatures, match panels, or normalize SCADA yet.

The tested environment used Pillow 13.0.0, pandas 3.1.0, Streamlit 1.66.1 and pytest 9.1.1. The packaged version ranges in `pyproject.toml` allow compatible updates; rerun the tests after installing on another computer. The synthetic sample is not evidence of field validation.

The short report at `reports/submissions/week01_03_image_importer.pdf` summarizes the tested result and outstanding real-data validation. The executable software and sample files are the actual milestone demonstration; the PDF is a companion document.

The existing Week 1-2 PDF and its builder were made for the **superseded** assignment. Do not submit them as evidence for the revised live-demo milestones without updating the content. The current source of requirements is `research/source/project_description_v3.docx`.
