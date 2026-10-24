# Data sources for the references skill

> Status: draft. Last reviewed: 2026-10-24. Data marked (research agent) were checked only by an automated research assistant; "orchestrator" refers to the AI assistant that coordinates the maintainers' work. Both kinds of check require human review.

## Bibliographic metadata
### Crossref REST API
- Official documentation: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- Public access requires no key. To use identified access ("polite pool"), simply provide an email address (`mailto` parameter or User-Agent header). (research agent)
- The client limits itself to one request per second by default (`--max-rps`) and honors the `Retry-After` header when a service asks it to wait. It does not read the `X-Rate-Limit-*` headers.
- To match a reference by title, `query.bibliographic` is used with up to three rows (`rows=3`) and `select` to limit fields; at most 3 candidates are returned.
- Bibliographic metadata is published without copyright restrictions; abstracts may remain subject to individual publisher rights. (research agent)

### doi.org (content negotiation)
- doi.org returns CSL-JSON for DOIs from other registration agencies (for example DataCite) when the Accept header asks for it; this was observed on 2026-10-20 (see below). If doi.org redirects to a host that is not in the allowed list, the request is refused and the reference ends with status `error`.

### NCBI E-utilities (PubMed)
- Uses `esummary` to resolve a PMID to its DOI. The `NCBI_API_KEY` key is optional. Current rate limits should be consulted in official NCBI documentation and are not recorded here.

### OpenAlex
- Since 2026 an API key is required; each key receives 1 USD of free daily credits (verified by the orchestrator on the official OpenAlex blog on 2026-10-19).
- Not used in this version: the search function is disabled in the code and makes no request, and `OPENALEX_API_KEY` enables nothing. Before enabling it, read the authentication rules at https://developers.openalex.org/guides/rate-limits.

## Journal abbreviations
- NLM: list of journals from the NLM catalog (`J_Medline.txt` file). US Public Domain according to the research agent. Official source: https://www.nlm.nih.gov/bsd/serfile_addedinfo.html (research agent).
- ISO 4 (LTWA): https://www.issn.org/services/online-services/access-to-the-ltwa/. The site blocked the research agent; redistribution terms are NOT verified.
- The skill never invents abbreviations: it uses the short title from metadata, an optional local file (`RFA_JOURNAL_ABBR_FILE`), or returns the full title.

## Styles and formatting engines
- Styles: CSL repository https://github.com/citation-style-language/styles (CC BY-SA 3.0). See `references/csl/NOTICE.md` and `references/csl/MANIFEST.yaml`.
- pandoc (preferred engine): software licensed under GPL-2.0-or-later used only as an external executable; implements complete CSL 1.0.2 (research agent). The skill does not bundle it.
- citeproc-py (fallback engine): BSD-2-Clause license; according to its documentation it passes only about 60 % of the official CSL test suite and does not fully disambiguate (research agent).
- citeproc-js: CPAL-1.0 or AGPL-3.0 license. NOT used.

## Compatibility observations (2026-10-19)

> Measured by the orchestrator with pandoc 3.9, citeproc-py 0.11.1, and CSL styles downloaded that day. May change with other versions.

- pandoc produced, for the test cases, the alphabetical ordering, year suffixes (2021a, 2021b), and in-text citations expected under APA 7.
- pandoc with `nlm-citation-sequence.csl`: in an edited book chapter, the text "In, editorDuarte P." was observed instead of "In: Duarte P, editor.". citeproc-py rendered that case correctly.
- citeproc-py does not apply year suffixes or sort the bibliography alphabetically (the skill sorts beforehand and warns with `year_suffix_not_applied`), and with NLM converted the page range 1-10 to "1–0".
- Therefore `format_reference.py` provides cross-checking between engines and warns about discrepancies.
- Under the `es-ES` locale, APA style displays page ranges with a hyphen (45-67) rather than an en-dash. Confirm whether this matches institutional expectations.
- The IEEE CSL implements version 11.29.2023 of the IEEE Reference Guide; the official guide may be newer.

## Live network observations (2026-10-20)

> Observed by the user when testing the fallback flow with a DataCite DOI (Zenodo).

- A DOI not in Crossref returns 404 on api.crossref.org. The request to doi.org with the `Accept: application/vnd.citationstyles.csl+json` header responded with a redirect (302) to `data.crosscite.org`, and from there the CSL-JSON was obtained.
- Therefore `data.crosscite.org` is included in the allowed hosts list and in `PRIVACY.md`. It receives the DOI, the Accept header, and a User-Agent without personal data.
- The contact email (`RFA_CONTACT_EMAIL`) is sent only to api.crossref.org; other hosts receive a User-Agent without an email.

## Compatibility observations (2026-10-23)

> Observed by the orchestrator on Linux with the system package pandoc 3.1.3 and with pandoc 3.9 from pypandoc_binary 1.17.

- With pandoc 3.1.3, the Vancouver style printed full given names (for example "Ana Maria Rivera" instead of "Rivera AM"). Before the writer fix of this version, document mode also left `[@key]` citations unprocessed. With pandoc 3.9 both were correct.
- A pandoc on the PATH is chosen before the copy installed by pypandoc, unless its version is known to be older than 3.9 and the pypandoc copy is 3.9 or later; a valid `RFA_PANDOC` always wins.
- The tools warn with `pandoc_version_untested` when the pandoc found is older than 3.9.
