# References workflow: retrieve, verify, format, validate

> Status: draft.

## Guiding principle
Only works that exist are cited. If a reference cannot be verified, it does not enter the final list: the user is asked for the DOI or the complete details. An author, year, DOI, volume or page range is never completed from memory. The tools support this rule but do not enforce it on their own, so the final validation with `--require-verified` is mandatory.

## Steps
1. **Retrieve.** Input: a DOI, a PMID, or the full title with author and year. Several references go in one JSONL file passed with `--in`, one JSON object per line with the keys `doi`, `pmid`, or `title`, `author` and `year`. `resolve_metadata.py` queries Crossref, resolves a PMID through NCBI, and uses doi.org when the DOI belongs to another registration agency. Exit codes: 0 all verified, 1 some not verified, 2 input error, 3 every record failed with a network error.
2. **Verify.** Each reference ends in one of these states:
   - `verified`: it enters the list, with its provenance (source and retrieval date).
   - `ambiguous`: up to 3 candidates are shown and the user is asked to choose; the skill does not choose for the user.
   - `not_found`, `unresolved_no_doi`, `error` or `invalid_input`: it does not enter the list; the DOI or the details are requested.
3. **Collect.** `--items-out` writes the verified items, and only those, to a CSL-JSON file. That file is the input of the next steps.
4. **Format.** `format_reference.py` applies the CSL style of the chosen standard. Preferred engine: pandoc 3.9 or later. Fallback engine: citeproc-py, with a partial-support warning. For numeric and NLM styles add `--cross-check` and show both renderings when `backend_disagreement` appears. Items without verified provenance produce `unverified_item`.
5. **Order.** `order_references.py`: alphabetical for author-date styles; for numeric styles, by order of first citation, which needs `--cited-keys`.
6. **Validate.** `validate_citations.py --require-verified` checks that every citation has its reference and every reference its citation, flags duplicates and missing required fields, and turns unverified references into errors.
7. **Review details.** `check_et_al_rules.py` shows how many authors the style lists; `abbreviate_journal.py` applies abbreviations only if a data source exists.

```bash
python references/scripts/resolve_metadata.py --in refs.jsonl --out resolved.json --items-out items.csl.json
python references/scripts/format_reference.py --items items.csl.json --style vancouver-nlm --cross-check
python references/scripts/validate_citations.py --doc paper.md --refs items.csl.json --require-verified
```

## Writing with keys
The text is written with keys such as `[@key]` and the references live in a CSL-JSON file. This makes formatting and validation mechanical and independent of interpreting hand-written citations. References resolved through doi.org get the same familyYEAR id as Crossref references; the original id is kept in `x-rfa.upstream_id`.

## What the skill does not do
- It does not invent references.
- It does not judge whether a source is relevant or of good quality.
- It does not replace the official standard or the instructions of the institution or journal: if the institution requires its own standard, that prevails.
