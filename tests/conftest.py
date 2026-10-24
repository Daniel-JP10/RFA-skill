"""Pytest configuration for the skill decision tools and the data layer."""

import json
import pathlib
import sys

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
SKILL_ROOT = TESTS_DIR.parent
REPO_ROOT = SKILL_ROOT.parent
SCRIPTS_DIR = SKILL_ROOT / "scripts"
REF_SCRIPTS_DIR = SKILL_ROOT / "references" / "scripts"
DATA_FILE = SKILL_ROOT / "data" / "rfa_data.json"
TEMPLATES_FILE = SKILL_ROOT / "disclosure" / "templates.json"
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_skill_data.py"

for _path in (SCRIPTS_DIR, REF_SCRIPTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

with open(DATA_FILE, "r", encoding="utf-8") as _f:
    _DATA = json.load(_f)


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Ensure no real network socket connections are made during testing."""
    def guard(*args, **kwargs):
        raise RuntimeError("Network calls blocked during tests")
    monkeypatch.setattr("socket.socket.connect", guard)


@pytest.fixture(scope="session")
def data() -> dict:
    return _DATA


@pytest.fixture(scope="session")
def templates() -> dict:
    with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def registry_location_codes(data) -> list:
    codes = []
    for entry in data["ai_policies"].values():
        for code in entry.get("locations") or []:
            if code not in codes:
                codes.append(code)
    return codes
