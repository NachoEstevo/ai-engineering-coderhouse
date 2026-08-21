import asyncio
import json
import logging

from chain import process_text


TEXT = """
La API de pagos en FastAPI comenzó a responder con errores 503. Redis presenta
latencia elevada y PostgreSQL agotó el pool de conexiones concurrentes.
"""


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    result = await process_text(TEXT)
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
