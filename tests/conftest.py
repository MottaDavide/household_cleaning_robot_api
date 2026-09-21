"""Shared fixtures for the Cleaning Robot API test suite."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from src.app.core import state
from src.app.main import app

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
