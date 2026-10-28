# Synthetic Week 1-3 sample

These inputs are generated examples for testing the importer. They are **not drone imagery, site data, or radiometric measurements**. The four files under `inspection/thermal/` are display-only thermal-style PNGs. The importer must not turn their colors into temperatures.

Run `python examples/week01_03/generate_samples.py` to create the same ten readable images, one intentionally broken JPEG, and one SCADA-style CSV. The generated folder follows the inspection template:

```text
inspection/
  rgb/       six readable JPEGs and one broken JPEG
  thermal/   four readable display-only PNGs
  scada/     one synthetic CSV
```

Scan the folder with `solar-pv-import scan examples/week01_03/inspection --output examples/week01_03/output`. The output contains `inspection_manifest.json` and `file_inventory.csv`. The expected software result is 10 images opened, 1 image error, and 1 CSV opened.

Real inspection data belong in `data/raw/`, not here. Do not use this sample as evidence of field validation or hotspot accuracy.
