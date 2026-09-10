from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    openai_api_key: SecretStr = Field(min_length=1)
    openai_model: str = "gpt-5.6-luna"
    database_path: Path = BASE_DIR / "storage" / "checkpoints.sqlite"
    recursion_limit: int = Field(default=10, ge=2, le=30)
    context_turns: int = Field(default=6, ge=1, le=10)

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )
