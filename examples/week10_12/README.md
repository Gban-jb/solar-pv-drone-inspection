# Combined synthetic inspection

This example links the earlier import, panel marking, and thermal review work in one inspection. Four RGB/thermal pairs are aligned by construction. Three pairs have fabricated pixel temperatures; the fourth has a color preview only. A five-row SCADA CSV is included for import. No file is from a real drone or plant.

## Run

From the project root:

```sh
.venv/bin/python examples/week10_12/generate_samples.py
.venv/bin/python -m streamlit run src/solar_pv/ui/app.py
```

Open **Inspection review** at `http://localhost:8501/review` or at the port shown by Streamlit. Click **Scan inspection** to show eight opened images and one SCADA CSV. The overview shows all four pairs, their readiness and whether each contributes to the inspection-wide export. Choose a pair to see its RGB and thermal views. The first thermal case has one candidate at the default 5 °C rule. The color-only case contributes panel records but shows no ΔT. Download the combined CSV or JSON observations from the page. The generated sample copies are in `output/observations.csv` and `output/observations.json`.

The top **Panel annotations** link opens the selected pair's RGB image and uses the same working labels file, `data/processed/week10_12_panel_annotations.csv`. Editing a box there changes the analysis shown after returning to **Inspection review**. The generator preserves that working CSV if it already exists. The saved `output/panel_annotations.csv` is the untouched example.

## Pairing and export

`inspection/inspection_pairs.csv` has an explicit `inspection_id`, a unique `pair_id`, relative RGB and thermal paths, the temperature JSON path, and `alignment_reviewed`. A reviewed flag means someone has checked whether the box coordinates can transfer; it does not establish plant identity. The current software requires equal image dimensions and refuses transfer when the flag is false.

The live app exports provisional schema version 0.2. It retains the earlier record, pair, label, temperature, alignment and quality fields and adds optional registry asset ID, mapping status, source image ID and inspection notes. The checked-in sample files under `output/` were generated before Phase 3 and remain historical version 0.1 fixtures. Synthetic and unverified IDs stay clearly marked. The exact interface must be agreed with Student 2 before Week 12 handover.

The 5 °C rule is only a demonstration threshold. An observation is a reason for review, not a confirmed defect or a per-panel power-loss measurement. Real use requires the camera's radiometric export and an independently reviewed RGB/thermal alignment.

## Fall checkpoint walkthrough

Allow about five minutes. Run the app from the project root using the command above.

1. In **New inspection**, open the `examples/week10_12/inspection` folder and scan it. Show the eight image files, the SCADA file, and any file warnings.
2. Open **Panel annotations** and choose the inspection's working labels file. Show a saved box and its synthetic ID. Do not describe the ID as a confirmed plant location.
3. Open **Inspection review** and scan the folder. Select the first pair to show the candidate overlay and its relative temperature comparison.
4. Select `nonradiometric_color_only`. Show that the preview is viewable but has no temperature or ΔT measurement.
5. Download the observation CSV or JSON and point out that the records are marked synthetic. The live app export is schema 0.2; the checked-in sample outputs are historical schema 0.1 files.
6. Close by stating the main limits: the images and readings are synthetic, no real camera radiometry has been tested, and this example does not establish physical panel locations or a diagnosed fault.

This is a prepared synthetic workflow, not yet the assignment's supervisor-selected **new** test image demonstration. Complete that acceptance step with an approved test image and verify the exported file on the demonstration computer. The separate Marshall-meter browser CSV download also remains unverified because the downloaded artifact could not be accessed for comparison; do not claim that test passed.

## Local verification

On November 7, 2026, a Streamlit `AppTest` scanned this example, selected a numeric pair and the display-only pair, confirmed the no-temperature warning and found both download controls with no app exceptions. The numeric example showed one candidate at ΔT 10.03 °C. The schema 0.3 CSV/JSON serialization produced 12 synthetic records; display-only records retained blank ΔT. A CSV verification copy was written outside the project to `/tmp/solar_pv_fall_checkpoint_check/synthetic_fall_observations.csv`. This does not verify a browser-downloaded file or satisfy the new-image supervisor demonstration.
