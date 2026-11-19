# Synthetic thermal review examples

The viewer demonstrates the Week 7-9 workflow with fabricated temperature grids. The three radiometric cases contain 3 labeled panels each, with stable, moderate, and warmer-panel patterns. A fourth color-only image has no temperature grid and should be identified as non-radiometric. None of these values is from a camera or a solar site.

## Run the example

From the project root:

```sh
.venv/bin/python examples/week07_09/generate_samples.py
.venv/bin/python -m streamlit run src/solar_pv/ui/app.py
```

Open **Thermal review** in the app. Change the ΔT threshold and inspect the panel table. Use the color-only case to show that the viewer withholds temperature comparisons when pixel temperatures are unavailable. A case result CSV can be downloaded from the page.

## Prototype data format

Each JSON file stores a `schema_version`, image path, preview path, image dimensions, temperature unit, capture time, radiometric availability, synthetic-data marker, and (for radiometric cases) a rectangular `temperature_grid`. The grid is a small software-development fixture, not a camera interchange format. The future camera decoder must supply a validated grid and preserve camera calibration settings where the camera requires them.

The analysis summarizes median temperature inside each saved panel box, compares that value with the nearest labeled panels, and reports ΔT in Celsius. The default 5 °C threshold is only a demonstration setting. A candidate is a review flag, not a defect diagnosis. Results are meaningful only when panel labels identify comparable modules and temperature measurements are valid.
