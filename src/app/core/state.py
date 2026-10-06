"""The whole of the application's memory, held in module-level globals.

No database and nothing on disk: the map currently loaded and the reports of
every session run against it live here for as long as the process does, which
the assignment allows explicitly. Anything reading or replacing them must go
through the module, as ``state.current_map`` -- importing a name directly
copies the value once and then stops tracking it.
"""

from typing import Any
""" 
current_map = {
    (0, 0): {"walkable": True,  "dirty": True},   # 'o'
    (1, 0): {"walkable": False, "dirty": False},  # 'x'
    (2, 0): {"walkable": True,  "dirty": True},   # 'o'
    (0, 1): {"walkable": True,  "dirty": True},
    (1, 1): {"walkable": True,  "dirty": True},
    (2, 1): {"walkable": True,  "dirty": True},
}
"""
current_map: dict[tuple[int, int], dict[str, Any]] | None = None


map_dimensions = {"rows": 0, "cols": 0}

session_history: list[dict[str, Any]] = []
"""  
i campi sono quelli dello schema CleanReport. Un esempio di report è:
[{
    "id": "c1a2b3...",                 # UUID come stringa
    "started_at": "2026-10-05T10:00:00+00:00",
    "finished_at": "2026-10-05T10:00:01+00:00",
    "state": "completed",              # oppure "error"
    "robot_model": "basic",            # oppure "premium"
    "submitted_actions": 3,
    "successful_steps": 3,
    "cleaned_tiles": [{"x": 0, "y": 0}, {"x": 1, "y": 0}],
    "final_position": {"x": 1, "y": 0},
    "duration_ms": 1000,
    "error": None
},
{
    "id": "d4e5f6...",
    "started_at": "2026-10-05T10:05:00+00:00",
    "finished_at": "2026-10-05T10:05:02+00:00",
    "state": "error",
    "robot_model": "premium",
    "submitted_actions": 5,
    "successful_steps": 2,
    "cleaned_tiles": [{"x": 0, "y": 0}, {"x": 1, "y": 0}],
    "final_position": {"x": 1, "y": 0},
    "duration_ms": 2000,
    "error": {
        "code": "collision",
        "message": "Hit an obstacle at (2, 0)",
        "position": {"x": 2, "y": 0}
    }
}]
"""
