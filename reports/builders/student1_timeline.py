"""Build Sudin Pokharel's Student 1 milestone timeline and input requests."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, Table, TableStyle

from layout import (
    STYLES,
    body,
    build_report,
    byline,
    divider,
    section,
    title,
)


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/submissions/student1_milestone_timeline.pdf"

cell_style = ParagraphStyle(
    "timeline_cell", parent=STYLES["body"], fontSize=9.1, leading=12.2,
    spaceAfter=0, alignment=TA_LEFT,
)
date_style = ParagraphStyle(
    "timeline_date", parent=cell_style, fontSize=8.5, leading=11.2,
)
week_style = ParagraphStyle(
    "timeline_week", parent=cell_style, fontName="AvenirNextDemi", fontSize=9.2,
)
head_style = ParagraphStyle(
    "timeline_head", parent=cell_style, fontName="AvenirNextDemi", fontSize=9.0,
)


def milestone_table(rows):
    data = [[
        Paragraph("Weeks / dates", head_style),
        Paragraph("Milestone", head_style),
        Paragraph("Work and completion check", head_style),
    ]]
    for weeks, dates, name, plan in rows:
        data.append([
            Paragraph(f"<b>{weeks}</b><br/>{dates}", date_style),
            Paragraph(name, cell_style),
            Paragraph(plan, cell_style),
        ])
    table = Table(data, colWidths=[82, 112, 262], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.65, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


before_components = [
    ("Weeks 1-3", "Oct 19-Nov 8<br/>2026", "Image importer", "The prototype passes a synthetic-data check. Keep improving the preview, metadata and missing-field display, and per-file error handling. Recheck with ten project images and one real SCADA CSV when supplied."),
    ("Weeks 4-6", "Nov 9-29<br/>2026", "Panel and row marking", "Build image review, box drawing, persistent IDs, and CSV save/reload. Test the interface with available images and agree on IDs and observation fields with Student 2. Obtain representative panel images for the 20-example acceptance check."),
]

after_components = [
    ("Weeks 7-9", "Nov 30-Dec 20<br/>2026", "Thermal hotspot viewer", "With the camera or representative radiometric files, identify the format and supported decoder. Compare nearby modules, show annotated temperature differences for three cases, and flag non-radiometric images. If equipment is later, keep simulated results clearly labeled and request a revised hardware-dependent check date."),
    ("Weeks 10-12", "Dec 21-Jan 10<br/>2026-27", "Fall prototype and handover", "Combine import, IDs, and thermal overlays; export an observation CSV. Use Week 11 for a clean install and unseen-image check. Use Week 12 for the prepared-dataset demo, five-minute recording, source, setup steps, and known limitations."),
]

spring = [
    ("Weeks 13-15", "Jan 11-31<br/>2027", "Visible RGB labels", "Add manual labels or a simple baseline for shade, dirt, and obvious obstruction. Clearly distinguish manual from automatic marks and show original and annotated images."),
    ("Weeks 16-18", "Feb 1-21<br/>2027", "SCADA context graph", "Plot inverter output against time and irradiance or a comparable baseline around an inspection. Show the timestamp link and explain that inverter-level data cannot prove an individual panel's power loss."),
    ("Weeks 19-22", "Feb 22-Mar 21<br/>2027", "Inspection map and ranked list", "Build the Streamlit layout, transparent severity rules, and CSV/JSON fields with Student 2. A reviewer should click a finding to see its image, temperature difference when valid, and data source."),
    ("Weeks 23-25", "Mar 22-Apr 11<br/>2027", "Integrated test and release", "Prepare a ten-case test set, clean repository, and setup guide. Verify installation on a second computer, then run the ten-minute supervisor-selected end-to-end demo: import, review, and export map and records."),
]

story = [
    title("Fall Milestone Timeline"),
    byline("Sudin Pokharel"),
    byline("Drone RGB/Thermal Fault Mapping | Dr. Raziq Yaqub | 23 October 2026"),
    divider(),
    section(1, "Schedule basis"),
    body(
        "The week blocks are consecutive Monday-to-Sunday periods, counted from the October 19 date in "
        "the Week 1 row. They follow the project description's milestone ranges. This places Fall Weeks "
        "10-12 after the description's listed December 15 Fall end, so treat that handover date as provisional."
    ),
    body(
        "<b>The Week 1-3 importer prototype has passed a local check with synthetic inputs only; project "
        "camera and SCADA files still need to be tested.</b>"
    ),
    section(2, "Fall milestones before the drone and camera are available"),
    milestone_table(before_components),
    section(3, "Fall milestones after the imaging components arrive"),
    milestone_table(after_components),
    PageBreak(),
    title("Spring Milestone Timeline"),
    byline("Sudin Pokharel"),
    byline("Drone RGB/Thermal Fault Mapping | Dr. Raziq Yaqub | 23 October 2026"),
    divider(),
    section(4, "Spring milestones"),
    milestone_table(spring),
    section(5, "Overall Student 1 outcome"),
    body(
        "The final deliverable is a runnable Python application for reviewing drone RGB and radiometric "
        "thermal images, viewing candidate hotspots and visible anomalies, recording panel or row "
        "observations, and exporting an evidence-based map or list as CSV and JSON. It will identify "
        "candidates for inspection, not claim a confirmed fault cause."
    ),
    section(6, "Deadline buffer and component request"),
    body(
        "The mapped Week 25 ends April 11. The project description lists May 15, 2027 as the Spring end; "
        "April 12-May 15 is reserved for fixes, final integration, and the supervisor-selected live demo."
    ),
    body(
        "Please let me know when the required drone and imaging components will be available. "
        "Once they are ready, I can confirm the camera/export workflow and test with images from the "
        "actual setup."
    ),
]

OUT.parent.mkdir(parents=True, exist_ok=True)
build_report(OUT, "Student 1 Milestone Timeline", "Sudin Pokharel", story)
print(OUT)
