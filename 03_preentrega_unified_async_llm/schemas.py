from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ModelConfig(BaseModel):
    provider: Provider
    model: str
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=256, gt=0, le=4096)


class ModelResponse(BaseModel):
    content: str = ""
    provider: Provider
    model: str
    error: str | None = None


class LLMSettings(BaseModel):
    config: ModelConfig
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def validate_selected_provider_key(self) -> "LLMSettings":
        api_key = self.openai_api_key if self.config.provider == Provider.OPENAI else self.anthropic_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise ValueError(f"Falta la API key para {self.config.provider.value}")
        return self
