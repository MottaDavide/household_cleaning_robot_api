"""The cleaning engine: src/app/robot/services.execute_cleaning_session.

These are unit tests -- no HTTP. They cover the rules that decide *what the
robot does*, which the 200/409 status code cannot express: which tiles get
cleaned and in what order, where the robot stops, what survives a collision,
and what lands in history.

Maps are written as TXT grids because that is the most readable way to state a
world: "oxo" is unambiguous in a way a tiles dict is not. `o` starts dirty,
`x` is non-walkable.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import pytest

from src.app.core import state
from src.app.robot.exceptions import (
    CollisionError,
    InvalidStartCoordinateError,
    NoMapLoadedError,
)
from src.app.robot.schemas import (
    MOVEMENT_DELTAS,
    Action,
    CleanReport,
    CleanRequest,
    Coordinate,
    Direction,
    RobotModel,
    SessionState,
)
from src.app.robot.services import execute_cleaning_session

LoadMap = Callable[[str], None]
Step = tuple[str, int]


def run(
    start: tuple[int, int] = (0, 0),
    model: str = "basic",
    actions: Iterable[Step] = (),
) -> CleanReport:
    return execute_cleaning_session(
        CleanRequest(
            start=Coordinate(x=start[0], y=start[1]),
            robot_model=model,
            actions=[Action(direction=d, steps=s) for d, s in actions],
        )
    )


def cleaned(report: CleanReport) -> list[tuple[int, int]]:
    return [(c.x, c.y) for c in report.cleaned_tiles]


def position(report: CleanReport) -> tuple[int, int]:
    return (report.final_position.x, report.final_position.y)


# --------------------------------------------------------------- movement

@pytest.mark.parametrize(
    ("direction", "expected"),
    [("north", (1, 0)), ("east", (2, 1)), ("south", (1, 2)), ("west", (0, 1))],
)
def test_each_direction_moves_the_documented_way(
    load_map: LoadMap, direction: str, expected: tuple[int, int]
) -> None:
    """north is y-1, east is x+1, south is y+1, west is x-1.

    Starting from the centre of a 3x3 so every direction has somewhere to go.
    This pins the delta table *and* the spelling of the enum values in one
    assertion -- a typo in either makes the robot walk the wrong way or makes
    the request unparseable.
    """
    load_map("ooo\nooo\nooo")

    report = run(start=(1, 1), actions=[(direction, 1)])

    assert position(report) == expected


def test_movement_deltas_cover_every_direction() -> None:
    """A direction the enum accepts but the delta table lacks is a KeyError at
    runtime, i.e. a 500 on a perfectly valid request."""
    assert set(MOVEMENT_DELTAS) == set(Direction)


def test_a_multi_step_action_is_executed_one_step_at_a_time(load_map: LoadMap) -> None:
    """Every tile along the way is visited, not just the destination."""
    load_map("oooo")

    report = run(actions=[("east", 3)])

    assert cleaned(report) == [(0, 0), (1, 0), (2, 0), (3, 0)]
    assert position(report) == (3, 0)


# ------------------------------------------------------------ the start tile

def test_the_starting_tile_is_processed_before_the_first_action(load_map: LoadMap) -> None:
    load_map("oo")

    report = run(actions=[("east", 1)])

    assert cleaned(report)[0] == (0, 0)


def test_successful_steps_excludes_the_starting_tile(load_map: LoadMap) -> None:
    """"successful_steps counts successful movements and does not include
    processing the starting tile"."""
    load_map("ooo")

    report = run(actions=[("east", 2)])

    assert report.successful_steps == 2
    assert len(cleaned(report)) == 3  # start + two moves


def test_a_session_with_no_actions_still_cleans_the_starting_tile(load_map: LoadMap) -> None:
    """"actions may be empty"."""
    load_map("oo")

    report = run(actions=[])

    assert report.state is SessionState.COMPLETED
    assert cleaned(report) == [(0, 0)]
    assert report.successful_steps == 0
    assert report.submitted_actions == 0
    assert position(report) == (0, 0)


def test_submitted_actions_counts_action_objects_not_steps(load_map: LoadMap) -> None:
    load_map("oooo")

    report = run(actions=[("east", 2), ("west", 1)])

    assert report.submitted_actions == 2
    assert report.successful_steps == 3


# ------------------------------------------------------------- robot models

def test_basic_cleans_tiles_that_are_already_clean(load_map: LoadMap) -> None:
    """"basic performs and reports a cleaning operation on every walkable tile
    it visits, even when that tile is already clean"."""
    load_map("oo")
    run(actions=[("east", 1)])  # first pass leaves both tiles clean

    report = run(actions=[("east", 1)])

    assert cleaned(report) == [(0, 0), (1, 0)]


def test_basic_reports_a_repeated_coordinate_more_than_once(load_map: LoadMap) -> None:
    """"repeated coordinates therefore appear more than once for a basic robot"."""
    load_map("oo")

    report = run(actions=[("east", 1), ("west", 1)])

    assert cleaned(report) == [(0, 0), (1, 0), (0, 0)]


def test_premium_skips_a_tile_that_is_already_clean(load_map: LoadMap) -> None:
    """The PDF premium example: one row, tile 0 dirty, tile 1 already clean."""
    load_map("oo")
    run(model="premium", actions=[])  # cleans (0, 0) only

    report = run(model="premium", actions=[("east", 1)])

    assert cleaned(report) == [(1, 0)]


def test_premium_run_twice_cleans_nothing_the_second_time(load_map: LoadMap) -> None:
    """Straight from the PDF: the same premium session repeated returns []."""
    load_map("oo")
    first = run(model="premium", actions=[("east", 1)])

    second = run(model="premium", actions=[("east", 1)])

    assert cleaned(first) == [(0, 0), (1, 0)]
    assert cleaned(second) == []
    assert second.state is SessionState.COMPLETED  # nothing cleaned is not an error


def test_premium_cleans_again_after_a_new_map_is_loaded(load_map: LoadMap) -> None:
    """"not for a premium robot unless the tile becomes dirty again after
    another map upload"."""
    load_map("oo")
    run(model="premium", actions=[("east", 1)])

    load_map("oo")
    report = run(model="premium", actions=[("east", 1)])

    assert cleaned(report) == [(0, 0), (1, 0)]


@pytest.mark.parametrize("model", ["basic", "premium"])
def test_both_models_mark_a_cleaned_tile_clean(load_map: LoadMap, model: str) -> None:
    """"Both models mark a tile clean whenever they perform a cleaning operation"."""
    load_map("oo")

    run(model=model, actions=[("east", 1)])

    assert all(not tile["dirty"] for tile in state.current_map.values())


def test_a_non_walkable_tile_is_never_cleaned(load_map: LoadMap) -> None:
    load_map("oxo\nooo")

    run(actions=[("south", 1), ("east", 2), ("north", 1)])

    assert state.current_map[(1, 0)]["dirty"] is False  # it was never dirty
    assert state.current_map[(1, 0)]["walkable"] is False


# --------------------------------------------------------------- collisions

def test_walking_into_an_obstacle_raises_with_an_error_report(load_map: LoadMap) -> None:
    load_map("oxo")

    with pytest.raises(CollisionError) as excinfo:
        run(actions=[("east", 1)])

    report = excinfo.value.report
    assert report.state is SessionState.ERROR
    assert report.error is not None
    assert report.error.code == "collision"
    assert report.error.message  # non-empty human-readable string
    assert (report.error.position.x, report.error.position.y) == (1, 0)


@pytest.mark.parametrize(
    ("direction", "expected"),
    [("north", (0, -1)), ("east", (1, 0)), ("south", (0, 1)), ("west", (-1, 0))],
)
def test_leaving_the_map_reports_the_out_of_bounds_coordinate(
    load_map: LoadMap, direction: str, expected: tuple[int, int]
) -> None:
    """"error.position is the coordinate the robot attempted to enter, even when
    it is outside the map".

    A 1x1 map so every direction walks off the edge on the first step, and each
    expected coordinate is outside the grid in a different way.
    """
    load_map("o")

    with pytest.raises(CollisionError) as excinfo:
        run(actions=[(direction, 1)])

    error = excinfo.value.report.error
    assert (error.position.x, error.position.y) == expected


def test_a_collision_stops_the_remaining_steps_and_actions(load_map: LoadMap) -> None:
    """"do not execute any later step or action"."""
    load_map("ooxo\noooo")

    with pytest.raises(CollisionError) as excinfo:
        run(actions=[("east", 3), ("south", 1)])

    report = excinfo.value.report
    assert report.successful_steps == 1  # only the step to (1, 0) landed
    assert position(report) == (1, 0)  # "final_position at the last valid coordinate"
    assert state.current_map[(0, 1)]["dirty"] is True  # the south action never ran


def test_a_collision_preserves_the_cleaning_already_performed(load_map: LoadMap) -> None:
    """"preserve cleaning operations already performed"."""
    load_map("ooxo")

    with pytest.raises(CollisionError) as excinfo:
        run(actions=[("east", 3)])

    assert cleaned(excinfo.value.report) == [(0, 0), (1, 0)]
    assert state.current_map[(0, 0)]["dirty"] is False
    assert state.current_map[(1, 0)]["dirty"] is False


def test_submitted_actions_is_the_full_count_even_when_a_collision_cuts_it_short(
    load_map: LoadMap,
) -> None:
    load_map("ox")

    with pytest.raises(CollisionError) as excinfo:
        run(actions=[("east", 1), ("south", 5), ("west", 2)])

    assert excinfo.value.report.submitted_actions == 3


# ----------------------------------------------------------- preconditions

def test_cleaning_without_a_map_is_rejected() -> None:
    assert state.current_map is None  # the autouse reset fixture guarantees this

    with pytest.raises(NoMapLoadedError):
        run()


@pytest.mark.parametrize(
    ("start", "why"),
    [
        ((1, 0), "non-walkable tile"),
        ((3, 0), "x beyond the last column"),
        ((0, 3), "y beyond the last row"),
        ((-1, 0), "negative x"),
        ((0, -1), "negative y"),
    ],
)
def test_an_unusable_start_coordinate_is_rejected(
    load_map: LoadMap, start: tuple[int, int], why: str
) -> None:
    """"the start coordinates must identify a walkable tile in the current map"."""
    load_map("oxo")

    with pytest.raises(InvalidStartCoordinateError):
        run(start=start)


def test_a_rejected_session_is_not_added_to_history(load_map: LoadMap) -> None:
    """Only sessions that actually ran are sessions."""
    load_map("oxo")

    with pytest.raises(InvalidStartCoordinateError):
        run(start=(1, 0))

    assert state.session_history == []


# ------------------------------------------------------------------ history

def test_a_completed_session_is_recorded(load_map: LoadMap) -> None:
    load_map("oo")

    report = run(actions=[("east", 1)])

    assert len(state.session_history) == 1
    assert state.session_history[0]["id"] == str(report.id)
    assert state.session_history[0]["state"] == "completed"


def test_a_collided_session_is_recorded(load_map: LoadMap) -> None:
    """"add the session to history with state error"."""
    load_map("ox")

    with pytest.raises(CollisionError):
        run(actions=[("east", 1)])

    assert len(state.session_history) == 1
    assert state.session_history[0]["state"] == "error"


def test_history_is_in_creation_order_oldest_first(load_map: LoadMap) -> None:
    load_map("oox")
    run(actions=[])
    with pytest.raises(CollisionError):
        run(actions=[("east", 2)])
    run(actions=[("east", 1)])

    assert [h["state"] for h in state.session_history] == ["completed", "error", "completed"]


def test_loading_a_new_map_does_not_erase_history(load_map: LoadMap) -> None:
    load_map("oo")
    run(actions=[])

    load_map("ooo")

    assert len(state.session_history) == 1


def test_every_session_gets_its_own_identifier(load_map: LoadMap) -> None:
    load_map("oo")

    ids = {run(actions=[]).id for _ in range(5)}

    assert len(ids) == 5


# ------------------------------------------------------------- report shape

def test_report_timestamps_and_duration_are_coherent(load_map: LoadMap) -> None:
    load_map("oo")

    report = run(actions=[("east", 1)])

    assert report.finished_at >= report.started_at
    assert report.duration_ms >= 0
    assert report.started_at.utcoffset().total_seconds() == 0  # UTC, per the contract


def test_a_completed_report_carries_no_error(load_map: LoadMap) -> None:
    load_map("oo")

    report = run(actions=[("east", 1)])

    assert report.state is SessionState.COMPLETED
    assert report.error is None


def test_the_report_echoes_the_requested_robot_model(load_map: LoadMap) -> None:
    load_map("oo")

    assert run(model="premium", actions=[]).robot_model is RobotModel.PREMIUM
