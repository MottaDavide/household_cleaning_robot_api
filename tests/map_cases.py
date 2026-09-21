"""Discovery of the on-disk map fixtures.

Every file under ``tests/fixtures/maps/<bucket>/`` is one test case, and the
bucket it sits in *is* its expected HTTP status. Adding a case means dropping a
file into the right directory -- no test code changes.

This lives in a plain module rather than in ``conftest.py`` because
``@pytest.mark.parametrize`` needs the case list at collection time, so it has
to be importable. ``tests`` resolves as a namespace package thanks to
``pythonpath = ["."]`` in pyproject.toml.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "maps"

# The one place the directory -> status mapping is written down. Buckets are
# named after the contract ("415 when the filename has an unsupported
# extension") rather than after the number, so `pytest -k unsupported_extension`
# reads as a sentence.
EXPECTED_STATUS_BY_BUCKET: dict[str, int] = {
    "valid": 200,
    "unsupported_extension": 415,
    "invalid_content": 422,
}

# Expected 200 bodies live in one manifest per bucket rather than in a sidecar
# per fixture. The `_` prefix is what keeps it out of discovery -- without it,
# a `.json` manifest would itself be collected and uploaded as a map.
MANIFEST_NAME = "_expected.json"


@dataclass(frozen=True)
class MapCase:
    path: Path
    bucket: str
    expected_status: int
    expected_body: dict | None  # only for bucket == "valid"

    def __str__(self) -> str:
        # pytest id, e.g. "invalid_content/ragged_shorter_row.txt"
        return f"{self.bucket}/{self.path.name}"


def load_manifest(bucket: str) -> dict[str, dict]:
    manifest = FIXTURES_ROOT / bucket / MANIFEST_NAME
    if not manifest.is_file():
        return {}
    return json.loads(manifest.read_text("utf-8"))


def discover_map_cases() -> list[MapCase]:
    """Collect every fixture file, pairing valid ones with their expected body.

    Deliberately tolerant: a fixture missing from the manifest yields
    ``expected_body=None`` instead of raising, so ``test_fixture_wiring`` can
    report every wiring problem at once rather than the session dying on the
    first one.
    """
    cases: list[MapCase] = []
    for bucket, status in EXPECTED_STATUS_BY_BUCKET.items():
        manifest = load_manifest(bucket)
        for path in sorted((FIXTURES_ROOT / bucket).iterdir()):
            if not path.is_file() or path.name.startswith("_"):
                continue
            cases.append(MapCase(path, bucket, status, manifest.get(path.name)))
    return cases


MAP_CASES: list[MapCase] = discover_map_cases()
VALID_CASES = [c for c in MAP_CASES if c.expected_status == 200]
REJECTED_CASES = [c for c in MAP_CASES if c.expected_status != 200]
