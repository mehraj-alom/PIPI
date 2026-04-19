from __future__ import annotations

from backend.services.output_context import CaseOutputManager


def test_get_or_create_reuses_same_context_for_same_patient():
    manager = CaseOutputManager()

    first = manager.get_or_create(patient_id="patient-001")
    second = manager.get_or_create(patient_id="patient-001")

    assert first["case_id"] == second["case_id"]
    assert first["context_key"] == "patient-001"
    assert first["case_dir"].exists()
    assert first["skintelligent_dir"].exists()
    assert first["documents_dir"].exists()


def test_get_or_create_builds_separate_contexts_for_different_keys():
    manager = CaseOutputManager()

    patient_ctx = manager.get_or_create(patient_id="patient-A")
    session_ctx = manager.get_or_create(session_id="session-A")

    assert patient_ctx["case_id"] != session_ctx["case_id"]
    assert patient_ctx["context_key"] == "patient-A"
    assert session_ctx["context_key"] == "session-A"


def test_sanitize_falls_back_to_anonymous_for_invalid_key():
    manager = CaseOutputManager()
    context = manager.get_or_create(patient_id="@@@###")

    assert context["context_key"] == "_"
