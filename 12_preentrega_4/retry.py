import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pinecone.exceptions import PineconeApiException
from urllib3.exceptions import MaxRetryError, ProtocolError
from urllib3.exceptions import TimeoutError as HTTPTimeoutError

T = TypeVar("T")
logger = logging.getLogger(__name__)
PINECONE_RETRYABLE = (
    PineconeApiException,
    ProtocolError,
    HTTPTimeoutError,
    MaxRetryError,
)


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
            if isinstance(error, PineconeApiException):
                status = error.status or 0
                if status not in (408, 429) and not 500 <= status < 600:
                    raise
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
