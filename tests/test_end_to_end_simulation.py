"""One long session against the running API, exercising the whole contract.

Every other module tests a rule in isolation. This one plays a realistic
sequence end to end and checks that the features agree with each other -- the
places where two correct-looking units still disagree:

* a map loaded as TXT and a map loaded as JSON feed the same robot;
* cleaning mutates state that the *next* session observes;
* replacing the map resets dirt but must not touch history;
* every session, completed or collided, must reappear in the CSV export with
  the exact values its JSON report carried.

The last point is the reason this test exists. /clean and /history are written
independently and share only the history list, so a field renamed on one side
is invisible until something reads both.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.map_cases import FIXTURES_ROOT

# oooo   A 3x4 map with a wall across the middle: the only way between the top
# oxxo   and bottom rows is along the left or the right edge.
# oooo
MAP_A = b"oooo\noxxo\noooo"

# The JSON example from the contract: 2x3, one non-walkable tile at (2, 0), and
# (1, 0) already clean -- which is what makes the premium rule observable.
MAP_B = FIXTURES_ROOT / "valid" / "spec_example_2x3.json"


def clean(client: TestClient, start: tuple[int, int], model: str, *actions: tuple[str, int]):
    return client.post(
        "/clean",
        json={
            "start": {"x": start[0], "y": start[1]},
            "robot_model": model,
            "actions": [{"direction": d, "steps": s} for d, s in actions],
        },
    )


def coords(report: dict[str, Any]) -> list[tuple[int, int]]:
    return [(t["x"], t["y"]) for t in report["cleaned_tiles"]]


def test_full_cleaning_campaign_is_consistent_from_upload_to_csv(
    client: TestClient,
    upload_map: Callable[..., Any],
    collision_report: Callable[[Any], dict[str, Any]],
) -> None:
    reports: list[dict[str, Any]] = []

    # -- the service is up ------------------------------------------------
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/history").text.startswith("id,started_at,state")

    # -- load the TXT map --------------------------------------------------
    assert upload_map(MAP_A, filename="apartment.txt").json() == {
        "rows": 3,
        "cols": 4,
        "walkable_tiles": 10,
    }

    # -- 1. a basic robot walks the perimeter and cleans all nine tiles ----
    response = clean(client, (0, 0), "basic", ("east", 3), ("south", 2), ("west", 3))
    assert response.status_code == 200
    report = response.json()
    reports.append(report)
    assert report["state"] == "completed"
    assert report["submitted_actions"] == 3
    assert report["successful_steps"] == 8
    assert coords(report) == [
        (0, 0), (1, 0), (2, 0), (3, 0),  # east along the top
        (3, 1), (3, 2),                  # south down the right edge
        (2, 2), (1, 2), (0, 2),          # west along the bottom
    ]
    assert report["final_position"] == {"x": 0, "y": 2}

    # -- 2. premium repeats the lap and finds nothing left to do -----------
    response = clean(client, (0, 0), "premium", ("east", 3), ("south", 2), ("west", 3))
    assert response.status_code == 200
    report = response.json()
    reports.append(report)
    assert report["state"] == "completed"
    assert report["successful_steps"] == 8, "it still walked the whole route"
    assert coords(report) == [], "every tile on the route was already clean"

    # -- 3. basic drives into the wall -------------------------------------
    # (0, 1) was never visited by the perimeter lap, so it is still dirty and
    # gets cleaned before the collision -- "preserve cleaning operations
    # already performed".
    report = collision_report(clean(client, (0, 0), "basic", ("south", 1), ("east", 1)))
    reports.append(report)
    assert report["state"] == "error"
    assert report["error"]["code"] == "collision"
    assert report["error"]["position"] == {"x": 1, "y": 1}, "the tile it tried to enter"
    assert report["final_position"] == {"x": 0, "y": 1}, "the last valid tile"
    assert report["successful_steps"] == 1
    assert coords(report) == [(0, 0), (0, 1)]

    # -- swap in the JSON map ----------------------------------------------
    assert upload_map(MAP_B).json() == {"rows": 2, "cols": 3, "walkable_tiles": 5}
    assert len(list(csv.reader(io.StringIO(client.get("/history").text)))) == 1 + 3, (
        "loading a map must not erase history"
    )

    # -- 4. premium on the fresh map: the contract's own example -----------
    # (0, 0) is dirty and gets cleaned; (1, 0) arrives already clean and is
    # skipped. The dirt from the new file is what makes (0, 0) dirty again.
    response = clean(client, (0, 0), "premium", ("east", 1))
    assert response.status_code == 200
    report = response.json()
    reports.append(report)
    assert coords(report) == [(0, 0)]
    assert report["successful_steps"] == 1

    # -- 5. basic walks off the eastern edge -------------------------------
    report = collision_report(clean(client, (2, 1), "basic", ("east", 1)))
    reports.append(report)
    assert report["error"]["position"] == {"x": 3, "y": 1}, "outside the map, still reported"
    assert report["successful_steps"] == 0
    assert coords(report) == [(2, 1)], "the start tile was processed before the failed step"

    # -- the CSV export must agree with all five reports -------------------
    export = client.get("/history")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")

    rows = list(csv.DictReader(io.StringIO(export.text, newline="")))
    assert len(rows) == 5, "every session that ran, completed or not"
    assert [r["state"] for r in rows] == [
        "completed",
        "completed",
        "error",
        "completed",
        "error",
    ]

    for index, (row, source) in enumerate(zip(rows, reports, strict=True)):
        because = f"row {index} disagrees with the report /clean returned"
        assert row["id"] == source["id"], because
        assert row["started_at"] == source["started_at"], because
        assert row["state"] == source["state"], because
        assert row["robot_model"] == source["robot_model"], because
        assert row["submitted_actions"] == str(source["submitted_actions"]), because
        assert row["successful_steps"] == str(source["successful_steps"]), because
        assert row["cleaned_tiles"] == str(len(source["cleaned_tiles"])), because
        assert row["duration_ms"] == str(source["duration_ms"]), because

    assert len({r["id"] for r in rows}) == 5, "session identifiers must be unique"
