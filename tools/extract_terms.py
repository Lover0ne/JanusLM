#!/usr/bin/env python3
from __future__ import annotations

"""
Term frequency extraction from a document.

Contract:
  --doc PATH             -> read document, tokenize, count all words.
  --wiki PATH            -> read wiki source page, extract [[wikilinks]]
                            as already_linked list. Optional: if omitted
                            or file not found, already_linked is empty.
  --json                 -> output machine-readable JSON to stdout.
  (no --json)            -> output human-readable frequency table.

Inputs:  document file (--doc), optionally wiki source page (--wiki)
Outputs: stdout (JSON or table)

No filtering, no stopwords, no classification. The agent decides what
is noise and what is relevant. This tool provides raw frequency data.

If this script fails:
  - Document not found -> error message
  - Wiki page not found -> already_linked is empty (not an error)
"""

import re
import sys
import json
import argparse
from collections import Counter
from pathlib import Path

from shared import REPO_ROOT, read_file, strip_frontmatter


def extract_wikilinks(content: str) -> list[str]:
    return re.findall(r'\[\[([^\]]+)\]\]', content)


def extract_terms(doc_path: Path, wiki_path: Path | None) -> dict:
    doc_content = read_file(doc_path)
    doc_text = strip_frontmatter(doc_content)

    if not doc_text.strip():
        return {
            "document": str(doc_path),
            "error": "Document is empty",
            "terms": [],
            "already_linked": [],
            "total_unique_terms": 0,
        }

    tokens = re.findall(r'\b\w+\b', doc_text)
    counts = Counter(tokens)
    terms = [{"term": term, "count": count} for term, count in counts.most_common()]

    already_linked: list[str] = []
    if wiki_path:
        wiki_content = read_file(wiki_path)
        if wiki_content:
            already_linked = extract_wikilinks(wiki_content)

    return {
        "document": str(doc_path),
        "total_unique_terms": len(counts),
        "terms": terms,
        "already_linked": already_linked,
    }


def format_table(result: dict) -> str:
    if result.get("error"):
        return f"Error: {result['error']}"

    lines = [
        f"Document: {result['document']}",
        f"Unique terms: {result['total_unique_terms']}",
        f"Already linked: {', '.join(result['already_linked']) or '(none)'}",
        "",
        f"{'Term':<30} {'Count':>5}",
        f"{'-'*30} {'-'*5}",
    ]
    for entry in result["terms"]:
        lines.append(f"{entry['term']:<30} {entry['count']:>5}")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract term frequencies from a document"
    )
    parser.add_argument("--doc", required=True, help="Path to the document to analyze")
    parser.add_argument("--wiki", default=None, help="Path to the wiki source page (for already_linked)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    doc_path = Path(args.doc)
    if not doc_path.is_absolute():
        doc_path = REPO_ROOT / args.doc

    if not doc_path.exists():
        print(json.dumps({"error": f"Document not found: {args.doc}"}), file=sys.stderr)
        sys.exit(1)

    wiki_path = None
    if args.wiki:
        wiki_path = Path(args.wiki)
        if not wiki_path.is_absolute():
            wiki_path = REPO_ROOT / args.wiki

    result = extract_terms(doc_path, wiki_path)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_table(result))
