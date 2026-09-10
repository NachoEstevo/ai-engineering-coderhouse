from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    pinecone_api_key: SecretStr
    openai_api_key: SecretStr
    index_name: str = Field(min_length=1)
    namespace: str = Field(default="asyncio-docs", min_length=1, pattern=r"\S")
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    top_k: int = Field(default=5, ge=1, le=20)

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
