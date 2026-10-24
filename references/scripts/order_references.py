# -*- coding: utf-8 -*-
"""Order references alphabetically or by order of first citation."""

import argparse
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

from _common import normalize_text

INITIAL_ARTICLES = {
    "a", "an", "the",
    "el", "la", "los", "las",
    "un", "una", "unos", "unas",
    "le", "la", "les", "un", "une", "des",
    "der", "die", "das", "ein", "eine",
}


def _strip_initial_article(title: str) -> str:
    if not title:
        return ""
    words = title.strip().split()
    if words and words[0].lower() in INITIAL_ARTICLES:
        return " ".join(words[1:])
    return title


def family_from_csl(path) -> str | None:
    """Extract citation-format category from a CSL file."""
    csl_path = pathlib.Path(path)
    if not csl_path.exists():
        return None
    try:
        tree = ET.parse(csl_path)
        root = tree.getroot()
        for elem in root.iter():
            tag = elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag
            if tag == "category" and "citation-format" in elem.attrib:
                return elem.attrib["citation-format"]
    except Exception:
        return None
    return None


def sort_key(item: dict) -> tuple:
    """Generate a deterministic sort key tuple for alphabetical ordering."""
    # 1. Main name: first author's family or literal; if none, editor; if none, title without article
    main_name = ""
    authors = item.get("author") or []
    editors = item.get("editor") or []

    if authors:
        first = authors[0]
        main_name = first.get("family") or first.get("literal") or ""
    elif editors:
        first = editors[0]
        main_name = first.get("family") or first.get("literal") or ""

    if not main_name:
        main_name = _strip_initial_article(item.get("title") or "")

    norm_main = normalize_text(main_name).replace(" ", "")

    # 2. Author initials
    initials_parts = []
    for person in authors:
        given = person.get("given") or ""
        inits = "".join(part[0].upper() for part in given.split() if part)
        initials_parts.append(inits)
    initials_str = "".join(initials_parts)

    # 3. Year
    year = 0
    issued = item.get("issued") or {}
    date_parts = issued.get("date-parts") or []
    if date_parts and date_parts[0] and date_parts[0][0]:
        try:
            year = int(date_parts[0][0])
        except (ValueError, TypeError):
            year = 0

    # 4. Title without initial article
    stripped_title = _strip_initial_article(item.get("title") or "")
    norm_title = normalize_text(stripped_title).replace(" ", "")

    return (norm_main, initials_str, year, norm_title)


def order_alphabetical(items: list[dict]) -> list[dict]:
    """Sort references alphabetically by sort_key."""
    return sorted(items, key=sort_key)


def order_by_first_citation(items: list[dict], cited_keys: list[str]) -> list[dict]:
    """Sort references by order of appearance in cited_keys; uncited at end."""
    item_map = {item["id"]: item for item in items if "id" in item}
    ordered = []
    seen = set()

    for key in cited_keys:
        if key in item_map and key not in seen:
            ordered.append(item_map[key])
            seen.add(key)

    # Uncited items at the end in their original order
    for item in items:
        item_id = item.get("id")
        if item_id not in seen:
            ordered.append(item)
            seen.add(item_id)

    return ordered


def order_for_style(items: list[dict], family: str | None, cited_keys: list[str] | None = None) -> list[dict]:
    """Order references according to CSL style family convention."""
    if family == "numeric":
        return order_by_first_citation(items, cited_keys or [])
    return order_alphabetical(items)


def main(argv=None):
    """CLI entry point for order_references."""
    parser = argparse.ArgumentParser(description="Order references by alphabetical or citation order.")
    parser.add_argument("--items", required=True, help="Path to CSL-JSON items file")
    parser.add_argument("--style-csl", help="Path to CSL file to extract style family")
    parser.add_argument("--family", choices=["author-date", "numeric", "label", "note"], help="Style family")
    parser.add_argument("--cited-keys", nargs="*", default=[], help="Keys in order of first citation")
    parser.add_argument("--out", help="Output JSON file (default stdout)")

    args = parser.parse_args(argv)

    try:
        with open(args.items, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception as e:
        sys.stderr.write(f"Error loading items: {e}\n")
        return 2

    family = args.family
    if not family and args.style_csl:
        family = family_from_csl(args.style_csl)

    ordered = order_for_style(items, family, cited_keys=args.cited_keys)
    out_json = json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json)
    else:
        sys.stdout.write(out_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
