"""PUT /map -- the documented HTTP contract, driven by real files on disk.

Every file under ``tests/fixtures/maps/<bucket>/`` is a test case:

    valid/                  -> 200, body taken from valid/_expected.json
    unsupported_extension/  -> 415
    invalid_content/        -> 422

Adding a case means dropping in a file. No test code changes.

Reading the JSON block: ``valid/spec_example_2x3.json`` is the **positive
control** for the whole JSON corpus. While it is red, every
``invalid_content/*.json`` case is green for the wrong reason -- if no ``.json``
upload can be parsed at all, rejecting one proves nothing. Always read
``valid/`` first.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from httpx import Response

from tests.map_cases import MAP_CASES, REJECTED_CASES, VALID_CASES, MapCase

Upload = Callable[..., Response]


@pytest.mark.parametrize("case", MAP_CASES, ids=str)
def test_upload_returns_the_documented_status(upload_map: Upload, case: MapCase) -> None:
    response = upload_map(case.path)

    assert response.status_code == case.expected_status, (
        f"{case} -> {response.status_code}: {response.text[:200]}"
    )


@pytest.mark.parametrize("case", VALID_CASES, ids=str)
def test_accepted_map_is_summarised_correctly(upload_map: Upload, case: MapCase) -> None:
    response = upload_map(case.path)

    # Exact equality: the summary has these three keys and nothing else.
    assert response.json() == case.expected_body


@pytest.mark.parametrize("case", REJECTED_CASES, ids=str)
def test_rejected_map_explains_itself(upload_map: Upload, case: MapCase) -> None:
    """The contract leaves the error body to us, so pin its shape, never its wording."""
    response = upload_map(case.path)

    assert response.headers["content-type"].startswith("application/json")
    assert response.json().get("detail"), f"{case} was rejected with no detail"


@pytest.mark.parametrize("case", VALID_CASES, ids=str)
def test_dispatch_is_by_filename_not_by_media_type(upload_map: Upload, case: MapCase) -> None:
    """The contract keys off the filename extension. Prove the header is ignored.

    Cheap to run over the whole valid corpus, and it pins a rule that is easy to
    break the first time someone "improves" the validation.
    """
    assert upload_map(case.path, media_type="image/png").status_code == 200
