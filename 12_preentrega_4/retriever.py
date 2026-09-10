import asyncio
import logging
from time import perf_counter

from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from pinecone import Pinecone

from config import BASE_DIR, Settings
from documents import chunk_documents, load_documents
from retry import PINECONE_RETRYABLE, run_with_retry

logger = logging.getLogger(__name__)
RETRIEVAL_RETRYABLE = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
    *PINECONE_RETRYABLE,
)


class RAGSystem:
    def __init__(self, ensemble_retriever, top_k: int = 5):
        self.ensemble_retriever = ensemble_retriever
        self.top_k = top_k

    @classmethod
    async def create(cls, settings: Settings) -> "RAGSystem":
        documents = chunk_documents(load_documents(BASE_DIR / "data"))
        bm25 = BM25Retriever.from_documents(documents)
        bm25.k = settings.top_k * 2

        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            dimensions=settings.embedding_dimension,
            api_key=settings.openai_api_key.get_secret_value(),
            max_retries=0,
        )
        pinecone = Pinecone(api_key=settings.pinecone_api_key.get_secret_value())
        index = await asyncio.to_thread(pinecone.Index, settings.index_name)
        vector_store = PineconeVectorStore(
            index=index,
            embedding=embeddings,
            namespace=settings.namespace,
            text_key="text",
        )
        vector_retriever = vector_store.as_retriever(
            search_kwargs={"k": settings.top_k * 2}
        )
        ensemble = EnsembleRetriever(
            retrievers=[bm25, vector_retriever],
            weights=[0.4, 0.6],
            id_key="chunk_id",
        )
        return cls(ensemble, settings.top_k)

    async def retrieve(self, query: str) -> list[Document]:
        started_at = perf_counter()

        async def search():
            return await self.ensemble_retriever.ainvoke(query)

        documents = await run_with_retry(search, RETRIEVAL_RETRYABLE)
        sources = set()
        result = []
        for document in documents:
            source = document.metadata["source"]
            if source not in sources:
                sources.add(source)
                result.append(document)
            if len(result) == self.top_k:
                break
        logger.info(
            "Recuperación de %s documentos completada en %.3f segundos",
            len(result),
            perf_counter() - started_at,
        )
        return result
