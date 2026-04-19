from __future__ import annotations

import importlib
import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def document_router_module(monkeypatch, tmp_path):
    class FakeDoclingClient:
        def process_document(self, file_path, report_type="lab_report"):
            return {
                "markdown": "# Lab",
                "chunks": [{"id": 1}],
                "medical_fields": {"report_type": report_type},
            }

        def extract_medical_fields(self, markdown):
            return {"engine": "docling", "len": len(markdown)}

    class FakeAdeClient:
        def process_document(self, file_path):
            return {
                "markdown": "# Rx",
                "chunks": [],
                "medical_fields": {"report_type": "prescription"},
            }

        def extract_medical_fields(self, markdown):
            return {"engine": "ade", "len": len(markdown)}

    fake_docprocess = types.ModuleType("backend.services.DOCPROCESS")
    fake_docprocess.get_docling_client = lambda: FakeDoclingClient()
    fake_docprocess.get_ade_client = lambda: FakeAdeClient()

    monkeypatch.setitem(sys.modules, "backend.services.DOCPROCESS", fake_docprocess)
    sys.modules.pop("api.routers.document_router", None)
    module = importlib.import_module("api.routers.document_router")

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(module, "DOCLING_UPLOAD_DIR", upload_dir)
    return module


def _build_app(document_router_module, tmp_path):
    class FakeCaseManager:
        def get_or_create(self, patient_id=None, session_id=None):
            case_dir = tmp_path / "output" / "case-1"
            docs_dir = case_dir / "documents"
            skin_dir = case_dir / "skintelligent"
            docs_dir.mkdir(parents=True, exist_ok=True)
            skin_dir.mkdir(parents=True, exist_ok=True)
            return {
                "case_id": "case-1",
                "context_key": patient_id or session_id or "default",
                "case_dir": case_dir,
                "documents_dir": docs_dir,
                "skintelligent_dir": skin_dir,
            }

    app = FastAPI()
    app.include_router(document_router_module.document_router)
    app.state.case_output_manager = FakeCaseManager()
    return app


def test_router_dispatch_lab_report(document_router_module, tmp_path):
    out = document_router_module.router(tmp_path / "sample.pdf", report_type="lab_report")
    assert out["medical_fields"]["report_type"] == "lab_report"


def test_router_dispatch_prescription(document_router_module, tmp_path):
    out = document_router_module.router(tmp_path / "sample.pdf", report_type="prescription")
    assert out["medical_fields"]["report_type"] == "prescription"


def test_router_invalid_type_raises(document_router_module, tmp_path):
    with pytest.raises(ValueError):
        document_router_module.router(tmp_path / "sample.pdf", report_type="other")


def test_upload_and_process_success(document_router_module, tmp_path):
    app = _build_app(document_router_module, tmp_path)
    client = TestClient(app)

    resp = client.post(
        "/ade/upload",
        files={"file": ("report.pdf", b"pdf-content", "application/pdf")},
        data={"report_type": "lab_report", "patient_id": "p1"},
        headers={"x-session-id": "s1"},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["engine"] == "docling"
    assert payload["chunk_count"] == 1
    assert payload["case"]["case_id"] == "case-1"


def test_upload_rejects_unsupported_file_type(document_router_module, tmp_path):
    app = _build_app(document_router_module, tmp_path)
    client = TestClient(app)

    resp = client.post(
        "/ade/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"report_type": "lab_report"},
    )

    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


def test_extract_fields_empty_markdown_returns_400(document_router_module, tmp_path):
    app = _build_app(document_router_module, tmp_path)
    client = TestClient(app)

    resp = client.post("/ade/extract", json={"markdown": "   "})

    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


def test_extract_fields_ade_success(document_router_module, tmp_path):
    app = _build_app(document_router_module, tmp_path)
    client = TestClient(app)

    resp = client.post("/ade/extract", json={"markdown": "content"})

    assert resp.status_code == 200
    assert resp.json()["medical_fields"]["engine"] == "ade"


def test_docling_extract_success(document_router_module, tmp_path):
    app = _build_app(document_router_module, tmp_path)
    client = TestClient(app)

    resp = client.post("/ade/docling/ext_markdown", json={"markdown": "content"})

    assert resp.status_code == 200
    assert resp.json()["medical_fields"]["engine"] == "docling"
