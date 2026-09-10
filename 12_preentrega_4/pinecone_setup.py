import asyncio
import logging
from time import perf_counter

from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeApiException

from config import Settings
from retry import run_with_retry

logger = logging.getLogger(__name__)


async def ensure_index(
    settings: Settings,
    client: Pinecone | None = None,
    poll_interval: float = 1.0,
    timeout: float = 60.0,
) -> Pinecone:
    started_at = perf_counter()
    pinecone = client or Pinecone(
        api_key=settings.pinecone_api_key.get_secret_value()
    )

    async def list_names():
        return await asyncio.to_thread(lambda: pinecone.list_indexes().names())

    names = await run_with_retry(list_names, (PineconeApiException,))
    if settings.index_name not in names:
        async def create():
            return await asyncio.to_thread(
                pinecone.create_index,
                name=settings.index_name,
                dimension=settings.embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )

        await run_with_retry(create, (PineconeApiException,))

    deadline = perf_counter() + timeout
    while True:
        async def describe():
            return await asyncio.to_thread(
                pinecone.describe_index,
                name=settings.index_name,
            )

        description = await run_with_retry(describe, (PineconeApiException,))
        if description.dimension != settings.embedding_dimension:
            raise ValueError(
                f"El índice tiene dimensión {description.dimension}, "
                f"pero se esperaba {settings.embedding_dimension}"
            )
        if description.status["ready"]:
            break
        if perf_counter() >= deadline:
            raise TimeoutError("Pinecone no habilitó el índice dentro del tiempo esperado")
        await asyncio.sleep(poll_interval)

    logger.info("Índice preparado en %.3f segundos", perf_counter() - started_at)
    return pinecone
