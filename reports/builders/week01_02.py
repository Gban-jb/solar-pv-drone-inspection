"""Build Sudin Pokharel's Week 1-2 report with the project report style."""

from pathlib import Path

from layout import body, build_report, byline, divider, label, reference, section, title


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/submissions/week01_02_initial_review.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

story = [
    title("Solar PV Fault Detection: Initial Review and Requirements"),
    byline("Sudin Pokharel"),
    byline("Student 1 project, Dr. Raziq Yaqub, 8 October 2026"),
    divider(),

    section(1, "Project scope"),
    body(
        "The project brief asks for a software module that uses drone photographs, thermal images, "
        "location, weather, and plant electrical readings to find and describe problems in a solar PV site [1]. "
        "The main task is to connect an image finding to the right panel and to the electrical data that may "
        "support it. The result should identify a possible fault, show the evidence, and give a confidence and "
        "severity score. Students 2 and 3 will use these findings for longer-term tracking and maintenance decisions."
    ),
    body(
        "At this stage I am defining what the tool should receive and report. I have not collected site data "
        "or tested a model yet."
    ),

    section(2, "Initial technical review"),
    body(
        "Thermal imaging can reveal areas that are unusually warm while panels are operating. It is already "
        "used for PV inspections, so finding a hot area alone would not answer this project's main question. "
        "Shade, dirt, reflections, and weather can affect an image, and similar heat patterns may have different "
        "causes. A thermal finding should be treated as evidence for inspection, not as a confirmed diagnosis [2]."
    ),
    body(
        "Work such as PV-Hawk shows how individual panels can be found and mapped from drone images [3]. "
        "Plant monitoring provides a second kind of evidence: a connected group may be producing less than "
        "expected under the measured weather conditions [4]. The detail of that evidence depends on the sensors. "
        "If the plant reports only inverter-level power, that reading cannot by itself prove which panel caused a loss."
    ),

    section(3, "Working fault categories"),
    body("I will begin with a small list of observable patterns and revise it after seeing real examples:"),
    label("Localized hot area.", "A small part of a panel is warmer than its surroundings. It may be related to shade or a cell or connection problem."),
    label("Warm module.", "One whole panel is warmer than similar nearby panels. The cause may be electrical or may relate to operating conditions."),
    label("Visible condition.", "Dirt, shading, an obstruction, broken glass, or other damage appears in a regular photograph."),
    label("Low electrical output.", "A string or inverter group produces less than expected after accounting for weather and operating status."),
    body("These labels describe observations. A cause will remain unknown when the evidence is not strong enough."),

    section(4, "Input and output requirements"),
    body(
        "The input should include original RGB and temperature-capable thermal images; capture time and GPS; "
        "a site map with stable panel IDs; sunlight and weather readings; inverter power and DC current/voltage; "
        "string readings if available; and alarm or maintenance records [1]. A wiring map is needed to connect "
        "a panel seen by the drone to the electrical equipment measured by the plant."
    ),
    body(
        "For each finding, the output should give the panel ID and location, visible and thermal observations, "
        "temperature difference when it can be measured, the related electrical deviation, a likely fault class, "
        "confidence, severity, and the source images and readings. Missing fields should be marked as missing. "
        "Electrical evidence should state whether it comes from a panel, string, or inverter group."
    ),

    section(5, "Next steps"),
    body(
        "I will first request a small sample of original images, plant readings, the site layout, and any known "
        "fault records. I will check which files contain actual temperature data, whether timestamps line up, "
        "and what level of electrical detail is available. Next I will make a simple record linking panels to "
        "locations and electrical groups. That will give me a sound starting point for the image and power "
        "analysis planned in later weeks."
    ),

    section("", "References"),
    reference(1, "R. Yaqub, <i>Student 1 Project Description</i>, Solar Project job description, 2026."),
    reference(2, "IEA PVPS Task 13, <link href='https://iea-pvps.org/key-topics/review-on-ir-and-el-imaging-for-pv-field-applications/' color='black'><u>Review on IR and EL Imaging for PV Field Applications</u></link>."),
    reference(3, "L. Bommes, <link href='https://github.com/lukasbommes/pv-hawk' color='black'><u>PV-Hawk repository and related publications</u></link>."),
    reference(4, "IEA PVPS Task 13, <link href='https://iea-pvps.org/key-topics/the-use-of-advanced-algorithms-in-pv-failure-monitoring/' color='black'><u>The Use of Advanced Algorithms in PV Failure Monitoring</u></link>."),
]

build_report(OUT, "Solar PV Fault Detection: Initial Review and Requirements", "Sudin Pokharel", story)
print(OUT)
