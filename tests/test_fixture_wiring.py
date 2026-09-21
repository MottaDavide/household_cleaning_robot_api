"""Guards on the fixture tree itself.

A fixture-driven suite has two ways to fail *open* -- to look green while
asserting nothing:

1. a fixture is added but never wired up, so it is silently never exercised;
2. git or an editor rewrites a byte-sensitive fixture, so the case still runs
   but no longer means what its name claims.

These tests close both holes. They never touch the application, so they must be
green from the very first run: if they are red, the problem is in the fixture
corpus, not in ``src/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.map_cases import (
    EXPECTED_STATUS_BY_BUCKET,
    FIXTURES_ROOT,
    MANIFEST_NAME,
    MAP_CASES,
    VALID_CASES,
    load_manifest,
)

SUMMARY_KEYS = {"rows", "cols", "walkable_tiles"}


@pytest.mark.parametrize("bucket", sorted(EXPECTED_STATUS_BY_BUCKET))
def test_every_bucket_contributes_cases(bucket: str) -> None:
    """A glob that silently matches nothing is the failure mode we fear most."""
    assert [c for c in MAP_CASES if c.bucket == bucket], f"no fixtures discovered in {bucket}/"


def test_no_unknown_directories_under_maps() -> None:
    """A typo'd bucket name would park fixtures where nothing collects them."""
    found = {p.name for p in FIXTURES_ROOT.iterdir() if p.is_dir()}
    assert found == set(EXPECTED_STATUS_BY_BUCKET)


def test_every_valid_fixture_has_an_expected_body() -> None:
    """Report *all* unwired fixtures at once, not just the first."""
    missing = sorted(str(c) for c in VALID_CASES if c.expected_body is None)
    assert not missing, f"missing from valid/{MANIFEST_NAME}: {missing}"


def test_manifest_has_no_entries_without_a_fixture() -> None:
    """The other direction: a renamed fixture leaves a dangling expectation."""
    on_disk = {c.path.name for c in VALID_CASES}
    orphaned = sorted(set(load_manifest("valid")) - on_disk)
    assert not orphaned, f"valid/{MANIFEST_NAME} names files that do not exist: {orphaned}"


def test_expected_bodies_have_exactly_the_summary_keys() -> None:
    for case in VALID_CASES:
        assert case.expected_body is not None
        assert set(case.expected_body) == SUMMARY_KEYS, f"{case} has odd keys"
        assert all(isinstance(v, int) for v in case.expected_body.values()), case


def test_manifests_are_not_collected_as_fixtures() -> None:
    """The manifest is a .json file living beside .json fixtures.

    Without the `_` prefix rule in discovery it would be collected and uploaded
    as a map, producing a phantom case that fails for a baffling reason.
    """
    assert MANIFEST_NAME.startswith("_")
    assert not [c for c in MAP_CASES if c.path.name.startswith("_")]


# --------------------------------------------------------------------------
# Byte-level canaries.
#
# git config core.autocrlf is `true` on Windows, so without the repo-root
# .gitattributes (`tests/fixtures/maps/** -text`) every one of these fixtures
# would be rewritten on checkout and quietly stop testing what it claims.
# These assertions fail loudly and by name instead.
# --------------------------------------------------------------------------

def fixture(bucket: str, name: str) -> Path:
    return FIXTURES_ROOT / bucket / name


def test_gitattributes_pins_the_fixture_bytes() -> None:
    gitattributes = FIXTURES_ROOT.parents[2] / ".gitattributes"
    assert gitattributes.is_file(), "repo-root .gitattributes is missing"
    assert "tests/fixtures/maps/** -text" in gitattributes.read_text("utf-8")


@pytest.mark.parametrize(
    "name",
    ["spec_example_3x4_crlf.txt", "spec_example_3x4_crlf_no_trailing_newline.txt"],
)
def test_crlf_fixtures_still_contain_crlf(name: str) -> None:
    data = fixture("valid", name).read_bytes()
    assert b"\r\n" in data, f"{name} claims CRLF but has none -- check .gitattributes"
    assert data.replace(b"\r\n", b"").count(b"\n") == 0, f"{name} has mixed line endings"


@pytest.mark.parametrize(
    "name",
    ["spec_example_3x4_no_trailing_newline.txt", "min_1x1_walkable.txt", "single_row_1x4.txt"],
)
def test_no_trailing_newline_fixtures_really_have_none(name: str) -> None:
    data = fixture("valid", name).read_bytes()
    assert not data.endswith(b"\n"), f"{name} grew a trailing newline -- an editor added it"


def test_exactly_one_trailing_newline_fixture_has_exactly_one() -> None:
    data = fixture("valid", "spec_example_3x4.txt").read_bytes()
    assert data.endswith(b"\n") and not data.endswith(b"\n\n")


@pytest.mark.parametrize(
    ("name", "ending"),
    [("two_trailing_newlines.txt", b"\n\n"), ("two_trailing_newlines_crlf.txt", b"\r\n\r\n")],
)
def test_two_trailing_newline_fixtures_really_have_two(name: str, ending: bytes) -> None:
    assert fixture("invalid_content", name).read_bytes().endswith(ending)


def test_non_utf8_fixture_is_still_undecodable() -> None:
    data = fixture("invalid_content", "non_utf8_bytes.txt").read_bytes()
    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8")


def test_lone_carriage_return_fixture_has_no_line_feed() -> None:
    data = fixture("invalid_content", "lone_carriage_return.txt").read_bytes()
    assert b"\r" in data and b"\n" not in data


def test_cyrillic_lookalike_is_valid_utf8_but_not_an_ascii_o() -> None:
    """The point of this fixture is that it *looks* like a legal map."""
    data = fixture("invalid_content", "cyrillic_o_lookalike.txt").read_bytes()
    # Compared by codepoint on purpose: writing the character itself would put
    # an invisible ASCII-o lookalike into the source, which is the trap this
    # fixture exists to catch.
    assert ord(data.decode("utf-8")[0]) == 0x43E  # CYRILLIC SMALL LETTER O


def test_unsupported_extension_fixtures_hold_valid_map_content() -> None:
    """415 must win over 422: these carry good maps under a bad filename."""
    for case in (c for c in MAP_CASES if c.bucket == "unsupported_extension"):
        text = case.path.read_bytes().decode("utf-8")
        assert set(text) <= {"o", "x", "\n"}, f"{case} should contain a valid TXT map"


def test_json_fixtures_named_malformed_are_the_only_unparseable_ones() -> None:
    """Keeps a typo in a structural fixture from masquerading as a syntax case."""
    intentionally_broken = {"malformed_syntax.json", "txt_content_in_json_file.json"}
    for case in MAP_CASES:
        if case.path.suffix.lower() != ".json" or case.path.name in intentionally_broken:
            continue
        try:
            json.loads(case.path.read_bytes())
        except json.JSONDecodeError as exc:  # pragma: no cover - guard
            pytest.fail(f"{case} is not valid JSON but is not named as a syntax case: {exc}")
