import asyncio
import os

from dotenv import load_dotenv

from clients import AsyncLLMManager
from schemas import ChatMessage, LLMSettings, ModelConfig, Provider


def load_settings() -> LLMSettings:
    provider = Provider(os.getenv("LLM_PROVIDER", "openai").lower())
    default_model = "gpt-4o-mini" if provider == Provider.OPENAI else "claude-3-5-haiku-latest"
    return LLMSettings(
        config=ModelConfig(
            provider=provider,
            model=os.getenv("LLM_MODEL", default_model),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "256")),
        ),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )


async def main() -> None:
    load_dotenv()
    try:
        manager = AsyncLLMManager(load_settings())
    except ValueError as error:
        print(f"Configuración inválida: {error}")
        return

    messages = [ChatMessage(role="user", content="¿Qué es la entropía?")]
    response = await manager.generate(messages)

    if response.error:
        print(f"Error controlado: {response.error}")
        return

    print(f"Respuesta normal:\n{response.content}\n")
    print("Streaming:")
    async for token in manager.stream(messages):
        print(token, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())
