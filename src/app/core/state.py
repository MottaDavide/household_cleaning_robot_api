"""The whole of the application's memory, held in module-level globals.

No database and nothing on disk: the map currently loaded and the reports of
every session run against it live here for as long as the process does, which
the assignment allows explicitly. Anything reading or replacing them must go
through the module, as ``state.current_map`` -- importing a name directly
copies the value once and then stops tracking it.
"""

from typing import Any

current_map: dict[tuple[int, int], dict[str, Any]] | None = None
map_dimensions = {"rows": 0, "cols": 0}

session_history: list[dict[str, Any]] = []