import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


async def run_with_retry(
    operation: Callable[[], Awaitable[T]],
    retryable_exceptions: tuple[type[BaseException], ...],
    attempts: int = 3,
    base_delay: float = 1.0,
) -> T:
    if attempts < 1:
        raise ValueError("attempts debe ser mayor que cero")

    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except retryable_exceptions as error:
            if attempt == attempts:
                raise
            delay = base_delay * 2 ** (attempt - 1)
            logger.warning(
                "Intento %s/%s falló con %s. Reintento en %.1f segundos",
                attempt,
                attempts,
                type(error).__name__,
                delay,
            )
            await asyncio.sleep(delay)

    raise RuntimeError("No se pudo completar la operación")
