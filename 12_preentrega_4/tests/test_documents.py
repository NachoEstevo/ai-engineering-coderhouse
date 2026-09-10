import logging

import tiktoken
from langchain_core.documents import Document


def test_load_documents_skips_invalid_files_and_adds_metadata(tmp_path, caplog):
    from documents import load_documents

    (tmp_path / "queues.md").write_text(
        "asyncio Queue distribuye trabajo", encoding="utf-8"
    )
    (tmp_path / "broken.md").write_bytes(b"\xff\xfe\xfa")

    with caplog.at_level(logging.ERROR):
        documents = load_documents(tmp_path)

    assert len(documents) == 1
    assert documents[0].metadata == {
        "source": "queues.md",
        "page": 1,
        "category": "queues",
        "tags": ["asyncio", "queues"],
    }
    assert "broken.md" in caplog.text


def test_chunk_documents_respects_token_limit_and_preserves_metadata():
    from documents import chunk_documents

    source = Document(
        page_content=" ".join(["semaphore"] * 120),
        metadata={
            "source": "semaphore.md",
            "page": 1,
            "category": "synchronization",
            "tags": ["asyncio", "semaphore"],
        },
    )

    chunks = chunk_documents([source], chunk_size=30, chunk_overlap=5)
    tokenizer = tiktoken.get_encoding("cl100k_base")

    assert len(chunks) > 1
    assert all(len(tokenizer.encode(chunk.page_content)) <= 30 for chunk in chunks)
    assert all(chunk.metadata["source"] == "semaphore.md" for chunk in chunks)
    assert all(chunk.metadata["chunk_id"] for chunk in chunks)
    assert len({chunk.metadata["chunk_id"] for chunk in chunks}) == len(chunks)


def test_ids_do_not_change_when_another_document_is_added():
    from documents import chunk_documents

    original = Document(page_content="Contenido estable", metadata={"source": "b.md"})
    inserted = Document(page_content="Documento nuevo", metadata={"source": "a.md"})
    first_id = chunk_documents([original])[0].metadata["chunk_id"]
    later = chunk_documents([inserted, original])
    assert later[1].metadata["chunk_id"] == first_id


def test_strict_loading_stops_before_destructive_synchronization(tmp_path):
    import pytest
    from documents import load_documents

    (tmp_path / "valid.md").write_text("Documento válido", encoding="utf-8")
    (tmp_path / "broken.md").write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="Ingesta detenida"):
        load_documents(tmp_path, strict=True)
