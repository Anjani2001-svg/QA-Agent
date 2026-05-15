# PDF/E-book Marketing QA Agent

`qa_agent.py` analyses an uploaded PDF/e-book and generates:

- `qa_report.json` (structured schema-like output)
- `qa_report.md` (human-readable report)

## Features

- PDF text parsing by page
- Heading and basic section extraction
- Table of contents detection and mismatch checking
- Repetition/duplicate paragraph detection
- UK English spelling checks for common US variants
- Readability and long-sentence checks
- CTA and link detection
- Legal/compliance language risk flagging
- Image presence signal checks
- Category-by-category QA rollup across 26 required categories

## Install

```bash
pip install pypdf
```

## Usage

```bash
python qa_agent.py /path/to/ebook.pdf --json-out qa_report.json --md-out qa_report.md
```

## Notes

- Where automated verification is limited (for example alt text/tag tree checks, or external fact-checking), the report marks items as needing verification/manual review.
- The report uses UK English wording and severity labels: Critical, Major, Minor, Suggestion.
