"""What an upload does to the world model, observed through the API.

The 200 summary reports three numbers, so most of what PUT /map actually *does*
is invisible at the HTTP layer. These tests cover the three contract rules
about that hidden state:

    "replaces the previous map"
    "resets all tile cleanliness according to the new file"
    "does not erase cleaning-session history"

This is the contract POST /clean will consume, which is why it is worth pinning
before /clean exists.
"""

from __future__ import annotations

from collections.abc import Callable

from httpx import Response

from src.app.core import state
from tests.map_cases import FIXTURES_ROOT

Upload = Callable[..., Response]

SPEC_3X4 = FIXTURES_ROOT / "valid" / "spec_example_3x4.txt"
MIN_1X1 = FIXTURES_ROOT / "valid" / "min_1x1_walkable.txt"
RAGGED = FIXTURES_ROOT / "invalid_content" / "ragged_shorter_row.txt"
WRONG_EXTENSION = FIXTURES_ROOT / "unsupported_extension" / "map.csv"


def test_successful_upload_publishes_the_map(upload_map: Upload) -> None:
    assert upload_map(SPEC_3X4).status_code == 200

    assert state.map_dimensions == {"rows": 3, "cols": 4}
    assert len(state.current_map) == 12


def test_loading_a_new_map_replaces_the_previous_one(upload_map: Upload) -> None:
    upload_map(SPEC_3X4)

    response = upload_map(MIN_1X1)

    assert response.json() == {"rows": 1, "cols": 1, "walkable_tiles": 1}
    assert state.map_dimensions == {"rows": 1, "cols": 1}
    # The 3x4 map is gone entirely, not merged into the new one.
    assert set(state.current_map) == {(0, 0)}


def test_reloading_a_map_resets_cleanliness(upload_map: Upload) -> None:
    """"resets all tile cleanliness according to the new file"."""
    upload_map(SPEC_3X4)
    # Simulate a cleaning session having swept the map.
    for tile in state.current_map.values():
        tile["dirty"] = False

    upload_map(SPEC_3X4)

    walkable = [t for t in state.current_map.values() if t["walkable"]]
    assert walkable and all(t["dirty"] for t in walkable)


def test_loading_a_map_does_not_erase_history(upload_map: Upload) -> None:
    """"does not erase cleaning-session history".

    Assertable today with a sentinel, even though nothing writes history yet.
    """
    state.session_history.append({"id": "sentinel"})

    upload_map(SPEC_3X4)

    assert state.session_history == [{"id": "sentinel"}]


def test_a_rejected_upload_leaves_the_current_map_untouched(upload_map: Upload) -> None:
    """Nothing was loaded, so nothing should have been replaced.

    Inferred from "loading a new map replaces the previous" rather than stated
    outright -- but it becomes load-bearing the moment POST /clean can run
    between two uploads.
    """
    upload_map(SPEC_3X4)
    before = {k: dict(v) for k, v in state.current_map.items()}

    assert upload_map(WRONG_EXTENSION).status_code == 415
    assert upload_map(RAGGED).status_code == 422

    assert state.current_map == before
    assert state.map_dimensions == {"rows": 3, "cols": 4}
