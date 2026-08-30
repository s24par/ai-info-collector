import httpx

from ai_info_collector.domain import CollectionConfig, SourceConfig
from ai_info_collector.http_client import create_collection_client


def collection_config(retry_count: int = 2) -> CollectionConfig:
    return CollectionConfig(
        retry_count=retry_count,
        sources=[SourceConfig(name="test", url="https://example.com")],
    )


def test_retries_transient_server_errors_for_get_requests() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, request=request)
        return httpx.Response(200, request=request)

    with create_collection_client(
        collection_config(), transport=httpx.MockTransport(handler)
    ) as client:
        response = client.get("https://example.com/feed.xml")

    assert response.status_code == 200
    assert attempts == 3


def test_does_not_retry_post_requests() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, request=request)

    with create_collection_client(
        collection_config(), transport=httpx.MockTransport(handler)
    ) as client:
        response = client.post("https://example.com/feed.xml")

    assert response.status_code == 503
    assert attempts == 1
