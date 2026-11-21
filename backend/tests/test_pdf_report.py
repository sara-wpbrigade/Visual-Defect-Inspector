"""Tests for the PDF report builder."""

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from app.schemas import (
    Action,
    Assessment,
    DefectLocation,
    InspectionReport,
    ReportContent,
    ReportSource,
    Severity,
    Verdict,
    VoiceNoteResult,
    VoiceStatus,
)
from app.services.pdf_report import build_report_pdf
from app.services.repository import InspectionRecord
from app.services.storage import OVERLAY_KIND, PHOTO_KIND, ArtifactStore

INSPECTION_ID = "3c3399c60f4f4b728e606ecc0d1fa7b5"
CREATED_AT = datetime(2026, 11, 18, 14, 5, tzinfo=UTC)
MAX_PDF_BYTES = 400_000
HUGE_PHOTO_SIZE = 3000
LONG_TEXT = "The flagged area is large and needs attention. " * 5


def make_record(
    *,
    verdict: Verdict = Verdict.DEFECT,
    needs_review: bool = False,
    source: ReportSource = ReportSource.AI,
    summary: str = "A large defect was found in the lower centre.",
    findings: list[str] | None = None,
    recommendations: list[str] | None = None,
    notice: str | None = None,
    voice_note: VoiceNoteResult | None = None,
) -> InspectionRecord:
    """Build a record for the PDF tests; the defaults describe a high-severity defect."""
    is_defect = verdict is Verdict.DEFECT
    assessment = Assessment(
        verdict=verdict,
        confidence=0.937,
        needs_review=needs_review,
        severity=Severity.HIGH if is_defect else Severity.NONE,
        area_ratio=0.175 if is_defect else 0.0,
        action=Action.REJECT if is_defect else Action.ACCEPT,
        location=DefectLocation(region="lower center", bbox=(0.4, 0.6, 0.6, 0.85))
        if is_defect
        else None,
    )
    content = ReportContent(
        summary=summary,
        findings=findings or ["A defect was detected."],
        recommendations=recommendations or ["Reject the item and remove it from the batch."],
        defect_type="contamination" if is_defect else None,
        voice_note_conflict=None,
    )
    report = InspectionReport(
        report_id=INSPECTION_ID,
        generated_at=CREATED_AT,
        persona="factory_qc_operator",
        source=source,
        content=content,
        manual_review_notice=notice,
    )
    return InspectionRecord(
        id=INSPECTION_ID,
        created_at=CREATED_AT,
        persona="factory_qc_operator",
        batch_id="batch_1",
        category="metal_nut",
        score=0.937,
        assessment=assessment,
        report=report,
        voice_note=voice_note,
    )


@pytest.fixture
def store(tmp_path: Path) -> ArtifactStore:
    """Return a store holding a photo and an overlay for the test inspection."""
    artifact_store = ArtifactStore(tmp_path)
    photo = Image.new("RGB", (400, 300), color=(120, 130, 140))
    overlay = photo.copy()
    ImageDraw.Draw(overlay).rectangle((150, 150, 250, 250), outline=(255, 0, 0), width=4)
    artifact_store.save(photo, INSPECTION_ID, PHOTO_KIND)
    artifact_store.save(overlay, INSPECTION_ID, OVERLAY_KIND)
    return artifact_store


def read_pdf(data: bytes) -> PdfReader:
    """Parse PDF bytes."""
    return PdfReader(io.BytesIO(data))


def full_text(data: bytes) -> str:
    """Return the text of every page, joined."""
    return "\n".join(page.extract_text() for page in read_pdf(data).pages)


def test_result_is_a_valid_pdf(store: ArtifactStore) -> None:
    """The output starts with the PDF marker and has at least one page."""
    data = build_report_pdf(make_record(), store)
    assert data.startswith(b"%PDF")
    assert len(read_pdf(data).pages) >= 1


def test_defect_report_shows_the_facts(store: ArtifactStore) -> None:
    """The header, banner and facts grid carry the verified values."""
    text = full_text(build_report_pdf(make_record(), store, batch_decision="Rejected"))
    for expected in (
        INSPECTION_ID,
        "Factory QC Operator",
        "DEFECT",
        "93.7%",
        "17.5%",
        "0.937",
        "Reject",
        "contamination (AI estimate)",
        "Metal nut",
        "batch_1",
        "Rejected",
        "Lower Center",
    ):
        assert expected in text


def test_pass_report_says_pass_and_accept(store: ArtifactStore) -> None:
    """A passing item shows PASS, the accept action and no defect type."""
    text = full_text(build_report_pdf(make_record(verdict=Verdict.PASS), store))
    assert "PASS" in text
    assert "Accept" in text
    assert "Not applicable" in text


def test_review_report_flags_manual_review(store: ArtifactStore) -> None:
    """A low-confidence result shows the banner and the notice."""
    record = make_record(needs_review=True, notice="Needs manual review: too close to call.")
    text = full_text(build_report_pdf(record, store))
    assert "NEEDS MANUAL REVIEW" in text
    assert "too close to call" in text


def test_missing_batch_decision_is_marked_unavailable(store: ArtifactStore) -> None:
    """Without a batch decision the report says so instead of leaving a blank."""
    assert "Not available" in full_text(build_report_pdf(make_record(), store))


def test_template_report_says_no_ai_was_used(store: ArtifactStore) -> None:
    """The closing note and the source row describe a template report."""
    text = full_text(build_report_pdf(make_record(source=ReportSource.TEMPLATE), store))
    assert "Fixed template" in text
    assert "fixed template" in text


def test_markup_in_text_is_shown_literally(store: ArtifactStore) -> None:
    """Angle brackets and ampersands in model text are printed, not interpreted."""
    record = make_record(summary="<b>bold</b> & <script>alert(1)</script>")
    text = full_text(build_report_pdf(record, store))
    assert "<b>bold</b>" in text
    assert "& <script>" in text


def test_unprintable_characters_do_not_break_the_report(store: ArtifactStore) -> None:
    """Characters outside the built-in font are replaced, not fatal."""
    record = make_record(summary="Width \u2265 5 mm \u2713 \u691c\u67fb")
    assert build_report_pdf(record, store).startswith(b"%PDF")


def test_long_content_wraps_and_every_page_is_numbered(store: ArtifactStore) -> None:
    """Long text flows onto more pages and each page shows its number."""
    record = make_record(
        summary=LONG_TEXT[:400],
        findings=[LONG_TEXT[:240]] * 5,
        recommendations=[LONG_TEXT[:240]] * 4,
    )
    reader = read_pdf(build_report_pdf(record, store))
    total = len(reader.pages)
    assert total >= 2
    for number, page in enumerate(reader.pages, start=1):
        assert f"Page {number} of {total}" in page.extract_text()


def test_voice_note_transcript_is_included(store: ArtifactStore) -> None:
    """A transcribed operator note appears in the PDF."""
    note = VoiceNoteResult(
        status=VoiceStatus.TRANSCRIBED,
        text="spots appeared after the rain",
        language="en",
        duration_seconds=2.5,
    )
    text = full_text(build_report_pdf(make_record(voice_note=note), store))
    assert "Voice note transcript" in text
    assert "spots appeared after the rain" in text


def test_silent_voice_note_is_reported_as_no_speech(store: ArtifactStore) -> None:
    """A silent recording is named instead of leaving an empty section."""
    note = VoiceNoteResult(status=VoiceStatus.NO_SPEECH, text="", duration_seconds=1.0)
    text = full_text(build_report_pdf(make_record(voice_note=note), store))
    assert "No intelligible speech was detected" in text


def test_missing_images_show_a_notice_instead_of_breaking(tmp_path: Path) -> None:
    """If the stored images are gone the report still builds, with a notice."""
    text = full_text(build_report_pdf(make_record(), ArtifactStore(tmp_path)))
    assert text.count("Image not available") == 2


def test_both_photos_are_embedded(store: ArtifactStore) -> None:
    """The original and the annotated photo appear on the first page."""
    page = read_pdf(build_report_pdf(make_record(), store)).pages[0]
    assert len(page.images) == 2


def test_large_photos_are_shrunk_so_the_pdf_stays_small(tmp_path: Path) -> None:
    """A huge photo does not bloat the file."""
    artifact_store = ArtifactStore(tmp_path)
    photo = Image.effect_noise((HUGE_PHOTO_SIZE, HUGE_PHOTO_SIZE), 40).convert("RGB")
    artifact_store.save(photo, INSPECTION_ID, PHOTO_KIND)
    artifact_store.save(photo, INSPECTION_ID, OVERLAY_KIND)
    assert len(build_report_pdf(make_record(), artifact_store)) < MAX_PDF_BYTES
