# Worked example: Systematic review in medicine (Vancouver)

This example demonstrates how the assistant handles a medical systematic review, identifying the required PRISMA 2020 reporting guideline and formatting references in Vancouver (NLM) style.

## User request

"I am conducting a systematic review on cardiovascular outcomes for a medical journal. Which reporting guideline is required and what citation style should I prepare?"

## Commands and outputs

### 1. Guideline and style recommendation

<!-- rfa:run id=ex-vancouver-recommend -->
```bash
python scripts/recommend.py --discipline medicine --document-type systematic-review --language en
```

<!-- rfa:excerpt of=ex-vancouver-recommend -->
```json
{
  "status": "ok",
  "reference_style": {
    "selection": "single_recommendation",
    "chosen": {
      "standard_id": "vancouver-nlm",
      "confidence": "high"
    }
  },
  "reporting": {
    "required": [
      "prisma-2020"
    ]
  }
}
```

### 2. Reference formatting

<!-- rfa:run id=ex-vancouver-format needs=pandoc -->
```bash
python references/scripts/format_reference.py --items references/tests/fixtures/items.csl.json --style vancouver-nlm --cross-check
```

<!-- rfa:excerpt of=ex-vancouver-format -->
```json
{
  "backend": "pandoc",
  "warnings": [
    {
      "code": "backend_disagreement",
      "id": "silva2020"
    },
    {
      "code": "backend_disagreement",
      "id": "many2018"
    }
  ]
}
```

## Assistant response

For a medical systematic review:

1. **Required reporting guideline**: PRISMA 2020 (Preferred Reporting Items for Systematic Reviews and Meta-Analyses) is required.
   - Official URL: https://www.bmj.com/content/372/bmj.n71
   - License and usage caveat: PRISMA 2020 is distributed under CC BY 4.0; license claims have not been independently verified, so provide direct links to the official BMJ specification and checklist.
2. **Citation standard**: Vancouver (NLM / ICMJE) is recommended with high confidence.
   - Official source: ICMJE Recommendations and NLM Citing Medicine (2nd ed.).
3. **Reference formatting**: The references were formatted in numeric Vancouver style with pandoc and cross-checked with citeproc-py. The cross-check flags two entries: for the edited chapter (`silva2020`) pandoc prints "In, editorDuarte P." where citeproc-py prints "In: Duarte P, editor."; for `many2018` citeproc-py prints the page range "1–0" instead of "1–10". Show both renderings and ask the user to check them against NLM Citing Medicine. The example items are fictional test fixtures without verified provenance, so they are also flagged with `unverified_item`; in real use only `verified` references are delivered.
