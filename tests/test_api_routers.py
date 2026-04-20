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


def _override_db():
    yield object()


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
    app.dependency_overrides[voice_agent_router.get_db] = _override_db

    client = TestClient(app)
    resp = client.post(
        "/tools/VoiceAgent/getPatientDetails",
        json={"Patient_Name": "John Doe", "patient_phone": "000"},
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == "John Doe"


def test_get_patient_details_returns_close_name_suggestions(monkeypatch):
    monkeypatch.setattr(voice_agent_router, "get_patient_by_phone", lambda db, phone: None)
    monkeypatch.setattr(voice_agent_router, "get_patient_by_name_exact", lambda db, name: None)
    monkeypatch.setattr(
        voice_agent_router,
        "get_patient_name_suggestions",
        lambda db, name: [SimpleNamespace(name="Mehraj Alom", phone="3647849434")],
    )

    app = _build_voice_app()
    app.dependency_overrides[voice_agent_router.get_db] = _override_db

    client = TestClient(app)
    resp = client.post(
        "/tools/VoiceAgent/getPatientDetails",
        json={"Patient_Name": "Mehraj Alam", "patient_phone": ""},
    )

    assert resp.status_code == 200
    assert "Similar records found" in resp.json()["error"]
    assert resp.json()["suggested_matches"] == [
        {"name": "Mehraj Alom", "phone_last4": "9434"},
    ]


def test_register_patient_splits_conditions(monkeypatch):
    captured = {}

    def _fake_upsert(db, *, phone, name, age=None, conditions=None, assigned_doctor_id=None):
        captured["conditions"] = conditions
        return SimpleNamespace(id=42)

    monkeypatch.setattr(voice_agent_router, "upsert_patient", _fake_upsert)

    app = _build_voice_app()
    app.dependency_overrides[voice_agent_router.get_db] = _override_db
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
    app.dependency_overrides[voice_agent_router.get_db] = _override_db
    client = TestClient(app)

    resp = client.post(
        "/tools/VoiceAgent/checkDoctorAvailability",
        json={"doctor_id": 1, "appointment_date": "20-04-2026", "time_preference": "morning"},
    )

    assert resp.status_code == 200
    assert "Invalid date format" in resp.json()["error"]


def test_book_appointment_conflict(monkeypatch):
    monkeypatch.setattr(
        voice_agent_router,
        "get_patient_appointment_for_slot",
        lambda *args, **kwargs: None,
    )

    def _raise_conflict(*args, **kwargs):
        raise voice_agent_router.AppointmentConflictError("conflict")

    monkeypatch.setattr(voice_agent_router, "create_appointment", _raise_conflict)

    app = _build_voice_app()
    app.dependency_overrides[voice_agent_router.get_db] = _override_db
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


def test_book_appointment_returns_existing_for_duplicate_request(monkeypatch):
    monkeypatch.setattr(
        voice_agent_router,
        "get_patient_appointment_for_slot",
        lambda *args, **kwargs: SimpleNamespace(id=7, status="confirmed"),
    )

    def _unexpected_create(*args, **kwargs):
        raise AssertionError("create_appointment should not be called when the appointment already exists")

    monkeypatch.setattr(voice_agent_router, "create_appointment", _unexpected_create)

    app = _build_voice_app()
    app.dependency_overrides[voice_agent_router.get_db] = _override_db
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
    assert resp.json() == {
        "success": True,
        "appointment_id": 7,
        "status": "confirmed",
        "already_booked": True,
    }


def test_voice_signed_url_uses_backend_agent_config(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"signed_url": "wss://signed.example.test/session"}

    def _fake_get(url, *, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(voice_agent_router.settings, "ELEVENLABS_AGENT_ID", '"agent_ab12cd34?branchId=agtbrch_ef56gh78"')
    monkeypatch.setattr(voice_agent_router.settings, "ELEVENLABS_API_KEY", "secret-key")
    monkeypatch.setattr(voice_agent_router.httpx, "get", _fake_get)

    client = TestClient(_build_voice_app())
    resp = client.get("/tools/VoiceAgent/signed-url")

    assert resp.status_code == 200
    assert resp.json()["signed_url"] == "wss://signed.example.test/session"
    assert captured["url"] == voice_agent_router.ELEVENLABS_SIGNED_URL_ENDPOINT
    assert captured["params"] == {
        "agent_id": "agent_ab12cd34",
        "branch_id": "agtbrch_ef56gh78",
    }
    assert captured["headers"] == {"xi-api-key": "secret-key"}
    assert captured["timeout"] == 10.0


def test_voice_signed_url_requires_backend_api_key(monkeypatch):
    monkeypatch.setattr(voice_agent_router.settings, "ELEVENLABS_AGENT_ID", "agent_ab12cd34")
    monkeypatch.setattr(voice_agent_router.settings, "ELEVENLABS_API_KEY", "")

    client = TestClient(_build_voice_app())
    resp = client.get("/tools/VoiceAgent/signed-url")

    assert resp.status_code == 503
    assert "ELEVENLABS_API_KEY" in resp.json()["detail"]
