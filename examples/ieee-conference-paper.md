# Worked example: Computer science conference paper (IEEE)

This example illustrates the assistant's recommendation for a computer science conference paper, noting the medium confidence rating and the need to verify conference-specific instructions.

## User request

"I am submitting a paper to an IEEE/ACM computer science conference. Which citation style should I format my paper in?"

## Commands and outputs

<!-- rfa:run id=ex-ieee-recommend -->
```bash
python scripts/recommend.py --discipline computer-science --document-type conference-paper --language en
```

<!-- rfa:excerpt of=ex-ieee-recommend -->
```json
{
  "status": "ok",
  "reference_style": {
    "selection": "single_recommendation",
    "chosen": {
      "standard_id": "ieee",
      "confidence": "medium"
    },
    "allowed": [
      "ieee",
      "acm",
      "apa-7"
    ]
  }
}
```

## Assistant response

For a computer science conference paper:

1. **Citation standard**: IEEE style is recommended as the discipline default.
   - Official source: IEEE Editorial Style Manual for Authors and IEEE Reference Guide.
   - Confidence: **Medium**. In the sample dataset (`sample_n: 3`), IEEE and ACM are equally common, and some engineering publications accept APA 7.
2. **Review caveat**: The metadata for IEEE is flagged as needing review, and conference proceedings frequently supply their own author kits (such as ACM or IEEE LaTeX templates).
3. **Actionable guidance**: Confirm whether the conference proceedings specifically require the IEEE or ACM template.
