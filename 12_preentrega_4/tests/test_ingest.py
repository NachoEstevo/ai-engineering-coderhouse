import asyncio

from langchain_core.documents import Document


class FakeIndex:
    def __init__(self):
        self.calls = []

    def upsert(self, **kwargs):
        self.calls.append(kwargs)
        return {"upserted_count": len(kwargs["vectors"])}


def test_build_vector_records_includes_content_and_metadata():
    from ingest import build_vector_records

    chunk = Document(
        page_content="asyncio.Semaphore limita concurrencia",
        metadata={
            "chunk_id": "sync-1",
            "source": "synchronization.md",
            "page": 1,
            "category": "synchronization",
            "tags": ["asyncio", "semaphore"],
        },
    )

    records = build_vector_records([chunk], [[0.1, 0.2, 0.3]], dimension=3)

    assert records == [
        {
            "id": "sync-1",
            "values": [0.1, 0.2, 0.3],
            "metadata": {
                "source": "synchronization.md",
                "page": 1,
                "category": "synchronization",
                "tags": ["asyncio", "semaphore"],
                "text": "asyncio.Semaphore limita concurrencia",
                "chunk_id": "sync-1",
            },
        }
    ]


def test_upsert_batches_uses_namespace_and_batch_size():
    from ingest import upsert_batches

    index = FakeIndex()
    records = [
        {"id": str(number), "values": [0.1], "metadata": {"text": str(number)}}
        for number in range(5)
    ]

    count = asyncio.run(
        upsert_batches(index, records, namespace="asyncio-docs", batch_size=2)
    )

    assert count == 5
    assert [len(call["vectors"]) for call in index.calls] == [2, 2, 1]
    assert all(call["namespace"] == "asyncio-docs" for call in index.calls)


def test_cleanup_only_deletes_explicit_ids_in_target_namespace():
    from ingest import delete_obsolete_vectors

    class FakeDeletionIndex:
        def __init__(self):
            self.calls = []

        def delete(self, **kwargs):
            self.calls.append(kwargs)

    index = FakeDeletionIndex()
    assert (
        asyncio.run(delete_obsolete_vectors(index, {"old-1", "old-2"}, "course")) == 2
    )
    assert index.calls == [{"ids": ["old-1", "old-2"], "namespace": "course"}]


def test_failed_upsert_never_deletes_existing_vectors(tmp_path, monkeypatch):
    import pytest
    import ingest
    from config import Settings

    (tmp_path / "a.md").write_text("Nuevo contenido", encoding="utf-8")
    deleted = []

    class FakeEmbeddingModel:
        def __init__(self, **kwargs):
            self.dimension = kwargs["dimensions"]

        async def aembed_documents(self, texts):
            return [[0.1] * self.dimension for _ in texts]

    class FailingIndex:
        def list(self, namespace):
            yield ["old-id"]

        def upsert(self, **kwargs):
            raise ValueError("Carga fallida")

        def delete(self, **kwargs):
            deleted.append(kwargs)

    class FakePinecone:
        def Index(self, name):
            return FailingIndex()

    async def ensure(settings):
        return FakePinecone()

    monkeypatch.setattr(ingest, "OpenAIEmbeddings", FakeEmbeddingModel)
    monkeypatch.setattr(ingest, "ensure_index", ensure)
    settings = Settings(
        pinecone_api_key="fake", openai_api_key="fake", index_name="test"
    )
    with pytest.raises(ValueError, match="Carga fallida"):
        asyncio.run(ingest.ingest_documents(settings, tmp_path))
    assert deleted == []
