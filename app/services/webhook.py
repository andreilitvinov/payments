import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from tenacity import retry_if_exception


def _is_retriable(exc: Exception) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


async def send_webhook_with_retry(
    webhook_url: str,
    payload: dict,
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> None:
    max_wait = base_delay_seconds * 4 if base_delay_seconds > 0 else 0

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=base_delay_seconds,
            min=base_delay_seconds,
            max=max_wait,
        ),
        retry=retry_if_exception(_is_retriable),
        reraise=True,
    )
    async def _send() -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()

    await _send()
