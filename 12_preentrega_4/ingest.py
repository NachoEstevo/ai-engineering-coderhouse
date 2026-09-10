import asyncio
import logging
from pathlib import Path
from time import perf_counter

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

from config import BASE_DIR, Settings
from documents import chunk_documents, load_documents
from pinecone_setup import ensure_index
from retry import PINECONE_RETRYABLE, run_with_retry

logger = logging.getLogger(__name__)
OPENAI_RETRYABLE = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)


def build_vector_records(
    chunks: list[Document],
    embeddings: list[list[float]],
    dimension: int,
) -> list[dict]:
    if len(chunks) != len(embeddings):
        raise ValueError("Cada chunk debe tener un embedding")

    records = []
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        if len(embedding) != dimension:
            raise ValueError(
                f"Embedding de dimensión {len(embedding)}; se esperaba {dimension}"
            )
        records.append(
            {
                "id": chunk.metadata["chunk_id"],
                "values": embedding,
                "metadata": {
                    "source": chunk.metadata["source"],
                    "page": chunk.metadata["page"],
                    "category": chunk.metadata["category"],
                    "tags": chunk.metadata["tags"],
                    "text": chunk.page_content,
                    "chunk_id": chunk.metadata["chunk_id"],
                },
            }
        )
    return records


async def upsert_batches(
    index,
    records: list[dict],
    namespace: str,
    batch_size: int = 100,
) -> int:
    if batch_size < 1:
        raise ValueError("batch_size debe ser mayor que cero")

    inserted = 0
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]

        async def upsert():
            return await asyncio.to_thread(
                index.upsert,
                vectors=batch,
                namespace=namespace,
            )

        response = await run_with_retry(upsert, PINECONE_RETRYABLE)
        if response["upserted_count"] != len(batch):
            raise RuntimeError(
                "Pinecone no confirmó el lote completo; no se eliminarán vectores."
            )
        inserted += len(batch)
    return inserted


async def ingest_documents(
    settings: Settings,
    data_dir: Path = BASE_DIR / "data",
) -> int:
    started_at = perf_counter()
    source_documents = load_documents(data_dir, strict=True)
    chunks = chunk_documents(source_documents)
    embedding_model = OpenAIEmbeddings(
        model=settings.embedding_model,
        dimensions=settings.embedding_dimension,
        api_key=settings.openai_api_key.get_secret_value(),
        max_retries=0,
    )

    async def embed():
        return await embedding_model.aembed_documents(
            [chunk.page_content for chunk in chunks]
        )

    pinecone = await ensure_index(settings)
    index = await asyncio.to_thread(pinecone.Index, settings.index_name)

    async def list_ids():
        return await asyncio.to_thread(
            lambda: {
                item
                for page in index.list(namespace=settings.namespace)
                for item in page
            }
        )

    previous_ids = await run_with_retry(list_ids, PINECONE_RETRYABLE)
    embeddings = await run_with_retry(embed, OPENAI_RETRYABLE)
    records = build_vector_records(
        chunks,
        embeddings,
        settings.embedding_dimension,
    )
    inserted = await upsert_batches(index, records, settings.namespace)
    current_ids = {record["id"] for record in records}
    removed = await delete_obsolete_vectors(
        index, previous_ids - current_ids, settings.namespace
    )
    logger.info("Vectores obsoletos eliminados: %s", removed)
    logger.info(
        "Ingesta de %s vectores completada en %.3f segundos",
        inserted,
        perf_counter() - started_at,
    )
    return inserted


async def delete_obsolete_vectors(index, obsolete_ids: set[str], namespace: str) -> int:
    if not namespace.strip():
        raise ValueError("La limpieza requiere un namespace explícito")
    ids = sorted(obsolete_ids)
    for start in range(0, len(ids), 100):
        batch = ids[start : start + 100]

        async def delete():
            return await asyncio.to_thread(index.delete, ids=batch, namespace=namespace)

        await run_with_retry(delete, PINECONE_RETRYABLE)
    return len(ids)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    inserted = await ingest_documents(Settings())
    print(f"Vectores insertados: {inserted}")


if __name__ == "__main__":
    asyncio.run(main())
