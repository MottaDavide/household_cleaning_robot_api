"""PUT /map at the HTTP level: things no map file on disk can express.

Multipart wiring, filename edge cases, media-type independence, method routing,
and the two byte-level inputs that cannot honestly live in a committed text
file. The rule the corpus follows:

    A case lives on disk when its meaning is visible when you open the file.
    A case lives inline here when its meaning is *invisible* -- encodings,
    byte-order marks, bytes that are not text at all.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from tests.map_cases import FIXTURES_ROOT

Upload = Callable[..., Response]

VALID_TXT = FIXTURES_ROOT / "valid" / "spec_example_3x4.txt"
VALID_JSON = FIXTURES_ROOT / "valid" / "spec_example_2x3.json"


# --------------------------------------------------------------- multipart

def test_request_without_a_body_is_rejected(client: TestClient) -> None:
    response = client.put("/map")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_field_must_be_named_file(client: TestClient) -> None:
    """The contract names the multipart field: "using the field name `file`"."""
    response = client.put("/map", files={"map": ("m.txt", b"oo\noo", "text/plain")})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_plain_form_field_is_not_accepted_as_a_file(client: TestClient) -> None:
    response = client.put("/map", data={"file": "oo\noo"})

    assert response.status_code == 422


def test_empty_filename_is_an_unsupported_extension(client: TestClient) -> None:
    """A real file part whose filename is empty has no extension, so: 415.

    Hand-built because httpx cannot express it -- ``files={"file": ("", ...)}``
    degrades to a plain form field, which FastAPI rejects as 422 before the
    route ever runs. That would test the client, not the service.
    """
    boundary = "cleaningrobotboundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename=""\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
        "oo\r\noo\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    response = client.put(
        "/map",
        content=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    assert response.status_code == 415


# --------------------------------------------------------------- filenames

@pytest.mark.parametrize("filename", ["map.txt", "map.TXT", "map.TxT", "MAP.Txt"])
def test_extension_is_compared_case_insensitively(upload_map: Upload, filename: str) -> None:
    assert upload_map(b"oo\noo", filename=filename).status_code == 200


def test_dotfile_named_only_txt_has_no_extension(upload_map: Upload) -> None:
    """``Path(".txt").suffix`` is "" -- a leading dot makes it a stem, not a suffix."""
    assert upload_map(b"oo\noo", filename=".txt").status_code == 415


def test_only_the_last_suffix_counts(upload_map: Upload) -> None:
    assert upload_map(b"oo\noo", filename="map.txt.gz").status_code == 415


# ------------------------------------------------------- media independence

def test_valid_txt_sent_as_an_image_is_still_accepted(upload_map: Upload) -> None:
    assert upload_map(VALID_TXT, media_type="image/png").status_code == 200


def test_unsupported_extension_sent_as_text_is_still_rejected(upload_map: Upload) -> None:
    assert upload_map(b"oo\noo", filename="map.csv", media_type="text/plain").status_code == 415


# ------------------------------------------------------------ byte-level

def test_non_utf8_txt_is_a_content_error_not_a_crash(upload_map: Upload) -> None:
    """Undecodable bytes are "contents that do not describe a valid map": 422.

    The on-disk twin of this case is invalid_content/non_utf8_bytes.txt; this
    one states the rule in bytes, where it cannot be mangled by tooling.
    """
    assert upload_map(b"\xff\xfeo\no", filename="map.txt").status_code == 422


def test_utf8_bom_is_not_a_tile_character(upload_map: Upload) -> None:
    """A BOM decodes cleanly but is not "o" or "x", and only those are valid.

    The contract does not mention byte-order marks, so this is the strict
    reading of "only lowercase o and x are valid tile characters" rather than a
    documented rule. Recorded here so the choice is visible and easy to revisit.
    """
    assert upload_map(b"\xef\xbb\xbfoo\noo", filename="map.txt").status_code == 422


# --------------------------------------------------------------- routing

@pytest.mark.parametrize("method", ["get", "post", "delete", "patch"])
def test_map_only_answers_put(client: TestClient, method: str) -> None:
    assert getattr(client, method)("/map").status_code == 405
