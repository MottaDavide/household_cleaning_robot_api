from typing import Any

current_map: dict[tuple[int, int], dict[str, Any]] | None = None
map_dimensions = {"rows": 0, "cols": 0}

session_history: list[dict[str, Any]] = []