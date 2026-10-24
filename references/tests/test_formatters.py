# -*- coding: utf-8 -*-
"""Tests for bibliographic formatting engines (pandoc and citeproc-py)."""

import pathlib
import re
import pytest
import yaml

from format_reference import (
    STYLE_MAP,
    BackendUnavailable,
    available_backends,
    format_bibliography,
    render_document,
)


def _strip_numeric_label(text: str) -> str:
    return re.sub(r"^\[?\d+\]?\.?\s*", "", text).strip()


def test_s1_apa_single_item(backend, items, golden, norm, csl_dir):
    """S1 APA: bibliography of single rivera2021a equals golden output."""
    single = [it for it in items if it["id"] == "rivera2021a"]
    csl = csl_dir / "apa-7.csl"
    res = format_bibliography(single, csl, backend=backend)
    assert len(res["entries"]) == 1
    text = res["entries"][0]["text"]
    assert norm(text) == norm(golden["rivera2021a"])


def test_s2_apa_okafor(backend, items, golden, norm, csl_dir):
    """S2 APA: bibliography of single okafor2019 equals golden output."""
    single = [it for it in items if it["id"] == "okafor2019"]
    csl = csl_dir / "apa-7.csl"
    res = format_bibliography(single, csl, backend=backend)
    assert len(res["entries"]) == 1
    text = res["entries"][0]["text"]
    assert norm(text) == norm(golden["okafor2019"])


def test_s3_apa_pandoc_year_suffixes(items, csl_dir):
    """S3 APA pandoc: rivera2021b receives (2021a) and rivera2021a receives (2021b)."""
    backends = available_backends()
    if not backends.get("pandoc"):
        pytest.skip("pandoc is not available")

    pair = [it for it in items if it["id"] in ("rivera2021a", "rivera2021b")]
    csl = csl_dir / "apa-7.csl"
    res = format_bibliography(pair, csl, backend="pandoc")
    entry_map = {e["id"]: e["text"] for e in res["entries"]}
    assert "(2021a)" in entry_map["rivera2021b"]
    assert "(2021b)" in entry_map["rivera2021a"]


def test_s3b_apa_citeproc_year_suffix_warning(items, csl_dir):
    """S3b APA citeproc-py: warning year_suffix_not_applied and (2021) in texts."""
    backends = available_backends()
    if not backends.get("citeproc-py"):
        pytest.skip("citeproc-py is not available")

    pair = [it for it in items if it["id"] in ("rivera2021a", "rivera2021b")]
    csl = csl_dir / "apa-7.csl"
    res = format_bibliography(pair, csl, backend="citeproc-py")
    warn_codes = [w["code"] for w in res["warnings"]]
    assert "year_suffix_not_applied" in warn_codes
    for e in res["entries"]:
        assert "(2021)" in e["text"]


def test_s4_apa_order(backend, items, csl_dir):
    """S4 APA: order of all 6 items matches expected alphabetical order."""
    csl = csl_dir / "apa-7.csl"
    res = format_bibliography(items, csl, backend=backend)
    ids_in_order = [e["id"] for e in res["entries"]]
    expected = ["many2018", "institute2022", "okafor2019", "rivera2021b", "rivera2021a", "silva2020"]
    assert ids_in_order == expected


def test_s5_vancouver_rivera(backend, items, norm, csl_dir):
    """S5 Vancouver: rivera2021a entry without numeric label matches expected."""
    csl = csl_dir / "vancouver.csl"
    res = format_bibliography(items, csl, backend=backend)
    entry = next(e for e in res["entries"] if e["id"] == "rivera2021a")
    clean_text = _strip_numeric_label(entry["text"])
    expected = "Rivera AM, Gomez L. Sample article title in sentence case. J Examples. 2021;12(3):45–67. doi:10.1234/rfa.example.001"
    assert norm(clean_text) == norm(expected)


def test_s5b_vancouver_many_authors(backend, items, csl_dir):
    """S5b Vancouver: many2018 contains first 6 authors + et al. and not 7th."""
    csl = csl_dir / "vancouver.csl"
    res = format_bibliography(items, csl, backend=backend)
    entry = next(e for e in res["entries"] if e["id"] == "many2018")
    assert "Alpha A, Beta B, Gamma C, Delta D, Epsilon E, Zeta F, et al." in entry["text"]
    assert "Eta G" not in entry["text"]


def test_s5c_vancouver_page_range(backend, items, csl_dir):
    """S5c Vancouver: many2018 contains 1–10 (xfail for citeproc-py)."""
    if backend == "citeproc-py":
        pytest.xfail(reason="citeproc-py 0.11.1 renders 1-10 as 1–0 with NLM")
    csl = csl_dir / "vancouver.csl"
    res = format_bibliography(items, csl, backend=backend)
    entry = next(e for e in res["entries"] if e["id"] == "many2018")
    assert "1–10" in entry["text"]


def test_s6_ieee(backend, items, csl_dir):
    """S6 IEEE: volume, issue, pages, and et al. formatting."""
    csl = csl_dir / "ieee-2024.csl"
    res = format_bibliography(items, csl, backend=backend)
    riv = next(e for e in res["entries"] if e["id"] == "rivera2021a")
    assert "A. M. Rivera and L. Gomez" in riv["text"]
    assert "vol. 12" in riv["text"]
    assert "no. 3" in riv["text"]
    assert "pp. 45–67" in riv["text"]

    many = next(e for e in res["entries"] if e["id"] == "many2018")
    norm_many = many["text"].replace("*", "")
    assert "A. Alpha et al." in norm_many


def test_s7_render_document_pandoc(fixtures_dir, items, csl_dir):
    """S7 render_document with pandoc: in-text citations and missing_key warning."""
    backends = available_backends()
    if not backends.get("pandoc"):
        pytest.skip("pandoc is not available")

    doc_path = fixtures_dir / "doc_keys.md"
    doc_text = doc_path.read_text(encoding="utf-8")
    csl = csl_dir / "apa-7.csl"

    res = render_document(doc_text, items, csl)
    rendered = res["text"]
    assert "Rivera & Gomez, 2021" in rendered
    assert "Okafor, 2019; Silva, 2020, p. 20" in rendered
    assert "Example Institute for Research (2022)" in rendered

    warn_codes = [w["code"] for w in res["warnings"]]
    assert "missing_key" in warn_codes
    missing_ids = [w["id"] for w in res["warnings"] if w["code"] == "missing_key"]
    assert "ghost2000" in missing_ids
    assert "ghost2000" in rendered


def test_s8_render_document_no_pandoc(monkeypatch, items, csl_dir):
    """S8 render_document without pandoc raises BackendUnavailable."""
    from format_reference import available_backends
    monkeypatch.setattr("format_reference.available_backends", lambda: {"pandoc": None, "citeproc-py": "0.11.1"})
    csl = csl_dir / "apa-7.csl"
    with pytest.raises(BackendUnavailable):
        render_document("# Test", items, csl)


def test_s9_cross_check(monkeypatch, items, csl_dir):
    """S9 Cross-check: disagreement produces backend_disagreement warning."""
    csl = csl_dir / "apa-7.csl"

    # 1. Different outputs
    def fake_pandoc(itms, csl_p, loc, exe):
        return [{"id": "rivera2021a", "html": "Text A", "text": "Text A"}]

    def fake_citeproc(itms, csl_p, loc):
        return [{"id": "rivera2021a", "html": "Text B", "text": "Text B"}], []

    monkeypatch.setattr("format_reference.available_backends", lambda: {"pandoc": "mock_pandoc", "citeproc-py": "0.11.1"})
    monkeypatch.setattr("format_reference._format_pandoc", fake_pandoc)
    monkeypatch.setattr("format_reference._format_citeproc", fake_citeproc)

    res_diff = format_bibliography([items[0]], csl, cross_check=True)
    codes_diff = [w["code"] for w in res_diff["warnings"]]
    assert "backend_disagreement" in codes_diff

    # 2. Identical outputs
    def fake_citeproc_same(itms, csl_p, loc):
        return [{"id": "rivera2021a", "html": "Text A", "text": "Text A"}], []

    monkeypatch.setattr("format_reference._format_citeproc", fake_citeproc_same)
    res_same = format_bibliography([items[0]], csl, cross_check=True)
    codes_same = [w["code"] for w in res_same["warnings"]]
    assert "backend_disagreement" not in codes_same


def test_s10_style_map(csl_dir):
    """S10 STYLE_MAP files exist in csl_dir and appear in MANIFEST.yaml."""
    manifest_path = csl_dir / "MANIFEST.yaml"
    assert manifest_path.exists()
    manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest_names = {f["spec_name"] for f in manifest_data["files"]}

    for key, filename in STYLE_MAP.items():
        csl_file = csl_dir / filename
        assert csl_file.exists(), f"File for {key} does not exist: {filename}"
        assert filename in manifest_names, f"File {filename} not in MANIFEST.yaml"


def test_s11_locale_es_es(items, csl_dir):
    """S11 Locale es-ES with pandoc contains 'Rivera, A. M.'."""
    backends = available_backends()
    if not backends.get("pandoc"):
        pytest.skip("pandoc is not available")

    single = [it for it in items if it["id"] == "rivera2021a"]
    csl = csl_dir / "apa-7.csl"
    res = format_bibliography(single, csl, locale="es-ES", backend="pandoc")
    assert len(res["entries"]) == 1
    assert "Rivera, A. M." in res["entries"][0]["text"]


def test_s12_render_document_pandoc_error(monkeypatch, items, csl_dir):
    """S12 render_document raises RuntimeError when pandoc returns non-zero exit code."""
    import subprocess
    csl = csl_dir / "apa-7.csl"
    monkeypatch.setattr("format_reference.available_backends", lambda: {"pandoc": "pandoc", "citeproc-py": "0.11.1"})

    class MockFailedProcess:
        returncode = 1
        stdout = ""
        stderr = "Error in pandoc processing"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockFailedProcess())
    with pytest.raises(RuntimeError):
        render_document("# Test", items, csl)


def test_s13_explicit_citeproc_warning(items, csl_dir):
    """S13 Explicit citeproc-py backend includes partial_csl_support warning."""
    backends = available_backends()
    if not backends.get("citeproc-py"):
        pytest.skip("citeproc-py is not available")
    csl = csl_dir / "apa-7.csl"
    res = format_bibliography(items[:1], csl, backend="citeproc-py")
    warn_codes = [w["code"] for w in res["warnings"]]
    assert "partial_csl_support" in warn_codes


def test_s14_citeproc_version_from_importlib():
    """S14 available_backends citeproc-py version matches importlib.metadata.version."""
    import importlib.metadata
    backends = available_backends()
    expected_version = importlib.metadata.version("citeproc-py")
    assert backends["citeproc-py"] == expected_version


def test_p1_stale_rfa_pandoc_returns_none(monkeypatch):
    """P1 RFA_PANDOC set to a non-existent path and no other pandoc: available_backends()['pandoc'] is None."""
    monkeypatch.setenv("RFA_PANDOC", "/non/existent/path/to/pandoc")
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    try:
        import pypandoc
        monkeypatch.setattr("pypandoc.get_pandoc_path", lambda: "/non/existent/pypandoc/pandoc")
    except ImportError:
        pass
    backends = available_backends()
    assert backends["pandoc"] is None


def test_p2_stale_rfa_pandoc_raises_backend_unavailable(monkeypatch, items, csl_dir):
    """P2 same situation: format_bibliography(..., backend='pandoc') raises BackendUnavailable and the message mentions RFA_PANDOC and the missing path."""
    stale_path = "/non/existent/path/to/pandoc"
    monkeypatch.setenv("RFA_PANDOC", stale_path)
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    try:
        import pypandoc
        monkeypatch.setattr("pypandoc.get_pandoc_path", lambda: "/non/existent/pypandoc/pandoc")
    except ImportError:
        pass
    csl = csl_dir / "apa-7.csl"
    with pytest.raises(BackendUnavailable) as exc_info:
        format_bibliography(items[:1], csl, backend="pandoc")
    msg = str(exc_info.value)
    assert "RFA_PANDOC" in msg
    assert stale_path in msg
    assert "pip install pypandoc_binary" in msg


def test_p3_rfa_pandoc_valid_executable(monkeypatch):
    """P3 RFA_PANDOC set to sys.executable: available_backends()['pandoc'] equals that path."""
    import sys
    monkeypatch.setenv("RFA_PANDOC", sys.executable)
    backends = available_backends()
    assert backends["pandoc"] == sys.executable


def test_p4_stale_rfa_pandoc_fallback_to_path(monkeypatch):
    """P4 RFA_PANDOC stale but shutil.which returns a valid path: the PATH candidate is returned."""
    import sys
    monkeypatch.setenv("RFA_PANDOC", "/non/existent/stale/pandoc")
    monkeypatch.setattr("shutil.which", lambda cmd: sys.executable if cmd == "pandoc" else None)
    backends = available_backends()
    assert backends["pandoc"] == sys.executable


def test_p5_pandoc_diagnostics_reports_stale_path(monkeypatch):
    """P5 pandoc_diagnostics() reports the stale RFA_PANDOC path and contains no other environment value."""
    from format_reference import pandoc_diagnostics
    stale_path = "/custom/stale/pandoc/bin"
    monkeypatch.setenv("RFA_PANDOC", stale_path)
    monkeypatch.setenv("SOME_SECRET_ENV_VAR", "super_secret_value")
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    try:
        import pypandoc
        monkeypatch.setattr("pypandoc.get_pandoc_path", lambda: "/non/existent/pypandoc/pandoc")
    except ImportError:
        pass
    diags = pandoc_diagnostics()
    combined = " ".join(diags)
    assert "RFA_PANDOC" in combined
    assert stale_path in combined
    assert "super_secret_value" not in combined
    assert "SOME_SECRET_ENV_VAR" not in combined




class _FakeProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_pandoc_backend(monkeypatch, version=(3, 9)):
    monkeypatch.setattr("format_reference.available_backends", lambda: {"pandoc": "fake_pandoc", "citeproc-py": None})
    monkeypatch.setattr("format_reference.pandoc_version", lambda path: version)


def _codes(res, code):
    return [w for w in res["warnings"] if w["code"] == code]


def test_p6_render_document_uses_markdown_without_citations_extension(monkeypatch, items, csl_dir):
    """P6 render_document asks pandoc for markdown-smart-citations, so citations are rendered by any pandoc version."""
    import subprocess
    _fake_pandoc_backend(monkeypatch)
    commands = []

    def fake_run(cmd, *args, **kwargs):
        commands.append(list(cmd))
        return _FakeProcess()

    monkeypatch.setattr(subprocess, "run", fake_run)
    render_document("Text [@rivera2021a].", items, csl_dir / "apa-7.csl")
    assert any(cmd[i] == "-t" and cmd[i + 1] == "markdown-smart-citations"
               for cmd in commands for i in range(len(cmd) - 1))


def test_p7_old_pandoc_version_warns(monkeypatch, items, csl_dir):
    """P7 pandoc older than 3.9 gives pandoc_version_untested with the dotted version."""
    _fake_pandoc_backend(monkeypatch, (3, 1, 3))
    monkeypatch.setattr("format_reference._format_pandoc", lambda itms, csl_p, loc, exe: [])
    res = format_bibliography(items[:1], csl_dir / "apa-7.csl", backend="pandoc")
    found = _codes(res, "pandoc_version_untested")
    assert len(found) == 1
    assert found[0]["version"] == "3.1.3"


def test_p8_tested_pandoc_version_does_not_warn(monkeypatch, items, csl_dir):
    """P8 pandoc 3.9 gives no pandoc_version_untested."""
    _fake_pandoc_backend(monkeypatch, (3, 9))
    monkeypatch.setattr("format_reference._format_pandoc", lambda itms, csl_p, loc, exe: [])
    res = format_bibliography(items[:1], csl_dir / "apa-7.csl", backend="pandoc")
    assert _codes(res, "pandoc_version_untested") == []


def test_p9_unknown_pandoc_version_warns(monkeypatch, items, csl_dir):
    """P9 an unreadable pandoc version gives pandoc_version_untested with version unknown."""
    _fake_pandoc_backend(monkeypatch, None)
    monkeypatch.setattr("format_reference._format_pandoc", lambda itms, csl_p, loc, exe: [])
    res = format_bibliography(items[:1], csl_dir / "apa-7.csl", backend="pandoc")
    found = _codes(res, "pandoc_version_untested")
    assert len(found) == 1
    assert found[0]["version"] == "unknown"


def test_p10_pandoc_error_message_is_redacted(monkeypatch, items, csl_dir):
    """P10 a pandoc failure does not leak the contact email in the RuntimeError message."""
    import subprocess
    fake_email = "contact.person@example.org"
    monkeypatch.setenv("RFA_CONTACT_EMAIL", fake_email)
    _fake_pandoc_backend(monkeypatch)
    monkeypatch.setattr(subprocess, "run",
                        lambda *args, **kwargs: _FakeProcess(1, "", f"failure for {fake_email}"))
    with pytest.raises(RuntimeError) as exc_info:
        format_bibliography(items[:1], csl_dir / "apa-7.csl", backend="pandoc")
    assert fake_email not in str(exc_info.value)


def test_u1_unverified_items_are_flagged(monkeypatch, items, csl_dir):
    """U1 fixture items have no x-rfa: one unverified_item per item, in input order."""
    _fake_pandoc_backend(monkeypatch)
    monkeypatch.setattr("format_reference._format_pandoc", lambda itms, csl_p, loc, exe: [])
    res = format_bibliography(items, csl_dir / "apa-7.csl", backend="pandoc")
    assert [w["id"] for w in _codes(res, "unverified_item")] == [it["id"] for it in items]


def test_u2_verified_item_is_not_flagged(monkeypatch, items, csl_dir):
    """U2 an item with x-rfa.status verified gives no unverified_item."""
    _fake_pandoc_backend(monkeypatch)
    monkeypatch.setattr("format_reference._format_pandoc", lambda itms, csl_p, loc, exe: [])
    item = dict(items[0], **{"x-rfa": {"status": "verified", "source": "crossref"}})
    res = format_bibliography([item], csl_dir / "apa-7.csl", backend="pandoc")
    assert _codes(res, "unverified_item") == []


def test_u3_render_document_flags_unverified(monkeypatch, items, csl_dir):
    """U3 render_document also emits unverified_item for items without verified provenance."""
    import subprocess
    _fake_pandoc_backend(monkeypatch)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _FakeProcess())
    res = render_document("Text [@rivera2021a].", items[:2], csl_dir / "apa-7.csl")
    assert [w["id"] for w in _codes(res, "unverified_item")] == [it["id"] for it in items[:2]]


def _fake_selection(monkeypatch, path_cand, pyp_cand, versions, rfa_pandoc=None):
    pypandoc = pytest.importorskip("pypandoc")
    if rfa_pandoc:
        monkeypatch.setenv("RFA_PANDOC", rfa_pandoc)
    else:
        monkeypatch.delenv("RFA_PANDOC", raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: path_cand if cmd == "pandoc" else None)
    monkeypatch.setattr(pypandoc, "get_pandoc_path", lambda: pyp_cand)
    monkeypatch.setattr("format_reference._is_valid_executable", lambda p: bool(p))
    monkeypatch.setattr("format_reference.pandoc_version", lambda p: versions.get(p))


def test_p11_old_path_pandoc_yields_to_tested_pypandoc(monkeypatch):
    """P11 an older pandoc on PATH yields to a pypandoc copy that meets the tested version."""
    _fake_selection(monkeypatch, "/fake/path/pandoc", "/fake/pyp/pandoc",
                    {"/fake/path/pandoc": (3, 1, 3), "/fake/pyp/pandoc": (3, 9)})
    assert available_backends()["pandoc"] == "/fake/pyp/pandoc"


def test_p12_path_pandoc_kept_when_unknown_or_tested(monkeypatch):
    """P12 the PATH pandoc is kept when its version is unknown or already tested."""
    _fake_selection(monkeypatch, "/fake/path/pandoc", "/fake/pyp/pandoc",
                    {"/fake/path/pandoc": None, "/fake/pyp/pandoc": (3, 9)})
    assert available_backends()["pandoc"] == "/fake/path/pandoc"
    _fake_selection(monkeypatch, "/fake/path/pandoc", "/fake/pyp/pandoc",
                    {"/fake/path/pandoc": (3, 9), "/fake/pyp/pandoc": (3, 10)})
    assert available_backends()["pandoc"] == "/fake/path/pandoc"


def test_p13_valid_rfa_pandoc_always_wins(monkeypatch):
    """P13 a valid RFA_PANDOC is returned even when it is older than the tested version."""
    _fake_selection(monkeypatch, "/fake/path/pandoc", "/fake/pyp/pandoc",
                    {"/fake/env/pandoc": (3, 1, 3), "/fake/path/pandoc": (3, 1, 3), "/fake/pyp/pandoc": (3, 9)},
                    rfa_pandoc="/fake/env/pandoc")
    assert available_backends()["pandoc"] == "/fake/env/pandoc"


