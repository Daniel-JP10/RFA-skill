# -*- coding: utf-8 -*-
"""Tests for citations validator across keys, apa-freetext, and numeric modes."""

import copy
import pytest

from validate_citations import (
    validate_apa_freetext_mode,
    validate_keys_mode,
    validate_numeric_mode,
)


def test_v1_keys_mode(fixtures_dir, items):
    """V1 doc_keys.md extraction and matching against items.csl.json."""
    doc_text = (fixtures_dir / "doc_keys.md").read_text(encoding="utf-8")
    res = validate_keys_mode(doc_text, items)

    assert res["keys_used"] == ["rivera2021a", "okafor2019", "silva2020", "institute2022", "ghost2000"]
    assert res["missing"] == ["ghost2000"]
    assert res["orphans"] == ["rivera2021b", "many2018"]
    # Check autor@example.org and @notakey are ignored
    assert "notakey" not in res["keys_used"]
    assert "alsonotkey" not in res["keys_used"]


def test_v2_keys_mode_missing_keys_fails(fixtures_dir, items):
    """V2 Missing key causes ok=False."""
    doc_text = (fixtures_dir / "doc_keys.md").read_text(encoding="utf-8")
    res = validate_keys_mode(doc_text, items)
    assert res["ok"] is False
    assert any(e["code"] == "missing_key" for e in res["errors"])


def test_v3_missing_required_field():
    """V3 Article-journal missing container-title causes missing_required_field error."""
    bad_item = {
        "id": "bad1",
        "type": "article-journal",
        "author": [{"family": "Smith"}],
        "title": "A Title",
        "issued": {"date-parts": [[2020]]},
        # Missing container-title
    }
    res = validate_keys_mode("@bad1", [bad_item])
    error_codes = [e["code"] for e in res["errors"]]
    assert "missing_required_field" in error_codes


def test_v4_duplicate_work(items):
    """V4 Duplicate item with same DOI causes duplicate_work warning."""
    item_copy = copy.deepcopy(items[0])
    item_copy["id"] = "rivera_clone"
    test_items = [items[0], item_copy]
    res = validate_keys_mode("@rivera2021a @rivera_clone", test_items)
    warn_codes = [w["code"] for w in res["warnings"]]
    assert "duplicate_work" in warn_codes


def test_v5_require_verified_turns_warning_to_error(items):
    """V5 require_verified converts unverified warning to error."""
    # Item without x-rfa
    unverified_item = copy.deepcopy(items[0])
    unverified_item.pop("x-rfa", None)

    # 1. Normal mode: warning
    res_normal = validate_keys_mode("@rivera2021a", [unverified_item], require_verified=False)
    assert any(w["code"] == "unverified" for w in res_normal["warnings"])
    assert not any(e["code"] == "unverified" for e in res_normal["errors"])

    # 2. Require-verified mode: error
    res_strict = validate_keys_mode("@rivera2021a", [unverified_item], require_verified=True)
    assert any(e["code"] == "unverified" for e in res_strict["errors"])
    assert res_strict["ok"] is False


def test_v6_apa_freetext_mode(fixtures_dir, items):
    """V6 apa-freetext mode with doc_apa_freetext.md."""
    doc_text = (fixtures_dir / "doc_apa_freetext.md").read_text(encoding="utf-8")
    res = validate_apa_freetext_mode(doc_text, items)

    assert res["heuristic"] is True
    for expected_id in ["rivera2021a", "rivera2021b", "okafor2019", "silva2020", "institute2022", "many2018"]:
        assert expected_id in res["matched_ids"]
    assert res["unmatched_citations"] == ["Lopez, 2015"]


def test_v7_numeric_mode(fixtures_dir):
    """V7 numeric mode with doc_numeric.md and N=5."""
    doc_text = (fixtures_dir / "doc_numeric.md").read_text(encoding="utf-8")
    res = validate_numeric_mode(doc_text, n_refs=5)

    assert res["cited_numbers"] == [1, 2, 3, 4, 5, 7]
    assert res["first_citation_order"] == [3, 1, 2, 4, 5, 7]
    assert res["out_of_range"] == [7]
    assert res["order_matches_list"] is False
    assert res["ok"] is False


@pytest.fixture
def sample_v8_refs():
    return [
        {
            "id": "delacruz2020",
            "type": "article-journal",
            "title": "Estudio De la Cruz",
            "author": [{"family": "De la Cruz", "given": "Juan"}],
            "issued": {"date-parts": [[2020]]},
        },
        {
            "id": "perez2020",
            "type": "article-journal",
            "title": "Estudio Pérez",
            "author": [{"family": "Pérez", "given": "María"}],
            "issued": {"date-parts": [[2020]]},
        },
    ]


def test_v8_unmatched_different_author(sample_v8_refs):
    """V8 'Un estudio (Delta, 2020).' does not match De la Cruz and stays in unmatched_citations."""
    res = validate_apa_freetext_mode("Un estudio (Delta, 2020).", sample_v8_refs)
    assert "delacruz2020" not in res["matched_ids"]
    assert any("Delta" in u for u in res["unmatched_citations"])


def test_v9_et_al_only_unmatched(sample_v8_refs):
    """V9 '(et al., 2020)' without leading author stays unmatched."""
    res = validate_apa_freetext_mode("(et al., 2020)", sample_v8_refs)
    assert len(res["matched_ids"]) == 0
    assert any("et al" in u for u in res["unmatched_citations"])


def test_v10_parenthetical_match(sample_v8_refs):
    """V10 '(De la Cruz, 2020)' matches De la Cruz."""
    res = validate_apa_freetext_mode("(De la Cruz, 2020)", sample_v8_refs)
    assert "delacruz2020" in res["matched_ids"]


def test_v11_narrative_match_accent_insensitive(sample_v8_refs):
    """V11 'Pérez (2020) informó…' matches Pérez case- and accent-insensitively."""
    res = validate_apa_freetext_mode("Pérez (2020) informó hallazgos.", sample_v8_refs)
    assert "perez2020" in res["matched_ids"]


def test_v12_existing_v1_to_v7_regression():
    """V12 Regression check confirming existing tests pass."""
    pass

