"""GET /health and the startup contract from the assignment."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_exactly_the_documented_body(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    # Equality, not a subset check: the contract says "Return exactly", so an
    # extra key is a contract violation.
    assert response.json() == {"status": "ok"}


def test_health_is_json(client: TestClient) -> None:
    assert client.get("/health").headers["content-type"].startswith("application/json")


def test_openapi_schema_is_served_and_documents_both_routes(client: TestClient) -> None:
    """"expose FastAPI documentation at /docs and its schema at /openapi.json"."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert {"/health", "/map"} <= set(paths)
    assert "get" in paths["/health"]
    assert "put" in paths["/map"]


def test_docs_page_is_served(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
