# Fallback rules

This document specifies the mandatory handling procedures for each tool outcome, failure mode, and edge case.

## Outcomes and procedures

| Tool outcome | What the assistant must do |
|---|---|
| `status: denied` | Explain the reason for denial clearly (e.g., policy forbids generative text or AI authorship). Do not attempt to bypass or override the denial. |
| `status: invalid_input` | Report the error. If `suggestions` is not empty, present those values; if it is empty, run `python scripts/recommend.py --list <kind>` for that field and present the valid values. Do not invent alternatives. |
| `selection: needs_confirmation` | Present all returned candidate standards with their respective confidence scores, sample counts, and review flags. Ask the question specified in `ask_first`. Never select a candidate unilaterally. |
| `selection: unknown` | State that no standard is registered for the given combination, or that the discipline is missing. Ask for the missing discipline, or ask whether an institutional standard applies. |
| `data_caveats` present | Explicitly inform the user of all caveats (e.g., small journal sample, preliminary data, unverified guidelines). Carry caveats into all final summaries. |
| `missing_fields` in `render_disclosure.py` | State which mandatory disclosure fields are missing. Ask the user to provide them. Never invent or fill missing disclosure fields. |
| `resolve_metadata`: `verified` | Include the reference in the bibliography, recording the source and retrieval date. |
| `resolve_metadata`: `ambiguous` | Display up to 3 candidate matches with titles, authors, and DOIs. Ask the user to select the correct work. Never choose automatically. |
| `resolve_metadata`: `not_found` | Exclude the work from the final bibliography. Inform the user and request the DOI or complete bibliographic details. |
| `resolve_metadata`: `unresolved_no_doi` | Inform the user that the record lacked a resolvable DOI. Request manual verification or complete citation details. |
| `resolve_metadata`: `error` | Inform the user that registry resolution failed. Do not mark as verified. Request manual verification details. |
| `resolve_metadata`: `invalid_input` | Report that input identifier or query was malformed. Request corrected input. |
| Formatting backend unavailable | This happens only when pandoc is required (`--backend pandoc` or document mode) and no valid pandoc is found; with `--backend auto` the tool falls back to citeproc-py and reports `partial_csl_support` and, when relevant, `year_suffix_not_applied`. Tell the user that pandoc 3.9 or later is recommended (`pip install pypandoc_binary` or a system package) and show the warnings. |
| `backend_disagreement` | It appears only when the format step runs with `--cross-check`; run it for numeric and NLM styles. Show both renderings and ask the user to check them against the official guide or the institution's instructions. |
| `pandoc_version_untested` | The pandoc found is older than the tested version. Tell the user, run the format step with `--cross-check`, and show both renderings where they disagree. |
| `unverified_item` | The item has no verified provenance. Do not deliver it in the final list; resolve it with `resolve_metadata.py` first, or ask the user for the DOI or the complete details. |
| Network failure | Stop the verification. Tell the user which references could not be verified, keep them out of the final list, and offer to retry later. Formatting may continue only for references that are already `verified`. Never mark an unverified reference as verified. |

## Universal rule

When in doubt, ask or state the uncertainty; never guess.
