# Synthetic panel and row marking examples

`inspection/rgb/` contains three generated practice images: a 20-panel array, a three-row array, and a six-panel close-up. `output/panel_annotations.csv` contains 22 boxes drawn and saved in the browser: 20 panel labels on the first image, one row label, and one close-up panel label. The first panel box has been marked confirmed after review. All 22 labels have unique annotation IDs. On November 5, the example CSV was reloaded in the browser after a full page refresh: the first image showed 20 saved boxes, the CSV showed 22 total labels, and `SYN-01` remained confirmed. These are synthetic examples, not drone imagery or real plant IDs.

Check the saved labels and their exact CSV round trip with:

```sh
.venv/bin/python examples/week04_06/verify_labels.py
```

The check verifies unique annotation IDs, image dimensions, and that every saved field, including box coordinates, survives save and reload. It writes `examples/week04_06/output/roundtrip_evidence.json`. Run the command from the project root after installing the project as described in the main `README.md`.

Regenerate the images with:

```sh
python examples/week04_06/generate_samples.py
```

The generator recreates the images, not the saved labels. For field-relevant validation, use representative RGB images when they are available and approved for use.

## Two-minute demo

1. Start the annotation page using the command in the project `README.md`. Open **Files and output**, and set **Label CSV** to the absolute path of `examples/week04_06/output/panel_annotations.csv` to inspect the saved example. Use the default `data/processed/panel_annotations.csv` for new practice work so the example stays unchanged.
2. On `synthetic_panel_array.png`, show the 20 saved panel boxes. Select `SYN-01`, choose **Edit selected**, and point out its confirmed box review. Confirmed means a person reviewed the box, not that a real plant ID was verified.
3. Select `synthetic_panel_array_rows.png` to show `SYN-ROW-A` as a row box. Select `synthetic_panel_array_closeup.png` to show a panel box on another image.
4. For a live edit, use the separate practice file `data/processed/week04_06_demo_annotations.csv`. On another computer, or to reset it, copy the saved example into that path with `cp examples/week04_06/output/panel_annotations.csv data/processed/week04_06_demo_annotations.csv` (use `copy` on Windows). Select the practice path under **Files and output**. Select a label, choose **Edit selected**, change its type, ID, or review state, and click **Save changes**. To replace its boundary, draw one rectangle, click the canvas update button, then save. The annotation ID stays the same. A duplicate plant ID on the same image or a box smaller than 8 canvas pixels is rejected.
5. Reload the page, set the practice CSV again under **Files and output**, and show that the saved boxes remain. A full page reload resets that input field to its default path.

## Setup check on another computer

Transfer the current project source, including `examples/week04_06/`, to the other computer. The private GitHub repository does not yet contain all local prototype changes, so cloning it alone is not currently enough. From the project root, create a Python 3.12 environment and install `.[ui,dev]` using the commands in the main `README.md`. Then run the verification command above and `.venv/bin/python -m pytest -q` (use `.venv\Scripts\python` on Windows). Start the app, open **Panel annotations**, and repeat steps 1-5. Record the computer, Python version, install result, test result, and whether the browser reload showed the saved edit. A clean virtual environment on the original Mac passed these checks on November 5; a second physical computer has not yet been tested.
