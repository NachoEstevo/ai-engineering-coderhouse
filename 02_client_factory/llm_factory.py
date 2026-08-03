from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import os

import anthropic
import openai
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic import BaseModel, SecretStr, model_validator


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMConfig(BaseModel):
    provider: Provider
    model: str
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def validate_selected_provider_key(self) -> "LLMConfig":
        api_key = self.openai_api_key if self.provider == Provider.OPENAI else self.anthropic_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise ValueError(f"Falta la API key para {self.provider.value}")
        return self


class BaseLLMClient(ABC):
    @abstractmethod
    async def chat(self, prompt: str) -> str:
        pass


class LLMClientError(RuntimeError):
    pass


class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.sdk_client = AsyncOpenAI(api_key=api_key)

    async def chat(self, prompt: str) -> str:
        try:
            response = await self.sdk_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""
        except openai.APIError as error:
            raise LLMClientError("No se pudo obtener una respuesta de OpenAI") from error


class AnthropicClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.sdk_client = AsyncAnthropic(api_key=api_key)

    async def chat(self, prompt: str) -> str:
        try:
            response = await self.sdk_client.messages.create(
                model=self.model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except anthropic.APIError as error:
            raise LLMClientError("No se pudo obtener una respuesta de Anthropic") from error


class LLMFactory:
    @staticmethod
    def create_client(provider: Provider, config: LLMConfig) -> BaseLLMClient:
        if provider != config.provider:
            raise ValueError("El proveedor debe coincidir con la configuración")
        if provider == Provider.OPENAI:
            return OpenAIClient(config.openai_api_key.get_secret_value(), config.model)
        return AnthropicClient(config.anthropic_api_key.get_secret_value(), config.model)


async def main() -> None:
    provider = Provider(os.getenv("LLM_PROVIDER", "openai").lower())
    api_key_name = "OPENAI_API_KEY" if provider == Provider.OPENAI else "ANTHROPIC_API_KEY"
    api_key = os.getenv(api_key_name)
    if not api_key:
        print(f"Definí {api_key_name} antes de ejecutar el script.")
        return
    default_model = "gpt-4o-mini" if provider == Provider.OPENAI else "claude-3-5-haiku-latest"
    config = LLMConfig(
        provider=provider,
        model=os.getenv("LLM_MODEL", default_model),
        openai_api_key=api_key if provider == Provider.OPENAI else None,
        anthropic_api_key=api_key if provider == Provider.ANTHROPIC else None,
    )
    client = LLMFactory.create_client(provider, config)
    print(await client.chat("Resumí en una oración qué es la concurrencia."))


if __name__ == "__main__":
    asyncio.run(main())
