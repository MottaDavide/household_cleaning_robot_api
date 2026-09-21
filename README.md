# Cleaning Robot API

A REST API that remotely controls a household cleaning robot: load a map, run
cleaning sessions over it, and download the session history as CSV.

Built with **FastAPI** and **Pydantic v2**. All state lives in memory for the
lifetime of the process — there is no database, and nothing survives a restart.

---

## Table of contents

- [Requirements](#requirements)
- [Quick start](#quick-start)
  - [With Docker](#with-docker)
  - [Without Docker](#without-docker)
- [Tooling](#tooling)
  - [uv](#uv)
  - [poe](#poe)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Tests](#tests)
- [Known gaps](#known-gaps)

---

## Requirements

| | |
|---|---|
| **Python** | **3.12** — pinned in [`.python-version`](.python-version) and enforced by `requires-python = ">=3.12"` in [`pyproject.toml`](pyproject.toml). Developed against CPython 3.12.13. |
| **Package manager** | [uv](https://docs.astral.sh/uv/) 0.11.24. [`uv.lock`](uv.lock) pins every transitive dependency. |
| **Docker** | Only if you want the containerised path. Any version with BuildKit (default since 23.0). |

The assignment allows Python 3.11+, but this project targets 3.12 because
`uv.lock` was resolved against it. Running on 3.11 means re-resolving the
lockfile, which defeats the point of having one.

Runtime dependencies are exactly four; everything else in the lockfile is a
transitive dependency of these:

```
fastapi>=0.115   pydantic>=2.9   python-multipart>=0.0.9   uvicorn[standard]>=0.30
```

---

## Quick start

### With Docker

The two commands from the assignment, unchanged:

```bash
docker build -t cleaning-robot .
```

```bash
docker run --rm -p 8000:8000 cleaning-robot
```

The service is then at <http://localhost:8000>, with interactive docs at
<http://localhost:8000/docs> and the schema at <http://localhost:8000/openapi.json>.

Check it is alive:

```bash
curl http://localhost:8000/health
```

The [`Dockerfile`](Dockerfile) is a two-stage build. The builder resolves
dependencies from `uv.lock`; the runtime stage receives only the resulting
virtualenv and `src/`, so uv, the build cache and every dev dependency stay out
of the shipped image. It runs as a non-root user (`appuser`, uid 10001) and
carries a `HEALTHCHECK` that polls `/health`. Measured cold start is well under
the 10 seconds the assignment allows.

### Without Docker

Three steps from a fresh clone. They are explained in detail in
[Tooling](#tooling) below.

```bash
uv sync
```

```bash
uv run uvicorn src.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Or, equivalently, through the task runner:

```bash
uv run poe dev
```

> **Why `src.app.main:app` and not `app.main:app`?**
> There is no `__init__.py` anywhere in `src/`; the code is imported as a
> namespace package with the repository root on `sys.path`. **Run every command
> from the repository root**, or the import will fail. `pythonpath = ["."]` in
> `pyproject.toml` does this for pytest, and the Dockerfile sets
> `PYTHONPATH=/app` for the container.

---

## Tooling

### uv

[uv](https://docs.astral.sh/uv/) is an extremely fast Python package and
project manager. This project uses it for two things: pinning the exact
dependency versions in `uv.lock`, and creating the virtualenv.

**Installing uv**

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Alternatives if you prefer: `pipx install uv`, `brew install uv`, or
`pip install uv`. Verify with `uv --version`.

**Creating the environment**

```bash
uv sync
```

That single command does all of the following, and is the best way to use uv
here:

- downloads CPython 3.12 if your machine does not have it (no pyenv needed);
- creates `.venv/` in the repository root;
- installs **exactly** the versions pinned in `uv.lock`, production and dev;
- re-syncs — adding *and removing* packages — so the environment always matches
  the lockfile.

Useful variations:

| Command | What it does |
|---|---|
| `uv sync --frozen` | Fails if `uv.lock` and `pyproject.toml` disagree instead of silently re-resolving. **Use this in CI.** |
| `uv sync --no-dev` | Production dependencies only — what the Dockerfile does. |
| `uv run <cmd>` | Runs `<cmd>` inside `.venv`, syncing first if needed. No manual activation. |
| `uv lock --upgrade` | Re-resolves and rewrites `uv.lock`. The only command that should change it. |
| `uv add <pkg>` | Adds a dependency to `pyproject.toml` and updates the lockfile. |

`uv run` means you never have to activate anything. If you prefer to, the venv
is an ordinary one:

```bash
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

> **Note on `--no-install-project`.** `pyproject.toml` deliberately has no
> `[build-system]`: this repository is an application, not a distributable
> package. `uv sync` handles that automatically, but any command that would
> install the project itself — as in the Dockerfile — needs
> `--no-install-project`.

### poe

[Poe the Poet](https://poethepoet.natn.io/) is the task runner. It is already a
dev dependency, so **`uv sync` installs it** — there is nothing extra to do.

If you want it available outside this project:

```bash
pipx install poethepoet
```

Or as a standalone uv tool, which is the lightest option:

```bash
uv tool install poethepoet
```

The tasks are defined under `[tool.poe.tasks]` in `pyproject.toml`:

| Task | Runs | Purpose |
|---|---|---|
| `uv run poe run` | `uvicorn src.app.main:app --host 0.0.0.0 --port 8000` | Serve on all interfaces, as the container does |
| `uv run poe dev` | `uvicorn ... --host 127.0.0.1 --port 8000 --reload` | Local development with auto-reload |
| `uv run poe test` | `pytest` | The whole test suite |
| `uv run poe lint` | `ruff check .` | Static analysis |
| `uv run poe format` | `ruff format .` | Auto-format |

List them any time with `uv run poe -h`.

---

## API reference

Four endpoints. Request and response bodies are JSON unless stated otherwise.

### `GET /health`

Liveness probe. Always returns `200` with exactly:

```json
{"status": "ok"}
```

### `PUT /map`

Loads or replaces the current map. **Multipart upload** under the field name
`file`. The filename extension decides the parser and is compared
case-insensitively — the `Content-Type` header is ignored.

```bash
curl -X PUT http://localhost:8000/map -F "file=@tests/fixtures/maps/valid/spec_example_3x4.txt"
```

| Status | When |
|---|---|
| `200` | `{"rows": 3, "cols": 4, "walkable_tiles": 10}` |
| `415` | The filename extension is not `.txt` or `.json` |
| `422` | The contents do not describe a valid map |

Loading a map replaces the previous one and resets all tile cleanliness, but
**does not erase session history**.

**TXT format** — a rectangular grid, `o` = walkable and initially dirty, `x` =
non-walkable. Only lowercase. Every row must be non-empty and the same width.
`\n` and `\r\n` both work, and one trailing line ending is allowed; a blank
line inside the grid is not.

```
oxoo
ooxo
oooo
```

**JSON format** — positive `rows` and `cols`, and exactly one tile per
coordinate in the rectangle (missing *and* duplicate coordinates are both
rejected). A walkable tile with `dirty` omitted starts dirty; a non-walkable
tile must have `dirty` omitted or `false`.

```json
{
  "rows": 2,
  "cols": 3,
  "tiles": [
    {"x": 0, "y": 0, "walkable": true, "dirty": true},
    {"x": 1, "y": 0, "walkable": true, "dirty": false},
    {"x": 2, "y": 0, "walkable": false, "dirty": false},
    {"x": 0, "y": 1, "walkable": true},
    {"x": 1, "y": 1, "walkable": true},
    {"x": 2, "y": 1, "walkable": true}
  ]
}
```

**Coordinates.** `(0, 0)` is top-left, `x` grows east (right), `y` grows south
(down). Movement deltas: `north` `(x, y-1)`, `east` `(x+1, y)`, `south`
`(x, y+1)`, `west` `(x-1, y)`.

### `POST /clean`

Runs one cleaning session on the current map.

Continuing from the `PUT /map` example above — the map is `oxoo / ooxo / oooo`,
so this route goes down the left edge and back along the bottom row, avoiding
both walls:

```bash
curl -X POST http://localhost:8000/clean -H "Content-Type: application/json" -d '{"start":{"x":0,"y":0},"robot_model":"basic","actions":[{"direction":"south","steps":2},{"direction":"east","steps":3}]}'
```

`start`, `robot_model` and `actions` are all required — `actions` may be empty,
but it must be present. `robot_model` is `basic` or `premium`; `direction` is
one of `north`/`east`/`south`/`west`, lowercase; `steps` is a positive integer.

The two robot models differ only in what they bother to clean:

- **`basic`** performs and reports a cleaning operation on every walkable tile
  it visits, even one that is already clean;
- **`premium`** cleans only a tile that is currently dirty, and skips the rest.

Both mark a tile clean when they clean it. The starting tile is processed
before the first action, and each action is executed one step at a time.

| Status | When |
|---|---|
| `200` | Session report, `state: "completed"` |
| `409` | No map has been loaded |
| `409` | A movement collided with an obstacle or the map boundary |
| `422` | Malformed request, or a start coordinate outside the map or non-walkable |

The response — this is the actual output of the command above, not an
illustration:

```json
{
  "id": "f528a51c-e6d2-4b6e-8791-7f8aa2803257",
  "started_at": "2026-09-21T21:26:44.965999Z",
  "finished_at": "2026-09-21T21:26:44.965999Z",
  "state": "completed",
  "robot_model": "basic",
  "submitted_actions": 2,
  "successful_steps": 5,
  "cleaned_tiles": [
    {"x": 0, "y": 0}, {"x": 0, "y": 1}, {"x": 0, "y": 2},
    {"x": 1, "y": 2}, {"x": 2, "y": 2}, {"x": 3, "y": 2}
  ],
  "final_position": {"x": 3, "y": 2},
  "duration_ms": 0,
  "error": null
}
```

`duration_ms` is genuinely `0`: the session finishes well inside the resolution
of the system clock.

`submitted_actions` counts action *objects*, not steps. `successful_steps`
counts movements and excludes processing the starting tile. `cleaned_tiles` is
ordered by cleaning time, so a coordinate can appear more than once for a
`basic` robot.

**On collision** the robot stops *before* the invalid coordinate, skips every
later step and action, keeps the cleaning it already did, and the session is
recorded in history with `state: "error"`.

On the same map, stepping east from `(0, 0)` walks straight into the wall at
`(1, 0)`:

```bash
curl -X POST http://localhost:8000/clean -H "Content-Type: application/json" -d '{"start":{"x":0,"y":0},"robot_model":"basic","actions":[{"direction":"east","steps":1}]}'
```

```json
{
  "detail": {
    "state": "error",
    "successful_steps": 0,
    "final_position": {"x": 0, "y": 0},
    "error": {
      "code": "collision",
      "message": "The robot cannot enter a non-walkable tile.",
      "position": {"x": 1, "y": 0}
    }
  }
}
```

Two things to note. The report is nested under `detail`, because it is returned
inside FastAPI's `HTTPException` envelope rather than as the bare body — the
fields above are abridged, the real report carries all eleven. And
`error.position` is the coordinate the robot *tried* to enter, reported even
when it lies outside the map.

### `GET /history`

Downloads the session history as RFC 4180 CSV (`text/csv`, CRLF terminators).

```bash
curl http://localhost:8000/history
```

Header, always, in this exact order. After the two sessions above it returns:

```csv
id,started_at,state,robot_model,submitted_actions,successful_steps,cleaned_tiles,duration_ms
f528a51c-e6d2-4b6e-8791-7f8aa2803257,2026-09-21T21:26:44.965999Z,completed,basic,2,5,6,0
8f282870-7b66-4440-82af-415b372d7087,2026-09-21T21:26:45.849482Z,error,basic,1,0,1,0
```

Both completed and error sessions appear, in creation order, oldest first.
`cleaned_tiles` is the **count** of cleaned tiles, not the list. `id` and
`started_at` match the JSON report exactly. An empty history returns the header
and no data rows. History survives a new map upload; it does not survive a
restart.

---

## Project structure

Each feature is a package of four files with the same roles throughout:
`routers.py` (HTTP), `schemas.py` (Pydantic models), `services.py` (domain
logic), `exceptions.py` (domain errors the router maps to status codes).

```
.
├── Dockerfile                   Two-stage build; see "With Docker"
├── .dockerignore                Keeps the build context to pyproject/uv.lock/src
├── .gitattributes               Stops git normalising the byte-sensitive test fixtures
├── .python-version              3.12
├── pyproject.toml               Dependencies, poe tasks, pytest and ruff config
├── uv.lock                      Exact pinned versions of every dependency
│
├── src/app/
│   ├── main.py                  Builds the FastAPI app and includes the three routers
│   ├── schemas.py               CustomBase, the shared Pydantic base class
│   │
│   ├── core/
│   │   └── state.py             In-memory state: current_map, map_dimensions,
│   │                            session_history. Module-level globals, no DB
│   ├── system/
│   │   ├── routers.py           GET /health
│   │   └── schemas.py           HealthResponse
│   ├── map/
│   │   ├── routers.py           PUT /map; maps domain errors to 415 / 422
│   │   ├── schemas.py           MapResponse, TileSchema, JsonMapSchema
│   │   ├── services.py          TXT and JSON parsers, and process_map_upload
│   │   └── exceptions.py        UnsupportedExtensionError, InvalidMapContentError
│   └── robot/
│       ├── routers.py           POST /clean and GET /history
│       ├── schemas.py           RobotModel, Direction, MOVEMENT_DELTAS, Action,
│       │                        CleanRequest, CleanReport, ErrorDetails
│       ├── services.py          execute_cleaning_session and generate_csv_history
│       └── exceptions.py        NoMapLoadedError, InvalidStartCoordinateError,
│                                CollisionError (carries the report)
└── tests/                       See "Tests"
```

---

## Tests

311 tests. Run them all:

```bash
uv run pytest
```

```bash
uv run poe test
```

Useful invocations:

| Command | Purpose |
|---|---|
| `uv run pytest tests/test_robot_session.py` | One module |
| `uv run pytest -k premium` | Everything matching a name |
| `uv run pytest -x -vv` | Stop at the first failure, verbose |
| `uv run pytest --collect-only -q` | List tests without running them |

Configuration lives in `[tool.pytest.ini_options]` in `pyproject.toml`.
`pythonpath = ["."]` is what makes `src.app...` importable, and
`empty_parameter_set_mark = "fail_at_collect"` turns a fixture glob that
matches nothing into a failure instead of a silent skip.

### What each module covers

| Module | Tests | Covers |
|---|---|---|
| `test_system.py` | 4 | `/health` returns exactly `{"status":"ok"}`; `/docs` and `/openapi.json` are served |
| `test_map_upload_contract.py` | 152 | Every fixture file under `tests/fixtures/maps/`, driven by directory |
| `test_map_upload_protocol.py` | 18 | Multipart wiring, filename edge cases, media-type independence, non-UTF-8 bytes, BOM |
| `test_map_parsers.py` | 18 | Parser units: coordinate orientation, cleanliness defaults, exception types |
| `test_map_domain_state.py` | 5 | Map replacement, cleanliness reset, history preservation |
| `test_robot_session.py` | 41 | The cleaning engine: movement deltas, basic vs premium, collisions, history |
| `test_clean_api.py` | 32 | `POST /clean` contract, including 15 malformed-request cases |
| `test_history_api.py` | 18 | CSV header, column order, CRLF, ordering, values matching the JSON report |
| `test_end_to_end_simulation.py` | 1 | One full campaign across every endpoint — see below |
| `test_fixture_wiring.py` | 22 | Guards on the fixture corpus itself |

### The fixture corpus

`tests/fixtures/maps/` holds 66 real `.txt` and `.json` files, auto-discovered
and parametrized. **The directory a file sits in is its expected HTTP status**:

```
tests/fixtures/maps/
├── valid/                   20 files → 200  (expected body in _expected.json)
├── unsupported_extension/    8 files → 415
└── invalid_content/         38 files → 422
```

Adding a test case means dropping in a file — no test code changes.
`tests/fixtures/maps/README.md` documents the conventions and, importantly,
which cases are deliberately *not* tested and why.

These fixtures are byte-sensitive: some assert CRLF versus LF, how many
trailing newlines a file has, or bytes that are not valid UTF-8.
`.gitattributes` stops git from normalising them, and the canary tests in
`test_fixture_wiring.py` fail loudly by name if anything ever does. Those
canaries never touch the application — **if they are red, the problem is the
fixture corpus, not `src/`.**

### The end-to-end simulation

`test_end_to_end_simulation.py` plays one realistic campaign: load a TXT map
with an interior wall → walk the perimeter with a `basic` robot → repeat the
lap with `premium` and find nothing left to clean → drive into the wall →
swap in a JSON map → run the contract's own premium example → walk off the
eastern edge. It then reads `/history` and checks **every CSV row against the
JSON report that produced it**, field by field.

That last step is the reason it exists. `/clean` and `/history` are written
independently and share only the in-memory history list, so a field renamed on
one side stays invisible until something reads both.

---

## Known gaps

Stated here rather than left to be discovered:

- **`uv run poe lint` reports 30 errors**, all in `src/` — unsorted imports and
  lines over 100 characters. `tests/` is clean. Twelve are auto-fixable with
  `uv run ruff check --fix src/`.
- **`/openapi.json` under-documents the error codes.** The schema advertises
  only `200` and `422` for `/map` and `/clean`; the `415` and `409` cases
  described above are real but not declared, because the routes do not pass a
  `responses={...}` argument.
- **The collision body is nested under `detail`**, as noted in the `POST /clean`
  section. The assignment describes it as "a report using the same fields as a
  completed report", which reads as the bare body; this is a deliberate
  deviation, and the test suite pins the shape actually served.
- **Nothing is persisted.** Map and history live in module-level globals in
  `src/app/core/state.py` and are lost on restart, which the assignment
  explicitly permits.
