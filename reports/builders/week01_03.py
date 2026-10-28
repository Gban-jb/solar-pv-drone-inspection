"""Build Sudin Pokharel's revised Week 1-3 importer report."""

from pathlib import Path

from layout import body, build_report, byline, divider, label, reference, section, title


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/submissions/week01_03_image_importer.pdf"

story = [
    title("Week 1-3 Image Importer"),
    byline("Sudin Pokharel"),
    byline("Student 1, Solar PV Drone Monitoring Project | Dr. Raziq Yaqub | 22 October 2026"),
    divider(),

    section(1, "Milestone objective"),
    body(
        "The revised description asks for a Python script and folder template that load RGB images, thermal "
        "files, and a SCADA CSV. It must show metadata and missing fields, open ten images and one CSV, and "
        "report bad files without crashing [1]. Panel marking and hotspot analysis come later."
    ),

    section(2, "Prototype delivered"),
    body(
        "I built an installable importer with two commands. Init creates rgb, thermal, and scada folders. "
        "Scan reads files one at a time and writes a JSON manifest and CSV inventory. A local viewer shows "
        "previews, file status, metadata, and the SCADA summary."
    ),
    label(
        "Image records.",
        "Each readable image has a type, dimensions, size, checksum, and available capture time, camera "
        "details, and GPS. Missing metadata becomes a warning. A damaged image receives an error entry "
        "without stopping the scan."
    ),
    label(
        "SCADA records.",
        "The importer reports CSV columns, row count, empty cells, and a preview. It rejects rows with the "
        "wrong number of values. Plant-specific field meanings and units are not assumed."
    ),

    section(3, "Demonstration result"),
    body(
        "I used six synthetic RGB JPEGs, four display-only thermal-style PNGs, one deliberately broken JPEG, "
        "and one synthetic inverter CSV. The scan opened all ten readable images, reported the bad file, "
        "and read 12 CSV rows. The viewer showed the images and missing metadata. Four automated tests "
        "passed, including malformed-file handling and output creation."
    ),
    body(
        "Sample inputs, outputs, and setup steps are included with the code. I tested locally with Python "
        "3.12, but have not yet verified the setup on a second physical computer."
    ),

    section(4, "Limits and next step"),
    body(
        "These files are not from the solar site. The thermal-style PNGs contain no measured temperatures, "
        "so I make no hotspot claim. I still need original thermal files, the camera model and export "
        "format, a real SCADA sample with field definitions, and the agreed panel or row IDs. The brief "
        "says SCADA access is available, but no site file has been verified here [1]."
    ),
    body(
        "Next I will test representative team-supplied files, confirm their metadata, then build the "
        "Week 4-6 panel marking tool on these inspection records."
    ),

    section("", "Reference"),
    reference(1, "R. Yaqub, <i>Solar PV Drone Monitoring Project: Project Job Description for Students 1-4, version 3</i>, 2026."),
]

OUT.parent.mkdir(parents=True, exist_ok=True)
build_report(OUT, "Week 1-3 Image Importer", "Sudin Pokharel", story)
print(OUT)
