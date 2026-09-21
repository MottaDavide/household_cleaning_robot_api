"""GET /history -- the RFC 4180 CSV export.

The contract pins this endpoint harder than any other: an exact header, an
exact column order, and values that must "exactly match the corresponding JSON
report values". So these tests assert on the bytes, not just on "it parses".
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.app.robot import services

LoadMap = Callable[[str], None]
CollisionReport = Callable[[Any], dict[str, Any]]

HEADER = (
    "id,started_at,state,robot_model,submitted_actions,"
    "successful_steps,cleaned_tiles,duration_ms"
)
COLUMNS = HEADER.split(",")


def clean_request(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "start": {"x": 0, "y": 0},
        "robot_model": "basic",
        "actions": [],
    }
    body.update(overrides)
    return body


def rows(response: Any) -> list[dict[str, str]]:
    """Parse the response as CSV. newline="" so the reader sees the real terminators."""
    return list(csv.DictReader(io.StringIO(response.text, newline="")))


# ------------------------------------------------------------------- shape

def test_history_is_served_as_csv(client: TestClient) -> None:
    response = client.get("/history")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


def test_empty_history_is_the_header_and_nothing_else(client: TestClient) -> None:
    """"return the header followed by no data rows when history is empty"."""
    response = client.get("/history")

    assert response.text == HEADER + "\r\n"


def test_header_columns_are_in_the_documented_order(
    client: TestClient, load_map: LoadMap
) -> None:
    load_map("oo")
    client.post("/clean", json=clean_request())

    first_line = client.get("/history").text.split("\r\n")[0]

    assert first_line == HEADER


def test_rows_use_crlf_terminators(client: TestClient, load_map: LoadMap) -> None:
    """RFC 4180 section 2.1: records are separated by CRLF."""
    load_map("oo")
    client.post("/clean", json=clean_request())

    body = client.get("/history").text

    assert body.endswith("\r\n")
    assert "\n" not in body.replace("\r\n", ""), "found a bare LF outside a CRLF pair"
    assert len(body.rstrip("\r\n").split("\r\n")) == 2  # header + one session


def test_every_row_has_exactly_the_documented_columns(
    client: TestClient, load_map: LoadMap
) -> None:
    load_map("oo")
    client.post("/clean", json=clean_request())

    reader = csv.reader(io.StringIO(client.get("/history").text, newline=""))

    assert all(len(row) == len(COLUMNS) for row in reader)


# ------------------------------------------------------------------ content

def test_a_completed_session_appears_with_its_report_values(
    client: TestClient, load_map: LoadMap
) -> None:
    """"id and started_at exactly match the corresponding JSON report values"."""
    load_map("ooo")
    report = client.post(
        "/clean", json=clean_request(actions=[{"direction": "east", "steps": 2}])
    ).json()

    (row,) = rows(client.get("/history"))

    assert row["id"] == report["id"]
    assert row["started_at"] == report["started_at"]
    assert row["state"] == "completed"
    assert row["robot_model"] == "basic"
    assert row["submitted_actions"] == str(report["submitted_actions"])
    assert row["successful_steps"] == str(report["successful_steps"])
    assert row["duration_ms"] == str(report["duration_ms"])


def test_started_at_is_the_session_start_not_its_end(
    client: TestClient, load_map: LoadMap, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The column is started_at, and only started_at.

    Comparing the CSV against the report is not enough on its own: a session
    finishes well inside the resolution of ``datetime.now``, so started_at and
    finished_at normally come out byte-identical and writing the wrong one is
    invisible. Forcing the clock apart is what gives this assertion teeth.
    """
    load_map("oo")
    ticks = iter(
        [
            datetime(2026, 7, 11, 9, 30, 0, tzinfo=UTC),
            datetime(2026, 7, 11, 9, 35, 0, tzinfo=UTC),
        ]
    )

    class SteppingClock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return next(ticks)

    monkeypatch.setattr(services, "datetime", SteppingClock)
    report = client.post("/clean", json=clean_request()).json()

    (row,) = rows(client.get("/history"))

    assert report["started_at"] != report["finished_at"], "the clock was forced apart"
    assert row["started_at"] == report["started_at"]


def test_cleaned_tiles_is_a_count_not_a_list(client: TestClient, load_map: LoadMap) -> None:
    """"cleaned_tiles is the number of entries in the report's cleaned_tiles array".

    The report field is a list of coordinates; serialising it verbatim would
    both break the column count and embed commas in a CSV field.
    """
    load_map("oooo")
    report = client.post(
        "/clean", json=clean_request(actions=[{"direction": "east", "steps": 3}])
    ).json()

    (row,) = rows(client.get("/history"))

    assert len(report["cleaned_tiles"]) == 4
    assert row["cleaned_tiles"] == "4"


def test_error_sessions_are_included(client: TestClient, load_map: LoadMap) -> None:
    """"include both completed and error sessions"."""
    load_map("ox")
    client.post("/clean", json=clean_request(actions=[{"direction": "east", "steps": 1}]))

    (row,) = rows(client.get("/history"))

    assert row["state"] == "error"


def test_sessions_are_listed_oldest_first(
    client: TestClient, load_map: LoadMap, collision_report: CollisionReport
) -> None:
    """"return sessions in creation order, oldest first".

    Deliberately mixes a collided session in between two completed ones: the
    order must come from when the session ran, not from how it ended.
    """
    load_map("oox")
    ids = [client.post("/clean", json=clean_request()).json()["id"]]
    ids.append(
        collision_report(
            client.post("/clean", json=clean_request(actions=[{"direction": "east", "steps": 2}]))
        )["id"]
    )
    ids.append(
        client.post(
            "/clean", json=clean_request(actions=[{"direction": "east", "steps": 1}])
        ).json()["id"]
    )

    listed = rows(client.get("/history"))

    assert [r["id"] for r in listed] == ids
    assert [r["state"] for r in listed] == ["completed", "error", "completed"]


def test_sessions_created_in_the_same_millisecond_keep_their_order(
    client: TestClient, load_map: LoadMap
) -> None:
    """"including when timestamps have equal precision".

    Ten back-to-back sessions will share a started_at at this resolution, so
    sorting by timestamp cannot reproduce the order -- only insertion order can.
    """
    load_map("oo")
    ids = [client.post("/clean", json=clean_request()).json()["id"] for _ in range(10)]

    assert [r["id"] for r in rows(client.get("/history"))] == ids


def test_history_survives_a_new_map_being_loaded(
    client: TestClient, load_map: LoadMap, upload_map: Callable[..., Any]
) -> None:
    """"retain history when a new map is loaded"."""
    load_map("oo")
    client.post("/clean", json=clean_request())

    upload_map(b"ooo\nooo", filename="replacement.txt")

    assert len(rows(client.get("/history"))) == 1


def test_a_rejected_session_is_not_listed(client: TestClient, load_map: LoadMap) -> None:
    """422 and 409-no-map never ran, so they are not sessions."""
    load_map("ox")
    assert client.post("/clean", json=clean_request(start={"x": 1, "y": 0})).status_code == 422
    assert client.post("/clean", json=clean_request(robot_model="nope")).status_code == 422

    assert rows(client.get("/history")) == []


# ------------------------------------------------------------------- wiring

def test_history_is_documented(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/history" in paths
    assert "get" in paths["/history"]


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_history_only_answers_get(client: TestClient, method: str) -> None:
    assert getattr(client, method)("/history").status_code == 405
