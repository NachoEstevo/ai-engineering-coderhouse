from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    openai_api_key: SecretStr = Field(min_length=1)
    openai_model: str = "gpt-5.6-luna"
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )


def create_model() -> ChatOpenAI:
    settings = Settings()
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        reasoning_effort="low",
        use_responses_api=True,
        max_retries=2,
        timeout=30,
        max_tokens=2000,
    )
