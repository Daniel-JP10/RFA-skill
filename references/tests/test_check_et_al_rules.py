# -*- coding: utf-8 -*-
"""Tests for 'et al.' truncation rules extractor."""

import pytest

from check_et_al_rules import describe, thresholds_from_csl


def test_e1_apa_thresholds(csl_dir):
    """E1 APA 7: bibliography and citation thresholds."""
    apa_csl = csl_dir / "apa-7.csl"
    if not apa_csl.exists():
        pytest.skip("apa-7.csl is not available")

    t = thresholds_from_csl(apa_csl)
    assert t["bibliography"]["min"] == 21
    assert t["bibliography"]["use_first"] == 19
    assert t["bibliography"]["use_last"] is True

    assert t["citation"]["min"] == 3
    assert t["citation"]["use_first"] == 1


def test_e2_vancouver_thresholds(csl_dir):
    """E2 Vancouver: bibliography min 7, use_first 6."""
    vanc_csl = csl_dir / "vancouver.csl"
    if not vanc_csl.exists():
        pytest.skip("vancouver.csl is not available")

    t = thresholds_from_csl(vanc_csl)
    assert t["bibliography"]["min"] == 7
    assert t["bibliography"]["use_first"] == 6


def test_e3_ieee_thresholds(csl_dir):
    """E3 IEEE: bibliography context resolved from name elements (min 7, use_first 1)."""
    ieee_csl = csl_dir / "ieee-2024.csl"
    if not ieee_csl.exists():
        pytest.skip("ieee-2024.csl is not available")

    t = thresholds_from_csl(ieee_csl)
    assert t["bibliography"]["min"] == 7
    assert t["bibliography"]["use_first"] == 1


def test_e4_apa_describe(csl_dir):
    """E4 APA describe: 25 authors in biblio, 2 authors in citation, 3 authors in citation."""
    apa_csl = csl_dir / "apa-7.csl"
    if not apa_csl.exists():
        pytest.skip("apa-7.csl is not available")

    t = thresholds_from_csl(apa_csl)

    d25 = describe(25, "bibliography", t)
    assert d25["displayed_authors"] == 20
    assert d25["last_author_shown"] is True
    assert d25["et_al"] is True

    d2 = describe(2, "citation", t)
    assert d2["displayed_authors"] == 2
    assert d2["et_al"] is False

    d3 = describe(3, "citation", t)
    assert d3["displayed_authors"] == 1
    assert d3["et_al"] is True


def test_e5_nlm_describe(csl_dir):
    """E5 NLM describe: 8 authors in bibliography."""
    vanc_csl = csl_dir / "vancouver.csl"
    if not vanc_csl.exists():
        pytest.skip("vancouver.csl is not available")

    t = thresholds_from_csl(vanc_csl)
    d8 = describe(8, "bibliography", t)
    assert d8["displayed_authors"] == 6
    assert d8["et_al"] is True
