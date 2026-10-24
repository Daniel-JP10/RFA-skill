# -*- coding: utf-8 -*-
"""Validate citations in Markdown documents against CSL-JSON references."""

import argparse
import json
import re
import sys

from _common import first_author_family, normalize_doi, normalize_text

REQUIRED_FIELDS = {
    "article-journal": ["author", "title", "issued", "container-title"],
    "book": [("author", "editor"), "title", "issued", "publisher"],
    "chapter": ["author", "title", "container-title", "issued", "publisher"],
    "paper-conference": ["author", "title", "container-title", "issued"],
    "report": ["title", "issued", ("author", "publisher")],
    "webpage": ["title", "URL"],
    "dataset": ["title", "issued", ("author", "publisher")],
    "thesis": ["author", "title", "issued", "publisher"],
}


def extract_pandoc_keys(markdown_text: str) -> list[str]:
    """Extract cited Pandoc citation keys in order of first appearance."""
    # 1. Strip fenced code blocks (``` or ~~~)
    clean = re.sub(r"```.*?```", "", markdown_text, flags=re.DOTALL)
    clean = re.sub(r"~~~.*?~~~", "", clean, flags=re.DOTALL)
    # 2. Strip inline code (`...`)
    clean = re.sub(r"`[^`]+`", "", clean)

    # 3. Pandoc key regex
    pattern = re.compile(r"(?:^|[^a-zA-Z0-9_.])@([a-zA-Z0-9_][a-zA-Z0-9_:.#$%&\-+?<>~/]*)")
    keys = []
    seen = set()

    for m in pattern.finditer(clean):
        key = m.group(1).rstrip(".,;:!?])}")
        if key and key not in seen:
            keys.append(key)
            seen.add(key)

    return keys


def _check_field(item: dict, field_spec) -> bool:
    if isinstance(field_spec, tuple):
        return any(_check_field(item, f) for f in field_spec)
    val = item.get(field_spec)
    if val is None:
        return False
    if isinstance(val, (list, dict, str)) and len(val) == 0:
        return False
    return True


def validate_keys_mode(doc_text: str, refs: list[dict], require_verified: bool = False) -> dict:
    """Validate Pandoc-style keys (@key) in document against reference list."""
    keys_used = extract_pandoc_keys(doc_text)

    # Track duplicate IDs
    seen_ids = set()
    duplicate_ids = []
    ref_map = {}
    for item in refs:
        item_id = item.get("id")
        if item_id:
            if item_id in seen_ids:
                if item_id not in duplicate_ids:
                    duplicate_ids.append(item_id)
            seen_ids.add(item_id)
            ref_map[item_id] = item

    missing = [k for k in keys_used if k not in ref_map]
    orphans = [item.get("id") for item in refs if item.get("id") not in keys_used]

    # Required fields check
    missing_fields = []
    for item in refs:
        item_id = item.get("id", "unknown")
        csl_type = item.get("type", "document")
        specs = REQUIRED_FIELDS.get(csl_type, ["title"])
        for req in specs:
            if not _check_field(item, req):
                field_name = "/".join(req) if isinstance(req, tuple) else req
                missing_fields.append({
                    "id": item_id,
                    "field": field_name,
                    "type": csl_type,
                })

    # Duplicate works check (by DOI or by title+year+first_author)
    duplicate_works = []
    doi_seen = {}
    title_seen = {}

    for item in refs:
        item_id = item.get("id")
        raw_doi = item.get("DOI")
        norm_doi = normalize_doi(raw_doi) if raw_doi else None

        if norm_doi:
            if norm_doi in doi_seen:
                duplicate_works.append({
                    "id": item_id,
                    "duplicate_of": doi_seen[norm_doi],
                    "basis": f"DOI: {norm_doi}",
                })
            else:
                doi_seen[norm_doi] = item_id

        # Title + Year + First Author
        title_str = normalize_text(item.get("title") or "")
        fam_str = normalize_text(first_author_family(item) or "")
        issued = item.get("issued") or {}
        parts = issued.get("date-parts") or []
        year_str = str(parts[0][0]) if parts and parts[0] else ""

        if title_str:
            work_key = (title_str, fam_str, year_str)
            if work_key in title_seen:
                if not any(d["id"] == item_id for d in duplicate_works):
                    duplicate_works.append({
                        "id": item_id,
                        "duplicate_of": title_seen[work_key],
                        "basis": f"Title/Author/Year: '{title_str[:30]}' / '{fam_str}' / '{year_str}'",
                    })
            else:
                title_seen[work_key] = item_id

    # Unverified items check
    unverified = []
    for item in refs:
        item_id = item.get("id")
        xrfa = item.get("x-rfa") or {}
        if xrfa.get("status") != "verified":
            unverified.append(item_id)

    errors = []
    warnings = []

    for k in missing:
        errors.append({"code": "missing_key", "id": k, "message": f"Cited key does not exist: {k}"})
    for d_id in duplicate_ids:
        errors.append({"code": "duplicate_id", "id": d_id, "message": f"Duplicate ID in references: {d_id}"})
    for mf in missing_fields:
        errors.append({
            "code": "missing_required_field",
            "id": mf["id"],
            "field": mf["field"],
            "message": f"Missing required field '{mf['field']}' for {mf['id']} ({mf['type']})",
        })

    for o_id in orphans:
        warnings.append({"code": "orphan", "id": o_id, "message": f"Orphan reference (not cited): {o_id}"})
    for dw in duplicate_works:
        warnings.append({
            "code": "duplicate_work",
            "id": dw["id"],
            "message": f"Possible duplicate of '{dw['duplicate_of']}' ({dw['basis']})",
        })

    for u_id in unverified:
        if require_verified:
            errors.append({"code": "unverified", "id": u_id, "message": f"Unverified reference: {u_id}"})
        else:
            warnings.append({"code": "unverified", "id": u_id, "message": f"Unverified reference: {u_id}"})

    ok = (len(errors) == 0)

    return {
        "ok": ok,
        "mode": "keys",
        "keys_used": keys_used,
        "missing": missing,
        "orphans": orphans,
        "duplicates": duplicate_ids,
        "duplicate_works": duplicate_works,
        "missing_fields": missing_fields,
        "unverified": unverified,
        "errors": errors,
        "warnings": warnings,
    }


def _clean_first_author(author_raw: str) -> str:
    cleaned = re.sub(r"\bet\s+al\.?", "", author_raw, flags=re.IGNORECASE).strip()
    parts = re.split(r"\s+(?:&|y|and|e)\s+|\s*&\s*", cleaned, maxsplit=1)
    return parts[0].strip() if parts else ""


def validate_apa_freetext_mode(doc_text: str, refs: list[dict]) -> dict:
    """Heuristic extraction of APA-style free-text citations and matching."""
    matched_ids = []
    unmatched_citations = []

    refs_by_year = {}
    for item in refs:
        item_id = item.get("id")
        fam = first_author_family(item) or ""
        norm_fam = normalize_text(fam).replace(" ", "")
        issued = item.get("issued") or {}
        parts = issued.get("date-parts") or []
        item_year = str(parts[0][0]) if parts and parts[0] else ""
        if item_year:
            refs_by_year.setdefault(item_year, []).append((norm_fam, item_id))

    # 1. Parenthetical: (Author, 2020) or (Author, 2021a, 2021b; Other, 2019)
    for m in re.finditer(r"\(([^)]+)\)", doc_text):
        content = m.group(1).strip()
        parts = [p.strip() for p in content.split(";")]
        for p in parts:
            m_auth_years = re.match(r"^(.*?)(?:,\s*|\s+)(\d{4}[a-z]?(?:\s*,\s*\d{4}[a-z]?)*)$", p)
            if m_auth_years:
                author_str = m_auth_years.group(1).strip()
                years_str = m_auth_years.group(2).strip()
                first_auth = _clean_first_author(author_str)
                norm_first = normalize_text(first_auth).replace(" ", "")

                for y_m in re.finditer(r"(\d{4})[a-z]?", years_str):
                    year = y_m.group(1)
                    matched = False
                    if norm_first:
                        for norm_fam, item_id in refs_by_year.get(year, []):
                            if norm_first == norm_fam:
                                matched = True
                                if item_id not in matched_ids:
                                    matched_ids.append(item_id)
                    if not matched:
                        label = f"{author_str}, {year}"
                        if label not in unmatched_citations:
                            unmatched_citations.append(label)

    # 2. Narrative: Author (2020)
    for m in re.finditer(r"\((1[89]\d\d|20\d\d)([a-z]?)\)", doc_text):
        year = m.group(1)
        preceding = doc_text[:m.start()]
        line_preceding = preceding.splitlines()[-1] if preceding.splitlines() else ""
        if "(" in line_preceding:
            continue
        cleaned_line = line_preceding.rstrip(" ,;:'\"")
        words = cleaned_line.split()
        if not words:
            continue
        max_words = words[-8:]

        matched = False
        matched_item_id = None
        for k in range(1, len(max_words) + 1):
            cand_suffix = " ".join(max_words[-k:])
            cand_first = _clean_first_author(cand_suffix)
            norm_cand = normalize_text(cand_first).replace(" ", "")
            if not norm_cand:
                continue
            for norm_fam, item_id in refs_by_year.get(year, []):
                if norm_cand == norm_fam:
                    matched = True
                    matched_item_id = item_id
                    break
            if matched:
                break

        if matched and matched_item_id not in matched_ids:
            matched_ids.append(matched_item_id)

    orphans = [item.get("id") for item in refs if item.get("id") not in matched_ids]

    errors = []
    warnings = []
    if unmatched_citations:
        warnings.append({"code": "unmatched_freetext", "citations": unmatched_citations})
    for o_id in orphans:
        warnings.append({"code": "orphan", "id": o_id})

    return {
        "ok": len(errors) == 0,
        "mode": "apa-freetext",
        "heuristic": True,
        "matched_ids": matched_ids,
        "unmatched_citations": unmatched_citations,
        "orphans": orphans,
        "errors": errors,
        "warnings": warnings,
    }


def validate_numeric_mode(doc_text: str, n_refs: int) -> dict:
    """Validate numeric citation sequences in Markdown document."""
    # Normalize forms like [4]–[5] or [4]-[5] into [4,5]
    text_norm = re.sub(
        r"\[(\d+)\]\s*[–—-]\s*\[(\d+)\]",
        lambda m: "[" + ",".join(str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1)) + "]",
        doc_text,
    )

    first_order = []
    for m in re.finditer(r"\[([\d\s,–—-]+)\]", text_norm):
        content = m.group(1)
        parts = re.split(r"[,;]\s*", content)
        for p in parts:
            p = p.strip()
            m_range = re.match(r"^(\d+)\s*[–—-]\s*(\d+)$", p)
            if m_range:
                start, end = int(m_range.group(1)), int(m_range.group(2))
                for num in range(start, end + 1):
                    if num not in first_order:
                        first_order.append(num)
            elif p.isdigit():
                num = int(p)
                if num not in first_order:
                    first_order.append(num)

    cited_numbers = sorted(list(set(first_order)))
    out_of_range = [num for num in cited_numbers if num < 1 or num > n_refs]
    uncited = [num for num in range(1, n_refs + 1) if num not in cited_numbers]
    order_matches_list = (first_order == list(range(1, len(first_order) + 1)))

    errors = []
    warnings = []

    if out_of_range:
        errors.append({
            "code": "out_of_range",
            "numbers": out_of_range,
            "message": f"Numeric citations out of range (1..{n_refs}): {out_of_range}",
        })
    if not order_matches_list:
        warnings.append({
            "code": "order_mismatch",
            "order": first_order,
            "message": f"The first-citation order {first_order} does not follow the sequence 1, 2, 3...",
        })
    for num in uncited:
        warnings.append({"code": "uncited_number", "number": num})

    return {
        "ok": len(errors) == 0,
        "mode": "numeric",
        "cited_numbers": cited_numbers,
        "first_citation_order": first_order,
        "out_of_range": out_of_range,
        "uncited": uncited,
        "order_matches_list": order_matches_list,
        "errors": errors,
        "warnings": warnings,
    }


def main(argv=None):
    """CLI entry point for validate_citations."""
    parser = argparse.ArgumentParser(description="Validate citations in Markdown document.")
    parser.add_argument("--doc", required=True, help="Path to markdown document")
    parser.add_argument("--refs", help="Path to CSL-JSON references file")
    parser.add_argument("--mode", choices=["keys", "apa-freetext", "numeric"], default="keys")
    parser.add_argument("--require-verified", action="store_true", help="Treat unverified references as errors")
    parser.add_argument("--n-refs", type=int, help="Total number of references for numeric mode")
    parser.add_argument("--out", help="Output JSON file (default stdout)")

    args = parser.parse_args(argv)

    try:
        with open(args.doc, "r", encoding="utf-8") as f:
            doc_text = f.read()
    except Exception as e:
        sys.stderr.write(f"Error reading doc: {e}\n")
        return 2

    refs = []
    if args.refs:
        try:
            with open(args.refs, "r", encoding="utf-8") as f:
                refs = json.load(f)
        except Exception as e:
            sys.stderr.write(f"Error reading refs: {e}\n")
            return 2

    if args.mode == "keys":
        res = validate_keys_mode(doc_text, refs, require_verified=args.require_verified)
    elif args.mode == "apa-freetext":
        res = validate_apa_freetext_mode(doc_text, refs)
    elif args.mode == "numeric":
        n = args.n_refs if args.n_refs is not None else len(refs)
        res = validate_numeric_mode(doc_text, n)

    out_json = json.dumps(res, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json)
    else:
        sys.stdout.write(out_json)

    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
