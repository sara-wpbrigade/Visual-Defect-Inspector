"""Rendering of a stored inspection as a PDF report."""

import io
import logging
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import Image as PdfImage

from app.schemas import Action, Assessment, ReportSource, Verdict, VoiceStatus
from app.services.repository import InspectionRecord
from app.services.storage import OVERLAY_KIND, PHOTO_KIND, ArtifactStore

logger = logging.getLogger(__name__)

PAGE_MARGIN = 1.8 * cm
FOOTER_SPACE = 0.8 * cm
FOOTER_FONT_SIZE = 8
CONTENT_WIDTH = A4[0] - 2 * PAGE_MARGIN
HEADER_SPLIT = 0.45
FACT_COLUMNS = (3.2 * cm, 5.5 * cm, 3.6 * cm, 5.0 * cm)
IMAGE_BOX = 5.4 * cm
IMAGE_MAX_PIXELS = 900
JPEG_QUALITY = 85
CELL_PADDING = 8
SPACER_SMALL = 4
SPACER_MEDIUM = 10

INK = colors.HexColor("#1D2733")
MUTED = colors.HexColor("#5B6770")
BRAND = colors.HexColor("#1F3A5F")
RULE = colors.HexColor("#D5DAE0")
PANEL = colors.HexColor("#F3F5F8")
PASS_COLOR = colors.HexColor("#1B7F4B")
DEFECT_COLOR = colors.HexColor("#B3261E")
REVIEW_COLOR = colors.HexColor("#B26A00")

AUTHOR = "Visual Defect Inspector"
TEXT_ENCODING = "cp1252"
TIME_FORMAT = "%Y-%m-%d %H:%M UTC"
NOT_DETERMINED = "Not determined"
NOT_APPLICABLE = "Not applicable"
NOT_AVAILABLE = "Not available"
IMAGE_MISSING_TEXT = "Image not available"
ACRONYMS = {"Qc": "QC"}
ACTION_LABELS = {Action.RE_INSPECT: "Re-inspect"}
FACTS_NOTE = (
    "Verdict, confidence, severity, flagged area, location and the recommended action are "
    "computed by the inspection system. They are not written by the AI."
)
AI_NOTE = (
    "The summary, findings and recommendations were written by an AI model from the facts above "
    "and checked by the system. The defect type is an AI estimate from the photo."
)
TEMPLATE_NOTE = (
    "The summary, findings and recommendations come from a fixed template because no AI "
    "model was used for this report."
)


BOLD = "Helvetica-Bold"
STYLE_SPECS: dict[str, dict[str, Any]] = {
    "title": {"fontName": BOLD, "fontSize": 20, "leading": 24, "textColor": colors.white},
    "meta": {"fontSize": 8.5, "leading": 11.5, "textColor": colors.white},
    "heading": {
        "fontName": BOLD,
        "fontSize": 12,
        "leading": 15,
        "textColor": BRAND,
        "spaceBefore": 14,
        "spaceAfter": 5,
    },
    "body": {"fontSize": 10, "leading": 14},
    "bullet": {"fontSize": 10, "leading": 14, "leftIndent": 12, "bulletIndent": 0},
    "label": {"fontName": BOLD, "fontSize": 8.5, "leading": 11, "textColor": MUTED},
    "value": {"fontSize": 10, "leading": 13},
    "caption": {"fontSize": 8.5, "leading": 11, "textColor": MUTED, "alignment": TA_CENTER},
    "banner": {
        "fontName": BOLD,
        "fontSize": 18,
        "leading": 22,
        "textColor": colors.white,
        "alignment": TA_CENTER,
    },
    "banner_note": {
        "fontSize": 10,
        "leading": 13,
        "textColor": colors.white,
        "alignment": TA_CENTER,
    },
    "note": {"fontSize": 8, "leading": 10.5, "textColor": MUTED},
    "alert": {"fontName": BOLD, "fontSize": 10, "leading": 13, "textColor": REVIEW_COLOR},
}


def _build_styles() -> dict[str, ParagraphStyle]:
    """Create the paragraph styles used by the report from the style table."""
    base = getSampleStyleSheet()["Normal"]
    return {
        name: ParagraphStyle(name, parent=base, **{"textColor": INK, **options})
        for name, options in STYLE_SPECS.items()
    }


STYLES = _build_styles()


def build_report_pdf(
    record: InspectionRecord, store: ArtifactStore, batch_decision: str | None = None
) -> bytes:
    """Render one stored inspection as a PDF and return its bytes.

    `batch_decision` is the readable decision for the batch this item represents.
    The document is laid out twice: the first pass only counts the pages, so the
    second pass can print "Page i of n" in every footer.
    """
    _, page_count = _render(record, store, batch_decision, total_pages=0)
    data, _ = _render(record, store, batch_decision, total_pages=page_count)
    return data


def _render(
    record: InspectionRecord,
    store: ArtifactStore,
    batch_decision: str | None,
    total_pages: int,
) -> tuple[bytes, int]:
    """Lay the report out once and return the PDF bytes with the number of pages."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=PAGE_MARGIN + FOOTER_SPACE,
        title=f"Inspection report {record.report.report_id}",
        author=AUTHOR,
        subject="Visual inspection report",
    )
    footer = partial(_draw_footer, reference=record.report.report_id, total_pages=total_pages)
    document.build(_story(record, store, batch_decision), onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue(), document.page


def _draw_footer(
    canvas: Canvas, document: SimpleDocTemplate, reference: str, total_pages: int
) -> None:
    """Draw the footer rule, the report reference and the page number."""
    y = PAGE_MARGIN - 0.2 * cm
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.line(PAGE_MARGIN, y + 0.4 * cm, A4[0] - PAGE_MARGIN, y + 0.4 * cm)
    canvas.setFont("Helvetica", FOOTER_FONT_SIZE)
    canvas.setFillColor(MUTED)
    canvas.drawString(PAGE_MARGIN, y, f"Inspection report {reference}")
    canvas.drawRightString(A4[0] - PAGE_MARGIN, y, f"Page {document.page} of {total_pages}")
    canvas.restoreState()


def _story(
    record: InspectionRecord, store: ArtifactStore, batch_decision: str | None
) -> list[Flowable]:
    """Assemble every section of the report in reading order."""
    content = record.report.content
    story: list[Flowable] = [
        _header(record),
        Spacer(1, SPACER_MEDIUM),
        _banner(record),
        Spacer(1, SPACER_MEDIUM),
        _facts_table(record, batch_decision),
        Spacer(1, SPACER_MEDIUM),
        _images_table(record, store),
    ]
    if record.report.manual_review_notice:
        story += [Spacer(1, SPACER_MEDIUM), _review_box(record.report.manual_review_notice)]
    story += _voice_note_section(record)
    story += _text_section("Summary", [content.summary], bullets=False)
    story += _text_section("Findings", content.findings, bullets=True)
    story += _text_section("Recommended actions", content.recommendations, bullets=True)
    if content.voice_note_conflict:
        story += _text_section("Voice note conflict", [content.voice_note_conflict], bullets=False)
    return story + _closing_notes(record)


def _para(text: str, style: str) -> Paragraph:
    """Build a paragraph from plain text, made safe for the built-in font and markup."""
    return Paragraph(_safe(text), STYLES[style])


def _safe(text: str) -> str:
    """Replace characters the built-in font cannot print, then escape markup characters."""
    printable = text.encode(TEXT_ENCODING, errors="replace").decode(TEXT_ENCODING)
    return escape(printable)


def _header(record: InspectionRecord) -> Table:
    """Build the title band with the report id, dates and user type."""
    report = record.report
    left = [_para("Inspection Report", "title"), _para(AUTHOR, "meta")]
    right = [
        _para(f"Report ID: {report.report_id}", "meta"),
        _para(f"Generated: {_format_time(report.generated_at)}", "meta"),
        _para(f"Inspected: {_format_time(record.created_at)}", "meta"),
        _para(f"User type: {_persona_label(record.persona)}", "meta"),
    ]
    table = Table(
        [[left, right]],
        colWidths=[CONTENT_WIDTH * HEADER_SPLIT, CONTENT_WIDTH * (1 - HEADER_SPLIT)],
    )
    table.setStyle(_padded_style(BRAND))
    return table


def _banner(record: InspectionRecord) -> Table:
    """Build the coloured verdict banner."""
    headline, note, color = _banner_parts(record)
    table = Table(
        [[[_para(headline, "banner"), _para(note, "banner_note")]]], colWidths=[CONTENT_WIDTH]
    )
    table.setStyle(_padded_style(color))
    return table


def _banner_parts(record: InspectionRecord) -> tuple[str, str, colors.Color]:
    """Return the banner headline, its second line and its colour."""
    assessment = record.assessment
    action = _action_label(assessment)
    if assessment.needs_review:
        verdict = assessment.verdict.value.upper()
        note = f"Automatic result: {verdict} ({_percent(assessment.confidence)}). Next: {action}"
        return "NEEDS MANUAL REVIEW", note, REVIEW_COLOR
    note = f"Confidence {_percent(assessment.confidence)}. Recommended action: {action}"
    if assessment.verdict is Verdict.PASS:
        return "PASS", note, PASS_COLOR
    return "DEFECT", note, DEFECT_COLOR


FACTS_TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, RULE),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
)


def _facts_table(record: InspectionRecord, batch_decision: str | None) -> Table:
    """Build the grid of verified facts."""
    cells = [
        [_para(a, "label"), _para(b, "value"), _para(c, "label"), _para(d, "value")]
        for a, b, c, d in _fact_rows(record, batch_decision)
    ]
    table = Table(cells, colWidths=list(FACT_COLUMNS))
    table.setStyle(FACTS_TABLE_STYLE)
    return table


def _fact_rows(
    record: InspectionRecord, batch_decision: str | None
) -> list[tuple[str, str, str, str]]:
    """Return the facts as rows of label, value, label, value."""
    assessment = record.assessment
    location = assessment.location.region.title() if assessment.location else NOT_APPLICABLE
    return [
        (
            "Verdict",
            assessment.verdict.value.title(),
            "Confidence",
            _percent(assessment.confidence),
        ),
        (
            "Severity",
            assessment.severity.value.title(),
            "Flagged area",
            _percent(assessment.area_ratio),
        ),
        ("Defect type", _defect_type_text(record), "Location", location),
        ("Anomaly score", f"{record.score:.3f}", "Recommended action", _action_label(assessment)),
        ("Category", _category_label(record.category), "Batch", record.batch_id or "None"),
        (
            "Batch decision",
            batch_decision or NOT_AVAILABLE,
            "Text written by",
            _source_label(record),
        ),
    ]


def _images_table(record: InspectionRecord, store: ArtifactStore) -> Table:
    """Place the original and the annotated photo side by side."""
    cells = [
        [
            _image_cell(store, record.id, PHOTO_KIND, "Original photo"),
            _image_cell(store, record.id, OVERLAY_KIND, "Annotated photo (flagged area in red)"),
        ]
    ]
    table = Table(cells, colWidths=[CONTENT_WIDTH / 2, CONTENT_WIDTH / 2])
    table.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER")])
    )
    return table


def _image_cell(
    store: ArtifactStore, inspection_id: str, kind: str, caption: str
) -> list[Flowable]:
    """Return one image with its caption, or a short notice if it cannot be read."""
    flowable = _load_image(store.path_for(inspection_id, kind))
    return [flowable, Spacer(1, SPACER_SMALL), _para(caption, "caption")]


def _load_image(path: Path) -> Flowable:
    """Read, shrink and re-encode an image so the PDF stays small."""
    try:
        with Image.open(path) as source:
            source.thumbnail((IMAGE_MAX_PIXELS, IMAGE_MAX_PIXELS))
            rgb = source.convert("RGB")
    except (OSError, ValueError):
        logger.warning("Report image is missing or unreadable: %s", path.name)
        return _para(IMAGE_MISSING_TEXT, "note")
    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    buffer.seek(0)
    scale = min(IMAGE_BOX / rgb.width, IMAGE_BOX / rgb.height)
    return PdfImage(buffer, width=rgb.width * scale, height=rgb.height * scale)


def _review_box(notice: str) -> Table:
    """Build the amber box that flags a result needing manual review."""
    table = Table([[_para(notice, "alert")]], colWidths=[CONTENT_WIDTH])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1.2, REVIEW_COLOR),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF6E5")),
                ("LEFTPADDING", (0, 0), (-1, -1), CELL_PADDING),
                ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PADDING),
                ("TOPPADDING", (0, 0), (-1, -1), CELL_PADDING),
                ("BOTTOMPADDING", (0, 0), (-1, -1), CELL_PADDING),
            ]
        )
    )
    return table


def _voice_note_section(record: InspectionRecord) -> list[Flowable]:
    """Show the operator's transcript, or say that no speech was detected."""
    note = record.voice_note
    if note is None:
        return []
    if note.status is VoiceStatus.NO_SPEECH or not note.text:
        return _text_section(
            "Voice note", ["No intelligible speech was detected in the recording."], bullets=False
        )
    return _text_section("Voice note transcript", [note.text], bullets=False)


def _text_section(title: str, items: list[str], *, bullets: bool) -> list[Flowable]:
    """Build a heading followed by plain paragraphs or bullet points."""
    heading = _para(title, "heading")
    if not bullets:
        plain: list[Flowable] = [heading]
        plain.extend(_para(item, "body") for item in items)
        return plain
    points: list[Flowable] = [
        Paragraph(_safe(item), STYLES["bullet"], bulletText="\u2022") for item in items
    ]
    return [KeepTogether([heading, points[0]]), *points[1:]]


def _closing_notes(record: InspectionRecord) -> list[Flowable]:
    """Explain which parts are computed and which were written by AI."""
    source_note = AI_NOTE if record.report.source is ReportSource.AI else TEMPLATE_NOTE
    return [Spacer(1, SPACER_MEDIUM), _para(f"{FACTS_NOTE} {source_note}", "note")]


def _padded_style(background: colors.Color) -> TableStyle:
    """Return the style of a full-width coloured band."""
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), background),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), CELL_PADDING + 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PADDING + 4),
            ("TOPPADDING", (0, 0), (-1, -1), CELL_PADDING + 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), CELL_PADDING + 2),
        ]
    )


def _category_label(category: str) -> str:
    """Turn a category id such as metal_nut into readable text."""
    return category.replace("_", " ").capitalize()


def _percent(value: float) -> str:
    """Format a 0 to 1 ratio as a percentage with one decimal."""
    return f"{value * 100:.1f}%"


def _format_time(moment: datetime) -> str:
    """Format a timestamp for the header."""
    return moment.strftime(TIME_FORMAT)


def _persona_label(persona: str) -> str:
    """Turn a persona id such as factory_qc_operator into readable text."""
    label = persona.replace("_", " ").title()
    for wrong, right in ACRONYMS.items():
        label = label.replace(wrong, right)
    return label


def _action_label(assessment: Assessment) -> str:
    """Return the recommended action as readable text."""
    return ACTION_LABELS.get(assessment.action, assessment.action.value.title())


def _defect_type_text(record: InspectionRecord) -> str:
    """Describe the defect type, labelling it as an AI estimate when present."""
    if record.assessment.verdict is Verdict.PASS:
        return NOT_APPLICABLE
    defect_type = record.report.content.defect_type
    return f"{defect_type} (AI estimate)" if defect_type else NOT_DETERMINED


def _source_label(record: InspectionRecord) -> str:
    """Say whether an AI model or the fixed template wrote the text."""
    return "AI model" if record.report.source is ReportSource.AI else "Fixed template"
