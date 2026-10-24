"""Scenario tests for recommend.py (Python API and CLI)."""

import ast
import json
import pathlib
import subprocess
import sys

import pytest

from recommend import list_items, recommend

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts"
RECOMMEND = SCRIPTS_DIR / "recommend.py"
NETWORK_MODULES = {"requests", "urllib", "http", "socket"}


def rule_ids(res):
    return [r["id"] for r in res["rules_applied"]]


def questions(res, field=None):
    return [q for q in res["open_questions"] if field is None or q["field"] == field]


def run_cli(*args):
    return subprocess.run([sys.executable, str(RECOMMEND), *args], capture_output=True)


def test_r1_psychology_quantitative_en(data):
    """R1 psychology + quantitative + en: single apa-7 (high); R-09, R-14, R-15; nothing required."""
    res = recommend({"discipline": "social-sciences/psychology", "document_type": "quantitative",
                     "language": "en"}, data)
    rs = res["reference_style"]
    assert res["status"] == "ok"
    assert rs["selection"] == "single_recommendation"
    assert rs["chosen"]["standard_id"] == "apa-7"
    assert rs["chosen"]["confidence"] == "high"
    assert rs["chosen"]["csl_style_key"] == "apa-7"
    assert {"R-09", "R-14", "R-15"} <= set(rule_ids(res))
    assert "apa-jars" in res["reporting"]["recommended"]
    assert {"data-availability-statement", "ethics-statements"} <= set(res["sections"]["recommended"])
    assert res["reporting"]["required"] == []
    assert res["sections"]["required"] == []


def test_r2_medicine_systematic_review(data):
    """R2 medicine + systematic-review: vancouver-nlm; PRISMA 2020 required with details."""
    res = recommend({"discipline": "medicine", "document_type": "systematic-review"}, data)
    assert res["reference_style"]["chosen"]["standard_id"] == "vancouver-nlm"
    assert res["reporting"]["required"] == ["prisma-2020"]
    assert res["reporting"]["study_design"] == "systematic-review"
    detail = next(d for d in res["reporting"]["details"] if d["id"] == "prisma-2020")
    assert detail["official_url"].startswith("https://")
    assert detail["license_claimed"]


def test_r3_medicine_trial_protocol(data):
    """R3 medicine + trial-protocol: SPIRIT 2025 required, study design rct."""
    res = recommend({"discipline": "medicine", "document_type": "trial-protocol"}, data)
    assert res["reporting"]["required"] == ["spirit-2025"]
    assert res["reporting"]["study_design"] == "rct"
    assert "consort-2025" not in res["reporting"]["recommended"]


def test_r4_nursing_low_confidence(data):
    """R4 nursing + quantitative: vancouver-nlm with low confidence, caveat and venue question."""
    res = recommend({"discipline": "nursing", "document_type": "quantitative"}, data)
    chosen = res["reference_style"]["chosen"]
    assert chosen["standard_id"] == "vancouver-nlm"
    assert chosen["confidence"] == "low"
    assert any("vancouver-nlm" in c and "low" in c for c in res["data_caveats"])
    assert any("venue or institution" in q["why"] for q in questions(res, "standard"))


def test_r5_user_choice_warnings(data):
    """R5 literature + academic-essay + ieee: user_choice; R-17 and not-in-allowed warnings."""
    res = recommend({"discipline": "literature", "document_type": "academic-essay",
                     "standard": "ieee"}, data)
    assert res["status"] == "ok"
    assert res["reference_style"]["selection"] == "user_choice"
    assert res["reference_style"]["chosen"]["standard_id"] == "ieee"
    assert any(w.get("rule") == "R-17" for w in res["warnings"])
    assert any(w["code"] == "standard_not_in_allowed" for w in res["warnings"])


def test_r6_ai_author_denied(data):
    """R6 ai_author true: denied by R-13; no recommendations produced."""
    res = recommend({"discipline": "psychology", "document_type": "quantitative",
                     "ai_author": True, "ai_use": "generative_content",
                     "policy": "springer-nature"}, data)
    assert res["status"] == "denied"
    assert [d["rule"] for d in res["denials"]] == ["R-13"]
    assert res["reference_style"]["chosen"] is None
    assert res["reference_style"]["candidates"] == []
    assert res["reporting"]["required"] == [] and res["reporting"]["recommended"] == []
    assert res["sections"] == {"required": [], "recommended": []}
    assert res["ai_disclosure"] is None


def test_r7_springer_generative(data):
    """R7 springer-nature + generative_content: required, registry placements, policy_url."""
    res = recommend({"policy": "springer-nature", "ai_use": "generative_content"}, data)
    ai = res["ai_disclosure"]
    assert ai["required"] is True
    assert ai["placements"] == data["ai_policies"]["springer-nature"]["locations"]
    assert ai["policy_url"].startswith("https://")
    assert ai["policy_date"] and ai["verified_on"]
    assert "ai-disclosure-statement" in res["sections"]["required"]


def test_r8_acm_language_editing_conditional(data):
    """R8 acm + language_editing: conditional with exemptions."""
    res = recommend({"policy": "acm", "ai_use": "language_editing"}, data)
    ai = res["ai_disclosure"]
    assert ai["required"] == "conditional"
    assert ai["exemptions"] == data["ai_policies"]["acm"]["exempt"]
    assert ai["exemptions"]
    assert ai["needs_review"] is True


def test_r9_no_policy_generative(data):
    """R9 no policy + generative_content: conditional, no placements, venue-policy question."""
    res = recommend({"ai_use": "generative_content"}, data)
    ai = res["ai_disclosure"]
    assert ai["required"] == "conditional"
    assert ai["placements"] == []
    q = questions(res, "policy")
    assert q and "policy" in q[0]["why"]
    assert set(q[0]["options"]) == set(data["ai_policies"])


def test_r10_education_thesis_es_co(data):
    """R10 education + thesis-masters + es-CO: R-16, R-21; apa-7; check_first; alternative."""
    res = recommend({"discipline": "education", "document_type": "thesis-masters",
                     "language": "es-CO"}, data)
    rs = res["reference_style"]
    assert {"R-16", "R-21"} <= set(rule_ids(res))
    assert rs["selection"] == "single_recommendation"
    assert rs["chosen"]["standard_id"] == "apa-7"
    assert "institutional-overrides" in rs["check_first"]
    assert "icontec-colombia" in rs["alternatives"]
    assert any("institution or journal impose its own norm" in q["why"]
               for q in questions(res, "standard"))


def test_r11_law_thesis_es_co_needs_confirmation(data):
    """R11 law + thesis-doctoral + es-CO: needs_confirmation, bluebook and hybrid; nothing chosen."""
    res = recommend({"discipline": "law", "document_type": "thesis-doctoral",
                     "language": "es-CO"}, data)
    rs = res["reference_style"]
    assert rs["selection"] == "needs_confirmation"
    assert rs["chosen"] is None
    ids = [c["standard_id"] for c in rs["candidates"]]
    assert "bluebook" in ids and "colombia-legal-hybrid" in ids
    conflict = [q for q in questions(res, "standard") if "conflict" in q["why"]]
    assert conflict and {"bluebook", "colombia-legal-hybrid"} <= set(conflict[0]["options"])
    ranks = {"high": 0, "medium": 1, "low": 2}
    order = [ranks[c["confidence"]] for c in rs["candidates"]]
    assert order == sorted(order)


def test_r12_inv01_consort_with_cohort(data):
    """R12 consort-2025 with study design cohort: denied by INV-01."""
    res = recommend({"study_design": "cohort", "reporting_guideline": "consort-2025"}, data)
    assert res["status"] == "denied"
    assert res["denials"][0]["rule"] == "INV-01"


def test_r13_misspelled_and_segment(data):
    """R13 'psycology' is invalid with a suggestion; 'psychology' resolves."""
    res = recommend({"discipline": "psycology"}, data)
    assert res["status"] == "invalid_input"
    assert "social-sciences/psychology" in res["errors"][0]["suggestions"]
    ok = recommend({"discipline": "psychology"}, data)
    assert ok["status"] == "ok"
    assert ok["reference_style"]["chosen"]["standard_id"] == "apa-7"


def test_r14_trial_protocol_guidelines(data):
    """R14 trial-protocol: spirit-2025 is valid; consort-2025 is denied."""
    ok = recommend({"document_type": "trial-protocol", "reporting_guideline": "spirit-2025"}, data)
    assert ok["status"] == "ok"
    assert ok["denials"] == []
    bad = recommend({"document_type": "trial-protocol", "reporting_guideline": "consort-2025"}, data)
    assert bad["status"] == "denied"
    assert bad["denials"][0]["rule"] == "INV-01"


def test_r15_cli_smoke():
    """R15 CLI: --list and a full query exit 0; an invalid id exits 1; output is JSON."""
    res = run_cli("--list", "disciplines")
    assert res.returncode == 0
    listing = json.loads(res.stdout.decode("utf-8"))
    assert len(listing["items"]) == 28
    res = run_cli("--discipline", "psychology", "--document-type", "quantitative",
                  "--language", "en", "--policy", "apa-journals", "--ai-use", "language_editing",
                  "--ai-author", "false")
    assert res.returncode == 0
    assert json.loads(res.stdout.decode("utf-8"))["status"] == "ok"
    res = run_cli("--discipline", "psycology")
    assert res.returncode == 1
    assert json.loads(res.stdout.decode("utf-8"))["status"] == "invalid_input"
    assert run_cli().returncode == 2
    assert run_cli("--ai-use", "magic").returncode == 2


def _imports_and_env(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports, env = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv"):
            env.append(node.attr)
        elif isinstance(node, ast.Name) and node.id in ("environ", "getenv"):
            env.append(node.id)
    return imports, env


def test_r16_deterministic_no_network_no_env(data):
    """R16 Same query twice gives identical JSON; no network modules; no environment reads."""
    q = {"discipline": "law", "document_type": "thesis-doctoral", "language": "es-CO",
         "ai_use": "generative_content", "policy": "elsevier"}
    a = json.dumps(recommend(dict(q), data), sort_keys=True)
    b = json.dumps(recommend(dict(q), data), sort_keys=True)
    assert a == b
    for name in ("recommend.py", "render_disclosure.py", "_data.py"):
        imports, env = _imports_and_env(SCRIPTS_DIR / name)
        assert not imports & NETWORK_MODULES, (name, imports & NETWORK_MODULES)
        assert env == [], name


def test_r17_pt_br_language_and_abnt_warning(data):
    """R17 pt-BR maps to the pt-br language id; abnt-brasil with en triggers R-20."""
    res = recommend({"language": "pt-BR", "standard": "abnt-brasil"}, data)
    assert res["status"] == "ok"
    assert "R-20" not in rule_ids(res)
    res = recommend({"language": "en", "standard": "abnt-brasil"}, data)
    assert any(w.get("rule") == "R-20" for w in res["warnings"])


def test_r18_area_only_discipline_suggests_leaves(data):
    """R18 An area id is not a discipline; its leaves are suggested."""
    res = recommend({"discipline": "health"}, data)
    assert res["status"] == "invalid_input"
    assert "health/medicine" in res["errors"][0]["suggestions"]


def test_r19_standard_variant_handling(data):
    """R19 chicago-18 without a variant asks for it; with author-date it maps to the CSL key."""
    res = recommend({"standard": "chicago-18"}, data)
    assert questions(res, "standard_variant")
    assert res["reference_style"]["chosen"]["csl_style_key"] is None
    res = recommend({"standard": "chicago-18", "standard_variant": "author-date"}, data)
    assert res["reference_style"]["chosen"]["csl_style_key"] == "chicago-18:author-date"
    assert not questions(res, "standard_variant")
    bad = recommend({"standard": "chicago-18", "standard_variant": "footnotes"}, data)
    assert bad["status"] == "invalid_input"
    assert "notes-bibliography" in bad["errors"][0]["suggestions"]


def test_r20_research_conduct_methods(data):
    """R20 research_conduct: required, methods placement, methods section."""
    res = recommend({"policy": "elsevier", "ai_use": "research_conduct"}, data)
    assert res["ai_disclosure"]["required"] is True
    assert res["ai_disclosure"]["placements"] == ["methods"]
    assert "methods-ai-description" in res["sections"]["required"]
    res = recommend({"policy": "mdpi", "ai_use": "research_conduct"}, data)
    assert res["ai_disclosure"]["placements"] == ["materials_and_methods"]


def test_r21_qualitative_any_of(data):
    """R21 qualitative document type: COREQ or SRQR as an any-of group."""
    res = recommend({"document_type": "qualitative"}, data)
    assert ["coreq", "srqr"] in res["reporting"]["any_of"]


def test_r22_no_csl_caveat(data):
    """R22 A chosen standard without a bundled CSL style produces a data caveat."""
    res = recommend({"discipline": "law", "document_type": "quantitative"}, data)
    assert res["reference_style"]["chosen"]["standard_id"] == "bluebook"
    assert any("No CSL style is bundled for bluebook" in c for c in res["data_caveats"])


def test_r23_language_not_requires_known_language(data):
    """R23 language_not never matches an unknown language; an open question is raised instead."""
    res = recommend({"standard": "icontec-colombia"}, data)
    assert "R-19" not in rule_ids(res)
    assert questions(res, "language")
    res = recommend({"standard": "icontec-colombia", "language": "es"}, data)
    assert "R-19" not in rule_ids(res)
    res = recommend({"standard": "icontec-colombia", "language": "en"}, data)
    assert "R-19" in rule_ids(res)


def test_r24_study_design_recommendations_and_conflict(data):
    """R24 A user study design recommends its guidelines; a conflict with the rules is surfaced."""
    res = recommend({"study_design": "routine-data-observational"}, data)
    assert res["reporting"]["recommended"] == ["strobe", "record"]
    res = recommend({"document_type": "systematic-review", "study_design": "cohort"}, data)
    assert any(w["code"] == "study_design_conflict" for w in res["warnings"])
    assert questions(res, "study_design")


def test_r25_reporting_guideline_on_essay_warns(data):
    """R25 R-23 warns when a reporting guideline is given for an essay."""
    res = recommend({"document_type": "academic-essay", "study_design": "qualitative-general",
                     "reporting_guideline": "srqr"}, data)
    assert any(w.get("rule") == "R-23" for w in res["warnings"])


def test_r26_json_in_with_cli_override(tmp_path):
    """R26 --json-in is read and CLI flags override it."""
    q = tmp_path / "q.json"
    q.write_text(json.dumps({"discipline": "nursing", "document_type": "quantitative"}),
                 encoding="utf-8")
    res = run_cli("--json-in", str(q), "--discipline", "medicine")
    assert res.returncode == 0
    out = json.loads(res.stdout.decode("utf-8"))
    assert out["reference_style"]["chosen"]["confidence"] == "high"
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    assert run_cli("--json-in", str(bad)).returncode == 2


@pytest.mark.parametrize("kind", ["disciplines", "document_types", "standards", "study_designs",
                                  "reporting_guidelines", "policies", "languages"])
def test_r27_list_every_kind(kind, data):
    """R27 --list works for every kind."""
    items = list_items(kind, data)["items"]
    assert items and all("id" in i for i in items)


def test_r28_unknown_field_and_invalid_values(data):
    """R28 Unknown fields and invalid values give invalid_input; the tool never guesses."""
    assert recommend({"discipline": "medicine", "norm": "apa"}, data)["status"] == "invalid_input"
    assert recommend({"standard_variant": "numeric"}, data)["status"] == "invalid_input"
    assert recommend({"ai_author": "maybe"}, data)["status"] == "invalid_input"
    assert recommend({"language": "xx"}, data)["status"] == "invalid_input"
    res = recommend({"discipline": "medicine"}, data)
    assert questions(res, "ai_use") and questions(res, "ai_author")
    res = recommend({"disciplin": "medicine"}, data)
    assert "discipline" in res["errors"][0]["suggestions"]


def test_r29_unplanned_language_variant(data):
    """R29 A variant outside the planned list is accepted with a warning; es-CO rules skip it."""
    res = recommend({"discipline": "education", "document_type": "thesis-masters",
                     "language": "es-PE"}, data)
    assert res["status"] == "ok"
    assert any(w["code"] == "unplanned_language_variant" for w in res["warnings"])
    assert "R-21" not in rule_ids(res)


def test_r30_variant_question_and_csl_caveat_are_independent(data):
    """R30 acm without a variant: a variant question and a no-CSL caveat, both."""
    res = recommend({"standard": "acm"}, data)
    assert questions(res, "standard_variant")
    assert any("No CSL style is bundled for acm" in c for c in res["data_caveats"])
    res = recommend({"standard": "cse", "standard_variant": "name-year"}, data)
    assert res["reference_style"]["chosen"]["csl_style_key"] == "cse:name-year"
    assert not any("No CSL style" in c for c in res["data_caveats"])


def test_r31_standard_source_is_surfaced(data):
    """R31 standard_source appears in the chosen candidate and in the allowed-list warning."""
    res = recommend({"discipline": "literature", "standard": "apa-7",
                     "standard_source": "institution"}, data)
    assert "institution" in res["reference_style"]["chosen"]["notes"]
    warning = next(w for w in res["warnings"] if w["code"] == "standard_not_in_allowed")
    assert "precedence" in warning["message"]
    assert recommend({"standard_source": "journal"}, data)["status"] == "invalid_input"


def test_r32_near_miss_question_explains_the_rule(data):
    """R32 A question raised by a near-miss rule names the rule and its reason."""
    res = recommend({"document_type": "academic-essay"}, data)
    q = questions(res, "reporting_guideline")
    assert q and "R-23" in q[0]["why"]
    assert q[0]["rules"] == ["R-23"]


def test_r33_unknown_resolve_from_is_a_caveat(data):
    """R33 A rule pointing at a source the tool does not read produces a data caveat."""
    import copy

    altered = copy.deepcopy(data)
    rule = next(r for r in altered["rules"] if r["id"] == "R-11")
    rule["then"]["resolve_from"] = "rfa-core/elsewhere.yaml"
    res = recommend({"ai_use": "generative_content", "policy": "wiley"}, altered)
    assert any("R-11" in c and "rfa-core/elsewhere.yaml" in c for c in res["data_caveats"])
    res = recommend({"ai_use": "generative_content", "policy": "wiley"}, data)
    assert not any("does not read" in c for c in res["data_caveats"])


def test_pp1_research_proposal_prisma_p_valid(data):
    """PP1 research-proposal + systematic-review + prisma-p: no denial."""
    res = recommend({"document_type": "research-proposal", "study_design": "systematic-review",
                     "reporting_guideline": "prisma-p"}, data)
    assert res["status"] == "ok" and res["denials"] == []


def test_pp2_registered_report_prisma_2020_denied(data):
    """PP2 registered-report + systematic-review + prisma-2020: denied by INV-01."""
    res = recommend({"document_type": "registered-report", "study_design": "systematic-review",
                     "reporting_guideline": "prisma-2020"}, data)
    assert res["status"] == "denied" and res["denials"][0]["rule"] == "INV-01"


def test_pp3_finished_review_prisma_p_denied(data):
    """PP3 a finished systematic review cannot use the protocol guideline prisma-p."""
    res = recommend({"document_type": "systematic-review", "reporting_guideline": "prisma-p"}, data)
    assert res["status"] == "denied" and res["denials"][0]["rule"] == "INV-01"


def test_pp4_protocol_type_with_empty_protocol_reporting(data):
    """PP4 research-proposal + cohort + strobe: reporting applies because protocol_reporting is empty."""
    res = recommend({"document_type": "research-proposal", "study_design": "cohort",
                     "reporting_guideline": "strobe"}, data)
    assert res["status"] == "ok"


def test_pp5_trial_protocol(data):
    """PP5 trial-protocol + rct: spirit-2025 valid, consort-2025 denied."""
    ok = recommend({"document_type": "trial-protocol", "study_design": "rct",
                    "reporting_guideline": "spirit-2025"}, data)
    bad = recommend({"document_type": "trial-protocol", "study_design": "rct",
                     "reporting_guideline": "consort-2025"}, data)
    assert ok["status"] == "ok"
    assert bad["status"] == "denied" and bad["denials"][0]["rule"] == "INV-01"


def test_pp6_research_proposal_recommends_prisma_p(data):
    """PP6 research-proposal + systematic-review: prisma-p recommended, prisma-2020 not."""
    res = recommend({"document_type": "research-proposal", "study_design": "systematic-review"}, data)
    assert "prisma-p" in res["reporting"]["recommended"]
    assert "prisma-2020" not in res["reporting"]["recommended"]


def test_q1_conflict_question_is_blocking(data):
    """Q1 R11: first question blocking on standard; AI questions informational; ask_first set."""
    res = recommend({"discipline": "law", "document_type": "thesis-doctoral", "language": "es-CO"}, data)
    first = res["open_questions"][0]
    assert first["priority"] == "blocking" and first["field"] == "standard"
    for field in ("ai_use", "ai_author"):
        assert all(qq["priority"] == "informational" for qq in questions(res, field))
    assert res["ask_first"] == first["why"]


def test_q2_standard_from_journal_has_no_check_first(data):
    """Q2 a journal-imposed standard: no check_first question and nothing blocking."""
    res = recommend({"discipline": "psychology", "document_type": "quantitative", "language": "en",
                     "standard": "apa-7", "standard_source": "journal"}, data)
    assert not any("impose its own norm" in qq["why"] for qq in res["open_questions"])
    assert res["ask_first"] is None
    res = recommend({"discipline": "education", "document_type": "thesis-masters", "language": "es-CO",
                     "standard": "apa-7", "standard_source": "institution"}, data)
    assert not any("impose its own norm" in qq["why"] for qq in res["open_questions"])


def test_q3_r1_questions_are_short(data):
    """Q3 R1 has at most 3 open questions and every why is at most 160 characters."""
    res = recommend({"discipline": "psychology", "document_type": "quantitative", "language": "en"}, data)
    assert len(res["open_questions"]) <= 3
    assert all(len(qq["why"]) <= 160 for qq in res["open_questions"])
    assert len({qq["field"] for qq in res["open_questions"]}) == len(res["open_questions"])


def test_q4_blocking_questions_come_first(data):
    """Q4 no informational question appears before a blocking one, across many queries."""
    for disc in data["disciplines"]:
        for dt in ("thesis-doctoral", "quantitative", "systematic-review", "research-proposal"):
            for lang in ("en", "es-CO"):
                res = recommend({"discipline": disc, "document_type": dt, "language": lang,
                                 "ai_use": "generative_content"}, data)
                prios = [qq["priority"] for qq in res["open_questions"]]
                assert prios == sorted(prios, key=lambda p: p != "blocking")
                assert (res["ask_first"] is not None) == ("blocking" in prios)
    bad = recommend({"discipline": "psycology"}, data)
    assert bad["open_questions"][0]["priority"] == "blocking" and bad["ask_first"]


def test_r34_research_conduct_methods_fallback_caveat(data):
    """R34 A policy with no methods location gets the methods placement and a caveat."""
    res = recommend({"ai_use": "research_conduct", "policy": "elsevier"}, data)
    assert any("lists no methods location" in c for c in res["data_caveats"])
    res = recommend({"ai_use": "research_conduct", "policy": "wiley"}, data)
    assert not any("lists no methods location" in c for c in res["data_caveats"])


def test_n1_suppress_r19_r20_near_miss(data):
    """N1 psychology + quantitative + en: no open question mentions R-19 or R-20."""
    res = recommend({"discipline": "psychology", "document_type": "quantitative", "language": "en"}, data)
    assert not any("R-19" in q.get("why", "") or "R-19" in q.get("rules", []) for q in res["open_questions"])
    assert not any("R-20" in q.get("why", "") or "R-20" in q.get("rules", []) for q in res["open_questions"])


def test_n2_suppress_r17_near_miss(data):
    """N2 literature + academic-essay (no standard): no question mentions R-17."""
    res = recommend({"discipline": "literature", "document_type": "academic-essay"}, data)
    assert not any("R-17" in q.get("why", "") or "R-17" in q.get("rules", []) for q in res["open_questions"])


def test_n3_law_thesis_doctoral_needs_confirmation(data):
    """N3 law + thesis-doctoral + es-CO: selection is still needs_confirmation and ask_first is not null."""
    res = recommend({"discipline": "law", "document_type": "thesis-doctoral", "language": "es-CO"}, data)
    assert res["reference_style"]["selection"] == "needs_confirmation"
    assert res["ask_first"] is not None


def test_n4_psychology_icontec_warning_produced(data):
    """N4 psychology + quantitative + en with --standard icontec-colombia: warning for R-19 produced."""
    res = recommend({"discipline": "psychology", "document_type": "quantitative", "language": "en",
                     "standard": "icontec-colombia"}, data)
    assert any(w.get("rule") == "R-19" for w in res["warnings"])


def test_t1_data_snapshot_has_snapshot_dates(data):
    """T1 data_snapshot carries meta.snapshot_dates."""
    res = recommend({"discipline": "psychology", "document_type": "quantitative", "language": "en"}, data)
    assert res["data_snapshot"]["snapshot_dates"] == data["meta"]["snapshot_dates"]


def _medicine(design):
    return {"discipline": "medicine", "document_type": "quantitative", "language": "en", "study_design": design}


def test_e1_rct_recommends_consort_2025(data):
    """E1 (SC-03) rct: consort-2025 recommended, not required."""
    res = recommend(_medicine("rct"), data)
    assert "consort-2025" in res["reporting"]["recommended"]
    assert "consort-2025" not in res["reporting"]["required"]


def test_e2_cohort_recommends_strobe(data):
    """E2 (SC-04) cohort: strobe recommended."""
    res = recommend(_medicine("cohort"), data)
    assert "strobe" in res["reporting"]["recommended"]


def test_e3_no_reporting_guideline_design(data):
    """E3 (SC-05) no-reporting-guideline: nothing required or recommended."""
    res = recommend(_medicine("no-reporting-guideline"), data)
    assert res["reporting"]["required"] == []
    assert res["reporting"]["recommended"] == []


def test_e4_case_report_requires_care(data):
    """E4 (SC-06) medicine case report: care required."""
    res = recommend({"discipline": "medicine", "document_type": "case-report", "language": "en"}, data)
    assert "care" in res["reporting"]["required"]


def test_e5_sociology_recommends_apa_jars(data):
    """E5 (SC-07) sociology quantitative: apa-jars recommended."""
    res = recommend({"discipline": "sociology", "document_type": "quantitative", "language": "en"}, data)
    assert "apa-jars" in res["reporting"]["recommended"]


def test_e6_elsevier_language_editing(data):
    """E6 (SC-08) Elsevier language editing: required, placements and exemptions from the policy entry."""
    res = recommend({"discipline": "psychology", "document_type": "quantitative", "language": "en",
                     "ai_use": "language_editing", "policy": "elsevier"}, data)
    entry = data["ai_policies"]["elsevier"]
    assert res["ai_disclosure"]["required"] is True
    assert res["ai_disclosure"]["placements"] == entry["locations"]
    assert res["ai_disclosure"]["exemptions"] == entry["exempt"]

def test_r35_policy_note_surfaces_in_caveats(data):
    """R35 a policy note without needs_review reaches data_caveats."""
    res = recommend({"policy": "ieee", "ai_use": "language_editing"}, data)
    note = data["ai_policies"]["ieee"]["note"]
    assert note
    assert f"AI policy 'ieee' note: {note}" in res["data_caveats"]
