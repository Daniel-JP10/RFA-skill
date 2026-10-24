# Intake questions

This guide defines the ordered questions the assistant asks when inputs are missing to determine applicable standards, reporting guidelines, document sections, and disclosure requirements.

## Intake order

1. **Document type**: What kind of document are you writing? (e.g., empirical article, systematic review, academic essay, conference paper).
2. **Discipline**: What is the primary academic field or discipline? (e.g., psychology, medicine, computer-science, literature).
3. **Language**: What language and locale variant are you writing in? (e.g., en, es, es-CO).
4. **Mandated standard**: Does your university, department, or target journal require a specific citation standard? If so, which one?
5. **Study design**: For empirical medical, health, or behavioral research, what specific study design was used? (for example `rct`, `cohort`, `systematic-review`; run `python scripts/recommend.py --list study_designs` for all values).
6. **AI use and venue policy**: Did you use AI assistance during writing or research, and what was its role? What is the venue's policy key if known?
7. **Desired output**: What specific output do you need right now? (e.g., structural outline, reference formatting, citation validation, AI-use statement).

## How to offer options

When presenting choices, retrieve valid values from `scripts/recommend.py` using the `--list` flag:

```bash
python scripts/recommend.py --list disciplines
python scripts/recommend.py --list document_types
python scripts/recommend.py --list standards
python scripts/recommend.py --list study_designs
python scripts/recommend.py --list reporting_guidelines
python scripts/recommend.py --list policies
python scripts/recommend.py --list languages
```

## Intake rules

- **Ask only what is missing**: Do not ask about parameters the user has already provided or that can be directly inferred from context.
- **One blocking question at a time**: If multiple blocking fields are missing, ask the first blocking question (`ask_first` from `scripts/recommend.py`) before asking follow-ups.
- **Never ask for what the user already said**: Retain provided parameters across conversational turns.
- **Handle uncertainty without guessing**: If the user is unsure about a field (for example the study design or a variant), say which field is unknown, run `scripts/recommend.py` with what is known, and show the resulting open question. Never assume a value.
- **Ask informational questions once at the end**: Non-blocking or optional questions (such as AI-use details or specific journal abbreviations) should be gathered after establishing core recommendations.

## Questions and CLI arguments

| Order | Question | CLI argument | Example value |
|---|---|---|---|
| 1 | Document type | `--document-type` | `quantitative` |
| 2 | Academic discipline | `--discipline` | `psychology` |
| 3 | Document language | `--language` | `en` |
| 4 | Mandated citation standard | `--standard` | `apa-7` |
| 4b | Source of standard mandate | `--standard-source` | `institution` |
| 5 | Empirical study design | `--study-design` | `rct` |
| 6 | Nature of AI assistance | `--ai-use` | `language_editing` |
| 6b | Target venue policy | `--policy` | `elsevier` |
