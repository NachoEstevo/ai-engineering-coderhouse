from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import anthropic
import openai
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from schemas import ChatMessage, LLMSettings, ModelResponse, Provider


def prepare_anthropic_messages(messages: list[ChatMessage]) -> tuple[str | None, list[dict[str, str]]]:
    system_messages = [message.content for message in messages if message.role == "system"]
    conversation = [message.model_dump() for message in messages if message.role != "system"]
    return "\n".join(system_messages) or None, conversation


class BaseLLMClient(ABC):
    @abstractmethod
    async def generate(self, messages: list[ChatMessage]) -> ModelResponse:
        pass

    @abstractmethod
    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        pass


class OpenAIClient(BaseLLMClient):
    def __init__(self, settings: LLMSettings) -> None:
        self.config = settings.config
        self.sdk_client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())

    async def generate(self, messages: list[ChatMessage]) -> ModelResponse:
        try:
            response = await self.sdk_client.chat.completions.create(
                model=self.config.model,
                messages=[message.model_dump() for message in messages],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            return ModelResponse(
                content=response.choices[0].message.content or "",
                provider=self.config.provider,
                model=self.config.model,
            )
        except openai.APIError as error:
            return ModelResponse(
                provider=self.config.provider,
                model=self.config.model,
                error=f"OpenAI: {error}",
            )

    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        try:
            stream = await self.sdk_client.chat.completions.create(
                model=self.config.model,
                messages=[message.model_dump() for message in messages],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except openai.APIError as error:
            yield f"[Error controlado de OpenAI: {error}]"


class AnthropicClient(BaseLLMClient):
    def __init__(self, settings: LLMSettings) -> None:
        self.config = settings.config
        self.sdk_client = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())

    async def generate(self, messages: list[ChatMessage]) -> ModelResponse:
        try:
            system, conversation = prepare_anthropic_messages(messages)
            request = {
                "model": self.config.model,
                "messages": conversation,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
            if system:
                request["system"] = system
            response = await self.sdk_client.messages.create(**request)
            return ModelResponse(
                content=response.content[0].text,
                provider=self.config.provider,
                model=self.config.model,
            )
        except anthropic.APIError as error:
            return ModelResponse(
                provider=self.config.provider,
                model=self.config.model,
                error=f"Anthropic: {error}",
            )

    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        try:
            system, conversation = prepare_anthropic_messages(messages)
            request = {
                "model": self.config.model,
                "messages": conversation,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "stream": True,
            }
            if system:
                request["system"] = system
            stream = await self.sdk_client.messages.create(**request)
            async for event in stream:
                if event.type == "content_block_delta":
                    yield event.delta.text
        except anthropic.APIError as error:
            yield f"[Error controlado de Anthropic: {error}]"


class AsyncLLMManager:
    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings
        self.client: BaseLLMClient
        if settings.config.provider == Provider.OPENAI:
            self.client = OpenAIClient(settings)
        else:
            self.client = AnthropicClient(settings)

    async def generate(self, messages: list[ChatMessage]) -> ModelResponse:
        return await self.client.generate(messages)

    async def stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        async for token in self.client.stream(messages):
            yield token
