from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
from PIL import Image

from logger import Database_logger as logger


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(slots=True)
class SkinCaseArtifact:
    run_id: str
    original_image_path: Path | None = None
    detection_boxes_path: Path | None = None
    gradcam_paths: list[Path] = field(default_factory=list)
    classification_results: list[dict[str, Any]] = field(default_factory=list)
    classification_report_path: Path | None = None


@dataclass(slots=True)
class DocumentCaseArtifact:
    artifact_id: str
    original_path: Path | None = None
    markdown_path: Path | None = None
    medical_fields_path: Path | None = None
    result_json_path: Path | None = None
    markdown: str = ""
    medical_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DoctorCasePacket:
    case_id: str | None
    case_dir: Path | None
    report_pdf_path: Path
    original_attachment_paths: list[Path] = field(default_factory=list)
    skin_artifacts: list[SkinCaseArtifact] = field(default_factory=list)
    document_artifacts: list[DocumentCaseArtifact] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def safe_text(value: Any) -> str:
    text = str(value if value is not None else "")
    text = re.sub(
        r"\S{48,}",
        lambda match: " ".join(
            match.group(0)[index:index + 40]
            for index in range(0, len(match.group(0)), 40)
        ),
        text,
    )
    return text.encode("latin-1", "replace").decode("latin-1")


def read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read JSON from %s", path)
        return None


def extract_run_id(report_path: Path) -> str:
    match = re.match(r"classification_report_(.+)\.txt$", report_path.name)
    return match.group(1) if match else report_path.stem


def load_classification_results(report_path: Path) -> list[dict[str, Any]]:
    raw_text = report_path.read_text(encoding="utf-8", errors="replace")
    json_start = raw_text.find("[")
    if json_start == -1:
        json_start = raw_text.find("{")
    if json_start == -1:
        return []

    try:
        payload = json.loads(raw_text[json_start:])
    except json.JSONDecodeError:
        logger.warning("Could not parse classification report JSON from %s", report_path)
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def collect_skin_artifacts(case_dir: Path) -> list[SkinCaseArtifact]:
    reports_dir = case_dir / "skintelligent" / "reports"
    images_dir = case_dir / "skintelligent" / "images"
    detection_boxes_dir = case_dir / "skintelligent" / "detection_boxes"
    artifacts: list[SkinCaseArtifact] = []

    for report_path in sorted(reports_dir.glob("classification_report_*.txt")):
        run_id = extract_run_id(report_path)
        classification_results = load_classification_results(report_path)

        original_candidates = sorted(images_dir.glob(f"original_image_{run_id}.*"))
        detection_candidates = sorted(detection_boxes_dir.glob(f"original_with_detection_boxes_{run_id}.*"))

        gradcam_candidates: list[Path] = []
        for result in classification_results:
            gradcam_value = result.get("gradcam")
            if gradcam_value:
                gradcam_candidates.append(Path(str(gradcam_value)))
            for gradcam_item in result.get("top_3_gradcams") or []:
                gradcam_value = gradcam_item.get("gradcam")
                if gradcam_value:
                    gradcam_candidates.append(Path(str(gradcam_value)))

        artifacts.append(
            SkinCaseArtifact(
                run_id=run_id,
                original_image_path=original_candidates[0] if original_candidates else None,
                detection_boxes_path=detection_candidates[0] if detection_candidates else None,
                gradcam_paths=[path for path in unique_paths(gradcam_candidates) if path.exists()][:3],
                classification_results=classification_results,
                classification_report_path=report_path,
            )
        )

    return artifacts


def collect_document_artifacts(case_dir: Path) -> list[DocumentCaseArtifact]:
    originals_dir = case_dir / "documents" / "originals"
    parsed_dir = case_dir / "documents" / "parsed"
    grouped: dict[str, DocumentCaseArtifact] = {}

    def ensure_record(artifact_id: str) -> DocumentCaseArtifact:
        if artifact_id not in grouped:
            grouped[artifact_id] = DocumentCaseArtifact(artifact_id=artifact_id)
        return grouped[artifact_id]

    for original_path in sorted(originals_dir.glob("*")):
        artifact_id = original_path.name.split("_", 1)[0]
        ensure_record(artifact_id).original_path = original_path

    for markdown_path in sorted(parsed_dir.glob("*.md")):
        artifact_id = markdown_path.name.split("_", 1)[0]
        record = ensure_record(artifact_id)
        record.markdown_path = markdown_path
        record.markdown = markdown_path.read_text(encoding="utf-8", errors="replace")

    for fields_path in sorted(parsed_dir.glob("*_medical_fields.json")):
        artifact_id = fields_path.name.split("_", 1)[0]
        record = ensure_record(artifact_id)
        record.medical_fields_path = fields_path
        payload = read_json(fields_path)
        if isinstance(payload, dict):
            record.medical_fields = payload

    for result_path in sorted(parsed_dir.glob("*_result.json")):
        artifact_id = result_path.name.split("_", 1)[0]
        record = ensure_record(artifact_id)
        record.result_json_path = result_path
        if not record.markdown or not record.medical_fields:
            payload = read_json(result_path)
            if isinstance(payload, dict):
                if not record.markdown:
                    record.markdown = str(payload.get("markdown") or "")
                if not record.medical_fields and isinstance(payload.get("medical_fields"), dict):
                    record.medical_fields = payload["medical_fields"]

    return sorted(grouped.values(), key=lambda item: item.artifact_id)


def format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def add_heading(pdf: FPDF, text: str, *, size: int = 14) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Arial", "B", size)
    pdf.cell(0, 8, safe_text(text), ln=1)


def add_body(pdf: FPDF, text: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, safe_text(text))


def add_image(pdf: FPDF, image_path: Path, title: str) -> None:
    if not image_path.exists() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
        return

    add_heading(pdf, title, size=11)
    try:
        with Image.open(image_path) as image:
            width, height = image.size
    except Exception:
        logger.exception("Failed to inspect image dimensions for %s", image_path)
        return

    if width <= 0 or height <= 0:
        render_width = 160
        render_height = 90
    else:
        max_width = 180
        max_height = 95
        scale = min(max_width / width, max_height / height)
        render_width = max(width * scale, 50)
        render_height = max(height * scale, 30)

    page_break_trigger = getattr(pdf, "page_break_trigger", pdf.h - pdf.b_margin)
    if pdf.get_y() + render_height + 6 > page_break_trigger:
        pdf.add_page()

    x_position = max((pdf.w - render_width) / 2, pdf.l_margin)
    y_position = pdf.get_y()
    pdf.image(str(image_path), x=x_position, y=y_position, w=render_width, h=render_height)
    pdf.ln(render_height + 4)


def add_medical_fields(pdf: FPDF, medical_fields: dict[str, Any]) -> None:
    if not medical_fields:
        add_body(pdf, "No structured medical fields were extracted.")
        return

    for key, value in medical_fields.items():
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 5, safe_text(f"{key}:"), ln=1)
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 5, safe_text(format_value(value)))


def render_packet_pdf(
    packet: DoctorCasePacket,
    *,
    patient,
    doctor,
    appointment_date: date,
    time_slot: str,
    appointment_id: int,
) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "PIPI Doctor Case Packet", ln=1, align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, safe_text(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"), ln=1, align="C")
    pdf.ln(4)

    add_heading(pdf, "Appointment Summary")
    add_body(
        pdf,
        "\n".join(
            [
                f"Appointment ID: {appointment_id}",
                f"Case ID: {packet.case_id or 'Not linked to a persisted case folder'}",
                f"Doctor: {getattr(doctor, 'name', 'Unknown')} ({getattr(doctor, 'specialization', 'Unknown')})",
                f"Patient: {getattr(patient, 'name', 'Unknown')}",
                f"Patient phone: {getattr(patient, 'phone', 'Not provided')}",
                f"Patient age: {getattr(patient, 'age', 'Not provided')}",
                f"Patient conditions: {', '.join(str(item) for item in (getattr(patient, 'conditions', None) or [])) or 'None provided'}",
                f"Appointment date: {appointment_date.isoformat()}",
                f"Appointment time: {time_slot}",
            ]
        ),
    )

    if packet.notes:
        add_heading(pdf, "Notes", size=12)
        for note in packet.notes:
            add_body(pdf, f"- {note}")

    add_heading(pdf, "Skin Analysis", size=13)
    if not packet.skin_artifacts:
        add_body(pdf, "No skin-analysis artifacts were found in the linked case folder.")
    for index, artifact in enumerate(packet.skin_artifacts, start=1):
        pdf.ln(2)
        add_heading(pdf, f"Skin run {index}", size=12)
        if artifact.original_image_path:
            add_image(pdf, artifact.original_image_path, "Original skin image")
        if artifact.detection_boxes_path:
            add_image(pdf, artifact.detection_boxes_path, "Detection overlay")

        if artifact.classification_results:
            for result_index, result in enumerate(artifact.classification_results, start=1):
                prediction_name = result.get("class_name", "Unknown")
                confidence = float(result.get("confidence", 0.0) or 0.0)
                summary_lines = [
                    f"Detection {result_index}: {prediction_name}",
                    f"Confidence: {confidence:.1%}",
                ]
                if result.get("warning"):
                    summary_lines.append(f"Warning: {result['warning']}")
                if result.get("det_confidence") is not None:
                    summary_lines.append(f"Detection confidence: {float(result['det_confidence']):.1%}")
                top_predictions = result.get("top_3_predictions") or []
                if top_predictions:
                    formatted = ", ".join(
                        f"{item.get('class_name', 'Unknown')} ({float(item.get('confidence', 0.0) or 0.0):.1%})"
                        for item in top_predictions[:3]
                    )
                    summary_lines.append(f"Top predictions: {formatted}")
                add_body(pdf, "\n".join(summary_lines))

        if artifact.gradcam_paths:
            for gradcam_index, gradcam_path in enumerate(artifact.gradcam_paths, start=1):
                add_image(pdf, gradcam_path, f"Grad-CAM++ overlay {gradcam_index}")

    pdf.add_page()
    add_heading(pdf, "Document Extraction", size=13)
    if not packet.document_artifacts:
        add_body(pdf, "No uploaded medical documents were found in the linked case folder.")

    for index, artifact in enumerate(packet.document_artifacts, start=1):
        pdf.ln(2)
        add_heading(pdf, f"Document {index}", size=12)
        if artifact.original_path:
            add_body(pdf, f"Original file: {artifact.original_path.name}")
            if artifact.original_path.suffix.lower() in IMAGE_EXTENSIONS:
                add_image(pdf, artifact.original_path, "Uploaded document preview")
            else:
                add_body(pdf, "The original document is attached separately because it is not an embeddable image format.")

        add_heading(pdf, "Extracted medical fields", size=11)
        add_medical_fields(pdf, artifact.medical_fields)

        add_heading(pdf, "Extracted markdown/text", size=11)
        if artifact.markdown.strip():
            add_body(pdf, artifact.markdown.strip())
        else:
            add_body(pdf, "No extracted markdown was available for this document.")

    pdf.add_page()
    add_heading(pdf, "Attached Original Uploads", size=13)
    if packet.original_attachment_paths:
        for path in packet.original_attachment_paths:
            add_body(pdf, f"- {path.name}")
    else:
        add_body(pdf, "No original uploaded files were available to attach.")

    pdf.output(str(packet.report_pdf_path))


def build_doctor_case_packet(
    *,
    patient,
    doctor,
    appointment_date: date,
    time_slot: str,
    appointment_id: int,
    case_context: dict | None = None,
) -> DoctorCasePacket:
    case_id = case_context.get("case_id") if case_context else None
    case_dir = Path(case_context["case_dir"]) if case_context and case_context.get("case_dir") else None
    notes: list[str] = []

    if case_dir is not None and not case_dir.exists():
        notes.append(f"Case directory was expected at {case_dir} but is not available.")
        case_dir = None

    skin_artifacts: list[SkinCaseArtifact] = []
    document_artifacts: list[DocumentCaseArtifact] = []
    original_attachment_paths: list[Path] = []

    if case_dir is not None:
        skin_artifacts = collect_skin_artifacts(case_dir)
        document_artifacts = collect_document_artifacts(case_dir)
        original_attachment_paths.extend(
            artifact.original_image_path
            for artifact in skin_artifacts
            if artifact.original_image_path is not None and artifact.original_image_path.exists()
        )
        original_attachment_paths.extend(
            artifact.original_path
            for artifact in document_artifacts
            if artifact.original_path is not None and artifact.original_path.exists()
        )
        if not skin_artifacts and not document_artifacts:
            notes.append("The linked case folder exists, but it does not contain skin or document artifacts yet.")
        report_dir = case_dir / "doctor_reports"
    else:
        notes.append("No persisted patient/session case folder was found, so the packet includes appointment data only.")
        report_dir = Path("output") / "doctor_reports"

    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    patient_key = getattr(patient, "id", None) or getattr(patient, "name", "patient")
    report_pdf_path = report_dir / f"doctor_case_packet_{patient_key}_{timestamp}.pdf"

    packet = DoctorCasePacket(
        case_id=case_id,
        case_dir=case_dir,
        report_pdf_path=report_pdf_path,
        original_attachment_paths=unique_paths([path for path in original_attachment_paths if path is not None]),
        skin_artifacts=skin_artifacts,
        document_artifacts=document_artifacts,
        notes=notes,
    )
    render_packet_pdf(
        packet,
        patient=patient,
        doctor=doctor,
        appointment_date=appointment_date,
        time_slot=time_slot,
        appointment_id=appointment_id,
    )
    return packet
