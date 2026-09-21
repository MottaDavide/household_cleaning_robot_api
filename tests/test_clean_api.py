"""POST /clean -- the documented HTTP contract.

Split from test_robot_session.py on the usual line: the engine's behaviour is
unit-tested there, and this module only covers what is visible over HTTP --
status codes, request validation, and the exact shape of the two report bodies.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

LoadMap = Callable[[str], None]
CollisionReport = Callable[[Any], dict[str, Any]]

REPORT_KEYS = {
    "id",
    "started_at",
    "finished_at",
    "state",
    "robot_model",
    "submitted_actions",
    "successful_steps",
    "cleaned_tiles",
    "final_position",
    "duration_ms",
    "error",
}


def request_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "start": {"x": 0, "y": 0},
        "robot_model": "basic",
        "actions": [],
    }
    body.update(overrides)
    return body


# ------------------------------------------------------------ happy path

def test_completed_session_matches_the_documented_report(
    client: TestClient, load_map: LoadMap
) -> None:
    """Reproduces the completed report from the PDF, field for field."""
    load_map("oooo\noooo")

    response = client.post(
        "/clean",
        json=request_body(
            actions=[{"direction": "east", "steps": 2}, {"direction": "south", "steps": 1}]
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == REPORT_KEYS
    assert body["state"] == "completed"
    assert body["robot_model"] == "basic"
    assert body["submitted_actions"] == 2
    assert body["successful_steps"] == 3
    assert body["cleaned_tiles"] == [
        {"x": 0, "y": 0},
        {"x": 1, "y": 0},
        {"x": 2, "y": 0},
        {"x": 2, "y": 1},
    ]
    assert body["final_position"] == {"x": 2, "y": 1}
    assert body["error"] is None
    assert body["duration_ms"] >= 0
    assert body["id"]  # server-generated, non-empty


def test_timestamps_are_rfc3339_in_utc(client: TestClient, load_map: LoadMap) -> None:
    from datetime import datetime

    load_map("oo")

    body = client.post("/clean", json=request_body()).json()

    for field in ("started_at", "finished_at"):
        parsed = datetime.fromisoformat(body[field])
        assert parsed.utcoffset() is not None, f"{field} carries no offset"
        assert parsed.utcoffset().total_seconds() == 0, f"{field} is not UTC"


# --------------------------------------------------------------- conflicts

def test_cleaning_before_any_map_is_loaded_is_a_conflict(client: TestClient) -> None:
    response = client.post("/clean", json=request_body())

    assert response.status_code == 409


def test_missing_map_outranks_a_bad_start_coordinate(client: TestClient) -> None:
    """With no map there is nothing to validate the coordinate against."""
    response = client.post("/clean", json=request_body(start={"x": 99, "y": 99}))

    assert response.status_code == 409


def test_collision_returns_an_error_report(
    client: TestClient, load_map: LoadMap, collision_report: CollisionReport
) -> None:
    """"return HTTP 409 with a report using the same fields as a completed report".

    The report travels inside the HTTPException ``detail`` envelope; the
    ``collision_report`` fixture unwraps it. What matters here is that the
    report itself carries every field a completed report does.
    """
    load_map("oxo")

    response = client.post(
        "/clean", json=request_body(actions=[{"direction": "east", "steps": 1}])
    )

    report = collision_report(response)

    assert set(report) == REPORT_KEYS, f"report fields differ: {set(report) ^ REPORT_KEYS}"
    assert report["state"] == "error"
    assert report["final_position"] == {"x": 0, "y": 0}

    error = report["error"]
    assert set(error) == {"code", "message", "position"}
    assert error["code"] == "collision"
    assert error["position"] == {"x": 1, "y": 0}
    # The contract fixes code and position but leaves the wording to us -- so
    # this asserts a non-empty human-readable string exists, not what it says.
    assert isinstance(error["message"], str) and error["message"].strip()


def test_collision_report_keeps_the_tiles_cleaned_so_far(
    client: TestClient, load_map: LoadMap, collision_report: CollisionReport
) -> None:
    load_map("ooxo")

    report = collision_report(
        client.post("/clean", json=request_body(actions=[{"direction": "east", "steps": 3}]))
    )

    assert report["cleaned_tiles"] == [{"x": 0, "y": 0}, {"x": 1, "y": 0}]
    assert report["successful_steps"] == 1


# -------------------------------------------------------------- rejections

@pytest.mark.parametrize(
    "start",
    [{"x": 1, "y": 0}, {"x": 3, "y": 0}, {"x": 0, "y": 3}, {"x": -1, "y": 0}],
    ids=["non-walkable", "x-out-of-range", "y-out-of-range", "negative"],
)
def test_unusable_start_coordinate_is_unprocessable(
    client: TestClient, load_map: LoadMap, start: dict[str, int]
) -> None:
    load_map("oxo")

    assert client.post("/clean", json=request_body(start=start)).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        request_body(actions=[{"direction": "up", "steps": 1}]),
        request_body(actions=[{"direction": "NORTH", "steps": 1}]),
        request_body(actions=[{"direction": "north"}]),
        request_body(actions=[{"steps": 1}]),
        request_body(actions=[{"direction": "north", "steps": 0}]),
        request_body(actions=[{"direction": "north", "steps": -1}]),
        request_body(actions=[{"direction": "north", "steps": 1.5}]),
        request_body(robot_model="deluxe"),
        request_body(robot_model="Basic"),
        request_body(start={"x": 0}),
        request_body(start={"x": 0.5, "y": 0}),
        {"robot_model": "basic", "actions": []},
        {"start": {"x": 0, "y": 0}, "actions": []},
        {"start": {"x": 0, "y": 0}, "robot_model": "basic"},
        {},
    ],
    ids=[
        "unknown-direction",
        "uppercase-direction",
        "action-without-steps",
        "action-without-direction",
        "steps-zero",
        "steps-negative",
        "steps-fractional",
        "unknown-robot-model",
        "capitalised-robot-model",
        "start-without-y",
        "start-x-fractional",
        "no-start",
        "no-robot-model",
        "no-actions",
        "empty-body",
    ],
)
def test_malformed_request_is_unprocessable(
    client: TestClient, load_map: LoadMap, body: dict[str, Any]
) -> None:
    """"start, robot_model, and actions are required, even when actions is empty"."""
    load_map("ooo\nooo")

    assert client.post("/clean", json=body).status_code == 422


def test_empty_actions_list_is_accepted(client: TestClient, load_map: LoadMap) -> None:
    """Required, but allowed to be empty -- the start tile is still processed."""
    load_map("oo")

    response = client.post("/clean", json=request_body(actions=[]))

    assert response.status_code == 200
    assert response.json()["cleaned_tiles"] == [{"x": 0, "y": 0}]


# ------------------------------------------------------------------ wiring

def test_clean_is_registered_and_documented(client: TestClient) -> None:
    """A router that is never included answers 404, and the failure looks like
    a routing typo rather than a missing include."""
    paths = client.get("/openapi.json").json()["paths"]

    assert "/clean" in paths
    assert "post" in paths["/clean"]


@pytest.mark.parametrize("method", ["get", "put", "delete", "patch"])
def test_clean_only_answers_post(client: TestClient, method: str) -> None:
    assert getattr(client, method)("/clean").status_code == 405


def test_uploading_a_map_between_sessions_resets_dirt_but_keeps_history(
    client: TestClient, load_map: LoadMap, upload_map: Callable[..., Any]
) -> None:
    """The two features meeting: /clean writes history, PUT /map must not erase it."""
    load_map("oo")
    client.post("/clean", json=request_body(robot_model="premium", actions=[]))

    assert upload_map(b"oo", filename="reload.txt").status_code == 200

    body = client.post(
        "/clean", json=request_body(robot_model="premium", actions=[])
    ).json()
    assert body["cleaned_tiles"] == [{"x": 0, "y": 0}], "reload should make the tile dirty again"

    from src.app.core import state

    assert len(state.session_history) == 2
