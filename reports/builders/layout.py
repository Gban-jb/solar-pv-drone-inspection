"""Black-and-white report layout for the Student 1 Solar PV project."""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer


pdfmetrics.registerFont(TTFont("AvenirNext", "/System/Library/Fonts/Avenir Next.ttc", subfontIndex=7))
pdfmetrics.registerFont(TTFont("AvenirNextDemi", "/System/Library/Fonts/Avenir Next.ttc", subfontIndex=2))
pdfmetrics.registerFont(TTFont("Georgia", "/System/Library/Fonts/Supplemental/Georgia.ttf"))
pdfmetrics.registerFont(TTFont("GeorgiaBold", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"))
pdfmetrics.registerFont(TTFont("GeorgiaItalic", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"))
pdfmetrics.registerFont(TTFont("GeorgiaBoldItalic", "/System/Library/Fonts/Supplemental/Georgia Bold Italic.ttf"))
pdfmetrics.registerFontFamily(
    "Georgia", normal="Georgia", bold="GeorgiaBold",
    italic="GeorgiaItalic", boldItalic="GeorgiaBoldItalic",
)


def make_styles():
    return {
        "title": ParagraphStyle(
            "title", fontName="AvenirNextDemi", fontSize=15.4, leading=19.5,
            textColor=colors.black, spaceAfter=9,
        ),
        "byline": ParagraphStyle(
            "byline", fontName="AvenirNext", fontSize=9.5, leading=13.6,
            textColor=colors.black, spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "section", fontName="AvenirNextDemi", fontSize=10.6, leading=14.5,
            textColor=colors.black, spaceBefore=13, spaceAfter=3,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "body", fontName="Georgia", fontSize=10.1, leading=15.1,
            textColor=colors.black, spaceAfter=8,
        ),
        "label": ParagraphStyle(
            "label", fontName="Georgia", fontSize=10.1, leading=15.1,
            leftIndent=16, firstLineIndent=-16, textColor=colors.black,
            spaceAfter=5,
        ),
        "reference": ParagraphStyle(
            "reference", fontName="Georgia", fontSize=9.1, leading=13.1,
            leftIndent=20, firstLineIndent=-20, textColor=colors.black,
            spaceAfter=4,
        ),
    }


STYLES = make_styles()


def title(text):
    return Paragraph(text, STYLES["title"])


def byline(text):
    return Paragraph(text, STYLES["byline"])


def section(number, text):
    heading = f"{number}. {text}" if number else text
    return KeepTogether([
        Paragraph(heading, STYLES["section"]),
        HRFlowable(width="100%", thickness=0.4, color=colors.black, spaceAfter=7),
    ])


def body(text):
    return Paragraph(text, STYLES["body"])


def label(name, text):
    return Paragraph(f"<b>{name}</b> {text}", STYLES["label"])


def reference(number, text):
    return Paragraph(f"[{number}] {text}", STYLES["reference"])


def spacer(points=9):
    return Spacer(1, points)


def divider():
    return HRFlowable(width="100%", thickness=0.8, color=colors.black,
                      spaceBefore=10, spaceAfter=8)


def _page_number(canvas, document):
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.4)
    canvas.line(72, 52, letter[0] - 72, 52)
    canvas.setFont("AvenirNext", 8.5)
    canvas.drawRightString(letter[0] - 72, 42, str(document.page))
    canvas.restoreState()


def build_report(path, document_title, author, story):
    doc = SimpleDocTemplate(
        str(path), pagesize=letter,
        leftMargin=72, rightMargin=72, topMargin=66, bottomMargin=64,
        title=document_title, author=author,
    )
    doc.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
