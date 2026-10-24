# Skill data layer

`rfa_data.json` is generated from the maintainers' source files and published here as is. Do not edit it by hand; report an error through an issue instead. The file is deterministic: sorted keys, two-space indentation, UTF-8, LF line endings and one trailing newline. The tests that compare it with its sources run only in the maintainers' repository and are skipped in a standalone copy of the skill.

Each policy and standard entry carries its own provenance in `verified_on`, `verified_by` and `needs_review`. The `verified_by` values `research_agent` and `orchestrator_search` mean automated, AI-assisted checks against the official pages; neither replaces human review.

## Top-level keys

| Key | Content |
|---|---|
| `meta` | `schema_version` (1), `rfa_version`, `core_version`, `source_hashes` (path relative to the repository root -> SHA-256 of every input file; line endings are normalized to LF before hashing, except `.csl` files, which are hashed byte for byte), `snapshot_dates` (`policy_registry` and `standards_meta`, each a `min`/`max` range of `verified_on`), `enums` (`ai_use_kind`, `writing_assistance`, `effects`). |
| `disciplines` | Discipline leaves keyed by id: `id`, `area`, `display_name`. |
| `document_types` | Document types keyed by id: `id`, `group`, `display_name`. |
| `standards` | Citation standards keyed by id: `id`, `display_name`, `family`, `variants`, `csl_style_keys` (keys of `STYLE_MAP` that point to the standard; empty when no CSL style is bundled), `kind`, and from `_meta.yaml`: `edition`, `year`, `official_source`, `additional_sources` (always a list), `verification`, `verified_by`, `needs_review`, `verified_on`, `notes` (null when the standard has no metadata file, as for `institutional-overrides`). |
| `defaults` | The 28 `defaults_by_discipline` entries of the compatibility matrix, unchanged, plus `display_name`. Read `confidence`, `evidence` and `sample_n` before relying on a default. |
| `rules` | The compatibility-matrix rules, unchanged (`id`, `when`, `effect`, `then`, `confidence`, `reason`). |
| `invariants` | The compatibility-matrix invariants, unchanged. |
| `precedence` | The content of `precedence.yaml`, unchanged. |
| `study_designs` | The manifest `study_designs` map, unchanged (`reporting`, optional `protocol_reporting` and `note`). |
| `protocol_document_types` | Document types that describe a planned study (from the manifest): `trial-protocol`, `registered-report`, `research-proposal`. For these, invariant INV-01 uses the study design's `protocol_reporting` when it is not empty, and `reporting` otherwise. |
| `reporting_guidelines` | Guidelines keyed by id: `id`, `version`, `year`, `official_url`, `license_claimed`, `redistribution_claimed`, `needs_review`, `note`, `verified_on`, `study_designs` (designs that list the guideline). License data are claims, not legal advice. |
| `ai_policies` | The policy-registry entries keyed by registry key, unchanged. They are a dated snapshot: check `policy_date`, `verified_on` and `needs_review`. |
| `languages` | `languages`, `regions` and `variants_planned` from the manifest. |

## Consumers

- `rfa-skill/scripts/recommend.py` (standard, reporting guideline, sections, warnings). Each
  item of `open_questions` has `field`, `why`, `priority` (`blocking` or `informational`), and
  optionally `rules` (ids of the rules the answer decides) and `options`. Blocking questions
  come first; the top-level `ask_first` is the text of the first blocking question, or null.
- `rfa-skill/scripts/render_disclosure.py` (AI-use statements; also reads
  `rfa-skill/disclosure/templates.json`). The optional `statements` parameter (CLI:
  `--statements acknowledgments,methods`) limits the output to the requested statement types;
  `verification` is then required only when `methods` is requested, and the output echoes the
  request in `statements_requested`.
