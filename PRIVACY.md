# RFA skill privacy notice

> Status: draft pending legal review. This is not legal advice.

## What it does NOT do
- It includes no telemetry, analytics or logging of what the user writes.
- It does not keep the content of documents or references after a run. During a run, the formatting tool writes the references, and in document mode the whole document, to a temporary folder so that pandoc can read them; that folder is deleted when the run ends. Content is saved permanently only when the user asks for an output file.
- It does not send the text of the document to any service.

## What data leaves the user's computer
Only the scripts in `references/` open network connections, and they send only the minimum data of each reference:

| Service | What is sent | Purpose |
|---|---|---|
| Crossref (api.crossref.org) | A DOI, or the title, author and year of a reference | Verify that the work exists and retrieve its metadata |
| doi.org and Crosscite (data.crosscite.org) | A DOI | Retrieve metadata of DOIs from other registration agencies (for example DataCite or Zenodo) |
| NCBI E-utilities (eutils.ncbi.nlm.nih.gov) | A PMID | Resolve a PMID to its DOI |
| OpenAlex (api.openalex.org) | Nothing in this version | Listed in the allowed hosts for a future search feature; that code path is disabled and makes no request |

## Optional environment variables
- `RFA_CONTACT_EMAIL`: if defined, it is sent to Crossref in the User-Agent header and as the `mailto` parameter, to use its identified access ("polite pool"). It is sent to no other host. It is the user's personal data: define it only if you agree.
- `NCBI_API_KEY`: the user's own NCBI key, sent only to NCBI. `OPENALEX_API_KEY` is reserved and not used in this version. Keys are only read from the environment and are never written to files, outputs or error messages.
- `RFA_JOURNAL_ABBR_FILE`: optional local path to a list of journal abbreviations.
- `RFA_PANDOC`: optional local path to the pandoc executable. It is used only to find pandoc on the computer.
- The HTTP library also honors the standard proxy and certificate variables of the system (for example `HTTPS_PROXY`, `NO_PROXY` and `REQUESTS_CA_BUNDLE`) and the user's netrc file. RFA does not set or send them.

## Outside our control
The agent or platform where the skill runs processes the user's content under its own privacy policies. RFA does not control that processing.
