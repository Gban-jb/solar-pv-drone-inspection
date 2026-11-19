# Solar PV Drone Fault Mapping - Student 1

## AAMU Solar PV Inspection Platform

Use Python 3.12 and Node 20 or newer. Start the Python API and React app in separate terminals from the project root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[ui,dev,api]"
.venv/bin/python -m uvicorn solar_pv.api.server:app --host 127.0.0.1 --port 8000
```

```sh
cd frontend
npm ci
npm run dev -- --port 5173
```

Open [the project homepage](http://127.0.0.1:5173/). **Open Inspection Dashboard** loads the last inspection or the built-in sample. Use **Make working copy** to try edits. Upload also offers the importer and 20-box annotation samples. Your working inspections are saved locally under `data/processed/workspaces/` in their own folders. Keep a copy of that folder for handover or recovery. The API is intended for one local server process. A public homepage build may serve the bundled attributed examples, but shared use of the inspection API needs its own access controls.

- **Upload** imports individually validated RGB, thermal preview, supported temperature-grid JSON and meter CSV files. It preserves originals, reports missing metadata and errors, and lets you review image pairs.
- **Inspect** provides RGB and thermal views, a side-by-side comparison, zoom, pan, fit and fullscreen. Save boxes and reviewer observations with persistent IDs. Confirm panel boxes and verify alignment to enable automatic nearby-panel comparisons. Use separate regions for comparisons without transferring geometry between unregistered images.
- **Findings** opens the evidence for each record and exports the current filtered set as CSV or JSON. Schema 0.3 is the default, and 0.2 is available for compatibility. Light, Dark and System are available in the workspace header.

The current numerical examples are synthetic. A thermal preview carries no pixel temperatures. Real radiometric results still require the actual camera, an independently validated decoder and calibration, and reviewed registration. See `project_context.md` for the research limits and remaining acceptance steps.

The bundled synthetic inspection runs without AAMU flight images, SCADA exports, or engineering drawings. The original Streamlit viewer can open existing inspection records and optional local meter and drawing files. Obtain authorized copies separately for those views. The two drawing-backed integration tests skip when the optional files are absent.

```sh
.venv/bin/python -m streamlit run src/solar_pv/ui/app.py --server.address 127.0.0.1 --server.port 8514
```

## Project layout

| Area | Purpose |
| --- | --- |
| `index.html` | Local browser index for the working demos, current reports, and project files. |
| `AGENTS.md`, `project_context.md` | Instructions and concise handoff context for future work. |
| `reports/style.md` | Locked format for project reports and documents. |
| `reports/builders/` | Reusable PDF layout and report-specific source scripts. |
| `reports/submissions/` | Professor-facing PDFs; the current Week 1-3 summary is here. |
| `research/source/` | The current v3 assignment, superseded original, and May 2023 AAMU engineering review PDF. |
| `research/literature/`, `research/requirements/`, `research/analysis/` | Reading notes, verified requirements, and source-data assessments. |
| `research/reports/` | Research milestone audits and meeting demonstration guides. |
| `research/requirements/` | Assignment plan and five-phase site-aware implementation plan. |
| `configs/sites/` | Versioned drawing-based site specifications; not field-verified plant layouts. |
| `src/solar_pv/` | Application package; importer, annotations, thermal analysis, drawing viewer, and one browser app. |
| `frontend/` | React/Vite homepage and Upload, Inspect and Findings workspaces. |
| `tests/`, `configs/` | Software tests and site/application configuration. |
| `data/`, `artifacts/` | Local datasets and generated outputs; their contents are excluded from Git. |
| `images/public_uav_pv/` | Local, CC BY 4.0 research thermal-fusion samples and their attribution; image files are excluded from Git. |
| `images/public_uav_rgb_soiling/` | Local CC BY 4.0 UAV RGB soiling sample, labels, and attribution; image files are excluded from Git. |
| `examples/week01_03/`, `examples/week04_06/`, `examples/week07_09/`, `examples/week10_12/` | Clearly synthetic examples for the Fall workflows. |

To open the local project index, run `python -m http.server 8510 --bind 127.0.0.1` from the project root and visit `http://localhost:8510/`. Start the Streamlit app using the command below for its prototype link to work.

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

Use `data/raw/` for original inputs, `data/interim/` for conversions, and `data/processed/` for analysis-ready data. Put model files in `artifacts/models/` and experiment outputs in `artifacts/runs/`. Working copies of Marshall's meter exports are in ignored `data/raw/marshall_2026/`; their assessment is in `research/analysis/marshall_meter_data_review.md`. Public UAV thermal-fusion and RGB soiling samples are stored under the root `images/` folder; see each dataset README for attribution and limits. The thermal previews are display-only, the RGB set is a separate source with no paired thermal data, and neither comes from AAMU. No trained model is included.

Place each new file in the area that owns it. Keep the root for project-wide entry points and update this map when the structure changes.

## Engineering drawing and provisional site registry

For the optional drawing workspace, place the authorized May 8, 2023 AAMU review PDF at `research/source/aamu_60pct_review_2023-05-08.pdf` and the approved preview images under `src/solar_pv/ui/assets/drawings/`. These source files are handled separately from the app checkout.

`configs/sites/aamu_2023_review.json` records the internally consistent review-drawing design: 2,538 modules, 94 strings of 27, and eight inverters. The model and registry code under `src/solar_pv/domain/` and `src/solar_pv/storage/` validate those totals and generate candidate IDs. To recreate the ignored local CSV:

```sh
.venv/bin/python -m solar_pv.storage.site_registry \
  --spec configs/sites/aamu_2023_review.json \
  --project-root . \
  --output data/processed/aamu_2023_review_registry.csv
```

This produces one site, eight inverter, 94 string, and 2,538 module records. Every asset has `design_provisional` status. Module sequence numbers are electrical string positions, not verified physical panel locations. The observation exports do not yet use these IDs automatically. The drawing says **for review only, not for construction**; request as-built records before treating the registry as installed equipment.

## Solar Farm Map (Phase 2)

From the project root, install the UI dependencies as below, then start the existing app:

```sh
.venv/bin/python -m streamlit run src/solar_pv/ui/app.py --server.address 127.0.0.1 --server.port 8513
```

Open `http://127.0.0.1:8513/site-layout`. The page displays cropped, source-checked previews of WI101 (PDF page 4), WP101.1 (page 7) and WP101.2 (page 8). Use the drawing switch, wheel or +/- zoom, drag to pan, **Fit**, or **100%**. Zoom and pan are saved per sheet for the current browser session.

For a short walkthrough, select **INV.05** in the searchable inverter list. The page opens WP101.1 and lists 12 design strings. Select one string to see its 27 module candidates, then select a module to read its ID, source sheet, provisional mapping status and any linked inspection evidence. WI101's rack block *types* are also available in a logical selector. The drawing does not establish reliable coordinates, block boundaries or a string-to-rack map, so the app places no physical asset markers or highlights on it. These are review-drawing design relationships, not surveyed locations or actual inspection findings. The registry's source PDF is required at `research/source/aamu_60pct_review_2023-05-08.pdf`; missing or changed source and preview files show an error.

## Image-to-asset traceability (Phase 3)

In **Panel annotations**, choose an RGB image and a saved box, then use **Link to Solar Asset**. Search the inverter, string and optional module selectors, and save the link. The existing local plant ID remains separate; the saved registry ID is initially **provisional**. You can edit or remove the link without deleting the box. The optional verification action requires a named reviewer and an approved source reference, and refuses synthetic images. Box review and physical mapping review are separate states. A stale registry ID remains on the label and is shown as unresolved.

The annotation CSV now appends inspection/image IDs, source designation, linked asset/type, mapping method/status/evidence, notes and modification time. Boxes use normalized `(x_min, y_min, x_max, y_max)` coordinates relative to the original image dimensions, with origin at the top left. These are image coordinates, not drawing or geographic coordinates. Old CSVs load without a migration step; the first save in the new format preserves an exact `.pre_asset_link.csv` backup beside the working CSV. New links are discoverable from **Solar Farm Map** through the ignored local index `data/processed/asset_evidence_index.json`. The asset card shows the highlighted RGB box, explicit thermal pairing if one exists, available metadata, notes, mapping status and any review observation. **Open highlighted annotation** returns to the saved box. The annotation page URL retains its selected inspection, label file, image and annotation across refreshes.

For an isolated synthetic walkthrough, copy `examples/week10_12/output/panel_annotations.csv` to `data/processed/phase3_demo_annotations.csv`, choose the Week 10–12 inspection folder and the copied CSV under **Files and output**, and link `syn-01-1` to `INV.05 → INV-05-01 → MOD-27`. A local demonstration copy is already present if following this checkout. The source example and normal working labels are untouched. Enter an optional visual observation, open the linked asset in **Solar Farm Map**, return to its highlighted annotation, then open **Inspection review** and download the observation CSV. The verified demo download is copied to ignored `artifacts/runs/phase3_demo_observations.csv`. Schema version 0.2 adds the registry ID, image ID, mapping status, provenance and notes while retaining the earlier fields. The synthetic example proves software traceability only; it does not verify that a real panel is at this design position or that a thermal candidate is a diagnosed fault. Original image files are never modified.

## Week 1-3 importer

Use Python 3.12. From the project root on macOS/Linux:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[ui,dev]"
.venv/bin/python examples/week01_03/generate_samples.py
.venv/bin/solar-pv-import scan examples/week01_03/inspection --output examples/week01_03/output
.venv/bin/python -m pytest -q
.venv/bin/python -m streamlit run src/solar_pv/ui/app.py
```

On Windows, use `py -3.12 -m venv .venv` and replace `.venv/bin/python` with `.venv\Scripts\python`. Run the installed `solar-pv-import` command from `.venv\Scripts\solar-pv-import.exe`.

For a new inspection, run `solar-pv-import init data/raw/<inspection-name>` and place original files in the created `rgb/`, `thermal/`, and `scada/` folders. Then use `solar-pv-import scan data/raw/<inspection-name> --output data/processed/<inspection-name>`. The output includes a JSON manifest and a flat CSV inventory. The importer reports unreadable files individually, keeps processing, and marks absent capture time/GPS/camera model as warnings. It does **not** calculate temperatures, match panels, or normalize SCADA yet.

On November 5, 2026, a fresh Python 3.12 virtual environment on this Mac installed the project from `pyproject.toml`, loaded the annotation page, and passed all 19 tests. The packaged version ranges allow compatible updates; rerun the tests after installing on another computer. This is not a second-computer check or field validation.

The short report at `reports/submissions/week01_03_image_importer.pdf` summarizes the tested result and outstanding real-data validation. The executable software and sample files are the actual milestone demonstration; the PDF is a companion document.

### Public drone thermal-fusion sample for the demo

For a public RGB import demo, scan `/Users/mac/Documents/Solar_PV/images/public_uav_rgb_soiling/inspection`; this test split contains 23 readable 640×640 RGB crops and supplied labels. For a thermal image import demo, scan `/Users/mac/Documents/Solar_PV/images/public_uav_pv/inspection`; it contains 50 readable thermal-fusion previews. These are separate research sources, not AAMU data, and must not be paired. The thermal files do not support pixel-temperature/ΔT analysis. Read each dataset README for attribution and limitations.

## Meter data from Mr. Marshall

Open **Meter data** at `/meter` in the single Streamlit app. It loads CSVs from Git-ignored `data/raw/marshall_2026/scada/`, reports file and missing-value counts, plots 30-minute averages of available power readings without connecting across gaps, and lists full days with near-zero recorded power separately from days with missing readings. A date selector narrows the view. The file details show the three gaps between exports. The inventory importer now counts literal `null` and `undefined` as missing values and warns about incomplete CSVs. Meter scope and timestamp timezone are unconfirmed; this view does not attribute output to panels or estimate lost energy. Source assessment and questions are in `research/analysis/marshall_meter_data_review.md`.

## Week 4-6 panel and row marking

The app's **Panel annotations** page loads RGB and thermal previews from an inspection folder. Draw one rectangle, click the canvas update button, choose panel or row, then save. The CSV holds stable annotation IDs and normalized coordinates. The saved Week 4-6 example contains 22 labels across three synthetic images; select `examples/week04_06/output/panel_annotations.csv` under **Files and output** to view it. The app's default working CSV is separate. See `examples/week04_06/README.md` for the demo. Box review does not confirm a real plant asset ID.

## Week 7-9 thermal review

The **Thermal review** page reads documented synthetic temperature-grid examples, overlays saved panel boxes, compares each panel median with nearby panels, and flags differences at the selected threshold. Its thermal-only false-color scale colors the labeled panel areas blue for cooler values through teal/yellow/orange to red for hotter values, while leaving the surrounding image neutral. Adjustable Celsius endpoints and a legend make the displayed range clear; the observations table gives each labeled panel's median temperature and relative ΔT. Defaults use the coolest panel median and hottest in-panel pixel. The scale is for visualization, not a universal fault classification. A color-only sample is marked non-radiometric. Generate the examples with `.venv/bin/python examples/week07_09/generate_samples.py`; see `examples/week07_09/README.md`. The real camera format, decoder and temperature settings still need confirmation.

## Combined inspection review

Use **New inspection** in the app to load a folder with `rgb/`, `thermal/`, and optional `scada/` folders. Scan the folder, choose one RGB image and one thermal image, inspect both previews and their dimensions, then save the pair. A temperature-grid JSON file is optional; when none is selected, the thermal image is treated as display-only and ΔT is unavailable. Confirm image alignment only after reviewing the pair, and mark generated inputs as synthetic so that status reaches the exported records. Saved pairs are written to `inspection_pairs.csv` in that inspection folder and are available in **Inspection review**. Pairs with unreviewed alignment or mismatched dimensions remain visible, but panel transfer and observation generation are blocked.

Generate the aligned synthetic inspection with `.venv/bin/python examples/week10_12/generate_samples.py`. Open **Inspection review** in the same app and scan the inspection. The overview lists every pair's alignment, panel labels, thermal data, export status, observation count and exclusion reason. An unreviewed, unlabeled or unreadable pair is excluded without blocking valid pairs. A display-only thermal pair can export panel observations with temperature and ΔT unavailable. Choose a pair to inspect its RGB and thermal overlays, then download one inspection-wide observation CSV or JSON. **Panel annotations** opens the selected pair's RGB image after you visit the review page. Its editable working labels are `data/processed/week10_12_panel_annotations.csv`; the generator creates this file only if it is missing, so rerunning it does not replace your edits. The original example labels and sample outputs remain under `examples/week10_12/output/`. See `examples/week10_12/README.md` for the workflow and provisional export fields.

The pairing CSV explicitly names each RGB image, thermal image, optional temperature-grid file, inspection ID and alignment-review flag. Boxes transfer between images only for reviewed pairs with matching dimensions. This synthetic alignment is a development fixture; real RGB/thermal registration and camera temperature decoding still need validation. Student 2's final interchange field names are not yet agreed.

## Phase 4 thermal, meter and evidence review

The Thermal review page opens a paired RGB/thermal case, shows source and measurement basis, and supports zooming. It distinguishes display-only thermal images from synthetic numeric grids, unverified numeric grids and explicitly calibration-referenced numeric grids. For a valid numeric source, reviewers can select an independent thermal region and optional reference region; the app reports min, max, mean, median, valid and excluded sample counts, and unit. No threshold is applied by default. RGB boxes are copied only after alignment review and matching dimensions. Saved observation category, reviewer severity, review status, notes and normalized thermal bounds persist in the existing annotation CSV.

The Meter data page exposes the columns present in each CSV, preserves raw cell values and source row identity, reports invalid/missing values, duplicates, out-of-order records and observed cadence, filters and plots a chosen field, and exports filtered records. Meter scope proposals persist as unverified. Correlation readiness fails closed while timestamp, timezone, scope, time overlap and verified asset link prerequisites are missing. The provided Marshall files have no documented timezone or meter ID/scope, so the app makes no module-level electrical association.

Observation CSV and JSON schema 0.3 include measurement basis, region statistics and provenance. The existing schema 0.2 export functions remain available. Read `research/analysis/phase4_data_readiness.md` for audited inputs and unavailable evidence. No native radiometric camera original or site-calibrated temperature has been tested.

The existing Week 1-2 PDF and its builder were made for the **superseded** assignment. Do not submit them as evidence for the revised live-demo milestones without updating the content. The current source of requirements is `research/source/project_description_v3.docx`.
