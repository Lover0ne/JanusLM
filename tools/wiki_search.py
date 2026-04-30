#!/usr/bin/env python3
from __future__ import annotations

"""
Search wiki pages by terms provided via stdin, or find backlinks.

Contract:
  stdin                  -> one search term per line (empty lines ignored)
  --tag TAG              -> filter results to pages with this tag
  --json                 -> output machine-readable JSON to stdout
  (no --json)            -> output human-readable table
  --backlinks NAME       -> find all pages with [[NAME]] wikilink
                           (no stdin needed, ignores --tag)

Inputs:  search terms (stdin) OR backlink target (--backlinks),
         optionally a tag filter (--tag, term search only)
Outputs: stdout (JSON array or table) — one entry per matching page,
         sorted by number of distinct matched terms (descending).
         For backlinks: sorted alphabetically by page path.

Each result includes: page path, title, description (from index.md),
type, tags, matched_terms, match_count, wikilinks.
"""

import re
import sys
import json
import argparse
from pathlib import Path

from shared import read_file, REPO_ROOT, WIKI_DIR, extract_tags, WIKI_META_FILES


INDEX_FILE = WIKI_DIR / "index.md"

SUBDIRS = {
    "sources": "source",
    "entities": "entity",
    "concepts": "concept",
}


def extract_wikilinks(content: str) -> list[str]:
    return re.findall(r'\[\[([^\]]+)\]\]', content)


def parse_index_descriptions() -> dict[str, str]:
    """Parse index.md and return {relative_path: description}."""
    content = read_file(INDEX_FILE)
    descriptions: dict[str, str] = {}
    for match in re.finditer(r'-\s*\[.*?\]\((.+?)\)\s*[—–-]\s*(.*)', content):
        path = match.group(1).strip()
        desc = match.group(2).strip()
        descriptions[path] = desc
    return descriptions


def extract_title(content: str, fallback: str) -> str:
    match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def search_wiki(terms: list[str], tag_filter: str | None) -> list[dict]:
    descriptions = parse_index_descriptions()
    results: list[dict] = []

    for subdir_name, page_type in SUBDIRS.items():
        subdir = WIKI_DIR / subdir_name
        if not subdir.exists():
            continue
        for page_path in subdir.glob("*.md"):
            if page_path.name in WIKI_META_FILES:
                continue

            content = read_file(page_path)
            if not content.strip():
                continue

            tags = extract_tags(content)
            if tag_filter and tag_filter not in tags:
                continue

            title = extract_title(content, page_path.stem)
            rel_path = f"{subdir_name}/{page_path.name}"

            matched: list[str] = []
            content_lower = content.lower()
            for term in terms:
                if re.search(re.escape(term.lower()), content_lower):
                    matched.append(term)

            if not matched:
                continue

            wikilinks = extract_wikilinks(content)
            description = descriptions.get(rel_path, "")

            results.append({
                "page": f"wiki/{rel_path}",
                "title": title,
                "description": description,
                "type": page_type,
                "tags": tags,
                "matched_terms": matched,
                "match_count": len(matched),
                "wikilinks": wikilinks,
            })

    results.sort(key=lambda r: r["match_count"], reverse=True)
    return results


def find_backlinks(name: str) -> list[dict]:
    descriptions = parse_index_descriptions()
    pattern = f"[[{name}]]"
    results: list[dict] = []

    for subdir_name, page_type in SUBDIRS.items():
        subdir = WIKI_DIR / subdir_name
        if not subdir.exists():
            continue
        for page_path in subdir.glob("*.md"):
            if page_path.name in WIKI_META_FILES:
                continue
            content = read_file(page_path)
            if pattern not in content:
                continue

            title = extract_title(content, page_path.stem)
            rel_path = f"{subdir_name}/{page_path.name}"
            results.append({
                "page": f"wiki/{rel_path}",
                "title": title,
                "type": page_type,
                "tags": extract_tags(content),
            })

    results.sort(key=lambda r: r["page"])
    return results


def format_table(results: list[dict]) -> str:
    if not results:
        return "No matching pages found."

    lines = [
        f"{'Page':<40} {'Title':<25} {'Type':<8} {'Matches':>7}  Matched Terms",
        f"{'-'*40} {'-'*25} {'-'*8} {'-'*7}  {'-'*30}",
    ]
    for r in results:
        terms_str = ", ".join(r["matched_terms"])
        lines.append(
            f"{r['page']:<40} {r['title']:<25} {r['type']:<8} {r['match_count']:>7}  {terms_str}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search wiki pages by terms from stdin")
    parser.add_argument("--tag", default=None, help="Filter results to pages with this tag")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--backlinks", metavar="NAME", default=None,
                        help="Find all pages with [[NAME]] wikilink (no stdin needed)")
    args = parser.parse_args()

    if args.backlinks:
        results = find_backlinks(args.backlinks)
        output = {"action": "backlinks", "target": args.backlinks,
                  "count": len(results), "pages": results}
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            if not results:
                print(f"No pages link to [[{args.backlinks}]].")
            else:
                print(f"Pages linking to [[{args.backlinks}]] ({len(results)}):\n")
                for r in results:
                    print(f"  {r['page']:<45} {r['title']:<25} {r['type']}")
        sys.exit(0)

    terms = [line.strip() for line in sys.stdin if line.strip()]

    if not terms:
        if args.json:
            print(json.dumps({"error": "No search terms provided via stdin"}))
        else:
            print("Error: No search terms provided via stdin.")
        sys.exit(1)

    results = search_wiki(terms, args.tag)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(format_table(results))
