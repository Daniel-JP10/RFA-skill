# -*- coding: utf-8 -*-
"""Pytest fixtures and configuration for reference skill tests."""

import json
import pathlib
import re
import sys
import urllib.parse

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "scripts"
SKILL_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
CSL_DIR = SKILL_ROOT / "csl"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _common import ALLOWED_HOSTS, HostNotAllowed, Response
from format_reference import available_backends


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Ensure no real network socket connections are made during testing."""
    def guard(*args, **kwargs):
        raise RuntimeError("Network calls blocked during tests")
    monkeypatch.setattr("socket.socket.connect", guard)


@pytest.fixture
def fixtures_dir() -> pathlib.Path:
    return FIXTURES_DIR


@pytest.fixture
def csl_dir() -> pathlib.Path:
    return CSL_DIR


@pytest.fixture
def items(fixtures_dir) -> list[dict]:
    with open(fixtures_dir / "items.csl.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def golden(fixtures_dir) -> dict:
    with open(fixtures_dir / "golden_apa7.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def norm():
    def _norm(s: str) -> str:
        if not s:
            return ""
        clean = s.replace("\u00a0", " ")
        return re.sub(r"\s+", " ", clean).strip()
    return _norm


class FakeClient:
    """Mock HTTP client for deterministic offline testing."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def get(self, url: str, params=None, headers=None) -> Response:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        if ":" in host:
            host = host.split(":", 1)[0]
        if host not in ALLOWED_HOSTS:
            raise HostNotAllowed(f"Host '{host}' is not allowed in tests")

        call_record = {
            "url": url,
            "params": dict(params or {}),
            "headers": dict(headers or {}),
        }
        self.calls.append(call_record)

        resp = self.responses.get(url)
        if resp is None:
            base_url = url.split("?")[0]
            resp = self.responses.get(base_url)

        if isinstance(resp, list):
            if resp:
                resp_val = resp.pop(0)
            else:
                return Response(404, {}, "Not found")
        else:
            resp_val = resp

        if resp_val is None:
            return Response(404, {}, "Not found")
        if isinstance(resp_val, Response):
            return resp_val
        if isinstance(resp_val, tuple):
            return Response(resp_val[0], resp_val[1], resp_val[2])
        return resp_val


@pytest.fixture
def fake_client_factory():
    def _factory(responses=None):
        return FakeClient(responses=responses)
    return _factory


@pytest.fixture(params=["pandoc", "citeproc-py"])
def backend(request):
    b = request.param
    backends = available_backends()
    if b == "pandoc" and not backends.get("pandoc"):
        pytest.skip("pandoc is not available")
    if b == "citeproc-py" and not backends.get("citeproc-py"):
        pytest.skip("citeproc-py is not available")
    return b
