import json
from datetime import datetime
from pathlib import Path
import re
import uuid


class CaseOutputManager:
    """Create and reuse one case folder per patient/session for current app runtime."""

    def __init__(self, base_dir: str | Path = "output"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._contexts = {}

    def _sanitize(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
        return cleaned[:80] if cleaned else "anonymous"

    def _manifest_path(self, case_dir: Path) -> Path:
        return case_dir / "case_context.json"

    def _persist_context(self, context: dict) -> None:
        manifest_path = self._manifest_path(Path(context["case_dir"]))
        payload = {
            "case_id": context.get("case_id"),
            "context_key": context.get("context_key"),
            "patient_id": context.get("patient_id"),
            "session_id": context.get("session_id"),
            "case_dir": str(context.get("case_dir")),
            "skintelligent_dir": str(context.get("skintelligent_dir")),
            "documents_dir": str(context.get("documents_dir")),
            "updated_at": datetime.utcnow().isoformat(),
        }
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_context_from_manifest(self, manifest_path: Path) -> dict | None:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        case_dir = Path(payload["case_dir"])
        context = {
            "case_id": payload.get("case_id"),
            "context_key": payload.get("context_key"),
            "case_dir": case_dir,
            "skintelligent_dir": Path(payload.get("skintelligent_dir") or case_dir / "skintelligent"),
            "documents_dir": Path(payload.get("documents_dir") or case_dir / "documents"),
            "patient_id": payload.get("patient_id"),
            "session_id": payload.get("session_id"),
        }
        return context

    def get_existing(self, patient_id: str | None = None, session_id: str | None = None):
        key_source = patient_id or session_id
        if not key_source:
            return None

        context_key = self._sanitize(str(key_source))
        existing = self._contexts.get(context_key)
        if existing:
            self._persist_context(existing)
            return existing

        manifests = sorted(
            self.base_dir.glob("*/case_context.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for manifest_path in manifests:
            context = self._load_context_from_manifest(manifest_path)
            if not context:
                continue

            same_patient = patient_id is not None and str(context.get("patient_id")) == str(patient_id)
            same_session = session_id is not None and str(context.get("session_id")) == str(session_id)
            same_key = context.get("context_key") == context_key
            if same_patient or same_session or same_key:
                self._contexts[context_key] = context
                self._persist_context(context)
                return context

        return None

    def get_or_create(self, patient_id: str | None = None, session_id: str | None = None):
        existing = self.get_existing(patient_id=patient_id, session_id=session_id)
        if existing:
            return existing

        key_source = patient_id or session_id or "default_session"
        context_key = self._sanitize(str(key_source))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        case_id = f"{timestamp}_{uuid.uuid4().hex}"

        case_dir = self.base_dir / case_id
        skin_dir = case_dir / "skintelligent"
        documents_dir = case_dir / "documents"

        skin_dir.mkdir(parents=True, exist_ok=True)
        documents_dir.mkdir(parents=True, exist_ok=True)

        context = {
            "case_id": case_id,
            "context_key": context_key,
            "case_dir": case_dir,
            "skintelligent_dir": skin_dir,
            "documents_dir": documents_dir,
            "patient_id": patient_id,
            "session_id": session_id,
        }

        self._contexts[context_key] = context
        self._persist_context(context)
        return context
