import asyncio
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ingest import BASE_DIR, get_collection
from schemas import RAGResponse

load_dotenv(BASE_DIR / ".env")


def build_chain():
    parser = PydanticOutputParser(pydantic_object=RAGResponse)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Responde exclusivamente con el CONTEXTO proporcionado. "
                "Si la respuesta no está en el contexto, responde exactamente 'No lo sé' "
                "y usa una lista de referencias vacía.\n\n"
                "CONTEXTO:\n{context}\n\n"
                "{format_instructions}",
            ),
            ("human", "Pregunta: {question}"),
        ]
    )
    model = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
    )
    return prompt | model | parser, parser


def format_context(results: dict) -> str:
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    return "\n\n".join(
        f"Fuente: {metadata['source']} | Fragmento: {metadata['chunk']}\n{document}"
        for document, metadata in zip(documents, metadatas, strict=True)
    )


async def get_rag_response(query: str) -> RAGResponse:
    collection = get_collection()
    results = collection.query(
        query_texts=[query],
        n_results=3,
        include=["documents", "metadatas"],
    )
    chain, parser = build_chain()
    return await chain.ainvoke(
        {
            "question": query,
            "context": format_context(results),
            "format_instructions": parser.get_format_instructions(),
        }
    )


async def main() -> None:
    collection = get_collection()
    if collection.count() == 0:
        print("No hay documentos indexados. Ejecutá primero: python ingest.py")
        return

    questions = [
        "¿Qué tecnología se usa para almacenar las transacciones?",
        "¿Qué sistema de mensajería utiliza PagoClaro?",
    ]

    for question in questions:
        response = await get_rag_response(question)
        print(f"Pregunta: {question}")
        print(f"Respuesta: {response.answer}")
        print(f"Referencias: {response.references}\n")


if __name__ == "__main__":
    asyncio.run(main())
