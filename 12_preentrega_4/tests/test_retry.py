import asyncio


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
