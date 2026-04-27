#!/usr/bin/env python3
from __future__ import annotations

"""
Wiki KB statistics dashboard.

Contract:
  (no flags)  -> human-readable stats to stdout
  --json      -> structured JSON to stdout

Inputs:  wiki/**/*.md files, wiki/log.md
Outputs: stdout only (no files written)

If this script fails:
  - No wiki/ directory -> "Wiki directory not found", exit 1
  - No .md files -> valid state, returns all zeros
  - Malformed frontmatter -> page counted but type = "unknown"
"""

import re
import sys
import json
import argparse
from collections import Counter
from datetime import date

from shared import WIKI_DIR, LOG_FILE, read_file, all_wiki_pages, extract_tags


def extract_type(content: str) -> str:
    match = re.search(r'^type:\s*(\S+)', content, re.MULTILINE)
    return match.group(1).strip('"\'') if match else "unknown"


def parse_last_op(log_content: str, op: str) -> str | None:
    matches = re.findall(
        rf'^## \[(\d{{4}}-\d{{2}}-\d{{2}})\] {op} \|',
        log_content,
        re.MULTILINE,
    )
    return matches[0] if matches else None


def compute_stats() -> dict:
    if not WIKI_DIR.exists():
        print("Wiki directory not found", file=sys.stderr)
        sys.exit(1)

    pages = all_wiki_pages()

    type_counts: Counter = Counter()
    tag_counts: Counter = Counter()
    total_links = 0
    page_stems = {p.stem.lower() for p in pages}
    outbound: dict[str, int] = {}
    inbound_set: set[str] = set()

    for p in pages:
        content = read_file(p)
        type_counts[extract_type(content)] += 1

        for t in extract_tags(content):
            tag_counts[t] += 1

        links = re.findall(r'\[\[([^\]]+)\]\]', content)
        key = p.stem.lower()
        valid_links = [
            link for link in links
            if link.lower() in page_stems and link.lower() != key
        ]
        outbound[key] = len(valid_links)
        total_links += len(valid_links)
        for link in valid_links:
            inbound_set.add(link.lower())

    orphan_count = sum(
        1 for p in pages
        if outbound.get(p.stem.lower(), 0) == 0
        and p.stem.lower() not in inbound_set
    )

    link_density = total_links / len(pages) if pages else 0.0
    log_content = read_file(LOG_FILE)

    return {
        "date": date.today().isoformat(),
        "total_pages": len(pages),
        "by_type": dict(type_counts.most_common()),
        "by_tag": dict(tag_counts.most_common()),
        "link_density": round(link_density, 2),
        "orphan_count": orphan_count,
        "last_ingest": parse_last_op(log_content, "ingest"),
        "last_heal": parse_last_op(log_content, "heal"),
    }


def format_stats(stats: dict) -> str:
    lines = [
        f"# Wiki Stats — {stats['date']}",
        "",
        f"**{stats['total_pages']}** pages total",
        "",
        "## By Type",
    ]
    if stats["by_type"]:
        for t, c in stats["by_type"].items():
            lines.append(f"  {t}: {c}")
    else:
        lines.append("  (no pages)")
    lines.append("")

    lines.append("## By Project Tag")
    if stats["by_tag"]:
        for t, c in stats["by_tag"].items():
            lines.append(f"  {t}: {c}")
    else:
        lines.append("  (no tags)")
    lines.append("")

    lines.append("## Metrics")
    lines.append(f"  Link density: {stats['link_density']} wikilinks/page")
    lines.append(f"  Orphan pages: {stats['orphan_count']}")
    lines.append(f"  Last ingest: {stats['last_ingest'] or 'never'}")
    lines.append(f"  Last heal: {stats['last_heal'] or 'never'}")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Wiki KB statistics dashboard"
    )
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of human-readable")
    args = parser.parse_args()

    stats = compute_stats()
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(format_stats(stats))
