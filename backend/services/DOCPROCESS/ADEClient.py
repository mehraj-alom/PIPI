from pathlib import Path
from dotenv import load_dotenv
import os
from typing import Optional
from functools import lru_cache

from landingai_ade import LandingAIADE
from landingai_ade.lib import pydantic_to_json_schema


from logger import DocProcess_logger as logger
from  backend.services.DOCPROCESS.doc_utils.ADE_SCHEMA import MedicalRecordSchema

#Load env
repo_root = Path(__file__).resolve().parents[3]
repo_env_path = repo_root / ".env"
if repo_env_path.exists():
    load_dotenv(repo_env_path, override=True)


class ADEClient:
    def __init__(self):
        api_key = os.getenv("VISION_AGENT_API_KEY") or os.getenv("VISION_API_KEY")
        if not api_key:
            raise EnvironmentError("VISION_AGENT_API_KEY or VISION_API_KEY not set")
        self.client = LandingAIADE(apikey=api_key)

    def parse_document(self, file_path: str | Path) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"{file_path} not found")

        response = self.client.parse(
            document=path,
            model="dpt-2-latest",
        )

        chunks = []
        for chunk in response.chunks:
            grounding = []
            if getattr(chunk, "grounding", None):
                box = chunk.grounding.box
                grounding = [{
                    "page": chunk.grounding.page,
                    "coordinates": {
                        "top": box.top,
                        "bottom": box.bottom,
                        "left": box.left,
                        "right": box.right,
                    }
                }]

            chunks.append({
                "chunk_id": chunk.id,
                "chunk_type": chunk.type,
                "text": chunk.markdown,
                "grounding": grounding,
            })

        return {
            "markdown": response.markdown,
            "chunks": chunks,
        }

    def extract_medical_fields(self, markdown: str) -> dict:
        schema = pydantic_to_json_schema(MedicalRecordSchema)

        response = self.client.extract(
            markdown=markdown,
            schema=schema,
        )

        extraction = getattr(response, "extraction", None)
        if isinstance(extraction, dict):
            return extraction
        return {}

    def process_document(self, file_path: str | Path) -> dict:
        parsed = self.parse_document(file_path)
        extracted = self.extract_medical_fields(parsed["markdown"])

        return {
            "markdown": parsed["markdown"],
            "chunks": parsed["chunks"],
            "medical_fields": extracted,
        }


@lru_cache(maxsize=2)
def get_ade_client():
    return ADEClient()