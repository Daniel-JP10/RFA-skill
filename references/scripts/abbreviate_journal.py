# -*- coding: utf-8 -*-
"""Abbreviate journal titles using item metadata or NLM catalog abbreviations."""

import argparse
import json
import os
import pathlib
import re
import sys

from _common import normalize_text


def load_abbr_file(path) -> dict:
    """Parse an NLM-format journal abbreviation file."""
    abbr_path = pathlib.Path(path)
    if not abbr_path.exists():
        raise FileNotFoundError(f"Abbreviation file not found: {abbr_path}")

    content = abbr_path.read_text(encoding="utf-8", errors="replace")
    raw_blocks = re.split(r"(?m)^\s*-{10,}\s*$", content)
    blocks = [b.strip() for b in raw_blocks if b.strip()]

    abbr_map = {}
    for block in blocks:
        entry = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            entry[key] = val

        title = entry.get("JournalTitle")
        if title:
            norm_key = normalize_text(title)
            abbr_map[norm_key] = entry

    return abbr_map


def abbreviate(item: dict, abbr_map: dict | None = None, style: str = "medline") -> dict:
    """Return abbreviated journal title following strict preference order."""
    container_title = item.get("container-title") or ""
    container_short = item.get("container-title-short")

    # 1. Prefer container-title-short in item
    if container_short:
        return {
            "title": container_title or container_short,
            "abbreviated": container_short,
            "source": "container-title-short",
            "abbreviation_unavailable": False,
        }

    # 2. Local abbreviation file
    if abbr_map and container_title:
        norm_key = normalize_text(container_title)
        entry = abbr_map.get(norm_key)
        if entry:
            if style == "iso":
                abbr_val = entry.get("IsoAbbr") or entry.get("MedAbbr")
            else:
                abbr_val = entry.get("MedAbbr") or entry.get("IsoAbbr")

            if abbr_val:
                return {
                    "title": container_title,
                    "abbreviated": abbr_val,
                    "source": "abbr_file",
                    "abbreviation_unavailable": False,
                }

    # 3. None available: return full title
    return {
        "title": container_title,
        "abbreviated": container_title,
        "source": "none",
        "abbreviation_unavailable": True,
    }


def main(argv=None):
    """CLI entry point for abbreviate_journal."""
    parser = argparse.ArgumentParser(description="Abbreviate journal titles.")
    parser.add_argument("--items", required=True, help="Path to CSL-JSON items file")
    parser.add_argument("--abbr-file", help="Path to NLM-style abbreviation file")
    parser.add_argument("--style", choices=["medline", "iso"], default="medline")
    parser.add_argument("--out", help="Output file (default stdout)")

    args = parser.parse_args(argv)

    try:
        with open(args.items, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception as e:
        sys.stderr.write(f"Error reading items: {e}\n")
        return 2

    abbr_file_path = args.abbr_file or os.environ.get("RFA_JOURNAL_ABBR_FILE")
    abbr_map = None
    if abbr_file_path:
        try:
            abbr_map = load_abbr_file(abbr_file_path)
        except Exception as e:
            sys.stderr.write(f"Warning: could not load abbr file: {e}\n")

    results = []
    for it in items:
        res = abbreviate(it, abbr_map=abbr_map, style=args.style)
        results.append({
            "id": it.get("id"),
            **res,
        })

    out_json = json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json)
    else:
        sys.stdout.write(out_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
