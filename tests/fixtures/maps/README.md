# Map fixtures

Every file in a bucket directory is one test case, and **the bucket is the
expected HTTP status**:

| Directory                | Status | Expected body                        |
| ------------------------ | ------ | ------------------------------------ |
| `valid/`                 | 200    | from `valid/_expected.json`          |
| `unsupported_extension/` | 415    | not asserted (only the status)       |
| `invalid_content/`       | 422    | not asserted (only the status)       |

Discovery lives in [`tests/map_cases.py`](../../map_cases.py); the assertions
live in [`tests/test_map_upload_contract.py`](../../test_map_upload_contract.py).

## Adding a case

1. Drop the file into the right bucket. No test code changes.
2. If it goes in `valid/`, add its expected summary to `valid/_expected.json`.
   `test_fixture_wiring.py` fails if you forget, and fails again if you leave a
   manifest entry behind after renaming a fixture.

Files whose name starts with `_` are metadata, not cases. That prefix is the
only thing keeping `_expected.json` — itself a `.json` file sitting next to
`.json` fixtures — from being collected and uploaded as a map.

## On disk vs inline

> A case lives on disk when its meaning is visible when you open the file.
> A case lives inline in a test when its meaning is **invisible** — encodings,
> byte-order marks, bytes that are not text at all.

So the LF / CRLF / trailing-newline matrix is on disk (visible enough, and
guarded), while the UTF-8 BOM case is a byte literal in
`test_map_upload_protocol.py`. `non_utf8_bytes.txt` is the one deliberate
exception: it is kept on disk so the corpus stays complete, and it has an inline
twin in the protocol module stating the same rule where tooling cannot reach it.

## These bytes are load-bearing

`git config core.autocrlf` is `true` on Windows. Without the repo-root
`.gitattributes` (`tests/fixtures/maps/** -text`), git would rewrite line
endings on checkout and the newline fixtures would silently stop testing what
their names claim — a false green, the worst outcome for a suite like this.

`.gitattributes` is the fix; the byte-level canaries in `test_fixture_wiring.py`
are the alarm if it ever stops working. Those canaries never touch the
application, so **if they are red the problem is the fixture corpus, not
`src/`**.

Do not open these files in an editor that trims trailing whitespace or
"fixes" final newlines. Note that `space_character.txt` keeps its space in the
*middle* of a row for exactly this reason: as a trailing space it would have
quietly become a ragged-row case instead.

Filenames are also load-bearing, and NTFS is case-insensitive — two fixtures
differing only by case (`map.txt` / `MAP.TXT`) would be the same file. The
case-insensitivity of the extension check is covered by distinct stems
(`uppercase_extension.TXT`, `mixed_case_extension.TxT`) plus parametrized
filenames in `test_map_upload_protocol.py`.

## Deliberately not tested

Judgement calls, recorded so they read as decisions rather than oversights.

**Pydantic coerces these, and the contract says it may.** The spec states that
"rejecting other JSON types coerced to a boolean (for example the string
`"true"`) is not required". Asserting 422 for them would fail, and would be
wrong:

- `{"walkable": "true"}` — coerced to `True`
- `{"rows": "2"}` — coerced to `2`
- `{"rows": true}` — coerced to `1`
- `{"rows": 2.0}` — an integral float is accepted for an `int` field. This is
  why the rejection fixture uses **1.5**, not 2.0.

**Undocumented, so out of bounds.** The spec says hidden tests "do not test
undocumented behavior":

- extra keys on a tile object (`{"x":0,"y":0,"walkable":true,"color":"red"}`) —
  currently ignored. Whether to reject them is an implementation decision
  (`model_config = ConfigDict(extra="forbid")`), not a test decision.
- mixing `\n` and `\r\n` in one file — both endings are individually accepted
  and mixing is not addressed.

**Error wording.** The contract says "the exact error body for ordinary
validation failures is up to you", so the suite asserts the status code and
that a non-empty `detail` is present, never the message text. One consequence
worth knowing: two redundant checks that produce the same status are
indistinguishable to these tests. `_parse_txt_map` has such a pair — removing
the blank-row check leaves the ragged-row check to catch the same inputs with a
different message, and the suite stays green. That is the intended trade-off,
not a gap.
