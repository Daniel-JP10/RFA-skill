# -*- coding: utf-8 -*-
"""Tests for references sorting and ordering."""

import pytest

from order_references import (
    family_from_csl,
    order_alphabetical,
    order_by_first_citation,
    order_for_style,
    sort_key,
)


def test_o1_alphabetical_order(items):
    """O1 Alphabetical ordering of the 6 test items."""
    ordered = order_alphabetical(items)
    ids = [it["id"] for it in ordered]
    expected = ["many2018", "institute2022", "okafor2019", "rivera2021b", "rivera2021a", "silva2020"]
    assert ids == expected


def test_o2_sort_key_accents_and_spaces():
    """O2 sort_key ignores accents and whitespace in family names."""
    item_alvarez = {"id": "alv", "author": [{"family": "Álvarez"}], "title": "A"}
    item_blanco = {"id": "bla", "author": [{"family": "Blanco"}], "title": "B"}
    assert sort_key(item_alvarez) < sort_key(item_blanco)

    item_mac_space = {"id": "m1", "author": [{"family": "Mac Donald"}], "title": "T"}
    item_mac_nospace = {"id": "m2", "author": [{"family": "MacDonald"}], "title": "T"}
    # Main name part of sort_key should be identical
    assert sort_key(item_mac_space)[0] == sort_key(item_mac_nospace)[0]


def test_o3_order_by_first_citation(items):
    """O3 order_by_first_citation preserves citation order and puts uncited at end."""
    cited = ["silva2020", "okafor2019"]
    ordered = order_by_first_citation(items, cited)
    ids = [it["id"] for it in ordered]
    assert ids[:2] == ["silva2020", "okafor2019"]
    assert set(ids[2:]) == {"rivera2021a", "rivera2021b", "institute2022", "many2018"}


def test_o4_title_without_initial_article():
    """O4 Item without author sorts by title stripped of leading article."""
    item1 = {"id": "t1", "title": "The Quantum Computing Review", "issued": {"date-parts": [[2020]]}}
    item2 = {"id": "t2", "title": "Quantum Physics Basics", "issued": {"date-parts": [[2020]]}}
    assert sort_key(item1)[0] == "quantumcomputingreview"
    assert sort_key(item2)[0] == "quantumphysicsbasics"
    assert sort_key(item1) < sort_key(item2)


def test_o5_family_from_csl(csl_dir):
    """O5 family_from_csl extracts category citation-format correctly."""
    assert family_from_csl(csl_dir / "apa-7.csl") == "author-date"
    assert family_from_csl(csl_dir / "vancouver.csl") == "numeric"
    assert family_from_csl(csl_dir / "ieee-2024.csl") == "numeric"
