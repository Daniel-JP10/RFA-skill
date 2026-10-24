# -*- coding: utf-8 -*-
"""Analyze and describe 'et al.' truncation rules from CSL files."""

import argparse
import json
import pathlib
import sys
import xml.etree.ElementTree as ET


def _parse_et_al_attribs(elem) -> dict:
    et_min = elem.attrib.get("et-al-min")
    et_first = elem.attrib.get("et-al-use-first")
    et_last = elem.attrib.get("et-al-use-last")

    return {
        "min": int(et_min) if et_min is not None else None,
        "use_first": int(et_first) if et_first is not None else None,
        "use_last": (et_last.lower() == "true") if et_last is not None else None,
    }


def thresholds_from_csl(path) -> dict:
    """Extract et-al truncation thresholds for citation and bibliography contexts."""
    csl_path = pathlib.Path(path)
    if not csl_path.exists():
        raise FileNotFoundError(f"CSL file not found: {csl_path}")

    tree = ET.parse(csl_path)
    root = tree.getroot()

    all_et_al_elements = []
    citation_own = None
    bib_own = None
    name_elements = []

    for elem in root.iter():
        tag = elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag
        attribs = _parse_et_al_attribs(elem)
        if attribs["min"] is not None:
            all_et_al_elements.append({
                "element": tag,
                "scope": tag,
                "min": attribs["min"],
                "use_first": attribs["use_first"],
                "use_last": attribs["use_last"],
            })
            if tag == "citation":
                citation_own = attribs
            elif tag == "bibliography":
                bib_own = attribs
            elif tag in ("name", "names"):
                name_elements.append(attribs)

    # Context resolution
    citation_resolved = None
    if citation_own is not None:
        citation_resolved = citation_own
    elif name_elements and all(n == name_elements[0] for n in name_elements):
        citation_resolved = name_elements[0]

    bib_resolved = None
    if bib_own is not None:
        bib_resolved = bib_own
    elif name_elements and all(n == name_elements[0] for n in name_elements):
        bib_resolved = name_elements[0]

    result = {
        "citation": citation_resolved or {"min": None, "use_first": None, "use_last": None},
        "bibliography": bib_resolved or {"min": None, "use_first": None, "use_last": None},
        "elements": all_et_al_elements,
        "resolved": {
            "citation": (citation_resolved is not None),
            "bibliography": (bib_resolved is not None),
        },
    }

    return result


def describe(n_authors: int, context: str, thresholds: dict) -> dict:
    """Describe formatting behavior for a given number of authors in a context."""
    ctx_thresholds = thresholds.get(context) or thresholds
    t_min = ctx_thresholds.get("min")
    t_first = ctx_thresholds.get("use_first")
    t_last = ctx_thresholds.get("use_last")

    if t_min is None:
        return {
            "n_authors": n_authors,
            "displayed_authors": n_authors,
            "et_al": False,
            "last_author_shown": False,
            "rule": "No et-al rule defined; all authors are shown.",
            "resolved": False,
        }

    if n_authors < t_min:
        return {
            "n_authors": n_authors,
            "displayed_authors": n_authors,
            "et_al": False,
            "last_author_shown": False,
            "rule": f"For {n_authors} < {t_min}, all authors are shown.",
            "resolved": True,
        }

    use_first = t_first if t_first is not None else 1
    use_last = bool(t_last)
    displayed = use_first + (1 if use_last else 0)

    rule_str = f"For {n_authors} >= {t_min}, {use_first} authors are shown"
    if use_last:
        rule_str += ", followed by an ellipsis and the last author."
    else:
        rule_str += ", followed by et al."

    return {
        "n_authors": n_authors,
        "displayed_authors": displayed,
        "et_al": True,
        "last_author_shown": use_last,
        "rule": rule_str,
        "resolved": True,
    }


def main(argv=None):
    """CLI entry point for check_et_al_rules."""
    parser = argparse.ArgumentParser(description="Check 'et al.' rules from CSL file.")
    parser.add_argument("--csl", required=True, help="Path to CSL style file")
    parser.add_argument("--authors", type=int, help="Number of authors to evaluate")
    parser.add_argument("--context", choices=["citation", "bibliography"], default="bibliography")
    parser.add_argument("--out", help="Output file (default stdout)")

    args = parser.parse_args(argv)

    try:
        thresholds = thresholds_from_csl(args.csl)
    except Exception as e:
        sys.stderr.write(f"Error parsing CSL: {e}\n")
        return 2

    if args.authors is not None:
        res = describe(args.authors, args.context, thresholds)
    else:
        res = thresholds

    out_json = json.dumps(res, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json)
    else:
        sys.stdout.write(out_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
