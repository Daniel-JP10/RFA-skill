# AI-use statement templates

This document explains the statement templates provided by `scripts/render_disclosure.py` and provides worked examples for each statement type.

## Statement types

Depending on the venue's policy and placement rules, statements may be generated for three primary locations:

1. **Acknowledgments**: Used for general disclosures, dedicated "Declaration of Generative AI" sections, or back-matter notes.
2. **Methods**: Used when AI tools are utilized in study execution, data processing, code generation, or draft generation requiring explicit verification descriptions.
3. **Cover letter**: Used to notify journal editors of AI use during initial manuscript submission.

## Worked examples

Each example shows the command and an excerpt of its real output. The `rfa:run` markers make the documentation tests execute the commands and compare the excerpts.

### 1. Acknowledgments statement (Elsevier policy)

Command:
<!-- rfa:run id=tpl-acknowledgments -->
```bash
python scripts/render_disclosure.py --policy elsevier --kind language_editing --tool ExampleAI --version 1.0 --developer "Example Labs" --purpose "Grammar checking and readability improvement" --date 2026-10-21 --verification "Author reviewed and edited all suggestions"
```

Rendered output:
<!-- rfa:excerpt of=tpl-acknowledgments -->
```json
{
  "status": "ok",
  "statements": {
    "acknowledgments": {
      "text": "During the preparation of this work, the author(s) used ExampleAI (1.0, Example Labs) on 2026-10-21 for Grammar checking and readability improvement. The author(s) reviewed and edited the output and take(s) full responsibility for the content of this work."
    }
  },
  "source": {
    "policy": "elsevier",
    "policy_url": "https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals",
    "policy_date": "2026-06",
    "verified_on": "2026-10-24",
    "needs_review": false
  },
  "notes": [
    "The policy entry is a snapshot dated 2026-06 and verified on 2026-10-24; check the current text before submission.",
    "Policy note: Journal policy page; the previous URL is the policy for books. A research pass also reported exemptions for basic reference-manager functions without generative AI and for accessibility assistive technology; only the grammar, spelling and punctuation exemption was confirmed independently.",
    "The acknowledgments template is used as the general declaration text for dedicated declaration sections.",
    "Policies list acceptable locations; use the one(s) the venue's instructions require."
  ]
}
```

### 2. Methods statement (Springer Nature policy)

Command:
<!-- rfa:run id=tpl-methods -->
```bash
python scripts/render_disclosure.py --policy springer-nature --kind generative_content --tool ExampleAI --version 1.0 --developer "Example Labs" --purpose "Drafting introductory background paragraphs" --date 2026-10-21 --verification "Authors independently verified all factual assertions against primary sources" --statements methods
```

Rendered output:
<!-- rfa:excerpt of=tpl-methods -->
```json
{
  "status": "ok",
  "statements": {
    "methods": {
      "text": "ExampleAI (1.0, Example Labs) was used on 2026-10-21 for Drafting introductory background paragraphs. Verification of the output: Authors independently verified all factual assertions against primary sources."
    }
  },
  "source": {
    "policy": "springer-nature",
    "policy_url": "https://www.springernature.com/gp/policies/editorial-policies/ai-manuscript-preparation",
    "policy_date": "2026-01",
    "verified_on": "2026-10-24",
    "needs_review": false
  },
  "notes": [
    "The policy entry is a snapshot dated 2026-01 and verified on 2026-10-24; check the current text before submission.",
    "Policy note: The author guidance classifies even low-risk uses such as language editing as requiring a description of the use and confirmation of author accountability. The previous URL is guidance for editors. The author page shows no date; policy_date comes from an earlier reading.",
    "The acknowledgments template is used as the general declaration text for dedicated declaration sections.",
    "Policies list acceptable locations; use the one(s) the venue's instructions require."
  ]
}
```

### 3. Cover letter statement (ICMJE policy)

Command:
<!-- rfa:run id=tpl-cover-letter -->
```bash
python scripts/render_disclosure.py --policy icmje --kind generative_content --tool ExampleAI --version 1.0 --developer "Example Labs" --purpose "Assisting with initial draft translations" --date 2026-10-21 --verification "Authors verified translation accuracy" --statements cover_letter
```

Rendered output:
<!-- rfa:excerpt of=tpl-cover-letter -->
```json
{
  "status": "ok",
  "statements": {
    "cover_letter": {
      "text": "In preparing this manuscript, the author(s) used ExampleAI (1.0, Example Labs) for Assisting with initial draft translations. This use is disclosed in the acknowledgments section of the manuscript."
    }
  },
  "source": {
    "policy": "icmje",
    "policy_url": "https://www.icmje.org/recommendations/browse/artificial-intelligence/ai-use-by-authors.html",
    "policy_date": "2026-01",
    "verified_on": "2026-10-19",
    "needs_review": false
  },
  "notes": [
    "The policy entry is a snapshot dated 2026-01 and verified on 2026-10-19; check the current text before submission.",
    "Policies list acceptable locations; use the one(s) the venue's instructions require."
  ]
}
```

## Confirming assertions

Every generated statement includes an `assertions_to_confirm` array. The assistant must present these assertions to the author and request confirmation before finalizing the text:
- For example: confirming that the author took full responsibility for the content and reviewed the output.
- These assertions reflect requirements of the publishers' policies; the assistant must not skip them.

## Missing fields stop output

If a field that the policy and the statement type require is missing, the script stops with exit code 1 and status `missing_fields`. The required fields are `tool`, `version`, `developer` and `purpose`, plus `verification` when a methods statement is produced. The `required` value of a policy tells whether disclosure is needed: `true` (required), `false` (not required), `"conditional"` (depends on the use; read the policy notes and confirm with the user before omitting a statement) or `null` (the policy does not say).
```json
{
  "status": "missing_fields",
  "missing_fields": ["tool", "version", "developer", "purpose"]
}
```
The assistant must never guess or fabricate missing fields; it must ask the user to supply them.
