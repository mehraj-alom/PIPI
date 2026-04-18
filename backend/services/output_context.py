from datetime import datetime
from pathlib import Path
import re
import uuid


class CaseOutputManager:
    """Create and reuse one case folder per patient/session for current app runtime."""

    def __init__(self):
        self._contexts = {}

    def _sanitize(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
        return cleaned[:80] if cleaned else "anonymous"

    def get_or_create(self, patient_id: str | None = None, session_id: str | None = None):
        key_source = patient_id or session_id or "default_session"
        context_key = self._sanitize(str(key_source))

        existing = self._contexts.get(context_key)
        if existing:
            return existing

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        case_id = f"{timestamp}_{uuid.uuid4().hex}"

        case_dir = Path("output") / case_id
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
        return context
