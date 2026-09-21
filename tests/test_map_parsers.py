"""Unit tests for the map parsers in src/app/map/services.py.

The split from the HTTP tests follows one rule: if an assertion is expressible
in the HTTP response, it is tested through HTTP; if it is about internal domain
state or about which exception type crosses the service/router boundary, it is
tested here. Nothing is asserted in both places.

Two things only exist at this layer:

* the *shape* of the tiles dictionary -- coordinate orientation and per-tile
  cleanliness, neither of which the three-number summary can reveal;
* the exception-type contract the router's 415/422 mapping is built on.

Error messages are deliberately never asserted. The contract says the error
body is ours to choose, and pinning wording here would break on every rewording
while proving nothing.
"""

from __future__ import annotations

import pytest

from src.app.core import state
from src.app.map.exceptions import InvalidMapContentError, UnsupportedExtensionError
from src.app.map.services import _parse_json_map, _parse_txt_map, process_map_upload


def json_map(tiles: str, rows: int = 1, cols: int = 1) -> bytes:
    return f'{{"rows": {rows}, "cols": {cols}, "tiles": [{tiles}]}}'.encode()


# ------------------------------------------------------------- orientation

def test_txt_tiles_are_keyed_by_x_then_y() -> None:
    """(0, 0) is top-left, x runs east, y runs south.

    The most valuable assertion in the suite, because it is the one the API
    cannot make. A transposed implementation still reports the right rows, cols
    and walkable_tiles -- and then every (x + 1, y) step in POST /clean walks
    the wrong axis. The map is deliberately non-square and asymmetric so a
    transposition cannot pass by coincidence.
    """
    tiles, rows, cols = _parse_txt_map("oxx\nxxx")

    assert (rows, cols) == (2, 3)
    assert set(tiles) == {(x, y) for x in range(3) for y in range(2)}
    assert tiles[(0, 0)]["walkable"] is True
    assert tiles[(1, 0)]["walkable"] is False  # east of the start
    assert tiles[(0, 1)]["walkable"] is False  # south of the start


def test_txt_parses_every_row_not_just_the_first() -> None:
    tiles, rows, cols = _parse_txt_map("oxoo\nooxo\noooo")

    assert (rows, cols) == (3, 4)
    assert len(tiles) == 12
    assert sum(1 for t in tiles.values() if t["walkable"]) == 10


# ------------------------------------------------------------- cleanliness

def test_txt_walkable_tiles_start_dirty() -> None:
    tiles, _, _ = _parse_txt_map("ox")

    assert tiles[(0, 0)] == {"walkable": True, "dirty": True}
    assert tiles[(1, 0)] == {"walkable": False, "dirty": False}


@pytest.mark.parametrize(
    ("tile_json", "expected_dirty"),
    [
        ('{"x": 0, "y": 0, "walkable": true}', True),  # omitted -> starts dirty
        ('{"x": 0, "y": 0, "walkable": true, "dirty": true}', True),
        ('{"x": 0, "y": 0, "walkable": true, "dirty": false}', False),
        ('{"x": 0, "y": 0, "walkable": false}', False),
        ('{"x": 0, "y": 0, "walkable": false, "dirty": false}', False),
    ],
)
def test_json_cleanliness_matrix(tile_json: str, expected_dirty: bool) -> None:
    """The rule set with the most branches and no API visibility at all."""
    tiles, _, _ = _parse_json_map(json_map(tile_json))

    assert tiles[(0, 0)]["dirty"] is expected_dirty


def test_json_non_walkable_tile_cannot_be_dirty() -> None:
    with pytest.raises(InvalidMapContentError):
        _parse_json_map(json_map('{"x": 0, "y": 0, "walkable": false, "dirty": true}'))


def test_json_origin_tile_is_inside_the_bounds() -> None:
    """Coordinates are zero-based, so (0, 0) is the top-left tile, not out of range."""
    tiles, _, _ = _parse_json_map(json_map('{"x": 0, "y": 0, "walkable": true}'))

    assert (0, 0) in tiles


# ------------------------------------------------- exception-type contract

def test_unsupported_extension_raises_before_the_content_is_read() -> None:
    """Undecodable bytes behind a bad extension must still be an extension error.

    This is what makes 415 beat 422 at the HTTP layer.
    """
    with pytest.raises(UnsupportedExtensionError):
        process_map_upload("map.csv", b"\xff\xfe")


def test_undecodable_txt_raises_a_content_error_not_unicode_decode_error() -> None:
    """The router only maps InvalidMapContentError to 422; anything else is a 500."""
    with pytest.raises(InvalidMapContentError):
        process_map_upload("map.txt", b"\xff\xfeo\no")


@pytest.mark.parametrize(
    "content",
    [b"{", b"[]", b'{"rows": 1, "cols": 1}', b'{"rows": 0, "cols": 1, "tiles": []}'],
    ids=["syntax", "root-array", "no-tiles", "rows-not-positive"],
)
def test_structural_json_failures_raise_a_content_error(content: bytes) -> None:
    with pytest.raises(InvalidMapContentError):
        _parse_json_map(content)


# -------------------------------------------------------- state and result

def test_process_map_upload_returns_only_the_summary_keys() -> None:
    summary = process_map_upload("map.txt", b"oxoo\nooxo\noooo")

    assert summary == {"rows": 3, "cols": 4, "walkable_tiles": 10}


def test_process_map_upload_publishes_state_but_keeps_history() -> None:
    state.session_history.append({"id": "sentinel"})

    process_map_upload("map.txt", b"ox")

    assert state.map_dimensions == {"rows": 1, "cols": 2}
    assert state.current_map[(0, 0)]["walkable"] is True
    assert state.session_history == [{"id": "sentinel"}]
