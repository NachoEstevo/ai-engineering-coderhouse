import logging
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

import tiktoken
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


def load_documents(data_dir: Path, strict: bool = False) -> list[Document]:
    documents = []
    for path in sorted(data_dir.glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            logger.error("No se pudo leer %s: %s", path.name, error)
            if strict:
                raise ValueError(
                    f"Ingesta detenida: no se pudo leer {path.name}"
                ) from error
            continue

        if not content.strip():
            if strict:
                raise ValueError(f"Ingesta detenida: {path.name} está vacío")
            continue

        category = path.stem.replace("_", "-")
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": path.name,
                    "page": 1,
                    "category": category,
                    "tags": ["asyncio", path.stem],
                },
            )
        )

    if not documents:
        raise ValueError(f"No se encontraron documentos válidos en {data_dir}")
    return documents


def chunk_documents(
    documents: list[Document],
    chunk_size: int = 600,
    chunk_overlap: int = 80,
) -> list[Document]:
    tokenizer = tiktoken.get_encoding("cl100k_base")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=lambda text: len(tokenizer.encode(text)),
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    split_chunks = splitter.split_documents(documents)
    chunks = []
    token_step = chunk_size - chunk_overlap
    for chunk in split_chunks:
        tokens = tokenizer.encode(chunk.page_content)
        if len(tokens) <= chunk_size:
            chunks.append(chunk)
            continue
        for start in range(0, len(tokens), token_step):
            token_slice = tokens[start : start + chunk_size]
            chunks.append(
                Document(
                    page_content=tokenizer.decode(token_slice).strip(),
                    metadata=chunk.metadata.copy(),
                )
            )
            if start + chunk_size >= len(tokens):
                break

    positions = defaultdict(int)
    for chunk in chunks:
        source = chunk.metadata["source"]
        position = positions[source]
        identity = f"{source}:{position}:{chunk.page_content}"
        chunk.metadata["chunk_id"] = sha256(identity.encode("utf-8")).hexdigest()
        positions[source] += 1
    return chunks
