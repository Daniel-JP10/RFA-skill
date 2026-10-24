# RFA scholarly writing helper

A skill that helps structure scholarly documents, verify and format references, and write AI-use disclosures. It is built to avoid three things: invented sources, silent guesses, and hidden AI use.

## What you get
- A recommendation of the citation standard, reporting guideline and sections for a document, with confidence levels and review flags.
- Reference verification against public registries and formatting with CSL styles.
- Citation validation: every citation has a reference and every reference is cited.
- AI-use statements that follow a venue's policy, in English and Spanish.

## Quick start
Requirements: Python 3.10 or later and the packages in `references/requirements.txt`. Pandoc 3.9 or later is optional but recommended for reference formatting; install it with `pip install pypandoc_binary` or a system package.

```bash
python scripts/recommend.py --list disciplines
python scripts/recommend.py --discipline psychology --document-type quantitative --language en
```

See `SKILL.md` for the full workflow and `references/workflow.md` for the references pipeline.

## Supported styles
<!-- BEGIN styles-table -->
| ID | Display name | Edition | Official source | Verified on | Needs review |
|---|---|---|---|---|---|
| abnt-brasil | ABNT NBR 6023, 10520 and 14724 | NBR 6023:2025 (3rd ed., 22-Sep-2025; corrected version 2026); NBR 10520:2023 (2nd ed., 19-Jul-2023); NBR 14724:2024 (4th ed., 11-Dec-2024; in force since 11-Jan-2025) | - | 2026-10-19 | No |
| acm | ACM Reference Format | ACM Reference Format (web, updated 11-Jul-2023) | https://www.acm.org/publications/authors/reference-formatting | 2026-10-18 | No |
| acs | ACS Guide to Scholarly Communication | ACS Guide to Scholarly Communication (continuous digital edition; in 2020 it replaced the ACS Style Guide, 3rd ed., 2006) | https://pubs.acs.org/page/jacsat/submission/authors.html | 2026-10-19 | No |
| aip | AIP Publishing style | AIP Publishing Author Instructions (online) | https://publishing.aip.org/resources/researchers/author-instructions/ | 2026-10-19 | No |
| ama-11 | AMA Manual of Style, 11th edition | 11th | https://academic.oup.com/amamanualofstyle/pages/about | 2026-10-18 | No |
| ams | AMS Style Guide | AMS Style Guide: Journals (October 2017 revision) | https://www.ams.org/arc/styleguide/index.html | 2026-10-18 | No |
| apa-7 | APA Publication Manual, 7th edition | 7th | https://apastyle.apa.org/products/publication-manual-7th-edition | 2026-10-19 | No |
| aps | APS (Physical Review) style | APS Physical Review Style Guide | https://journals.aps.org/authors/references-physical-review-physical-review-letters | 2026-10-18 | No |
| apsa | APSA Style Manual | APSA Style Manual (2018 revision, 2023 update) | https://connect.apsanet.org/stylemanual/sample-page/about/ | 2026-10-18 | No |
| asa | ASA Style Guide | 7th (June 2022) | https://www.asanet.org/publications/journals/asa-style-guide/ | 2026-10-24 | No |
| bluebook | The Bluebook, 22nd edition | 22nd (published in late May 2025) | https://www.legalbluebook.com/ | 2026-10-19 | No |
| chicago-18 | The Chicago Manual of Style, 18th edition | 18th | https://www.chicagomanualofstyle.org/help-tools/what-s-new.html | 2026-10-19 | No |
| colombia-legal-hybrid | Colombian legal citation practice (not an official standard) | Documented practice without an official standard: APA 7 with an adaptation of the Bluebook, or Chicago notes plus the Bluebook | - | 2026-10-18 | Yes |
| cse | CSE Manual, 9th edition | 9th (The CSE Manual) | https://www.councilscienceeditors.org/cse-manual | 2026-10-19 | No |
| harvard | Harvard (institution-specific variants) | No single standard; main variant Cite Them Right (13th ed., 26-Jun-2025) | https://www.bloomsbury.com/uk/cite-them-right-9781350934252/ | 2026-10-19 | No |
| icontec-colombia | ICONTEC NTC 1486:2022 | NTC 1486:2022 (8th update; reapproved on 2024-12-04) | https://tienda.icontec.org/gp-documentacion-presentacion-de-trabajos-academicos-y-referencias-bibliograficas-ntc1486-2022.html | 2026-10-19 | No |
| ieee | IEEE Reference Guide | IEEE Editorial Style Manual for Authors and IEEE Reference Guide (online edition 2024/2025) | https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-the-text-of-your-article/ieee-editorial-style-manual/ | 2026-10-19 | Yes |
| institutional-overrides | Institution-specific rules | - | - | - | - |
| iso-690 | ISO 690:2021 | 4th (ISO 690:2021, June 2021) | https://www.une.org/encuentra-tu-norma/busca-tu-norma/norma?c=N0072646 | 2026-10-19 | No |
| mla-9 | MLA Handbook, 9th edition | 9th | https://style.mla.org/mla-handbook-ninth-edition/ | 2026-10-18 | No |
| oscola | OSCOLA, 5th edition | 5th (official PDF published online in March 2026; includes rule 3.7.13 on generative AI) | https://www.law.ox.ac.uk/oscola | 2026-10-19 | No |
| vancouver-nlm | Vancouver (ICMJE / NLM Citing Medicine) | ICMJE Recommendations (January 2026) + NLM Citing Medicine (2nd ed.) | https://www.icmje.org/news-and-editorials/updated_recommendations_jan2026.html | 2026-10-19 | No |
<!-- END styles-table -->

The table is generated from the data layer. Some standards have no bundled CSL file, so references cannot be formatted for them even though they can be recommended.

## Principles
- It never invents a source. The workflow excludes references that cannot be verified instead of completing them, and the final check `validate_citations.py --require-verified` turns any unverified reference into an error.
- When recommendations conflict, it shows the options and asks.
- It surfaces uncertainty: confidence, needs-review flags and snapshot dates.
- It helps you disclose AI use according to your venue's policy. It does not help conceal AI use or evade AI-text detectors.
- There is no telemetry. See `PRIVACY.md`.

## Limitations
The data is a dated snapshot. Several disciplines rest on small journal samples. Structure guidance by document type is not available yet. Always confirm requirements with your institution or journal.

## Development
Install the development dependencies with `pip install -r requirements-dev.txt`. Run it from the skill folder, where the file lives. It includes `pypandoc_binary`, which bundles pandoc 3.9, so all tests run. If you prefer a system pandoc, use version 3.9 or later: older versions were observed to format Vancouver names and in-text citations incorrectly, and the tools warn with `pandoc_version_untested`. Set `RFA_PANDOC` to choose a specific pandoc executable. If pandoc is not found, the tools say why and the fallback engine is used with warnings.

## Documentation
Spanish documentation is in `docs/es/`.

## Trademarks
APA, MLA, Chicago, IEEE, AMA, ACS, CSE, ICMJE, Crossref, NLM, PubMed and the other names of style guides, publishers and services mentioned in this skill belong to their respective owners. RFA is an independent project and is not affiliated with, sponsored by or endorsed by any of them. The skill gives paraphrased rules, links to official sources and its own examples; it does not reproduce the manuals.

## License
MIT. See `LICENSE`. The CSL style files in `references/csl/` keep their own license, CC BY-SA 3.0; see `references/csl/NOTICE.md`.
