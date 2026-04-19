from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import skintelligent_router, voice_agent_router


def test_skin_endpoint_rejects_invalid_image():
    app = FastAPI()
    app.include_router(skintelligent_router.router)
    app.state.vision_pipeline = SimpleNamespace()
    app.state.case_output_manager = SimpleNamespace(get_or_create=lambda **_: {})

    client = TestClient(app)
    resp = client.post(
        "/Skin/SKIN_TELLIGENT",
        files={"file": ("bad.txt", b"not-an-image", "text/plain")},
    )

    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid image file"


def test_skin_endpoint_returns_pipeline_output(monkeypatch):
    class FakePipeline:
        def run_image(self, image, output_root):
            return image, ["crop1", "crop2"], [{"vision_summary": "stable"}], {"run_id": "r1"}

    class FakeCaseManager:
        def get_or_create(self, patient_id=None, session_id=None):
            return {
                "case_id": "c1",
                "context_key": "p1",
                "case_dir": "output/c1",
                "skintelligent_dir": "output/c1/skintelligent",
                "documents_dir": "output/c1/documents",
            }

    monkeypatch.setattr(skintelligent_router.cv2, "imdecode", lambda *_: np.zeros((10, 10, 3), dtype=np.uint8))

    app = FastAPI()
    app.include_router(skintelligent_router.router)
    app.state.vision_pipeline = FakePipeline()
    app.state.case_output_manager = FakeCaseManager()

    client = TestClient(app)
    resp = client.post(
        "/Skin/SKIN_TELLIGENT",
        files={"file": ("img.jpg", b"fake-bytes", "image/jpeg")},
        data={"patient_id": "p1"},
        headers={"x-session-id": "s1"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["detections"] == 2
    assert data["vision_summary"] == "stable"
    assert data["case"]["case_id"] == "c1"


def _build_voice_app():
    app = FastAPI()
    app.include_router(voice_agent_router.router)
    return app


def test_get_patient_details_falls_back_to_name(monkeypatch):
    monkeypatch.setattr(voice_agent_router, "get_patient_by_phone", lambda db, phone: None)
    monkeypatch.setattr(
        voice_agent_router,
        "get_patient_by_name_exact",
        lambda db, name: SimpleNamespace(
            id=1,
            name="John Doe",
            phone="123",
            age=30,
            conditions=["eczema"],
            assigned_doctor_id=9,
        ),
    )

    app = _build_voice_app()
    app.dependency_overrides[voice_agent_router.get_db] = lambda: iter([object()])

    client = TestClient(app)
    resp = client.post(
        "/tools/VoiceAgent/getPatientDetails",
        json={"Patient_Name": "John Doe", "patient_phone": "000"},
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == "John Doe"


def test_register_patient_splits_conditions(monkeypatch):
    captured = {}

    def _fake_upsert(db, *, phone, name, age=None, conditions=None, assigned_doctor_id=None):
        captured["conditions"] = conditions
        return SimpleNamespace(id=42)

    monkeypatch.setattr(voice_agent_router, "upsert_patient", _fake_upsert)

    app = _build_voice_app()
    app.dependency_overrides[voice_agent_router.get_db] = lambda: iter([object()])
    client = TestClient(app)

    resp = client.post(
        "/tools/VoiceAgent/registerNewPatient",
        json={
            "patient_phone": "1234567890",
            "patient_name": "Jane",
            "age": 26,
            "Patient_conditions": "asthma, allergy",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert captured["conditions"] == ["asthma", "allergy"]


def test_check_doctor_availability_invalid_date_returns_error():
    app = _build_voice_app()
    app.dependency_overrides[voice_agent_router.get_db] = lambda: iter([object()])
    client = TestClient(app)

    resp = client.post(
        "/tools/VoiceAgent/checkDoctorAvailability",
        json={"doctor_id": 1, "appointment_date": "20-04-2026", "time_preference": "morning"},
    )

    assert resp.status_code == 200
    assert "Invalid date format" in resp.json()["error"]


def test_book_appointment_conflict(monkeypatch):
    def _raise_conflict(*args, **kwargs):
        raise voice_agent_router.AppointmentConflictError("conflict")

    monkeypatch.setattr(voice_agent_router, "create_appointment", _raise_conflict)

    app = _build_voice_app()
    app.dependency_overrides[voice_agent_router.get_db] = lambda: iter([object()])
    client = TestClient(app)

    resp = client.post(
        "/tools/VoiceAgent/bookAppointment",
        json={
            "doctor_id": 1,
            "patient_id": "2",
            "appointment_date": "2026-04-20",
            "time_slot": "10:00",
        },
    )

    assert resp.status_code == 200
    assert "no longer available" in resp.json()["error"]
