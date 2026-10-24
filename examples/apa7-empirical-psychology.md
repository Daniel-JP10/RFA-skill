# Worked example: Empirical quantitative psychology (APA 7)

This example demonstrates how the assistant recommends reporting guidelines, document sections, and citation standards for an empirical quantitative psychology study, and formats references using pandoc.

## User request

"I am writing a quantitative empirical paper on cognitive behavioral therapy for an English-language psychology journal. What citation style and guidelines should I follow, and can you format my references?"

## Commands and outputs

### 1. Structural and style recommendation

<!-- rfa:run id=ex-apa7-recommend -->
```bash
python scripts/recommend.py --discipline psychology --document-type quantitative --language en
```

<!-- rfa:excerpt of=ex-apa7-recommend -->
```json
{
  "status": "ok",
  "reference_style": {
    "selection": "single_recommendation",
    "chosen": {
      "standard_id": "apa-7",
      "confidence": "high"
    }
  },
  "reporting": {
    "recommended": [
      "apa-jars"
    ]
  }
}
```

### 2. Reference formatting

<!-- rfa:run id=ex-apa7-format needs=pandoc -->
```bash
python references/scripts/format_reference.py --items references/tests/fixtures/items.csl.json --style apa-7
```

<!-- rfa:excerpt of=ex-apa7-format -->
```json
{
  "backend": "pandoc",
  "warnings": [
    {
      "code": "unverified_item",
      "id": "rivera2021a"
    }
  ]
}
```

## Assistant response

For a quantitative empirical psychology paper in English:

1. **Citation standard**: APA 7th edition is recommended with high confidence (`sample_n: 3`).
   - Official manual: https://apastyle.apa.org/products/publication-manual-7th-edition
2. **Reporting guideline**: APA JARS (Journal Article Reporting Standards for Quantitative Research) is recommended.
   - Official URL: https://apastyle.apa.org/jars
   - Note: APA JARS checklists are subject to copyright; link directly to the official APA checklist rather than reproducing it in full.
3. **Recommended sections**: Include a Data Availability Statement and Ethics Statements (institutional review board approval and informed consent).
4. **Reference formatting**: The example items are fictional test fixtures without verified provenance, so the tool flags each one with `unverified_item`. In real use, only references with status `verified` are formatted and delivered, and the answer ends with the data snapshot dates from `data_snapshot.snapshot_dates`.
