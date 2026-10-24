# -*- coding: utf-8 -*-
"""Tests for bibliographic metadata resolver."""

import json
import pytest

from _common import HostNotAllowed, RequestsClient, Response, normalize_doi, redact, user_agent
from resolve_metadata import crossref_to_csl, main, resolve


def test_r1_crossref_to_csl(fixtures_dir):
    """R1 crossref_to_csl converts work message to CSL-JSON correctly."""
    work_file = fixtures_dir / "crossref_work_sample.json"
    data = json.loads(work_file.read_text(encoding="utf-8"))
    msg = data["message"]
    item = crossref_to_csl(msg)

    assert item["type"] == "article-journal"
    assert item["title"] == "Sample article title in sentence case"
    assert len(item["author"]) == 2
    assert item["author"][0] == {"family": "Rivera", "given": "Ana Maria"}
    assert item["author"][1] == {"family": "Gomez", "given": "Luis"}
    assert item["container-title-short"] == "J Examples"
    assert item["issued"]["date-parts"] == [[2021, 5, 10]]
    assert item["volume"] == "12"
    assert item["issue"] == "3"
    assert item["page"] == "45-67"
    assert item["DOI"] == "10.1234/rfa.example.001"
    assert "abstract" not in item


def test_r2_valid_doi(fixtures_dir, fake_client_factory):
    """R2 valid DOI resolves via Crossref to verified status."""
    work_file = fixtures_dir / "crossref_work_sample.json"
    work_text = work_file.read_text(encoding="utf-8")
    client = fake_client_factory({
        "https://api.crossref.org/works/10.1234/rfa.example.001": Response(200, {}, work_text),
    })

    res = resolve({"doi": "10.1234/rfa.example.001"}, client)
    assert res["status"] == "verified"
    assert res["item"]["x-rfa"]["source"] == "crossref"
    assert res["item"]["x-rfa"]["status"] == "verified"
    assert "retrieved_at" in res["item"]["x-rfa"]


def test_r3_doi_fallback_doi_org(fixtures_dir, fake_client_factory):
    """R3 404 on Crossref falls back to doi.org content negotiation."""
    items_file = fixtures_dir / "items.csl.json"
    items_data = json.loads(items_file.read_text(encoding="utf-8"))
    sample_csl = json.dumps(items_data[0])

    client = fake_client_factory({
        "https://api.crossref.org/works/10.1234/datacite.001": Response(404, {}, "Not found"),
        "https://doi.org/10.1234/datacite.001": Response(200, {}, sample_csl),
    })

    res = resolve({"doi": "10.1234/datacite.001"}, client)
    assert res["status"] == "verified"
    assert res["item"]["x-rfa"]["source"] == "doi.org"
    assert len(client.calls) == 2
    doi_call = client.calls[1]
    assert doi_call["headers"].get("Accept") == "application/vnd.citationstyles.csl+json"


def test_r4_doi_not_found(fake_client_factory):
    """R4 Non-existent DOI returns not_found."""
    client = fake_client_factory({
        "https://api.crossref.org/works/10.1234/notfound": Response(404, {}, "Not found"),
        "https://doi.org/10.1234/notfound": Response(404, {}, "Not found"),
    })

    res = resolve({"doi": "10.1234/notfound"}, client)
    assert res["status"] == "not_found"
    assert res["item"] is None


def test_r5_title_match(fixtures_dir, fake_client_factory):
    """R5 Title + Author + Year matching single candidate resolves to verified."""
    search_file = fixtures_dir / "crossref_search_sample.json"
    search_text = search_file.read_text(encoding="utf-8")

    client = fake_client_factory({
        "https://api.crossref.org/works": Response(200, {}, search_text),
    })

    record = {
        "title": "Sample article title in sentence case",
        "author": "Rivera",
        "year": "2021",
    }
    res = resolve(record, client)
    assert res["status"] == "verified"
    assert res["item"]["DOI"] == "10.1234/rfa.example.001"


def test_r6_title_ambiguous(fake_client_factory):
    """R6 Two candidates with high similarity return ambiguous without selecting an item."""
    items = [
        {"title": ["Sample article title in sentence case"], "DOI": "10.1234/1", "author": [{"family": "Rivera"}]},
        {"title": ["Sample article title in sentence case"], "DOI": "10.1234/2", "author": [{"family": "Gomez"}]},
    ]
    resp_body = json.dumps({"status": "ok", "message": {"items": items}})

    client = fake_client_factory({
        "https://api.crossref.org/works": Response(200, {}, resp_body),
    })

    res = resolve({"title": "Sample article title in sentence case"}, client)
    assert res["status"] == "ambiguous"
    assert res["item"] is None
    assert len(res["candidates"]) == 2


def test_r7_title_not_found(fake_client_factory):
    """R7 Completely unrelated title query returns not_found."""
    items = [
        {"title": ["Quantum fluctuations in microcavities"], "DOI": "10.1234/3"},
    ]
    resp_body = json.dumps({"status": "ok", "message": {"items": items}})

    client = fake_client_factory({
        "https://api.crossref.org/works": Response(200, {}, resp_body),
    })

    res = resolve({"title": "Historical analysis of Latin American legal reforms"}, client)
    assert res["status"] == "not_found"
    assert res["item"] is None


def test_r8_pmid_resolution(fixtures_dir, fake_client_factory):
    """R8 PMID without DOI gives unresolved_no_doi; PMID with DOI resolves DOI."""
    work_file = fixtures_dir / "crossref_work_sample.json"
    work_text = work_file.read_text(encoding="utf-8")

    # 1. PMID without DOI
    no_doi_body = json.dumps({
        "result": {
            "1111": {
                "title": "Old Article Title",
                "source": "Old Journal",
                "pubdate": "1980",
                "articleids": [{"idtype": "pubmed", "value": "1111"}],
            }
        }
    })

    client_no_doi = fake_client_factory({
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi": Response(200, {}, no_doi_body),
    })

    res1 = resolve({"pmid": "1111"}, client_no_doi)
    assert res1["status"] == "unresolved_no_doi"
    assert res1["item"] is None
    assert res1["provenance"]["raw"]["title"] == "Old Article Title"

    # 2. PMID with DOI
    with_doi_body = json.dumps({
        "result": {
            "2222": {
                "title": "New Article",
                "articleids": [
                    {"idtype": "pubmed", "value": "2222"},
                    {"idtype": "doi", "value": "10.1234/rfa.example.001"},
                ],
            }
        }
    })

    client_with_doi = fake_client_factory({
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi": Response(200, {}, with_doi_body),
        "https://api.crossref.org/works/10.1234/rfa.example.001": Response(200, {}, work_text),
    })

    res2 = resolve({"pmid": "2222"}, client_with_doi)
    assert res2["status"] == "verified"
    assert res2["item"]["DOI"] == "10.1234/rfa.example.001"


def test_r9_retries_and_errors(monkeypatch):
    """R9 429 retries succeed; 500 retries exhaust to status: error without exception."""
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
            msg = '{"message": {"type": "journal-article", "title": ["A"], "DOI": "10.1234/a"}}'
            return MockResponse(200, {}, msg)

    client429 = RequestsClient(max_rps=0, sleep=fake_sleep, session=MockSession429())
    res429 = resolve({"doi": "10.1234/a"}, client429)
    assert res429["status"] == "verified"
    assert 2 in sleeps

    # 2. Continuous 500 error
    class MockSession500:
        def get(self, url, **kwargs):
            return MockResponse(500, {}, "Server error", reason="Server error")

    client500 = RequestsClient(retries=2, max_rps=0, sleep=fake_sleep, session=MockSession500())
    res500 = resolve({"doi": "10.1234/b"}, client500)
    assert res500["status"] == "error"
    assert "reason" in res500["provenance"]


def test_r10_privacy_and_allowed_hosts():
    """R10 Sensitive keys and emails redacted; non-allowed host raises HostNotAllowed."""
    env_with_email = {"RFA_CONTACT_EMAIL": "user@example.org", "NCBI_API_KEY": "secret123"}
    ua = user_agent(env=env_with_email, host="api.crossref.org")
    assert "user@example.org" in ua

    ua_plain = user_agent(env={}, host="api.crossref.org")
    assert "user@example.org" not in ua_plain

    redacted = redact("Error with secret123 and user@example.org", env=env_with_email)
    assert "secret123" not in redacted
    assert "user@example.org" not in redacted
    assert "***" in redacted

    client = RequestsClient(max_rps=0)
    with pytest.raises(HostNotAllowed):
        client.get("https://example.com/api")


def test_r11_normalize_doi():
    """R11 normalize_doi accepts valid DOIs and rejects invalid strings."""
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("doi:10.1234/abc") == "10.1234/abc"
    assert normalize_doi(" 10.1234/abc ") == "10.1234/abc"
    assert normalize_doi("http://dx.doi.org/10.1234/ABC") == "10.1234/abc"
    assert normalize_doi("1234/abc") is None
    assert normalize_doi("https://other.org/10.1234/abc") is None


def test_r12_no_openalex_calls(fake_client_factory):
    """R12 resolve does not make any requests to api.openalex.org."""
    client = fake_client_factory({
        "https://api.crossref.org/works/10.1234/xyz": Response(404, {}, "Not found"),
        "https://doi.org/10.1234/xyz": Response(404, {}, "Not found"),
    })
    resolve({"doi": "10.1234/xyz"}, client)
    hosts = [c["url"] for c in client.calls]
    assert not any("openalex" in h for h in hosts)


def test_r13_doi_url_encoding(fake_client_factory):
    """R13 DOI with ? and # is properly percent-encoded in URLs for Crossref and doi.org."""
    test_doi = "10.1234/abc?x=1#frag"
    client = fake_client_factory({
        "https://api.crossref.org/works/10.1234/abc%3Fx=1%23frag": Response(404, {}, "Not found"),
        "https://doi.org/10.1234/abc%3Fx=1%23frag": Response(404, {}, "Not found"),
    })
    resolve({"doi": test_doi}, client)
    urls = [c["url"] for c in client.calls]
    for u in urls:
        assert "%3F" in u
        assert "%23" in u
        assert "?x=1" not in u


def test_r14_doi_org_non_dict_or_no_title(fake_client_factory):
    """R14 doi.org returning a list or dict without title results in not_found."""
    client_list = fake_client_factory({
        "https://api.crossref.org/works/10.1234/list": Response(404, {}, "Not found"),
        "https://doi.org/10.1234/list": Response(200, {}, '[{"id": "item1"}]'),
    })
    res_list = resolve({"doi": "10.1234/list"}, client_list)
    assert res_list["status"] == "not_found"

    client_no_title = fake_client_factory({
        "https://api.crossref.org/works/10.1234/notitle": Response(404, {}, "Not found"),
        "https://doi.org/10.1234/notitle": Response(200, {}, '{"id": "item1", "type": "book"}'),
    })
    res_no_title = resolve({"doi": "10.1234/notitle"}, client_no_title)
    assert res_no_title["status"] == "not_found"


def test_r15_main_cli_malformed_and_empty(tmp_path, capsys):
    """R15 main with malformed line outputs error with line number and code 2; empty file returns code 2."""
    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_text('{"doi": "10.1234/a"}\n{bad json}\n{"doi": "10.1234/c"}\n', encoding="utf-8")

    code_bad = main(["--in", str(bad_jsonl)])
    captured_bad = capsys.readouterr()
    assert code_bad == 2
    assert "2" in captured_bad.err

    empty_jsonl = tmp_path / "empty.jsonl"
    empty_jsonl.write_text("", encoding="utf-8")
    code_empty = main(["--in", str(empty_jsonl)])
    assert code_empty == 2


def test_r16_title_search_match_fields(fixtures_dir, fake_client_factory):
    """R16 Verified title search includes year_match and author_match in x-rfa.match."""
    search_file = fixtures_dir / "crossref_search_sample.json"
    search_text = search_file.read_text(encoding="utf-8")

    client = fake_client_factory({
        "https://api.crossref.org/works": Response(200, {}, search_text),
    })
    res = resolve({
        "title": "Sample article title in sentence case",
        "author": "Rivera",
        "year": "2021",
    }, client)

    assert res["status"] == "verified"
    match = res["item"]["x-rfa"]["match"]
    assert "year_match" in match
    assert "author_match" in match
    assert match["year_match"] is True
    assert match["author_match"] is True


def test_r17_network_exception_redacts_email(monkeypatch):
    """R17 Network exception with encoded email has redacted provenance.reason."""
    env = {"RFA_CONTACT_EMAIL": "ana.perez@example.org"}

    class MockFailingClient:
        def get(self, url, **kwargs):
            raise Exception("Connection reset to https://api.crossref.org/works?mailto=ana.perez%40example.org")

    res = resolve({"doi": "10.1234/test"}, MockFailingClient(), env=env)
    assert res["status"] == "error"
    reason = res["provenance"]["reason"]
    assert "ana.perez" not in reason
    assert "ana.perez%40example.org" not in reason
    assert "***" in reason



def _items_out_client(fixtures_dir, fake_client_factory):
    work_text = (fixtures_dir / "crossref_work_sample.json").read_text(encoding="utf-8")
    return fake_client_factory({
        "https://api.crossref.org/works/10.1234/rfa.example.001": Response(200, {}, work_text),
        "https://api.crossref.org/works/10.9999/missing": Response(404, {}, "Not found"),
        "https://doi.org/10.9999/missing": Response(404, {}, "Not found"),
    })


def test_i1_items_out_keeps_only_verified(tmp_path, monkeypatch, fixtures_dir, fake_client_factory):
    """I1 --items-out writes only the verified item of a mixed --in file."""
    client = _items_out_client(fixtures_dir, fake_client_factory)
    monkeypatch.setattr("resolve_metadata.RequestsClient", lambda **kwargs: client)
    refs = tmp_path / "refs.jsonl"
    refs.write_text('{"doi": "10.1234/rfa.example.001"}\n{"doi": "10.9999/missing"}\n', encoding="utf-8")
    items_out = tmp_path / "items.csl.json"
    main(["--in", str(refs), "--out", str(tmp_path / "resolved.json"), "--items-out", str(items_out)])
    items = json.loads(items_out.read_text(encoding="utf-8"))
    assert len(items) == 1
    assert items[0]["DOI"] == "10.1234/rfa.example.001"
    assert items[0]["x-rfa"]["status"] == "verified"


def test_i2_items_out_single_record_is_list(tmp_path, monkeypatch, fixtures_dir, fake_client_factory):
    """I2 a single resolved --doi still gives a list of length 1."""
    client = _items_out_client(fixtures_dir, fake_client_factory)
    monkeypatch.setattr("resolve_metadata.RequestsClient", lambda **kwargs: client)
    items_out = tmp_path / "items.csl.json"
    main(["--doi", "10.1234/rfa.example.001", "--out", str(tmp_path / "resolved.json"),
          "--items-out", str(items_out)])
    items = json.loads(items_out.read_text(encoding="utf-8"))
    assert isinstance(items, list)
    assert len(items) == 1


def test_i3_items_out_without_verified_writes_empty_list(tmp_path, monkeypatch, fixtures_dir, fake_client_factory):
    """I3 no verified result: the items file is [] and the exit code is unchanged."""
    client = _items_out_client(fixtures_dir, fake_client_factory)
    monkeypatch.setattr("resolve_metadata.RequestsClient", lambda **kwargs: client)
    out = str(tmp_path / "resolved.json")
    code_plain = main(["--doi", "10.9999/missing", "--out", out])
    items_out = tmp_path / "items.csl.json"
    code_items = main(["--doi", "10.9999/missing", "--out", out, "--items-out", str(items_out)])
    assert json.loads(items_out.read_text(encoding="utf-8")) == []
    assert code_items == code_plain

def test_i4_doi_org_item_gets_family_year_id(fake_client_factory):
    """I4 an item resolved through doi.org gets the familyYEAR id and keeps the upstream id."""
    upstream = {"id": "https://doi.org/10.5281/zenodo.1", "type": "dataset", "title": "A dataset",
                "author": [{"family": "P\u00e9rez", "given": "Ana"}], "issued": {"date-parts": [[2020]]}}
    client = fake_client_factory({
        "https://api.crossref.org/works/10.5281/zenodo.1": Response(404, {}, "Not found"),
        "https://doi.org/10.5281/zenodo.1": Response(200, {}, json.dumps(upstream)),
    })
    res = resolve({"doi": "10.5281/zenodo.1"}, client)
    assert res["status"] == "verified"
    assert res["item"]["id"] == "perez2020"
    assert res["item"]["x-rfa"]["upstream_id"] == "https://doi.org/10.5281/zenodo.1"

