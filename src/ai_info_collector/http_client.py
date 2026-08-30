import httpx
from httpx_retries import Retry, RetryTransport

from .domain import CollectionConfig


def create_collection_client(
    config: CollectionConfig, *, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    retry = Retry(
        total=config.retry_count,
        allowed_methods={"GET", "HEAD"},
        status_forcelist={429, 500, 502, 503, 504},
        backoff_factor=0.5,
        respect_retry_after_header=True,
    )
    return httpx.Client(
        transport=RetryTransport(transport=transport, retry=retry),
        timeout=config.timeout_seconds,
        follow_redirects=True,
    )
