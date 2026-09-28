import asyncio
import json
import logging
import re
import unicodedata
from pathlib import Path

from langchain_core.tools import StructuredTool, tool
from pydantic import ValidationError

from state import Source

logger = logging.getLogger(__name__)
STOPWORDS = {
    "a",
    "al",
    "como",
    "con",
    "cual",
    "de",
    "del",
    "el",
    "en",
    "es",
    "esta",
    "estos",
    "la",
    "las",
    "lo",
    "los",
    "o",
    "para",
    "por",
    "que",
    "se",
    "sin",
    "son",
    "su",
    "un",
    "una",
    "y",
}


def tokens(text: str) -> set[str]:
    normalized = "".join(
        c
        for c in unicodedata.normalize("NFD", text.casefold())
        if not unicodedata.combining(c)
    )
    return set(re.findall(r"[a-z0-9]+", normalized)) - STOPWORDS


def search_documents(query: str, directory: Path) -> dict:
    matches = []
    errors = []
    try:
        paths = sorted(directory.glob("*.json"))
        if not directory.is_dir():
            raise FileNotFoundError
    except OSError as exc:
        return {
            "sources": [],
            "errors": [{"file": directory.name, "type": type(exc).__name__}],
        }
    query_tokens = tokens(query)
    for path in paths:
        try:
            source = Source.model_validate(json.loads(path.read_text(encoding="utf-8")))
            score = len(query_tokens & tokens(source.text + " " + source.title))
            if score:
                matches.append((score, source))
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
            error = {"file": path.name, "type": type(exc).__name__}
            errors.append(error)
            logger.warning(
                "document_error file=%s type=%s", path.name, type(exc).__name__
            )
    matches.sort(key=lambda item: (-item[0], item[1].id))
    return {"sources": [s.model_dump() for _, s in matches[:3]], "errors": errors}


def make_research_tool(directory: Path) -> StructuredTool:
    @tool
    async def buscar_fuentes(query: str) -> dict:
        """Busca coincidencias léxicas reales en documentos locales de estadística y devuelve hasta tres textos citados y errores por archivo."""
        return await asyncio.to_thread(search_documents, query, directory)

    return buscar_fuentes
