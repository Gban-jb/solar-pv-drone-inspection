# Student 1 Solar PV Project Context

Student: Sudin Pokharel
Last updated: 2026-10-28
Current milestone week: working Week 2 (October 26-November 1) under the October 19 start; supervisor calendar unconfirmed. Week 1-3 importer prototype locally verified with synthetic inputs; formal acceptance is pending.
Current assignment: `research/source/project_description_v3.docx` (the newer October 2026 version). The earlier `research/source/project_description.docx` is retained only for history.
Report format: `reports/style.md` is locked; `reports/builders/layout.py` implements its PDF style.
Application base: `src/solar_pv/`; directory ownership is mapped in `README.md`.

## Handoff rule

After each project task, replace outdated status and next steps here. Keep this file below roughly 2,500 words. Distinguish assignment requirements, recommendations, and work actually verified. Do not turn it into a chronological log.

## What the revised assignment asks

Student 1 owns **Drone RGB/Thermal Fault Mapping**. Build a runnable Python application that imports drone RGB photos and radiometric thermal files, helps a reviewer identify panels or rows, highlights suspected warm regions and visible anomalies, and exports an inspection map/list as CSV and JSON. Add inverter/SCADA and weather context where available. The output is an **observation and inspection-priority prototype**, not a confirmed root-cause diagnosis, module-level power-loss proof, or production inspection service.

Inputs: RGB images; radiometric thermal images with *readable pixel temperatures*; image timestamps and GPS; persistent panel/module or row IDs; optionally SCADA inverter power/energy and irradiance/weather. A false-color thermal picture without accessible temperature values must be flagged as non-radiometric, not assigned invented degrees Celsius. Module identity from aerial views can be uncertain; manually confirmed IDs or row/table IDs are acceptable. RGB may reveal dirt, shade or obvious obstructions, but microcrack detection is not promised.

Outputs: annotated image viewer; suspected hotspot and visible-anomaly list; reliable module/row IDs or explicit uncertainty; inspection map/layout; evidence and data-quality flags; CSV/JSON records for Student 2. Temperature difference (ΔT) is relative to nearby comparable modules when valid radiometric data permit it. A hot region is a reason to inspect, not proof of a particular defect. Inverter-level SCADA must remain inverter-level context, not be attributed as an individual module's measured loss.

The **final outcome is a Python software prototype**, eventually with a Streamlit inspection map/viewer, not a standalone model or only a report. The broader group has a drone-building and sensor/communications need; the document does not assign Student 1 sole responsibility for constructing the aircraft. Student 4 builds a separate ground-based RF survey kit, not a sensor mounted to this drone.

## Eight required deliverables

| Milestone | Student 1 build and live acceptance evidence |
| --- | --- |
| Fall W1-3 | Image importer and folder template: load RGB, thermal and one SCADA CSV; inspect 10 images, show metadata/missing fields and report bad files without crashing. |
| Fall W4-6 | Viewer to draw/confirm panel or row boxes, assign persistent IDs and save labels to CSV; label 20 examples and reload them correctly. |
| Fall W7-9 | Thermal hotspot viewer: read actual pixel temperatures when supported, compare nearby modules and display an annotated ΔT for at least three cases; flag non-radiometric images. |
| Fall W10-12 | One app combining import, manual/assisted IDs, hotspot overlays and observation CSV export; supervisor opens a new test image. |
| Spring W13-15 | Add manual-assisted RGB labels or simple baseline for shade, dirt and obvious obstruction; visibly distinguish manual from automatic marks. |
| Spring W16-18 | Plot inverter output against time and irradiance/comparable baseline around inspection time; explain the inverter-level limit. |
| Spring W19-22 | Streamlit map/layout, simple severity rules and CSV/JSON schema for Student 2; click a finding to see image, ΔT and source. |
| Spring W23-25 | Clean repo, 10-case test set, installation guide and end-to-end demo: import new images/SCADA, review candidates and export map/inspection records. |

Fall Week 12 checkpoint: prepared-dataset live demo, committed source, setup steps, five-minute recording and known limitations so a replacement student can continue. Final acceptance: working code, relevant physical kit where applicable, sample inputs and outputs, tests, setup guide and a ten-minute live demonstration on a supervisor-selected case. A report or slides alone is insufficient. Each milestone calls for tangible live evidence; the project-wide wording also mentions a populated database, interactive screen and physical device at every milestone, which should be clarified against Student 1's more specific milestone tests.

The document describes Fall as 12 weeks / up to 240 hours and Spring as 13 weeks / up to 260 hours, at 20 hours per week. It lists August 18 to December 15, 2026 and January 8 to May 15, 2027, but also says activities began later in September. Ask the supervisor for the actual milestone calendar and any make-up-hours expectations. The full-semester compensation condition and Student Project Leader duties are administrative/project-wide; do not assume Sudin is the designated leader.

## Practical architecture and boundaries

```text
RGB + radiometric thermal + timestamps/GPS       inverter SCADA + weather (optional)
                 |                                             |
           robust file import and metadata / quality checks
                 |                                             |
          image viewer + saved row/module IDs      timestamped context graph
                 |                                             |
       comparable-module thermal ΔT; visible labels
                 +----------------------+----------------------+
                                        |
                 reviewed observations + quality/uncertainty flags
                                        |
                   map/layout + CSV/JSON export for Student 2
```

Use the existing `src/solar_pv/` packages by responsibility, but do not force the earlier, larger AI architecture onto this assignment. Recommended stack, subject to real sample files: Python 3.12 in a virtual environment; Pillow for Week 1-3 image decoding, metadata and thumbnails; pandas for SCADA CSV; standard-library `argparse` for a folder-based importer; pytest for corrupt/missing-field and round-trip tests. A small Streamlit browser can show previews and inventory, then grow into the Spring map. For panel boxes, evaluate a simple interactive rectangle tool before adding a heavy UI framework. Use the actual camera vendor's supported radiometric decoder for temperatures once the model/format is known; OpenCV is optional for later image operations. Begin with CSV/JSON and a stable file layout. SQLite is a possible later choice only if persistent multi-inspection storage is needed; Student 2 owns the asset-history database. Deep learning, root-cause classification, PostGIS, and a production API are **not required** by the revised assignment. If no label set exists, use manual/assisted marking and transparent thresholds first.

## Week 1-3 importer status

The specific test is ten opened images, one readable SCADA CSV, visible metadata/missing fields, and bad-file reporting without a crash. The implementation is in `src/solar_pv/ingestion/` with `init` and `scan` CLI commands; `src/solar_pv/ui/inventory.py` provides a local Streamlit preview. `pyproject.toml` defines installation. `examples/week01_03/` contains clearly synthetic input and output files plus a generator. On October 28, a fresh scan opened 10/11 synthetic images, flagged one deliberately broken JPEG, read one 12-row synthetic SCADA CSV, and wrote JSON/CSV inventories. Metadata and missing-field warnings were checked in the manifest. All four pytest tests passed. The Streamlit viewer started (HTTP 200), and its Scan button passed an AppTest interaction check with 10/11 images, 1/1 CSV, one displayed error, and no app exceptions. `reports/submissions/week01_03_image_importer.pdf` is the short professor-facing summary in the locked style. Setup and commands are in `README.md`.

This **does not verify** a real radiometric camera file, real SCADA fields, site data, or installation on a second physical computer. No professor-facing live/recorded demonstration or acceptance has been confirmed. The project folder is not yet a Git repository; Week 12 explicitly requires committed source, and the project-wide handoff asks for reproducible code. The synthetic thermal-style PNGs are display-only; no temperatures or hotspots were calculated. Missing EXIF is a warning, not an image failure. Keep original values in the manifest, and do not guess timestamps or radiometry.

Early shared contract with Student 2: stable site/row/module identifier and granularity, inspection timestamp and timezone, image/source reference, manual-versus-automatic label, anomaly type, ΔT plus radiometric-validity flag, location/mapping confidence, data-quality flags and record ID. Confirm CSV/JSON field names and units together. Student 3 may later consume findings through Student 2, but Student 1's explicit schema task is for Student 2. Student 4 remains an independent communications layer.

## Project-wide gates and unresolved inputs

The revision says SCADA access is available from Marshall's office but does not include a field list, sampling interval, export file or actual access verification. It says no drone currently exists and one must be built. Sudin reports that another person will prepare the plant layout; its owner, format and delivery date remain unconfirmed. The layout is needed to associate image annotations with real site asset IDs and positions for the later map, but the Week 4-6 draw/save/reload tool can use clearly provisional annotation IDs until it arrives. Before field work, the team needs written site and drone-flight permission, pilot/airspace compliance, radiometric export support, plant layout and sensor permissions. By Week 6, confirm thermal files can be decoded and SCADA can be time-joined. By Week 12, freeze common schemas; by Week 18 exchange sample files among Students 1-3. If site access is unavailable, deliver a clearly labeled lab-validated prototype, not a claimed 1.2 MW field service. The revised document targets four reproducible student demos and an optional integrated overview by Week 25, not a guaranteed production platform.

Questions for the supervisor: exact milestone dates; who builds/procures the drone and radiometric camera; camera model and raw file format; sample flight images; SCADA CSV fields/access; plant layout and ID convention; who supplies representative tests; how the project-wide "database and physical device every milestone" rule applies to software-only Student 1 tasks. Confirm whether any earlier Week 1-2 submission must be revised.

## Verified status and next action

The new DOCX is archived in `research/source/`, and the full current plan is `research/requirements/project_plan_v3.md`. The old proposal and `reports/submissions/week01_02_initial_review.pdf` reflect the **superseded assignment**. The Week 1-3 importer has passed the synthetic local demo and tests described above, but the second-computer check, actual-data validation, and supervisor demonstration remain unconfirmed. There is no panel annotation, radiometric analysis, or final inspection map yet.

The professor-facing timeline is `reports/submissions/student1_milestone_timeline.pdf`. Its first page is titled Fall Milestone Timeline and its second page Spring Milestone Timeline. Week blocks are consecutive Monday-to-Sunday periods counted from the October 19, 2026 date in the Week 1 table row. Under this mapping, Week 12 ends January 10, 2027, after the assignment's listed December 15 Fall end; that handover date is marked provisional. Week 25 ends April 11, with April 12-May 15 reserved for final fixes and demonstration. The PDF keeps the synthetic-only importer status bold and asks when the drone and imaging components will be available without addressing Dr. Yaqub by name in that request.

Next for Week 1-3: repeat the live importer demo for the supervisor using the clearly synthetic sample; supply code, setup steps, sample inputs/outputs and the short PDF; confirm the code runs on a second computer, or record this as pending rather than claiming acceptance. Arrange a Git repository/committed source before the Week 12 handover. Request representative camera/SCADA exports and confirm the decoder/field behavior when available; do not block the synthetic software demonstration on equipment or plant layout. Then begin the Week 4-6 marking tool: select an image, draw a box, assign a stable annotation ID, save to CSV and reload it. Keep plant asset IDs blank or provisional until the external layout/ID convention arrives. Agree observation fields with Student 2 and obtain representative panel images for the 20-example check. Confirm layout format and ID hierarchy, drone/camera timing, camera format and SCADA field definitions.
