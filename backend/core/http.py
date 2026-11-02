import logging
import time
from typing import Any

import httpx

from core.errors import UpstreamError

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2
RETRY_DELAY_S = 0.3

client = httpx.Client(
    timeout=httpx.Timeout(10, connect=3), headers={"User-Agent": "spotter-truck-routing/1.0"}
)


def _retryable(status: int) -> bool:
    return status == 429 or status >= 500


def request_json(method: str, url: str, *, service: str, **kwargs) -> Any:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            logger.warning("%s request failed (attempt %d): %r", service, attempt, exc)
            if attempt == MAX_ATTEMPTS:
                raise UpstreamError(service) from exc
        except httpx.HTTPError as exc:
            logger.warning("%s request failed: %r", service, exc)
            raise UpstreamError(service) from exc
        else:
            if not response.is_error:
                break
            logger.warning(
                "%s returned HTTP %d (attempt %d)", service, response.status_code, attempt
            )
            if not _retryable(response.status_code) or attempt == MAX_ATTEMPTS:
                raise UpstreamError(service, response.status_code, response.text[:500])
        time.sleep(RETRY_DELAY_S)
    try:
        return response.json()
    except ValueError as exc:
        logger.warning("%s returned invalid JSON", service)
        raise UpstreamError(service, response.status_code, response.text[:500]) from exc
