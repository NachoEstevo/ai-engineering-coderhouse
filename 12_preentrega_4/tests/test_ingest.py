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
