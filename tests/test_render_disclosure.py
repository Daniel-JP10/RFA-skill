"""Tests for render_disclosure.py (AI-use statements driven by the policy registry)."""

import json
import pathlib
import subprocess
import sys

import pytest

from render_disclosure import render

RENDER = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "render_disclosure.py"
REGISTRY_KEYS = sorted(json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "data" / "rfa_data.json")
    .read_text(encoding="utf-8"))["ai_policies"])

FULL = {
    "tool": "ExampleAssistant",
    "version": "2.1",
    "developer": "Example Labs",
    "purpose": "editing the language of the discussion section",
    "verification": "the authors checked every sentence against their own results",
}


def strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v)
    elif isinstance(node, str):
        yield node


def test_d1_springer_generative_en(data):
    """D1 springer-nature + generative_content, all fields: statements, placements, source."""
    res = render("springer-nature", "generative_content", data=data, **FULL)
    assert res["status"] == "ok"
    assert res["required"] is True
    assert [p["code"] for p in res["placements"]] == data["ai_policies"]["springer-nature"]["locations"]
    assert res["statements"]
    assert "methods" in res["statements"]
    assert "ExampleAssistant (2.1, Example Labs)" in res["statements"]["methods"]["text"]
    assert res["source"]["policy_url"].startswith("https://")
    assert res["source"]["policy_date"] and res["source"]["verified_on"]
    assert res["source"]["needs_review"] is False
    assert res["assertions_to_confirm"]


def test_d2_missing_purpose(data):
    """D2 Missing purpose: missing_fields, no statement, the field named."""
    fields = dict(FULL, purpose=None)
    res = render("springer-nature", "generative_content", data=data, **fields)
    assert res["status"] == "missing_fields"
    assert res["statements"] == {}
    assert res["assertions_to_confirm"] == []
    assert "purpose" in res["missing_fields"]
    assert any(e.get("field") == "purpose" for e in res["errors"])
    blank = render("springer-nature", "generative_content", data=data, **dict(FULL, purpose="  "))
    assert blank["status"] == "missing_fields"


def test_d3_spanish(data):
    """D3 lang es: Spanish statement and Spanish location labels."""
    res = render("wiley", "generative_content", lang="es", data=data, **FULL)
    assert res["status"] == "ok"
    ack = res["statements"]["acknowledgments"]["text"]
    assert ack.startswith("Durante la preparación de este trabajo")
    labels = {p["code"]: p["label"] for p in res["placements"]}
    assert labels["acknowledgments"] == "agradecimientos"
    assert labels["methods"] == "métodos"
    assert res["assertions_to_confirm"][0] == "Los autores revisaron y editaron el resultado."


def test_d4_acm_language_editing(data):
    """D4 acm + language_editing: conditional, exemptions listed."""
    res = render("acm", "language_editing", data=data, **FULL)
    assert res["required"] == "conditional"
    assert res["exemptions"] == data["ai_policies"]["acm"]["exempt"]
    assert res["exemptions"]
    assert any("exemptions" in n for n in res["notes"])
    assert res["source"]["needs_review"] is True


def test_d5_kind_none(data):
    """D5 kind none: nothing required, no statement."""
    res = render("elsevier", "none", data=data, **FULL)
    assert res["status"] == "ok"
    assert res["required"] is False
    assert res["statements"] == {}
    assert res["placements"] == []


def test_d6_unknown_policy(data):
    """D6 Unknown policy: error with suggestions."""
    res = render("springer-natur", "generative_content", data=data, **FULL)
    assert res["status"] == "invalid_input"
    err = res["errors"][0]
    assert err["code"] == "unknown_policy"
    assert "springer-nature" in err["suggestions"]


@pytest.mark.parametrize("lang", ["en", "es"])
def test_d7_no_unfilled_placeholders(lang, data):
    """D7 No output string contains an unfilled '{'."""
    for key in REGISTRY_KEYS:
        for kind in ("generative_content", "language_editing", "research_conduct"):
            res = render(key, kind, date="2026-10-01", lang=lang, data=data, **FULL)
            for s in strings(res):
                assert "{" not in s, (key, kind, s)


def test_d8_research_conduct_methods(data):
    """D8 research_conduct: a methods statement that requires verification."""
    res = render("icmje", "research_conduct", data=data, **FULL)
    assert res["status"] == "ok"
    assert list(res["statements"]) == ["methods"]
    assert "Verification of the output" in res["statements"]["methods"]["text"]
    missing = render("icmje", "research_conduct", data=data, **dict(FULL, verification=None))
    assert missing["status"] == "missing_fields"
    assert missing["missing_fields"] == ["verification"]
    assert missing["statements"] == {}


@pytest.mark.parametrize("policy", REGISTRY_KEYS)
def test_d9_every_policy_renders(policy, data):
    """D9 Every registry policy renders without error for generative_content."""
    res = render(policy, "generative_content", data=data, **FULL)
    assert res["status"] == "ok", res["errors"]
    assert res["errors"] == []
    assert res["statements"]
    assert all(p["label"] for p in res["placements"])


def test_d10_date_clause(data):
    """D10 The date clause appears only when a date is given, in the requested language."""
    en = render("wiley", "generative_content", date="March 2026", data=data, **FULL)
    assert "(2.1, Example Labs) on March 2026 for" in en["statements"]["acknowledgments"]["text"]
    es = render("wiley", "generative_content", date="marzo de 2026", lang="es", data=data, **FULL)
    assert "(2.1, Example Labs) el marzo de 2026 para" in es["statements"]["acknowledgments"]["text"]
    no_date = render("wiley", "generative_content", data=data, **FULL)
    assert "(2.1, Example Labs) for" in no_date["statements"]["acknowledgments"]["text"]


def test_d11_cover_letter_refers_to_manuscript_section(data):
    """D11 ICMJE lists a cover letter; it names the manuscript section where use is disclosed."""
    res = render("icmje", "generative_content", data=data, **FULL)
    cover = res["statements"]["cover_letter"]["text"]
    assert "disclosed in the acknowledgments section" in cover
    assert "The use is disclosed in the stated section." in res["assertions_to_confirm"]


def test_d12_dedicated_section_uses_declaration_text(data):
    """D12 Elsevier's dedicated section gets the general declaration statement."""
    res = render("elsevier", "generative_content", data=data, **FULL)
    ack = res["statements"]["acknowledgments"]
    assert ack["placements"] == ["separate_section_before_references"]
    assert ack["text"].startswith("During the preparation of this work")


def test_d13_invalid_kind_and_language(data):
    """D13 Unknown kind or language: invalid_input with suggestions."""
    res = render("wiley", "magic", data=data, **FULL)
    assert res["status"] == "invalid_input"
    assert res["errors"][0]["code"] == "unknown_kind"
    res = render("wiley", "generative_content", lang="fr", data=data, **FULL)
    assert res["errors"][0]["code"] == "unsupported_language"


def test_d14_cli():
    """D14 CLI: complete input exits 0 with JSON; missing fields exit 1."""
    base = [sys.executable, str(RENDER), "--policy", "plos", "--kind", "generative_content",
            "--tool", "T", "--version", "1", "--developer", "D", "--purpose", "P"]
    ok = subprocess.run(base + ["--verification", "V", "--lang", "es"], capture_output=True)
    assert ok.returncode == 0
    assert json.loads(ok.stdout.decode("utf-8"))["status"] == "ok"
    missing = subprocess.run(base, capture_output=True)
    assert missing.returncode == 1
    assert json.loads(missing.stdout.decode("utf-8"))["status"] == "missing_fields"


@pytest.mark.parametrize("purpose", ["{verification}", "testing {x}", "closing brace }"])
def test_d15_braces_in_user_fields_are_rejected(purpose, data):
    """D15 Braces in a field are rejected cleanly; user text is never treated as a template."""
    res = render("wiley", "generative_content", data=data, **dict(FULL, purpose=purpose))
    assert res["status"] == "invalid_input"
    assert res["errors"][0]["code"] == "invalid_characters"
    assert res["errors"][0]["fields"] == ["purpose"]
    assert res["statements"] == {}


NO_VERIFICATION = {k: v for k, v in FULL.items() if k != "verification"}


def test_e1_acknowledgments_only(data):
    """E1 acknowledgments only, no verification needed: only that statement is produced."""
    res = render("wiley", "generative_content", data=data, statements=["acknowledgments"],
                 **NO_VERIFICATION)
    assert res["status"] == "ok"
    assert list(res["statements"]) == ["acknowledgments"]
    assert res["statements_requested"] == ["acknowledgments"]


def test_e2_methods_requires_verification(data):
    """E2 methods requested without verification: missing_fields naming verification."""
    res = render("wiley", "generative_content", data=data, statements=["methods"], **NO_VERIFICATION)
    assert res["status"] == "missing_fields"
    assert res["missing_fields"] == ["verification"]
    assert res["statements"] == {}


def test_e3_invalid_statement_name(data):
    """E3 an invalid statement type lists the valid options."""
    res = render("wiley", "generative_content", data=data, statements=["abstract"], **FULL)
    assert res["status"] == "invalid_input"
    err = res["errors"][0]
    assert err["code"] == "invalid_statements"
    assert err["suggestions"] == ["acknowledgments", "methods", "cover_letter"]


def test_e4_default_unchanged_and_cover_letter_placement(data):
    """E4 default output equals statements=None; a requested cover letter needs a placement."""
    assert render("icmje", "generative_content", data=data, **FULL) == \
        render("icmje", "generative_content", data=data, statements=None, **FULL)
    res = render("icmje", "generative_content", data=data, statements=["cover_letter"],
                 **NO_VERIFICATION)
    assert res["status"] == "ok" and list(res["statements"]) == ["cover_letter"]
    assert "acknowledgments section" in res["statements"]["cover_letter"]["text"]
    altered = {**data, "ai_policies": {**data["ai_policies"], "wiley": {
        **data["ai_policies"]["wiley"], "locations": ["cover_letter"]}}}
    res = render("wiley", "generative_content", data=altered, statements=["cover_letter"],
                 **NO_VERIFICATION)
    assert res["status"] == "missing_fields" and res["missing_fields"] == ["placement"]


def test_e5_cli_statements_option():
    """E5 --statements on the CLI."""
    base = [sys.executable, str(RENDER), "--policy", "wiley", "--kind", "generative_content",
            "--tool", "T", "--version", "1", "--developer", "D", "--purpose", "P"]
    ok = subprocess.run(base + ["--statements", "acknowledgments"], capture_output=True)
    assert ok.returncode == 0
    assert list(json.loads(ok.stdout.decode("utf-8"))["statements"]) == ["acknowledgments"]


def test_d16_research_conduct_without_methods_location(data):
    """D16 Elsevier lists no methods location: methods statement plus an explanatory note."""
    res = render("elsevier", "research_conduct", data=data, **FULL)
    assert list(res["statements"]) == ["methods"]
    assert any("lists no methods location" in n for n in res["notes"])
    res = render("wiley", "research_conduct", data=data, **FULL)
    assert not any("lists no methods location" in n for n in res["notes"])

def test_d16_policy_note_in_notes(data):
    """D16 a policy note without needs_review reaches the statement notes."""
    res = render("ieee", "language_editing", data=data, **FULL)
    note = data["ai_policies"]["ieee"]["note"]
    assert note
    assert f"Policy note: {note}" in res["notes"]
