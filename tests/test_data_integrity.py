"""Integrity tests for the generated skill data layer (rfa-skill/data/rfa_data.json)."""

import hashlib
import importlib.util
import pathlib
import re
import subprocess
import sys

import pytest

SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_ROOT.parent
DATA_FILE = SKILL_ROOT / "data" / "rfa_data.json"
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_skill_data.py"

if not BUILD_SCRIPT.exists(): pytest.skip("repository-only test: tools/ is absent", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("_rfa_build_skill_data", BUILD_SCRIPT)
_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build)
hash_file = _build.hash_file

# Accented vowels, u with diaeresis, n with tilde and inverted marks, built from code points.
SPANISH_LETTERS = re.compile("[" + "".join(chr(c) for c in (
    0xE1, 0xE9, 0xED, 0xF3, 0xFA, 0xC1, 0xC9, 0xCD, 0xD3, 0xDA,
    0xE0, 0xE8, 0xEC, 0xF2, 0xF9, 0xC0, 0xC8, 0xCC, 0xD2, 0xD9,
    0xFC, 0xDC, 0xF1, 0xD1, 0xBF, 0xA1)) + "]")


def _run_build(*args):
    return subprocess.run([sys.executable, str(BUILD_SCRIPT), *args], cwd=str(REPO_ROOT),
                          capture_output=True, text=True)


def _strings(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)
    elif isinstance(node, str):
        yield node


def test_i1_build_check_passes():
    """I1 rfa_data.json equals a fresh build."""
    res = _run_build("--check")
    assert res.returncode == 0, res.stderr


def test_i2_source_hashes_match_current_files(data):
    """I2 meta.source_hashes match the current input files."""
    hashes = data["meta"]["source_hashes"]
    assert len(hashes) >= 29
    for rel, digest in hashes.items():
        path = REPO_ROOT / rel
        assert path.is_file(), rel
        assert hash_file(path) == digest, rel


def test_i8_hash_file_line_endings(tmp_path):
    """I8 hash_file ignores CRLF in text files but keeps .csl bytes exact."""
    lf = (REPO_ROOT / "rfa-core" / "precedence.yaml").read_bytes().replace(b"\r\n", b"\n")
    crlf_yaml = tmp_path / "copy.yaml"
    crlf_yaml.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert hash_file(crlf_yaml) == hashlib.sha256(lf).hexdigest()
    csl = (SKILL_ROOT / "references" / "csl" / "apa-7.csl").read_bytes()
    crlf_csl = tmp_path / "copy.csl"
    crlf_csl.write_bytes(csl.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert hash_file(crlf_csl) != hashlib.sha256(csl.replace(b"\r\n", b"\n")).hexdigest()


def test_i3_referenced_ids_exist(data):
    """I3 Every id referenced by defaults, rules, study designs, standards and policies exists."""
    standards = set(data["standards"])
    disciplines = set(data["disciplines"])
    areas = {d["area"] for d in data["disciplines"].values()}
    doc_types = set(data["document_types"])
    groups = {d["group"] for d in data["document_types"].values()}
    guidelines = set(data["reporting_guidelines"])
    designs = set(data["study_designs"])
    languages = set(data["languages"]["languages"])
    variants = {v for vs in data["languages"]["variants_planned"].values() for v in vs}
    std_variants = {v for s in data["standards"].values() for v in s["variants"]}

    assert set(data["defaults"]) == disciplines
    for leaf, d in data["defaults"].items():
        if d["default"] is not None:
            assert d["default"] in standards, leaf
            assert d["default"] in d["allowed"], leaf
        for s in d["allowed"]:
            assert s in standards, (leaf, s)
        for gap in d.get("gap", []):
            assert gap not in standards, (leaf, gap)
        if d.get("variant"):
            assert d["variant"] in data["standards"][d["default"]]["variants"], leaf

    def values(v):
        return v if isinstance(v, list) else [v]

    when_universe = {
        "document_type": doc_types, "document_type_group": groups, "discipline": disciplines,
        "discipline_area": areas, "standard": standards, "standard_variant": std_variants,
        "language": languages, "language_not": languages, "language_variant": variants,
        "reporting_guideline": guidelines | {"any"}, "ai_use_kind": set(data["meta"]["enums"]["ai_use_kind"]),
        "ai_listed_as_author": {True, False},
    }
    then_universe = {
        "reporting_guideline": guidelines, "reporting_guideline_any_of": guidelines,
        "study_design": designs, "default_standard": standards, "standard": standards,
        "alternative": standards, "check_first": standards,
    }
    for rule in data["rules"]:
        assert rule["effect"] in data["meta"]["enums"]["effects"], rule["id"]
        for key, v in rule["when"].items():
            assert key in when_universe, (rule["id"], key)
            for item in values(v):
                assert item in when_universe[key], (rule["id"], key, item)
        for key, v in (rule.get("then") or {}).items():
            if key in then_universe:
                for item in values(v):
                    assert item in then_universe[key], (rule["id"], key, item)

    for sd, sdata in data["study_designs"].items():
        for g in (sdata.get("reporting") or []) + (sdata.get("protocol_reporting") or []):
            assert g in guidelines, (sd, g)
    for gid, g in data["reporting_guidelines"].items():
        assert g["study_designs"], gid
        for sd in g["study_designs"]:
            assert sd in designs, (gid, sd)
    for sid, s in data["standards"].items():
        assert s["id"] == sid
    for key, p in data["ai_policies"].items():
        assert p["writing_assistance"] in data["meta"]["enums"]["writing_assistance"], key


def test_i4_csl_style_keys_exist(data):
    """I4 Every csl_style_key is a STYLE_MAP key and its CSL file exists."""
    from format_reference import STYLE_MAP

    seen = []
    for sid, s in data["standards"].items():
        for key in s["csl_style_keys"]:
            assert key in STYLE_MAP, (sid, key)
            assert (SKILL_ROOT / "references" / "csl" / STYLE_MAP[key]).is_file(), key
            seen.append(key)
    assert sorted(seen) == sorted(STYLE_MAP)


def test_i5_display_names_and_location_labels(data, templates, registry_location_codes):
    """I5 Every standard has a display_name; every registry location has en and es labels."""
    for sid, s in data["standards"].items():
        assert isinstance(s["display_name"], str) and s["display_name"].strip(), sid
    for collection in ("disciplines", "document_types", "defaults"):
        for item_id, item in data[collection].items():
            assert item["display_name"].strip(), (collection, item_id)
    assert registry_location_codes
    for code in registry_location_codes:
        labels = templates["locations"].get(code)
        assert labels, code
        assert labels.get("en", "").strip() and labels.get("es", "").strip(), code


def test_i6_no_spanish_letters_in_data(data):
    """I6 No string in rfa_data.json contains Spanish letters or inverted punctuation."""
    offending = [s for s in _strings(data) if SPANISH_LETTERS.search(s)]
    assert offending == []


def test_i7_build_is_deterministic(tmp_path):
    """I7 Two builds produce byte-identical output, equal to the committed file."""
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert _run_build("--out", str(a)).returncode == 0
    assert _run_build("--out", str(b)).returncode == 0
    assert a.read_bytes() == b.read_bytes()
    assert a.read_bytes() == DATA_FILE.read_bytes()
    raw = a.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n") and b"\r" not in raw


def test_i8_meta_versions_and_snapshot_dates(data):
    """I8 meta carries schema, versions and snapshot date ranges."""
    meta = data["meta"]
    assert meta["schema_version"] == 1
    assert meta["rfa_version"] and meta["core_version"]
    for key in ("policy_registry", "standards_meta"):
        rng = meta["snapshot_dates"][key]
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", rng["min"]) and rng["min"] <= rng["max"]
    assert set(data) == {
        "meta", "disciplines", "document_types", "standards", "defaults", "rules", "invariants",
        "precedence", "study_designs", "reporting_guidelines", "ai_policies", "languages",
        "protocol_document_types",
    }
