# -*- coding: utf-8 -*-
"""Regression tests for common HTTP client, host whitelisting, and redaction."""

import pytest

from _common import ALLOWED_HOSTS, HostNotAllowed, HttpError, RequestsClient, Response, redact, user_agent


def test_c1_validate_host():
    """C1 _validate_host blocks malicious or non-whitelisted URLs and allows valid ones."""
    client = RequestsClient(max_rps=0)

    blocked_urls = [
        "https://api.crossref.org:443@evil.example/x",
        "https://api.crossref.org@evil.example/x",
        "http://api.crossref.org/works/x",
        "https://api.crossref.org:8443/x",
        "https://evil.example/x",
    ]
    for url in blocked_urls:
        with pytest.raises(HostNotAllowed):
            client._validate_host(url)

    allowed_urls = [
        "https://api.crossref.org/works/x",
        "https://doi.org/10.1/x",
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        "https://api.crossref.org:443/works/x",
    ]
    for url in allowed_urls:
        client._validate_host(url)  # Must not raise


def test_c2_redirect_to_disallowed_host():
    """C2 Redirect to an unallowed or spoofed host raises HostNotAllowed."""
    class MockRedirectSession:
        def get(self, url, **kwargs):
            return Response(302, {"Location": "https://api.crossref.org:443@evil.example/"}, "")

    client = RequestsClient(max_rps=0, session=MockRedirectSession())
    with pytest.raises(HostNotAllowed):
        client.get("https://api.crossref.org/works/test")


def test_c3_infinite_redirect_loop():
    """C3 Infinite redirect loop raises HttpError with 'redirect' and max 6 requests."""
    calls = []

    class MockLoopSession:
        def get(self, url, **kwargs):
            calls.append(url)
            return Response(302, {"Location": "https://api.crossref.org/works/loop"}, "")

    client = RequestsClient(max_rps=0, session=MockLoopSession())
    with pytest.raises(HttpError) as exc_info:
        client.get("https://api.crossref.org/works/loop")

    assert "redirect" in str(exc_info.value).lower()
    assert len(calls) <= 6


def test_c4_redact_variants():
    """C4 redact hides raw email and encoded variants case-insensitively, and API keys."""
    env = {
        "RFA_CONTACT_EMAIL": "ana.perez@example.org",
        "NCBI_API_KEY": "my_secret_key_123",
    }
    raw_text = "Contact: ana.perez@example.org"
    enc_text = "URL: https://api.crossref.org/works?mailto=ana.perez%40example.org"
    enc_upper = "URL: https://api.crossref.org/works?mailto=ana.perez%40EXAMPLE.org"
    key_text = "API key: my_secret_key_123"

    assert redact(raw_text, env=env) == "Contact: ***"
    assert redact(enc_text, env=env) == "URL: https://api.crossref.org/works?mailto=***"
    assert redact(enc_upper, env=env) == "URL: https://api.crossref.org/works?mailto=***"
    assert redact(key_text, env=env) == "API key: ***"


def test_c5_exception_redacts_email_in_url(monkeypatch):
    """C5 Session exception containing mailto with encoded email produces redacted HttpError."""
    monkeypatch.setenv("RFA_CONTACT_EMAIL", "ana.perez@example.org")

    class MockFailingSession:
        def get(self, url, **kwargs):
            raise Exception("Connection failed to https://api.crossref.org/works?mailto=ana.perez%40example.org")

    client = RequestsClient(retries=0, max_rps=0, session=MockFailingSession())
    with pytest.raises(HttpError) as exc_info:
        client.get("https://api.crossref.org/works?mailto=ana.perez%40example.org")

    error_str = str(exc_info.value)
    # Check that ana.perez@example.org does not appear in any form
    assert "ana.perez" not in error_str
    assert "ana.perez%40example.org" not in error_str
    assert "ana.perez%40EXAMPLE.org" not in error_str
    assert "***" in error_str


def test_c6_retries_429_and_5xx_still_work():
    """C6 Retries for 429 and 5xx continue functioning properly."""
    sleeps = []
    fake_sleep = lambda s: sleeps.append(s)

    class MockResponse:
        def __init__(self, status_code, headers, text, reason=""):
            self.status_code = status_code
            self.headers = headers
            self.text = text
            self.reason = reason

    # 1. 429 retry then 200
    class MockSession429:
        count = 0
        def get(self, url, **kwargs):
            self.count += 1
            if self.count == 1:
                return MockResponse(429, {"Retry-After": "2"}, "Rate limit", reason="Rate limit")
            return MockResponse(200, {}, "OK")

    client429 = RequestsClient(max_rps=0, sleep=fake_sleep, session=MockSession429())
    res429 = client429.get("https://api.crossref.org/works/test")
    assert res429.status == 200
    assert 2 in sleeps

    # 2. Continuous 500 error exhausts retries and raises HttpError
    class MockSession500:
        def get(self, url, **kwargs):
            return MockResponse(500, {}, "Server error", reason="Server error")

    client500 = RequestsClient(retries=2, max_rps=0, sleep=fake_sleep, session=MockSession500())
    with pytest.raises(HttpError) as exc_info:
        client500.get("https://api.crossref.org/works/test")
    assert exc_info.value.status == 500


def test_h1_allowed_hosts_set():
    """H1 ALLOWED_HOSTS is exactly the set of 5 hosts."""
    assert ALLOWED_HOSTS == {
        "api.crossref.org",
        "doi.org",
        "data.crosscite.org",
        "eutils.ncbi.nlm.nih.gov",
        "api.openalex.org",
    }


def test_h2_validate_host_data_crosscite():
    """H2 _validate_host allows data.crosscite.org and blocks malicious/subdomain variants."""
    client = RequestsClient(max_rps=0)
    # Permitted:
    client._validate_host("https://data.crosscite.org/10.5281%2Fzenodo.10853560")

    # Blocked:
    blocked = [
        "https://evil.crosscite.org/x",
        "https://data.crosscite.org.evil.example/x",
        "https://crosscite.org/x",
    ]
    for url in blocked:
        with pytest.raises(HostNotAllowed):
            client._validate_host(url)


def test_h3_redirect_preserves_accept_header():
    """H3 doi.org 302 to data.crosscite.org preserves Accept header and returns 200 body."""
    requests_log = []

    class MockRedirectSession:
        def get(self, url, headers=None, **kwargs):
            requests_log.append((url, dict(headers or {})))
            if url == "https://doi.org/10.5281/zenodo.10853560":
                return Response(
                    302,
                    {"Location": "https://data.crosscite.org/10.5281%2Fzenodo.10853560"},
                    "",
                )
            elif url == "https://data.crosscite.org/10.5281%2Fzenodo.10853560":
                return Response(200, {"Content-Type": "application/vnd.citationstyles.csl+json"}, '{"title": "dataset"}')
            return Response(404, {}, "Not found")

    client = RequestsClient(max_rps=0, session=MockRedirectSession())
    accept_val = "application/vnd.citationstyles.csl+json"
    res = client.get("https://doi.org/10.5281/zenodo.10853560", headers={"Accept": accept_val})

    assert res.status == 200
    assert res.body == '{"title": "dataset"}'
    assert len(requests_log) == 2
    # Verify second request preserved the Accept header
    second_req_url, second_req_headers = requests_log[1]
    assert second_req_url == "https://data.crosscite.org/10.5281%2Fzenodo.10853560"
    assert second_req_headers.get("Accept") == accept_val


def test_h4_user_agent_only_sends_email_to_crossref(monkeypatch):
    """H4 User-Agent only includes mailto for api.crossref.org and not other hosts or redirects."""
    email = "ana.perez@example.org"
    monkeypatch.setenv("RFA_CONTACT_EMAIL", email)

    sent_headers = {}

    class MockLoggingSession:
        def get(self, url, headers=None, **kwargs):
            sent_headers[url] = dict(headers or {})
            if url == "https://doi.org/redirect":
                return Response(302, {"Location": "https://data.crosscite.org/dest"}, "")
            return Response(200, {}, "OK")

    client = RequestsClient(max_rps=0, session=MockLoggingSession())

    # 1. api.crossref.org
    client.get("https://api.crossref.org/works/123")
    cr_ua = sent_headers["https://api.crossref.org/works/123"]["User-Agent"]
    assert f"mailto:{email}" in cr_ua

    # 2. Other allowed hosts
    other_urls = [
        "https://doi.org/item",
        "https://data.crosscite.org/item",
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        "https://api.openalex.org/works",
    ]
    for u in other_urls:
        client.get(u)
        ua = sent_headers[u]["User-Agent"]
        assert email not in ua
        assert "ana.perez" not in ua
        assert "%40" not in ua
        assert "mailto" not in ua

    # 3. Redirect from doi.org to data.crosscite.org
    client.get("https://doi.org/redirect")
    redirect_ua = sent_headers["https://data.crosscite.org/dest"]["User-Agent"]
    assert email not in redirect_ua
    assert "ana.perez" not in redirect_ua
    assert "%40" not in redirect_ua
    assert "mailto" not in redirect_ua


def test_h5_user_agent_without_contact_email(monkeypatch):
    """H5 Without RFA_CONTACT_EMAIL, no User-Agent contains 'mailto'."""
    monkeypatch.delenv("RFA_CONTACT_EMAIL", raising=False)

    sent_headers = {}

    class MockLoggingSession:
        def get(self, url, headers=None, **kwargs):
            sent_headers[url] = dict(headers or {})
            return Response(200, {}, "OK")

    client = RequestsClient(max_rps=0, session=MockLoggingSession())

    hosts_to_test = [
        "https://api.crossref.org/works/123",
        "https://doi.org/item",
        "https://data.crosscite.org/item",
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        "https://api.openalex.org/works",
    ]
    for u in hosts_to_test:
        client.get(u)
        ua = sent_headers[u]["User-Agent"]
        assert "mailto" not in ua
