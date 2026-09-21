"""Shared fixtures for the Cleaning Robot API test suite."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from src.app.core import state
from src.app.main import app
from src.app.map.services import process_map_upload

# The part media type we send for every upload, pinned on purpose:
#
#   1. The contract routes on the *filename extension*, never on this header.
#      Sending something wrong-for-everything keeps that honest -- if the
#      implementation ever starts consulting Content-Type, the suite notices.
#   2. Determinism. Letting httpx guess calls mimetypes.guess_type(), which on
#      Windows reads the registry (".csv" resolves to application/vnd.ms-excel
#      here), so the request bytes would differ between machines.
UPLOAD_MEDIA_TYPE = "application/octet-stream"


@pytest.fixture(autouse=True)
def reset_app_state() -> Iterator[None]:
    """Isolate every test from the one before it.

    The map lives in module-level globals with no production reset hook, so the
    fixture rebinds the attributes on the module object. Never
    ``from ... import current_map`` -- that captures a value, not the binding.

    Cleared on both sides: a failing test cannot poison a later one, and the
    session ends clean.
    """

    def clear() -> None:
        state.current_map = None
        state.map_dimensions = {"rows": 0, "cols": 0}  # fresh dict, no aliasing
        state.session_history = []

    clear()
    yield
    clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Used as a context manager so the ASGI lifespan actually runs. Costs
    # nothing today and keeps the suite correct if a lifespan is added later.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def collision_report() -> Callable[[Response], dict[str, Any]]:
    """Pull the error report out of a 409 collision response.

    /clean reports collisions with ``HTTPException(detail=report)``, and
    FastAPI's handler always wraps that in ``{"detail": ...}``, so the report
    arrives one level down rather than as the bare body.

    Every test reads it through here, which keeps the envelope described in a
    single place: if the endpoint ever returns the report at the top level,
    this function is the only thing that changes. The shape assertion below
    makes that switch fail loudly instead of silently skipping the checks.
    """

    def _report(response: Response) -> dict[str, Any]:
        assert response.status_code == 409, f"expected a collision, got {response.status_code}"
        body = response.json()
        assert set(body) == {"detail"}, f"expected the detail envelope, got {sorted(body)}"
        return body["detail"]

    return _report


@pytest.fixture
def load_map() -> Callable[[str], None]:
    """Put a map in place without going through HTTP.

    Cleaning tests are about the robot, not about upload plumbing, so they
    state their world as a TXT grid ("oxo\\nooo") and go straight to the
    parser. Uses the real loader rather than hand-building the tiles dict, so
    these tests stay honest about the shape /clean actually receives.
    """

    def _load(grid: str) -> None:
        process_map_upload("fixture.txt", grid.encode("utf-8"))

    return _load


@pytest.fixture
def upload_map(client: TestClient) -> Callable[..., Response]:
    """PUT a map to /map as multipart/form-data under the field name ``file``.

    Accepts raw bytes (with an explicit filename) or a Path, in which case the
    on-disk name and the on-disk *bytes* are used verbatim: ``read_bytes()``,
    never ``read_text()``, because trailing newlines and CRLF are load-bearing
    here and ``read_text()`` would apply universal-newline translation.
    """

    def _upload(
        content: bytes | Path,
        filename: str | None = None,
        media_type: str = UPLOAD_MEDIA_TYPE,
    ) -> Response:
        if isinstance(content, Path):
            filename = filename if filename is not None else content.name
            content = content.read_bytes()
        assert filename is not None, "filename is required when passing raw bytes"
        return client.put("/map", files={"file": (filename, content, media_type)})

    return _upload
