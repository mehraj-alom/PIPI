from __future__ import annotations

import json
from types import SimpleNamespace

from backend.services.doctor_case_packet import build_doctor_case_packet


def test_build_doctor_case_packet_collects_case_artifacts(tmp_path):
    case_dir = tmp_path / "output" / "case-123"
    skin_dir = case_dir / "skintelligent"
    docs_dir = case_dir / "documents"
    for subdir in [
        skin_dir / "images",
        skin_dir / "detection_boxes",
        skin_dir / "gradcam",
        skin_dir / "reports",
        docs_dir / "originals",
        docs_dir / "parsed",
    ]:
        subdir.mkdir(parents=True, exist_ok=True)

    run_id = "20260421_101010_abcd"
    original_skin = skin_dir / "images" / f"original_image_{run_id}.jpg"
    detection_boxes = skin_dir / "detection_boxes" / f"original_with_detection_boxes_{run_id}.jpg"
    gradcam = skin_dir / "gradcam" / f"gradcam_roi_{run_id}_0_top1_class15.jpg"
    for path in [original_skin, detection_boxes, gradcam]:
        path.write_bytes(b"fake-image")

    classification_results = [
        {
            "class_name": "Nail Fungus And Other Nail Disease",
            "confidence": 0.91,
            "gradcam": str(gradcam),
            "top_3_predictions": [
                {"class_name": "Nail Fungus And Other Nail Disease", "confidence": 0.91},
                {"class_name": "Psoriasis", "confidence": 0.05},
            ],
        }
    ]
    report_text = "SKIN_TELLIGENT Classification Report\n========================================\n\n"
    report_text += json.dumps(classification_results)
    (skin_dir / "reports" / f"classification_report_{run_id}.txt").write_text(report_text, encoding="utf-8")

    original_doc = docs_dir / "originals" / "artifact123_prescription.png"
    original_doc.write_bytes(b"fake-doc")
    (docs_dir / "parsed" / "artifact123_prescription.md").write_text("# Prescription\nTake medicine twice daily.", encoding="utf-8")
    (docs_dir / "parsed" / "artifact123_prescription_medical_fields.json").write_text(
        json.dumps({"medicines": ["Medicine A"], "follow_up": "1 week"}),
        encoding="utf-8",
    )

    packet = build_doctor_case_packet(
        patient=SimpleNamespace(id=4, name="John Doe", phone="1234567890", age=22, conditions=["skin issue"]),
        doctor=SimpleNamespace(name="Dr. Maya Reed", specialization="Dermatology"),
        appointment_date=SimpleNamespace(isoformat=lambda: "2026-04-21"),
        time_slot="10:00",
        appointment_id=9,
        case_context={"case_id": "case-123", "case_dir": case_dir},
    )

    assert packet.case_id == "case-123"
    assert packet.report_pdf_path.exists()
    assert [path.name for path in packet.original_attachment_paths] == [
        f"original_image_{run_id}.jpg",
        "artifact123_prescription.png",
    ]
