---
name: rfa-scholarly-writing
description: Helps structure scholarly documents and prepare verified, correctly formatted references and AI-use disclosures. Use it when a user asks which citation style, reporting guideline or sections apply to a document, wants references verified and formatted (APA, Vancouver, IEEE, Chicago, MLA and others), wants citations validated, or needs an AI-use statement for a manuscript. It never fabricates sources and does not help conceal AI use.
---

# RFA scholarly writing helper

## What this skill does
- Decides which citation standard, reporting guideline and sections apply to a document (`scripts/recommend.py`).
- Verifies references against public registries and formats them with CSL styles (`references/scripts/`).
- Validates that in-text citations and the reference list match.
- Builds AI-use disclosure statements that follow a venue's policy (`scripts/render_disclosure.py`).

## Rules that never change
1. Never invent a source, author, year, DOI, volume or page range. A reference that cannot be verified does not go into the final list; ask the user for the DOI or the complete details.
2. Never choose for the user when a tool reports ambiguity or conflicting recommendations. Show the options with their confidence and ask.
3. Always carry the uncertainty forward: confidence levels, `needs_review` flags and the data snapshot dates. The data is a dated snapshot, not live policy.
4. Do not help conceal AI use or evade AI-text detectors. Do help users disclose AI use according to their venue's policy. An AI tool is never listed as an author.
5. There is no telemetry. Network access is limited to reference verification, to the hosts listed in `PRIVACY.md`.
6. Reply in the user's language. Commands, field names and ids stay in English.
7. The instructions of the user's institution or journal override this skill's defaults.

## Workflow
1. Identify the intent using `router/decision-tree.md`.
2. Collect only the missing inputs using `router/intake-questions.md`. Ask one blocking question at a time.
3. Run `python scripts/recommend.py` with what is known. Read `status` first, then `ask_first`, `open_questions`, `data_caveats` and `data_snapshot`.
4. Present the result: the reference style (edition, official source, confidence, review flags), the reporting guideline with its official link and license caveat, and the recommended sections.
5. For references: resolve with `references/scripts/resolve_metadata.py` (use `--in` for several references and `--items-out` to collect the verified ones), keep only `verified` ones, ask about `ambiguous` ones, exclude the rest; format the collected file with `references/scripts/format_reference.py` (add `--cross-check` for numeric styles); before delivering, run `references/scripts/validate_citations.py` with `--require-verified`. `references/workflow.md` has the exact commands.
6. For AI disclosure: ask what the AI was used for, then run `scripts/render_disclosure.py`. Present the statements together with `assertions_to_confirm` and ask the user to confirm them. Never fill a missing field. Never call a statement compliant or approved: say that it follows the policy snapshot of the given date and must be checked against the current policy.
7. Close with a short summary that says what was verified, what was not, and the snapshot date.

## Tools
| Tool | Purpose |
|---|---|
| `scripts/recommend.py` | Rule engine: standard, reporting guideline, sections, warnings, AI disclosure requirements |
| `scripts/render_disclosure.py` | AI-use statement builder driven by the policy registry (en and es) |
| `references/scripts/resolve_metadata.py` | Verify DOI, PMID or title against public registries |
| `references/scripts/format_reference.py` | Format references and documents with a CSL style |
| `references/scripts/order_references.py` | Order references by the style family |
| `references/scripts/validate_citations.py` | Check citations against the reference list |
| `references/scripts/check_et_al_rules.py` | Show the author-list truncation rules of a style |
| `references/scripts/abbreviate_journal.py` | Abbreviate journal titles when a data source exists |

Run `python <script> --help` for the arguments. Use `python scripts/recommend.py --list <kind>` to see valid values.

## Reading the output of recommend.py
- `status`: `ok`, `invalid_input` (use the suggestions) or `denied` (explain the denial).
- `reference_style.selection`: `user_choice`, `single_recommendation`, `needs_confirmation` (never pick; show `candidates` and ask) or `unknown`.
- `open_questions`: each has a `priority`. Ask blocking ones first; `ask_first` holds the first blocking question.
- `data_caveats` and each candidate's `meta.needs_review`: tell the user when a recommendation rests on low confidence or on data that still needs review. Policy notes also arrive in `data_caveats` and in the statement `notes`; pass them on, for example a policy that recommends disclosing even exempt uses.
- `data_snapshot`: report the data version and `snapshot_dates` (the date range of the policy and standards data) when the answer depends on a policy or a standard's edition. Per-item dates are in `meta.verified_on`.
- `allowed`: the standards the data accepts for the combination. It is not a ranking and not a recommendation; the recommendation is `chosen`, or the `candidates` when `selection` is `needs_confirmation`.
- `confidence` with a small `sample_n`: say how many journals the recommendation rests on; `high` from three journals is not strong evidence.

## When something goes wrong
Follow `router/fallback-rules.md`. When in doubt, ask or state the uncertainty; never guess.

## Known limitations
- Reference styles are chosen from small journal samples for many disciplines; check the `confidence` and `sample_n` fields.
- Not every standard has a bundled CSL file (for example APS, AMS, Bluebook and Harvard variants); the tools say so, and references cannot be formatted for those.
- Detailed structure guidance by document type and discipline is not available yet (see `structure/README.md`). The skill reports the sections, guidelines and reference style that its data supports.
- Policies and editions are a dated snapshot and can change; the user should confirm with the venue.

## File map
- `README.md`: overview, installation and quick start.
- `PRIVACY.md`: what data leaves the computer.
- `router/`: intake questions, decision tree, fallback rules.
- `disclosure/`: when to disclose, statement templates.
- `references/`: reference workflow and data sources.
- `examples/`: worked examples. `evals/`: scenarios to check the skill.
- `docs/es/`: Spanish documentation.
