from hashlib import sha256
from pathlib import Path

import chromadb
import tiktoken
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VECTORSTORE_DIR = BASE_DIR / "vectorstore"
COLLECTION_NAME = "pagoclaro_knowledge"


def get_collection():
    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
    )


def build_splitter() -> RecursiveCharacterTextSplitter:
    tokenizer = tiktoken.get_encoding("cl100k_base")
    return RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=lambda text: len(tokenizer.encode(text)),
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def ingest_documents() -> int:
    collection = get_collection()
    if collection.count() > 0:
        return collection.count()

    splitter = build_splitter()
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, str | int]] = []

    for source_path in sorted(DATA_DIR.glob("*.md")):
        chunks = splitter.split_text(source_path.read_text(encoding="utf-8"))
        for chunk_index, chunk in enumerate(chunks):
            chunk_id = sha256(
                f"{source_path.name}:{chunk_index}:{chunk}".encode("utf-8")
            ).hexdigest()
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({"source": source_path.name, "chunk": chunk_index})

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(documents)


if __name__ == "__main__":
    indexed_chunks = ingest_documents()
    print(f"Fragmentos disponibles: {indexed_chunks}")
