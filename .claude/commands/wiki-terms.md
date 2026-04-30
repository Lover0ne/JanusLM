Extract term frequencies from a document for blind review during ingest.

Usage: /wiki-terms $ARGUMENTS

$ARGUMENTS is the document path, e.g. `raw/report.md`

Run `python tools/extract_terms.py --doc <path>` to extract terms.
Use `--wiki <page>` to compare with an existing wiki source page,
or `--json` for structured output.
