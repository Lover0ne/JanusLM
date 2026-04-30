Check domain affinity of a document against a project tag.

Usage: /wiki-validate $ARGUMENTS

$ARGUMENTS should be the document path and tag, e.g. `raw/report.md project-alpha`

Run `python tools/validate_domain.py --doc <path> --tag <tag>` to score affinity.
Use `--json` for structured output, `--save` to persist the result.
