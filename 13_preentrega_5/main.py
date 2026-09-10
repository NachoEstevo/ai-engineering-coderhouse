import argparse
import asyncio
import json
import logging
import sqlite3
from pathlib import Path

from agent import open_agent, run_turn
from config import Settings
from langgraph.errors import GraphRecursionError
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import ValidationError

logger = logging.getLogger(__name__)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Agente de soporte con memoria SQLite")
    parser.add_argument("query")
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--simulate-failure", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = Settings()
        if args.database:
            settings.database_path = args.database.resolve()
        async with open_agent(settings, args.simulate_failure) as graph:
            result = await run_turn(
                graph, args.query, args.thread_id, settings.recursion_limit
            )
        if args.trace:
            args.trace.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(
                args.trace.write_text,
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(result["respuesta"])
        logger.info("Turno completado en %.3fs", result["segundos"])
        return 0
    except GraphRecursionError:
        logger.error(
            "Se alcanzó el límite de pasos. Retomá con una consulta más específica."
        )
    except (APIConnectionError, APITimeoutError):
        logger.error("No se pudo conectar con OpenAI después de los reintentos.")
    except APIStatusError as error:
        logger.error(
            "OpenAI rechazó la solicitud (HTTP %s). Revisá acceso, clave o cuota.",
            error.status_code,
        )
    except ValidationError:
        logger.error("Configuración inválida. Revisá las variables de .env.")
    except (ValueError, OSError, sqlite3.Error) as error:
        logger.error(
            "No se pudo completar la operación (%s). Revisá entrada y archivos locales.",
            type(error).__name__,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
