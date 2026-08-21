import logging
import os

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from schemas import ExtraccionTecnica


logger = logging.getLogger(__name__)

INSTRUCCIONES_EXTRACCION = (
    "Extraé entidades técnicas del texto. Identificá tecnologías concretas, "
    "estimá la criticidad y redactá un resumen técnico. No inventes tecnologías "
    "que no estén presentes en el texto."
)

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "{instrucciones}"),
        ("human", "Texto a analizar:\n{texto}"),
    ]
)


def create_chain() -> Runnable:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Falta OPENAI_API_KEY en el archivo .env")

    model = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        api_key=api_key,
    )
    return (PROMPT | model.with_structured_output(ExtraccionTecnica)).with_retry(
        stop_after_attempt=2,
        retry_if_exception_type=(Exception,),
    )


async def process_text(text: str, pipeline: Runnable | None = None) -> ExtraccionTecnica:
    if not text.strip():
        raise ValueError("El texto de entrada no puede estar vacío")

    chain = pipeline or create_chain()
    logger.info("Iniciando validación técnica con LCEL; máximo de intentos: 2")

    try:
        result = await chain.ainvoke({"texto": text, "instrucciones": INSTRUCCIONES_EXTRACCION})
    except Exception:
        logger.exception("La extracción falló después de los reintentos")
        raise

    logger.info("Extracción validada: %s tecnologías; criticidad %s", len(result.tecnologias), result.nivel_de_criticidad.value)
    return result
