"""Generate the sample PDF reports committed under samples/reports/."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from app.core.categories import load_category_config
from app.core.persona import load_persona
from app.models.patchcore import PatchCoreDetector
from app.schemas import (
    InspectionReport,
    ReportContent,
    ReportSource,
    VoiceNoteResult,
    VoiceStatus,
)
from app.services.overlay import render_overlay
from app.services.pdf_report import build_report_pdf
from app.services.repository import InspectionRecord
from app.services.rules import assess
from app.services.storage import OVERLAY_KIND, PHOTO_KIND, ArtifactStore

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
SAMPLES_DIR = PROJECT_ROOT / "samples"
REPORTS_DIR = SAMPLES_DIR / "reports"
CHECKPOINT = (
    BACKEND_ROOT
    / "results"
    / "Patchcore"
    / "MVTecAD"
    / "bottle"
    / "v1"
    / "weights"
    / "lightning"
    / "model.ckpt"
)
GENERATED_AT = datetime(2026, 11, 21, 9, 15, tzinfo=UTC)
CATEGORY = "bottle"


def make_report(
    report_id: str,
    summary: str,
    findings: list[str],
    recommendations: list[str],
    defect_type: str | None,
    *,
    source: ReportSource = ReportSource.AI,
    manual_review_notice: str | None = None,
) -> InspectionReport:
    """Build one report block with the given wording."""
    return InspectionReport(
        report_id=report_id,
        generated_at=GENERATED_AT,
        persona="factory_qc_operator",
        source=source,
        content=ReportContent(
            summary=summary,
            findings=findings,
            recommendations=recommendations,
            defect_type=defect_type,
            voice_note_conflict=None,
        ),
        manual_review_notice=manual_review_notice,
    )


def build_case(
    name: str,
    image_name: str,
    inspection_id: str,
    batch_id: str,
    score_override: float | None,
    report: InspectionReport,
    batch_decision: str,
    voice_note: VoiceNoteResult | None = None,
) -> None:
    """Run the real detector on one sample image and write its PDF report."""
    persona = load_persona("factory_qc_operator").for_category(load_category_config(CATEGORY))
    photo = Image.open(SAMPLES_DIR / "images" / image_name).convert("RGB")
    detector = PatchCoreDetector(CHECKPOINT, "auto")
    detection = detector.detect(photo)
    score = detection.score if score_override is None else score_override
    assessment = assess(score, detection.mask, persona)
    with TemporaryDirectory() as temp_dir:
        store = ArtifactStore(Path(temp_dir))
        store.save(photo, inspection_id, PHOTO_KIND)
        store.save(
            render_overlay(photo, detection.mask, assessment.location),
            inspection_id,
            OVERLAY_KIND,
        )
        record = InspectionRecord(
            id=inspection_id,
            created_at=GENERATED_AT,
            persona="factory_qc_operator",
            batch_id=batch_id,
            category=CATEGORY,
            score=score,
            assessment=assessment,
            report=report,
            voice_note=voice_note,
        )
        (REPORTS_DIR / name).write_bytes(build_report_pdf(record, store, batch_decision))
    print(f"wrote {name}")


def main() -> None:
    """Build every committed sample report."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    pass_id = "a1" * 16
    build_case(
        "01_pass.pdf",
        "bottle_good_000.png",
        pass_id,
        "batch-demo-pass",
        None,
        make_report(
            pass_id,
            "The bottle passed inspection with 78.2% confidence; no defect was found.",
            [
                "The anomaly score is 0.218 and no region was flagged as defective.",
                "The item is suitable for the next stage of production.",
            ],
            ["Accept the item; no action is needed."],
            None,
        ),
        "Passed",
    )

    voice_id = "b2" * 16
    build_case(
        "02_defect_high_with_voice_note.pdf",
        "bottle_broken_large_000.png",
        voice_id,
        "batch-demo-voice",
        None,
        make_report(
            voice_id,
            "A high severity defect was found in the lower center of the bottle, "
            "covering 17.5% of the item.",
            [
                "The flagged area covers 17.5% of the item.",
                "The anomaly score is 0.937 and the confidence is 93.7%.",
                "The operator's note describes a chipped base near the lower center.",
            ],
            ["Reject the item and remove it from the batch."],
            "broken part",
        ),
        "Rejected",
        VoiceNoteResult(
            status=VoiceStatus.TRANSCRIBED,
            text="The base of this bottle is chipped near the lower centre.",
            language="en",
            duration_seconds=3.0,
            truncated=False,
        ),
    )

    review_id = "c3" * 16
    build_case(
        "03_needs_review_low_confidence.pdf",
        "bottle_broken_small_000.png",
        review_id,
        "batch-demo-review",
        0.55,
        make_report(
            review_id,
            "A small defect was found, but the result is close to the decision cutoff.",
            [
                "The flagged area covers 0.9% of the item.",
                "The anomaly score is 0.550 and the confidence is 55.0%.",
            ],
            ["Re-inspect the item manually; the automatic result is too close to call."],
            None,
            manual_review_notice=(
                "This result is uncertain and needs manual review before a final decision."
            ),
        ),
        "Needs review",
    )

    contamination_id = "d4" * 16
    build_case(
        "04_defect_medium_contamination.pdf",
        "bottle_contamination_000.png",
        contamination_id,
        "batch-demo-contamination",
        None,
        make_report(
            contamination_id,
            "A medium severity contamination defect covers 10.2% of the lower left of the bottle.",
            [
                "The flagged area covers 10.2% of the item.",
                "The anomaly score is 0.794 and the confidence is 79.4%.",
            ],
            ["Send the item to rework and re-inspect it after cleaning."],
            "contamination",
        ),
        "Rejected",
    )


if __name__ == "__main__":
    main()
