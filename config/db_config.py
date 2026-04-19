from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables."""

    DATABASE_URL: str = Field(default=f"sqlite:///{(PROJECT_ROOT / '.langgraph/app.sqlite').as_posix()}")
    LANGGRAPH_CHECKPOINT_DB: str = Field(default=str(PROJECT_ROOT / ".langgraph/checkpoints.sqlite"))
    LANGGRAPH_INTERRUPT_BEFORE: str = Field(default="")
    ENABLE_THREAD_POLLING: bool = Field(default=True)
    APP_TIMEZONE: str = Field(default="UTC")

    OPENAI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    VISION_API_KEY: str | None = None
    DEEPGRAM_API_KEY: str | None = None
    ELEVENLABS_API_KEY: str | None = None
    ELEVENLABS_VOICE_ID: str | None = None

    log_level: str = "INFO"
    allowed_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def checkpoint_path(self) -> Path:
        path = Path(self.LANGGRAPH_CHECKPOINT_DB)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def interrupt_before_nodes(self) -> list[str]:
        raw_value = (self.LANGGRAPH_INTERRUPT_BEFORE or "").strip()
        if not raw_value:
            return []
        parts = [part.strip() for part in raw_value.split(",") if part.strip()]
        seen: set[str] = set()
        result: list[str] = []
        for part in parts:
            if part not in seen:
                seen.add(part)
                result.append(part)
        return result


settings = Settings()
