"""Lint checks for files under rfa-skill/ (except test fixtures) and tools/build_skill_data.py."""

import json
import pathlib
import re

import pytest
import yaml

SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_ROOT.parent
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_skill_data.py"
if not BUILD_SCRIPT.exists(): pytest.skip("repository-only test: tools/ is absent", allow_module_level=True)

# Character classes are built from code points so this file stays ASCII.
EMOJI = re.compile("[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in (
    (0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF))) + chr(0xFE0F) + chr(0x200D) + "]")
SPANISH_CODEPOINTS = (
    0xE1, 0xE9, 0xED, 0xF3, 0xFA, 0xC1, 0xC9, 0xCD, 0xD3, 0xDA,  # acute vowels
    0xE0, 0xE8, 0xEC, 0xF2, 0xF9, 0xC0, 0xC8, 0xCC, 0xD2, 0xD9,  # grave vowels
    0xFC, 0xDC, 0xF1, 0xD1, 0xBF, 0xA1,  # u with diaeresis, n with tilde, inverted marks
)
SPANISH = re.compile("[" + "".join(chr(c) for c in SPANISH_CODEPOINTS) + "]")
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".csl", ".txt"}
# Pre-existing reference tests that end with two newlines. Test edits are restricted to string
# literals, so they are listed here instead of being reformatted (whitespace only).
KNOWN_EXTRA_NEWLINE = {
    "references/tests/test_abbreviate_journal.py",
    "references/tests/test_formatters.py",
    "references/tests/test_resolve_metadata.py",
    "references/tests/test_validate_citations.py",
}


def scoped_files() -> list:
    files = []
    for p in sorted(SKILL_ROOT.rglob("*")):
        if not p.is_file():
            continue
        parts = p.relative_to(SKILL_ROOT).parts
        if "fixtures" in parts or "__pycache__" in parts or ".pytest_cache" in parts:
            continue
        files.append(p)
    files.append(BUILD_SCRIPT)
    return files


def label(p: pathlib.Path) -> str:
    try:
        return p.relative_to(SKILL_ROOT).as_posix()
    except ValueError:
        return p.relative_to(REPO_ROOT).as_posix()


def test_l1_no_emoji():
    """L1 No emoji or pictographic characters."""
    offending = []
    for p in scoped_files():
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if EMOJI.search(text):
            offending.append(label(p))
    assert offending == []


def test_l2_no_spanish_letters_in_python():
    """L2 Python files outside tests contain no Spanish letters or inverted punctuation."""
    offending = []
    for p in scoped_files():
        if p.suffix != ".py" or "tests" in p.relative_to(REPO_ROOT).parts:
            continue
        if SPANISH.search(p.read_text(encoding="utf-8")):
            offending.append(label(p))
    assert offending == []


def test_l3_parse_newlines_and_tabs():
    """L3 JSON/YAML parse; text files end with one newline; no tabs in Markdown or YAML."""
    problems, extra_newline = [], set()
    for p in scoped_files():
        if p.suffix not in TEXT_SUFFIXES:
            continue
        raw = p.read_bytes()
        name = label(p)
        if not raw:
            continue
        text = raw.decode("utf-8")
        if p.suffix == ".json":
            try:
                json.loads(text)
            except ValueError as e:
                problems.append(f"{name}: invalid JSON ({e})")
        if p.suffix in (".yaml", ".yml"):
            try:
                yaml.safe_load(text)
            except yaml.YAMLError as e:
                problems.append(f"{name}: invalid YAML ({e})")
        if p.suffix in (".md", ".yaml", ".yml") and "\t" in text:
            problems.append(f"{name}: tab character")
        normalized = text.replace("\r\n", "\n")
        if not normalized.endswith("\n"):
            problems.append(f"{name}: no trailing newline")
        elif normalized.endswith("\n\n"):
            extra_newline.add(name)
    unexpected = sorted(extra_newline - KNOWN_EXTRA_NEWLINE)
    problems.extend(f"{n}: more than one trailing newline" for n in unexpected)
    assert problems == []


@pytest.mark.parametrize("name", sorted(KNOWN_EXTRA_NEWLINE))
def test_l3b_known_exceptions_still_needed(name):
    """L3b Each listed exception still exists and still needs the exception (no stale entries)."""
    raw = (SKILL_ROOT / name).read_bytes().replace(b"\r\n", b"\n")
    assert raw.endswith(b"\n\n"), f"{name} no longer needs the exception; remove it"
