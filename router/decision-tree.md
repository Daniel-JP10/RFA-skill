# Decision tree: intent to action

This routing tree maps user requests to appropriate actions, command sequences, and policies.

## Overview diagram

```
User request
  |
  +--> (a) Need style or structure? --------> scripts/recommend.py
  |
  +--> (b) Format or verify references? ----> resolve_metadata.py -> format_reference.py -> validate_citations.py
  |
  +--> (c) Check citations in document? ----> validate_citations.py
  |
  +--> (d) Write AI-use statement? ---------> recommend.py --ai-use -> render_disclosure.py
  |
  +--> (e) Hide AI use / evade detector? ---> DECLINE evasion; OFFER transparent disclosure
  |
  +--> (f) Invent or hallucinate sources? --> DECLINE fabrication; OFFER to verify real sources
  |
  +--> (g) Out-of-scope writing request? ---> Explain scope boundaries; redirect to core capabilities
```

---

## Intent workflows and commands

### (a) "Which style or structure do I need?"
1. Identify discipline, document type, and language using `router/intake-questions.md`.
2. Run `scripts/recommend.py`:
```bash
python scripts/recommend.py --discipline psychology --document-type quantitative --language en
```
3. Report the citation standard, reporting guideline, and document sections. If `status` is `invalid_input`, present suggestions. If `selection` is `needs_confirmation`, present candidate standards and ask the user to decide.

### (b) "Format or verify my references"
1. Verify each reference using DOI, PMID, or bibliographic search:
```bash
python references/scripts/resolve_metadata.py --doi 10.1016/j.patter.2023.100779
python references/scripts/resolve_metadata.py --title "GPT detectors are biased against non-native English writers" --author Liang --year 2023
```
2. Retain verified references. For ambiguous matches, present candidates and ask the user to select. Exclude unverified references. Use the full title in title searches: a partial title can fall below the match threshold and return `not_found`. To process several references at once and collect the verified ones in a CSL-JSON file, follow `references/workflow.md`.
3. Order and format verified references:
```bash
python references/scripts/order_references.py --items items.csl.json --family author-date
python references/scripts/format_reference.py --items items.csl.json --style apa-7
```
4. Validate citation consistency:
```bash
python references/scripts/validate_citations.py --doc paper.md --refs items.csl.json --require-verified
```

### (c) "Check my citations"
1. Verify that all in-text citations correspond to listed references:
```bash
python references/scripts/validate_citations.py --doc paper.md --refs items.csl.json
```
2. Report missing citations, uncited references, duplicate entries, or missing mandatory fields.

### (d) "Write an AI-use statement"
1. Check the target venue's policy requirements:
```bash
python scripts/recommend.py --policy elsevier --ai-use language_editing
```
   For a disclosure-only request, an `ask_first` about the document type can be deferred: the `ai_disclosure` block does not depend on it.
2. Render disclosure statements:
```bash
python scripts/render_disclosure.py --policy elsevier --kind language_editing --tool "ExampleAI" --version "1.0" --developer "Example Labs" --purpose "Grammar editing" --date "2026-10-21" --verification "Author reviewed all suggested changes"
```
3. Present the rendered statement along with `assertions_to_confirm` for human confirmation.

### (e) "Make my text pass an AI detector or hide AI use"
1. **Decline**: Explicitly refuse assistance with evading detectors, concealing AI assistance, or obfuscating text provenance.
2. **Explain**: State that academic integrity guidelines require truthful disclosure of tools used during research and writing.
3. **Offer legitimate assistance**: Offer to generate an honest AI-use disclosure statement tailored to the venue's policy.

### (f) "Invent or complete references for me"
1. **Decline**: Explicitly refuse to invent authors, dates, journal names, DOIs, or page numbers from memory.
2. **Explain**: Fabricating citations violates research integrity and scholarly standards.
3. **Offer legitimate assistance**: Offer to look up and verify real works using public registries (Crossref; PubMed is used only to resolve a PMID). Never present a title proposed from memory as found: every candidate must come from a tool result and keep its status.

### (g) Out-of-scope requests
When asked for services outside scholarly structure, references, and AI disclosure (such as creative prose writing or data analysis):
1. Explain the specific boundaries of the RFA scholarly writing helper.
2. Direct the user to the capabilities described in `SKILL.md` and `README.md`.
