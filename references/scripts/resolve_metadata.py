# -*- coding: utf-8 -*-
"""Resolve bibliographic metadata against Crossref, doi.org, and NCBI."""

import argparse
from datetime import datetime, timezone
import json
import os
import sys
import urllib.parse

from _common import (
    RequestsClient,
    first_author_family,
    normalize_doi,
    normalize_text,
    redact,
    title_similarity,
)

# Design parameters: title similarity thresholds and number of candidates
CONFIG = {
    "title_accept": 0.92,
    "title_min_candidate": 0.60,
    "search_rows": 3,
    "max_candidates": 3,
}

CROSSREF_TYPE_MAP = {
    "journal-article": "article-journal",
    "book-chapter": "chapter",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "proceedings-article": "paper-conference",
    "posted-content": "article",
    "dataset": "dataset",
    "report": "report",
    "dissertation": "thesis",
    "standard": "standard",
}


def openalex_search(*args, **kwargs):
    """Complementary OpenAlex search (disabled by default)."""
    raise NotImplementedError("disabled: see data-sources.md")


def make_csl_id(item: dict) -> str:
    """Build the familyYEAR id used for Crossref items from a CSL-JSON item."""
    names = item.get("author") or item.get("editor") or []
    first_fam = (names[0].get("family") or names[0].get("literal")) if names else None
    parts = (item.get("issued") or {}).get("date-parts") or []
    year = parts[0][0] if parts and parts[0] and parts[0][0] else None
    if first_fam:
        norm_fam = normalize_text(first_fam).replace(" ", "")
        return f"{norm_fam}{year}" if year else norm_fam
    return f"ref{year}" if year else "ref"


def crossref_to_csl(message: dict) -> dict:
    """Convert a Crossref work message dictionary to a CSL-JSON item."""
    csl_type = CROSSREF_TYPE_MAP.get(message.get("type", ""), "document")

    # Title
    titles = message.get("title") or []
    main_title = titles[0] if titles else ""
    subtitles = message.get("subtitle") or []
    if subtitles:
        title = f"{main_title}: {subtitles[0]}"
    else:
        title = main_title

    # Authors
    authors = []
    for a in message.get("author") or []:
        if "given" in a or "family" in a:
            authors.append({
                "family": a.get("family", ""),
                "given": a.get("given", ""),
            })
        elif "name" in a:
            authors.append({"literal": a["name"]})

    # Editors
    editors = []
    for e in message.get("editor") or []:
        if "given" in e or "family" in e:
            editors.append({
                "family": e.get("family", ""),
                "given": e.get("given", ""),
            })
        elif "name" in e:
            editors.append({"literal": e["name"]})

    # Container title
    containers = message.get("container-title") or []
    container_title = containers[0] if containers else None

    # Container short title
    short_containers = message.get("short-container-title") or []
    container_short = short_containers[0] if short_containers else None

    # Issued date
    issued = message.get("issued")
    if not issued or not issued.get("date-parts"):
        for date_key in ("published-print", "published-online", "published", "created"):
            candidate = message.get(date_key)
            if candidate and candidate.get("date-parts"):
                issued = candidate
                break

    # Year for ID
    year = None
    if issued and issued.get("date-parts"):
        parts = issued["date-parts"]
        if parts and parts[0] and parts[0][0]:
            year = parts[0][0]

    # ID generation
    first_fam = None
    if authors:
        first_fam = authors[0].get("family") or authors[0].get("literal")
    elif editors:
        first_fam = editors[0].get("family") or editors[0].get("literal")

    if first_fam:
        norm_fam = normalize_text(first_fam).replace(" ", "")
        csl_id = f"{norm_fam}{year}" if year else norm_fam
    else:
        csl_id = f"ref{year}" if year else "ref"

    item = {
        "id": csl_id,
        "type": csl_type,
        "title": title,
    }
    if authors:
        item["author"] = authors
    if editors:
        item["editor"] = editors
    if container_title:
        item["container-title"] = container_title
    if container_short:
        item["container-title-short"] = container_short
    if issued:
        item["issued"] = issued
    if "volume" in message:
        item["volume"] = str(message["volume"])
    if "issue" in message:
        item["issue"] = str(message["issue"])
    if "page" in message:
        item["page"] = str(message["page"])
    if "publisher" in message:
        item["publisher"] = message["publisher"]
    if "DOI" in message:
        item["DOI"] = message["DOI"]

    issns = message.get("ISSN") or []
    if issns:
        item["ISSN"] = issns[0] if isinstance(issns, list) else issns

    # Note: abstract is explicitly not copied per specification
    return item


def resolve(record: dict, client: RequestsClient, env=os.environ) -> dict:
    """Resolve a single bibliographic record into verified metadata."""
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        # Case 1: DOI provided
        if "doi" in record and record["doi"]:
            raw_doi = str(record["doi"])
            norm_doi = normalize_doi(raw_doi)
            if not norm_doi:
                return {
                    "input": record,
                    "status": "invalid_input",
                    "item": None,
                    "candidates": [],
                    "provenance": {},
                    "warnings": ["invalid_doi"],
                }

            # Try Crossref
            quoted_doi = urllib.parse.quote(norm_doi, safe="/")
            crossref_url = f"https://api.crossref.org/works/{quoted_doi}"
            params = {}
            if env.get("RFA_CONTACT_EMAIL"):
                params["mailto"] = env["RFA_CONTACT_EMAIL"]

            resp = client.get(crossref_url, params=params)
            if resp.status == 200:
                data = json.loads(resp.body)
                msg = data.get("message") or {}
                item = crossref_to_csl(msg)
                item["x-rfa"] = {
                    "status": "verified",
                    "source": "crossref",
                    "retrieved_at": now_iso,
                    "match": {"doi": norm_doi},
                }
                return {
                    "input": record,
                    "status": "verified",
                    "item": item,
                    "candidates": [],
                    "provenance": {"source": "crossref", "retrieved_at": now_iso},
                    "warnings": [],
                }

            if resp.status == 404:
                # Try doi.org content negotiation
                doi_url = f"https://doi.org/{quoted_doi}"
                doi_headers = {"Accept": "application/vnd.citationstyles.csl+json"}
                doi_resp = client.get(doi_url, headers=doi_headers)
                if doi_resp.status == 200:
                    try:
                        item = json.loads(doi_resp.body)
                        if isinstance(item, dict) and item.get("title"):
                            upstream_id = item.get("id")
                            item["id"] = make_csl_id(item)
                            item["x-rfa"] = {
                                "upstream_id": upstream_id,
                                "status": "verified",
                                "source": "doi.org",
                                "retrieved_at": now_iso,
                                "match": {"doi": norm_doi},
                            }
                            return {
                                "input": record,
                                "status": "verified",
                                "item": item,
                                "candidates": [],
                                "provenance": {"source": "doi.org", "retrieved_at": now_iso},
                                "warnings": [],
                            }
                    except json.JSONDecodeError:
                        pass

                return {
                    "input": record,
                    "status": "not_found",
                    "item": None,
                    "candidates": [],
                    "provenance": {"source": "doi.org"},
                    "warnings": [],
                }

            # Other status code
            return {
                "input": record,
                "status": "error",
                "item": None,
                "candidates": [],
                "provenance": {"reason": f"HTTP {resp.status}"},
                "warnings": [f"status_{resp.status}"],
            }

        # Case 2: PMID provided
        if "pmid" in record and record["pmid"]:
            pmid = str(record["pmid"]).strip()
            eutils_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            params = {
                "db": "pubmed",
                "id": pmid,
                "retmode": "json",
            }
            if env.get("NCBI_API_KEY"):
                params["api_key"] = env["NCBI_API_KEY"]

            resp = client.get(eutils_url, params=params)
            if resp.status == 200:
                data = json.loads(resp.body)
                result = data.get("result", {})
                pmid_data = result.get(pmid)
                if not pmid_data or "error" in pmid_data:
                    return {
                        "input": record,
                        "status": "not_found",
                        "item": None,
                        "candidates": [],
                        "provenance": {"source": "ncbi"},
                        "warnings": [],
                    }

                articleids = pmid_data.get("articleids") or []
                doi_found = None
                for aid in articleids:
                    if aid.get("idtype") == "doi":
                        doi_found = aid.get("value")
                        break

                if doi_found:
                    sub_record = dict(record)
                    sub_record["doi"] = doi_found
                    return resolve(sub_record, client, env=env)

                raw_meta = {
                    "title": pmid_data.get("title"),
                    "source": pmid_data.get("source"),
                    "pubdate": pmid_data.get("pubdate"),
                }
                return {
                    "input": record,
                    "status": "unresolved_no_doi",
                    "item": None,
                    "candidates": [],
                    "provenance": {"source": "ncbi", "raw": raw_meta},
                    "warnings": ["no_doi_found"],
                }

            return {
                "input": record,
                "status": "error",
                "item": None,
                "candidates": [],
                "provenance": {"reason": f"HTTP {resp.status}"},
                "warnings": [f"status_{resp.status}"],
            }

        # Case 3: Title provided
        if "title" in record and record["title"]:
            title_query = record["title"].strip()
            parts = [title_query]
            if record.get("author"):
                parts.append(str(record["author"]).strip())
            if record.get("year"):
                parts.append(str(record["year"]).strip())
            full_query = " ".join(parts)

            search_url = "https://api.crossref.org/works"
            params = {
                "query.bibliographic": full_query,
                "rows": CONFIG["search_rows"],
                "select": "DOI,title,author,issued,container-title,type,score",
            }
            if env.get("RFA_CONTACT_EMAIL"):
                params["mailto"] = env["RFA_CONTACT_EMAIL"]

            resp = client.get(search_url, params=params)
            if resp.status == 200:
                data = json.loads(resp.body)
                items = data.get("message", {}).get("items") or []

                candidates_with_sim = []
                for cand in items:
                    cand_titles = cand.get("title") or []
                    cand_title = cand_titles[0] if cand_titles else ""
                    sim = title_similarity(title_query, cand_title)
                    candidates_with_sim.append((sim, cand))

                candidates_with_sim.sort(key=lambda x: x[0], reverse=True)

                valid_candidates = [
                    (s, c) for s, c in candidates_with_sim if s >= CONFIG["title_min_candidate"]
                ]

                if not valid_candidates:
                    return {
                        "input": record,
                        "status": "not_found",
                        "item": None,
                        "candidates": [],
                        "provenance": {"source": "crossref"},
                        "warnings": [],
                    }

                best_sim, best_cand = valid_candidates[0]

                # Check year and author matches if provided
                year_given = record.get("year")
                author_given = record.get("author")

                year_match = True
                if year_given is not None:
                    cand_issued = best_cand.get("issued") or {}
                    parts = cand_issued.get("date-parts") or []
                    cand_year = parts[0][0] if parts and parts[0] else None
                    year_match = str(cand_year) == str(year_given)

                author_match = True
                if author_given is not None:
                    cand_fam = first_author_family(best_cand)
                    if cand_fam:
                        author_match = (
                            normalize_text(str(author_given)) in normalize_text(cand_fam)
                            or normalize_text(cand_fam) in normalize_text(str(author_given))
                        )
                    else:
                        author_match = False

                attribute_match = True
                if year_given is not None or author_given is not None:
                    attribute_match = (year_match or author_match)

                count_high_sim = sum(1 for s, _ in valid_candidates if s >= CONFIG["title_accept"])

                if best_sim >= CONFIG["title_accept"] and attribute_match and count_high_sim == 1:
                    # Verified single best match
                    item = crossref_to_csl(best_cand)
                    item["x-rfa"] = {
                        "status": "verified",
                        "source": "crossref",
                        "retrieved_at": now_iso,
                        "match": {
                            "query": full_query,
                            "doi": best_cand.get("DOI"),
                            "similarity": round(best_sim, 4),
                            "year_match": year_match if year_given is not None else None,
                            "author_match": author_match if author_given is not None else None,
                        },
                    }
                    return {
                        "input": record,
                        "status": "verified",
                        "item": item,
                        "candidates": [],
                        "provenance": {"source": "crossref", "retrieved_at": now_iso},
                        "warnings": [],
                    }

                # Ambiguous
                csl_candidates = [crossref_to_csl(c) for _, c in valid_candidates[:CONFIG["max_candidates"]]]
                return {
                    "input": record,
                    "status": "ambiguous",
                    "item": None,
                    "candidates": csl_candidates,
                    "provenance": {"source": "crossref"},
                    "warnings": ["multiple_or_partial_candidates"],
                }

            return {
                "input": record,
                "status": "error",
                "item": None,
                "candidates": [],
                "provenance": {"reason": f"HTTP {resp.status}"},
                "warnings": [f"status_{resp.status}"],
            }

        return {
            "input": record,
            "status": "invalid_input",
            "item": None,
            "candidates": [],
            "provenance": {},
            "warnings": ["no_doi_pmid_or_title"],
        }

    except Exception as e:
        redacted_reason = redact(f"{e.__class__.__name__}: {e}", env=env)
        return {
            "input": record,
            "status": "error",
            "item": None,
            "candidates": [],
            "provenance": {"reason": redacted_reason},
            "warnings": ["network_or_http_exception"],
        }


def main(argv=None):
    """CLI entry point for resolve_metadata."""
    parser = argparse.ArgumentParser(description="Resolve bibliographic metadata.")
    parser.add_argument("--doi", help="DOI to resolve")
    parser.add_argument("--pmid", help="PMID to resolve")
    parser.add_argument("--title", help="Title to search")
    parser.add_argument("--author", help="Author name to filter")
    parser.add_argument("--year", help="Year to filter")
    parser.add_argument("--in", dest="input_file", help="Input JSONL file")
    parser.add_argument("--out", dest="output_file", help="Output JSON file")
    parser.add_argument("--items-out", help="Write the verified items, and only those, to a CSL-JSON file")
    parser.add_argument("--max-rps", type=float, default=1.0, help="Max requests per second")

    args = parser.parse_args(argv)
    client = RequestsClient(max_rps=args.max_rps)

    records = []
    if args.input_file:
        try:
            with open(args.input_file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            sys.stderr.write(f"Error on line {line_no}: malformed JSON\n")
                            return 2
        except Exception as e:
            sys.stderr.write(f"Error reading file: {e}\n")
            return 2
        if not records:
            sys.stderr.write("Empty input\n")
            return 2
    elif args.doi:
        records.append({"doi": args.doi})
    elif args.pmid:
        records.append({"pmid": args.pmid})
    elif args.title:
        rec = {"title": args.title}
        if args.author:
            rec["author"] = args.author
        if args.year:
            rec["year"] = args.year
        records.append(rec)
    else:
        parser.print_help(sys.stderr)
        return 2

    if not records:
        sys.stderr.write("Empty input\n")
        return 2

    results = []
    seen_ids = set()

    for rec in records:
        res = resolve(rec, client)
        if res.get("item") and "id" in res["item"]:
            base_id = res["item"]["id"]
            csl_id = base_id
            counter = 2
            while csl_id in seen_ids:
                csl_id = f"{base_id}_{counter}"
                counter += 1
            seen_ids.add(csl_id)
            res["item"]["id"] = csl_id
        results.append(res)

    output_data = results if len(results) > 1 else results[0]
    out_json = json.dumps(output_data, indent=2, ensure_ascii=False) + "\n"

    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(out_json)
    else:
        sys.stdout.write(out_json)

    if args.items_out:
        verified_items = [r["item"] for r in results if r["status"] == "verified"]
        with open(args.items_out, "w", encoding="utf-8") as f:
            f.write(json.dumps(verified_items, indent=2, ensure_ascii=False) + "\n")

    # Return codes: 0 = OK, 1 = problems found, 3 = network error
    all_errors = all(r["status"] == "error" for r in results)
    if all_errors:
        return 3
    any_unverified = any(r["status"] != "verified" for r in results)
    if any_unverified:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
