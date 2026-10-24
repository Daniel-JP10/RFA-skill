# Reference accuracy and formatting evaluation scenarios

This evaluation suite defines test scenarios for verifying bibliographic data retrieval, registry resolution, error handling, citation consistency, and cross-engine formatting.

## Scenarios

| ID | Scenario | Tool arguments | Expected behavior | Pass criterion | Coverage / Test name |
|---|---|---|---|---|---|
| RA-01 | DOI registered in Crossref | `--doi 10.1016/j.patter.2023.100779` | Metadata from Crossref | `status == "verified"`; `x-rfa.source == "crossref"` | Offline: `test_r2_valid_doi`; live: manual |
| RA-02 | DOI from another registration agency | `--doi 10.5281/zenodo.10853560` | Falls back to doi.org content negotiation | `status == "verified"`; `x-rfa.source == "doi.org"` | Offline: `test_r3_doi_fallback_doi_org`; live: manual |
| RA-03 | Unique full-title match | `--title "GPT detectors are biased against non-native English writers" --author Liang --year 2023` | One match | `status == "verified"` | Offline: `test_r5_title_match`; live: manual |
| RA-04 | Ambiguous title | A title that matches several works | Up to 3 candidates, no automatic choice | `status == "ambiguous"`; at most 3 candidates | Offline: `test_r6_title_ambiguous` |
| RA-05 | Title not found | A fictional title | No metadata invented | `status == "not_found"` | Offline: `test_r7_title_not_found` |
| RA-06 | PMID without DOI | A PMID whose record has no DOI | Reports the missing DOI | `status == "unresolved_no_doi"` | Offline: `test_r8_pmid_resolution` |
| RA-07 | Missing citation key | `--doc doc.md --refs items.csl.json`, the document cites a key absent from the list | Validation fails | `ok` is false; an error with code `missing_key`; the key is listed in `missing` | Offline: `test_v2_keys_mode_missing_keys_fails` |
| RA-08 | Year suffix disambiguation | `--items items.csl.json --style apa-7` | pandoc gives 2021a and 2021b; citeproc-py warns | `year_suffix_not_applied` under citeproc-py | Offline: `test_s3_apa_pandoc_year_suffixes`, `test_s3b_apa_citeproc_year_suffix_warning` |
| RA-09 | Engine cross-check | `--items items.csl.json --style vancouver-nlm --cross-check` | Flags disagreements and shows both renderings | warning `backend_disagreement` | Offline: `test_s9_cross_check` |
| RA-10 | Items without verified provenance | `--items items.csl.json --style apa-7` | Each item is flagged | one `unverified_item` warning per item | Offline: `test_u1_unverified_items_are_flagged` |
| RA-11 | Collect verified items | `--in refs.jsonl --items-out items.csl.json` | Only verified items are written | every item has `x-rfa.status == "verified"` | Offline: `test_i1_items_out_keeps_only_verified` |
| RA-12 | pandoc older than the tested version | any format command | Warning | `pandoc_version_untested` | Offline: `test_p7_old_pandoc_version_warns` |
