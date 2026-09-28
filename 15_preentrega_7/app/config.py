from pathlib import Path
from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    redis_url: str = 'redis://127.0.0.1:16379/0'
    redis_prefix: str = 'pre7'
    api_key: SecretStr = Field(min_length=16)
    approval_key: SecretStr = Field(min_length=16)
    openai_api_key: SecretStr = Field(default=SecretStr(''))
    openai_model: Literal['gpt-6-luna'] = 'gpt-6-luna'
    job_timeout_seconds: float = Field(default=180, ge=0.1, le=900)
    worker_concurrency: int = Field(default=5, ge=1, le=5)
    model_config = SettingsConfigDict(env_file=BASE_DIR / '.env', extra='ignore')

    @model_validator(mode='after')
    def separate_keys(self):
        if self.api_key == self.approval_key:
            raise ValueError('API and approval keys must differ')
        return self


def create_model():
    settings = Settings()
    if not settings.openai_api_key.get_secret_value():
        raise ValueError('OPENAI_API_KEY required')
    return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key,
                      reasoning_effort='low', use_responses_api=True,
                      max_retries=2, timeout=30, max_tokens=2000)
