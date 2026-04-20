from __future__ import annotations

from backend.services.output_context import CaseOutputManager


def test_get_or_create_reuses_same_context_for_same_patient(tmp_path):
    manager = CaseOutputManager(base_dir=tmp_path / "output")

    first = manager.get_or_create(patient_id="patient-001")
    second = manager.get_or_create(patient_id="patient-001")

    assert first["case_id"] == second["case_id"]
    assert first["context_key"] == "patient-001"
    assert first["case_dir"].exists()
    assert first["skintelligent_dir"].exists()
    assert first["documents_dir"].exists()


def test_get_or_create_builds_separate_contexts_for_different_keys(tmp_path):
    manager = CaseOutputManager(base_dir=tmp_path / "output")

    patient_ctx = manager.get_or_create(patient_id="patient-A")
    session_ctx = manager.get_or_create(session_id="session-A")

    assert patient_ctx["case_id"] != session_ctx["case_id"]
    assert patient_ctx["context_key"] == "patient-A"
    assert session_ctx["context_key"] == "session-A"


def test_sanitize_falls_back_to_anonymous_for_invalid_key(tmp_path):
    manager = CaseOutputManager(base_dir=tmp_path / "output")
    context = manager.get_or_create(patient_id="@@@###")

    assert context["context_key"] == "_"


def test_get_existing_recovers_context_from_disk(tmp_path):
    first_manager = CaseOutputManager(base_dir=tmp_path / "output")
    created = first_manager.get_or_create(patient_id="patient-007")

    second_manager = CaseOutputManager(base_dir=tmp_path / "output")
    recovered = second_manager.get_existing(patient_id="patient-007")

    assert recovered is not None
    assert recovered["case_id"] == created["case_id"]
    assert recovered["case_dir"] == created["case_dir"]
