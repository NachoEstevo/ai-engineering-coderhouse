import asyncio
import pytest
from pinecone.exceptions import PineconeApiException


def test_run_with_retry_recovers_from_retryable_error():
    from retry import run_with_retry

    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("temporary")
        return "ok"

    result = asyncio.run(
        run_with_retry(operation, (ConnectionError,), attempts=3, base_delay=0)
    )

    assert result == "ok"
    assert attempts == 3


def test_run_with_retry_does_not_swallow_non_retryable_error():
    from retry import run_with_retry

    async def operation():
        raise ValueError("invalid")

    try:
        asyncio.run(run_with_retry(operation, (ConnectionError,), base_delay=0))
    except ValueError as error:
        assert str(error) == "invalid"
    else:
        raise AssertionError("ValueError debía propagarse")


@pytest.mark.parametrize(
    "status, expected_attempts", [(400, 1), (401, 1), (403, 1), (429, 3), (503, 3)]
)
def test_pinecone_retries_only_transient_statuses(status, expected_attempts):
    from retry import run_with_retry

    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        raise PineconeApiException(status=status)

    with pytest.raises(PineconeApiException):
        asyncio.run(run_with_retry(operation, (PineconeApiException,), base_delay=0))
    assert calls == expected_attempts
