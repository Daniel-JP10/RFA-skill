# -*- coding: utf-8 -*-
"""Tests for journal abbreviation engine."""

import pytest

from abbreviate_journal import abbreviate, load_abbr_file


def test_a1_container_title_short():
    """A1 With container-title-short present, it takes highest precedence."""
    item = {
        "container-title": "Journal of Examples",
        "container-title-short": "J. Ex.",
    }
    abbr_map = {"journalofexamples": {"MedAbbr": "J Examples", "IsoAbbr": "J. Examples"}}
    res = abbreviate(item, abbr_map=abbr_map, style="medline")
    assert res["abbreviated"] == "J. Ex."
    assert res["source"] == "container-title-short"
    assert res["abbreviation_unavailable"] is False


def test_a2_abbr_file_lookup(fixtures_dir):
    """A2 Abbr file lookup: medline vs iso, case and accent insensitive."""
    abbr_file = fixtures_dir / "journal_abbr_sample.txt"
    abbr_map = load_abbr_file(abbr_file)

    # 1. Journal of Examples -> J Examples (medline), J. Examples (iso)
    item1 = {"container-title": "Journal of Examples"}
    res1_med = abbreviate(item1, abbr_map=abbr_map, style="medline")
    assert res1_med["abbreviated"] == "J Examples"
    assert res1_med["source"] == "abbr_file"

    res1_iso = abbreviate(item1, abbr_map=abbr_map, style="iso")
    assert res1_iso["abbreviated"] == "J. Examples"
    assert res1_iso["source"] == "abbr_file"

    # 2. Annals of Sample Medicine -> Ann Sample Med (case-insensitive search)
    item2 = {"container-title": "annals of sample medicine"}
    res2 = abbreviate(item2, abbr_map=abbr_map, style="medline")
    assert res2["abbreviated"] == "Ann Sample Med"


def test_a3_no_source_available():
    """A3 Without any abbreviation source, return full title and abbreviation_unavailable=True."""
    item = {"container-title": "Journal of Rare Case Studies"}
    res = abbreviate(item, abbr_map=None)
    assert res["abbreviated"] == "Journal of Rare Case Studies"
    assert res["source"] == "none"
    assert res["abbreviation_unavailable"] is True


def test_a4_tolerant_parser(tmp_path):
    """A4 Parser tolerates empty values (e.g. ISSN Online:) and unknown lines."""
    sample = """--------------------------------------------------------
JrId: 10
JournalTitle: Tolerant Test Journal
MedAbbr: Tol Test J
ISSN (Print): 1111-2222
ISSN (Online):
UnknownHeader: Some random value
AnotherLineWithoutColon
--------------------------------------------------------
"""
    f = tmp_path / "test_abbr.txt"
    f.write_text(sample, encoding="utf-8")

    abbr_map = load_abbr_file(f)
    assert "tolerant test journal" in abbr_map
    entry = abbr_map["tolerant test journal"]
    assert entry["MedAbbr"] == "Tol Test J"
    assert entry["ISSN (Online)"] == ""


def test_a5_dash_separators_and_crlf(tmp_path):
    """A5 Parser accepts 20 and 60 dashes separators and CRLF line endings."""
    sample_content = (
        "JournalTitle: Sample Journal A\r\n"
        "MedAbbr: Sample J A\r\n"
        "--------------------\r\n"
        "JournalTitle: Sample Journal B\r\n"
        "MedAbbr: Sample J B\r\n"
        "------------------------------------------------------------\r\n"
    )
    f = tmp_path / "crlf_abbr.txt"
    f.write_bytes(sample_content.encode("utf-8"))

    abbr_map = load_abbr_file(f)
    assert len(abbr_map) == 2
    assert "sample journal a" in abbr_map
    assert "sample journal b" in abbr_map
    assert abbr_map["sample journal a"]["MedAbbr"] == "Sample J A"
    assert abbr_map["sample journal b"]["MedAbbr"] == "Sample J B"


def test_a6_single_record_without_separators(tmp_path):
    """A6 File without separator lines containing a single record is parsed without error."""
    sample = (
        "JrId: 1\n"
        "JournalTitle: Lone Journal\n"
        "MedAbbr: Lone J\n"
        "IsoAbbr: Lone J.\n"
    )
    f = tmp_path / "single_abbr.txt"
    f.write_text(sample, encoding="utf-8")

    abbr_map = load_abbr_file(f)
    assert len(abbr_map) == 1
    assert "lone journal" in abbr_map
    assert abbr_map["lone journal"]["MedAbbr"] == "Lone J"

