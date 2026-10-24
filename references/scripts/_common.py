# -*- coding: utf-8 -*-
"""Common utilities, HTTP client, and normalization helpers for RFA references."""

from collections import namedtuple
import difflib
import os
import re
import time
import unicodedata
import urllib.parse

import requests

RFA_VERSION = "0.1.0"
ALLOWED_HOSTS = {
    "api.crossref.org",
    "doi.org",
    "data.crosscite.org",
    "eutils.ncbi.nlm.nih.gov",
    "api.openalex.org",
}

Response = namedtuple("Response", "status headers body")


class HostNotAllowed(Exception):
    """Raised when an HTTP request targets a host outside ALLOWED_HOSTS."""
    pass


class HttpError(Exception):
    """Raised when an HTTP request fails after exhausted retries."""
    def __init__(self, status: int, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(f"HTTP {status}: {reason}")


def user_agent(env=os.environ, host=None) -> str:
    """Build the User-Agent header string. Includes mailto ONLY for api.crossref.org."""
    ua = f"RFA-skill/{RFA_VERSION}"
    if host == "api.crossref.org":
        email = env.get("RFA_CONTACT_EMAIL")
        if email:
            ua += f" (mailto:{email})"
    return ua


def redact(text: str, env=os.environ) -> str:
    """Redact sensitive environment variables from text (raw and encoded variants)."""
    if not text:
        return ""
    result = str(text)
    for var in ("NCBI_API_KEY", "OPENALEX_API_KEY", "RFA_CONTACT_EMAIL"):
        val = env.get(var)
        if not val:
            continue
        variants = {
            val,
            urllib.parse.quote(val, safe=""),
            urllib.parse.quote(val),
            urllib.parse.quote_plus(val),
        }
        for variant in sorted(variants, key=len, reverse=True):
            if variant:
                result = re.sub(re.escape(variant), "***", result, flags=re.IGNORECASE)
    return result


def normalize_doi(value: str) -> str | None:
    """Normalize and validate a DOI string."""
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    lower_s = s.lower()
    for prefix in ("https://doi.org/", "http://dx.doi.org/", "doi:"):
        if lower_s.startswith(prefix):
            s = s[len(prefix):].strip()
            break
    s = s.lower()
    if re.match(r"^10\.\d{4,9}/\S+$", s):
        return s
    return None


def normalize_text(s: str) -> str:
    """Normalize text with NFKD, no combining marks, casefold, and alnum spaces."""
    if not s:
        return ""
    decomposed = unicodedata.normalize("NFKD", s)
    no_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    cf = no_marks.casefold()
    clean = re.sub(r"[^\w]+", " ", cf).strip()
    return clean


def title_similarity(a: str, b: str) -> float:
    """Compute string similarity ratio on normalized text."""
    na = normalize_text(a)
    nb = normalize_text(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def first_author_family(item: dict) -> str | None:
    """Extract family name or literal from the first author, or first editor."""
    authors = item.get("author") or []
    if authors and len(authors) > 0:
        first = authors[0]
        return first.get("family") or first.get("literal")
    editors = item.get("editor") or []
    if editors and len(editors) > 0:
        first = editors[0]
        return first.get("family") or first.get("literal")
    return None


class RequestsClient:
    """Rate-limited HTTP client with strict host whitelist and exponential backoff."""

    def __init__(
        self,
        max_rps: float = 1.0,
        retries: int = 3,
        timeout: float = 15.0,
        sleep=time.sleep,
        session=None,
    ):
        self.max_rps = max_rps
        self.retries = retries
        self.timeout = timeout
        self.sleep = sleep
        self.session = session or requests.Session()
        self._last_request_time = 0.0

    def _validate_host(self, url: str):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https":
            raise HostNotAllowed("scheme not allowed")
        if parsed.username is not None or parsed.password is not None:
            raise HostNotAllowed("credentials not allowed in URL")
        try:
            port = parsed.port
        except ValueError:
            raise HostNotAllowed("invalid port")
        if port is not None and port != 443:
            raise HostNotAllowed(f"port {port} not allowed")

        host = (parsed.hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            raise HostNotAllowed(f"host '{host}' not allowed")

    def get(self, url: str, params=None, headers=None) -> Response:
        """Perform a validated GET request with rate limiting and retries."""
        self._validate_host(url)

        req_headers = dict(headers or {})
        user_agent_provided = any(k.lower() == "user-agent" for k in req_headers)

        current_url = url
        current_params = params

        if not user_agent_provided:
            parsed_initial = urllib.parse.urlparse(current_url)
            initial_host = (parsed_initial.hostname or "").lower()
            req_headers["User-Agent"] = user_agent(host=initial_host)

        backoffs = [1.0, 2.0, 4.0]
        status = None
        redirect_count = 0
        attempt = 0

        while attempt <= self.retries:
            # Rate limiting
            if self.max_rps > 0:
                elapsed = time.time() - self._last_request_time
                min_interval = 1.0 / self.max_rps
                if elapsed < min_interval:
                    self.sleep(min_interval - elapsed)

            self._last_request_time = time.time()

            try:
                # Do not follow redirects automatically so we can validate each redirect host
                resp = self.session.get(
                    current_url,
                    params=current_params,
                    headers=req_headers,
                    timeout=self.timeout,
                    allow_redirects=False,
                )
            except Exception as e:
                if attempt < self.retries:
                    delay = backoffs[attempt] if attempt < len(backoffs) else 4.0
                    self.sleep(delay)
                    attempt += 1
                    continue
                raise HttpError(0, redact(str(e)))

            # Handle redirects manually
            resp_status = getattr(resp, "status_code", getattr(resp, "status", None))
            if resp_status in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    return Response(resp_status, dict(resp.headers), getattr(resp, "text", getattr(resp, "body", "")))
                redirect_count += 1
                if redirect_count > 5:
                    raise HttpError(0, "Too many redirects")
                target_url = urllib.parse.urljoin(current_url, location)
                self._validate_host(target_url)
                current_url = target_url
                current_params = None  # Params are encoded in redirect location
                if not user_agent_provided:
                    parsed_target = urllib.parse.urlparse(target_url)
                    target_host = (parsed_target.hostname or "").lower()
                    req_headers["User-Agent"] = user_agent(host=target_host)
                continue

            status = resp_status

            # 429 Rate Limit
            if status == 429:
                if attempt < self.retries:
                    retry_after = resp.headers.get("Retry-After")
                    delay = None
                    if retry_after:
                        try:
                            delay = min(int(retry_after), 60)
                        except ValueError:
                            delay = None
                    if delay is None:
                        delay = backoffs[attempt] if attempt < len(backoffs) else 4.0
                    self.sleep(delay)
                    attempt += 1
                    continue
                reason = getattr(resp, "reason", None) or "Too Many Requests"
                raise HttpError(status, redact(reason))

            # 5xx Server Error
            if 500 <= status <= 599:
                if attempt < self.retries:
                    delay = backoffs[attempt] if attempt < len(backoffs) else 4.0
                    self.sleep(delay)
                    attempt += 1
                    continue
                reason = getattr(resp, "reason", None) or "Server Error"
                raise HttpError(status, redact(reason))

            # 2xx, 4xx, etc.
            return Response(status, dict(resp.headers), getattr(resp, "text", getattr(resp, "body", "")))

        raise HttpError(status or 0, "Retries exhausted")
