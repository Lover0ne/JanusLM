#!/usr/bin/env python3
from __future__ import annotations

"""
JanusLM capability guide.

Contract:
  (no flags) → compact table to stdout (area, capability, 1 example)
  --detail   → extended table (all examples, underlying tool, flags)
  --json     → structured JSON
  --area X   → filter by area name (case-insensitive)

Inputs:  none (curated registry only)
Outputs: stdout only (never writes files)

If this script fails:
  - It has no external dependencies and no file reads — it cannot fail.
"""

import sys
import json
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout.reconfigure(encoding="utf-8")

CAPABILITIES = [
    {
        "area": "Ingest",
        "items": [
            {
                "capability": "Ingest a document",
                "tool": "ingest.py --scan/--add/--init/--done + /maintainer skill",
                "flags": "--scan, --add, --set-tag, --init, --archive, --validate, --done, --skip, --touch, --check-rejected",
                "examples": [
                    "ingest raw/report.md",
                    "ingest all",
                    "add this file to the knowledge base",
                    "add this document to the wiki",
                ],
            },
            {
                "capability": "Convert before ingest",
                "tool": "/converter skill (.staging/ scripts)",
                "flags": "",
                "examples": [
                    "convert this PDF to markdown",
                    "I have a Word file to ingest",
                    "/convert",
                ],
            },
            {
                "capability": "Check ingest queue",
                "tool": "ingest.py --status/--next",
                "flags": "--status, --next N",
                "examples": [
                    "what's in the queue?",
                    "show ingest status",
                    "anything pending?",
                ],
            },
            {
                "capability": "Domain validation",
                "tool": "validate_domain.py --doc --tag",
                "flags": "--doc PATH, --tag TAG, --json, --save",
                "examples": [
                    "does this document belong to project-alpha?",
                    "validate the domain",
                    "check domain affinity",
                ],
            },
            {
                "capability": "Extract terms (blind review)",
                "tool": "extract_terms.py --doc",
                "flags": "--doc DOC, --wiki WIKI, --json",
                "examples": [
                    "extract terms from this document",
                    "run a blind term review",
                    "what entities does this doc mention?",
                ],
            },
        ],
    },
    {
        "area": "Query",
        "items": [
            {
                "capability": "Ask a question",
                "tool": "wiki_search.py + /maintainer Query Workflow",
                "flags": "--tag, --json",
                "examples": [
                    "what do we know about RAG?",
                    "summarize project alpha",
                    "what do we know about OpenAI?",
                    "query: main themes across projects",
                ],
            },
            {
                "capability": "Search by backlinks",
                "tool": "wiki_search.py --backlinks",
                "flags": "--backlinks NAME, --json",
                "examples": [
                    "who references Pinecone?",
                    "which pages mention RAG?",
                    "find all pages linking to OpenAI",
                ],
            },
            {
                "capability": "Cross-project comparison",
                "tool": "/maintainer Query Workflow (cross-project axis)",
                "flags": "",
                "examples": [
                    "which projects use embeddings?",
                    "compare projects on RAG",
                    "what do project-alpha and project-beta have in common?",
                ],
            },
        ],
    },
    {
        "area": "Maintenance",
        "items": [
            {
                "capability": "Health check (structural)",
                "tool": "health.py",
                "flags": "--json, --save",
                "examples": [
                    "is the wiki healthy?",
                    "check wiki integrity",
                    "are there any wiki problems?",
                    "/wiki-health",
                ],
            },
            {
                "capability": "Heal (auto-fix problems)",
                "tool": "heal.py --detect/--next/--done/--skip",
                "flags": "--detect, --status, --next N, --done ID, --skip ID --reason",
                "examples": [
                    "heal the wiki",
                    "fix broken links",
                    "repair the wiki",
                    "/heal",
                ],
            },
            {
                "capability": "Statistics dashboard",
                "tool": "wiki_stats.py",
                "flags": "--json",
                "examples": [
                    "wiki stats",
                    "how many pages?",
                    "how many pages do we have?",
                    "/wiki-stats",
                ],
            },
        ],
    },
    {
        "area": "Organization",
        "items": [
            {
                "capability": "Index management",
                "tool": "wiki_index.py add/remove/update",
                "flags": "add --section --name --path --description, remove --path, update --path --description",
                "examples": [
                    "add OpenAI to the index",
                    "remove this entry from the index",
                    "update the index description for RAG",
                ],
            },
            {
                "capability": "List project tags",
                "tool": "ingest.py --tags",
                "flags": "--tags",
                "examples": [
                    "show all tags",
                    "what tags exist?",
                    "list project tags",
                ],
            },
            {
                "capability": "Rename a tag",
                "tool": "ingest.py --rename-tag OLD --tag NEW",
                "flags": "--rename-tag, --tag",
                "examples": [
                    "rename tag project-alpha to ai-research",
                    "rename the tag",
                    "change the tag name from X to Y",
                ],
            },
            {
                "capability": "Forget (delete from wiki)",
                "tool": "/forget skill + wiki_protect.py",
                "flags": "",
                "examples": [
                    "forget project-alpha",
                    "remove the OpenAI entity",
                    "delete the RAG concept",
                    "/forget",
                ],
            },
            {
                "capability": "Scaffold recovery",
                "tool": "scaffold.py --check/--fix",
                "flags": "--check, --fix, --reset-deps, --mark-deps, --reset-privacy-deps, --mark-privacy-deps",
                "examples": [
                    "fix project structure",
                    "something is missing",
                    "restore the structure",
                    "/scaffold",
                ],
            },
        ],
    },
    {
        "area": "Graph",
        "items": [
            {
                "capability": "Build knowledge graph",
                "tool": "build_graph.py",
                "flags": "--report, --save, --json, --tag",
                "examples": [
                    "build the knowledge graph",
                    "generate the graph",
                    "update the graph",
                    "/wiki-graph",
                ],
            },
            {
                "capability": "View interactive graph",
                "tool": "print_graph.py",
                "flags": "--open",
                "examples": [
                    "show me the graph",
                    "open the graph",
                    "open the graph visualization",
                ],
            },
            {
                "capability": "Graph analysis report",
                "tool": "build_graph.py --report",
                "flags": "--report, --save, --json",
                "examples": [
                    "graph analysis",
                    "show orphans and hubs",
                    "graph health analysis",
                ],
            },
            {
                "capability": "Filter graph by project",
                "tool": "build_graph.py --tag",
                "flags": "--tag TAG",
                "examples": [
                    "graph for project-alpha",
                    "graph for project castle",
                    "show me the graph for ai-strategy",
                ],
            },
        ],
    },
    {
        "area": "Privacy",
        "items": [
            {
                "capability": "Enable privacy mode",
                "tool": "privacy_filter.py --setup + wiki_protect.py",
                "flags": "--setup",
                "examples": [
                    "enable privacy mode",
                    "anonymize everything",
                    "turn on privacy",
                    "/privacy-mode",
                ],
            },
            {
                "capability": "Disable privacy mode",
                "tool": "wiki_protect.py --toggle can_anonymize_pii",
                "flags": "",
                "examples": [
                    "disable privacy mode",
                    "turn off privacy",
                    "turn off anonymization",
                ],
            },
            {
                "capability": "Check privacy status",
                "tool": "privacy_filter.py --status",
                "flags": "--status, --hook-check, --test",
                "examples": [
                    "is privacy mode on?",
                    "privacy status",
                    "check privacy status",
                ],
            },
            {
                "capability": "Anonymize a single file",
                "tool": "privacy_filter.py --process FILE",
                "flags": "--process FILE",
                "examples": [
                    "anonymize this file",
                    "filter personal data from this document",
                    "mask PII in raw/doc.md",
                ],
            },
        ],
    },
    {
        "area": "Protection",
        "items": [
            {
                "capability": "Check wiki protection",
                "tool": "wiki_protect.py --status",
                "flags": "--status",
                "examples": [
                    "is the wiki locked?",
                    "protection status",
                    "show protection status",
                ],
            },
            {
                "capability": "Toggle edit protection",
                "tool": "wiki_protect.py --toggle can_modify",
                "flags": "--toggle can_modify",
                "examples": [
                    "enable wiki modifications",
                    "lock the wiki",
                    "unlock the wiki",
                ],
            },
            {
                "capability": "Toggle delete protection",
                "tool": "wiki_protect.py --toggle can_forget",
                "flags": "--toggle can_forget",
                "examples": [
                    "enable deletions",
                    "lock forget",
                    "allow deletions",
                ],
            },
        ],
    },
    {
        "area": "History",
        "items": [
            {
                "capability": "Recent activity",
                "tool": "log_report.py / wiki/log.md",
                "flags": "--json, --summary, --type, --last N",
                "examples": [
                    "what was done recently?",
                    "show the log",
                    "show recent activity",
                    "what happened in the wiki?",
                ],
            },
            {
                "capability": "Filter by operation",
                "tool": "log_report.py --type",
                "flags": "--type ingest|heal|graph",
                "examples": [
                    "show all ingests",
                    "show recent heals",
                    "list graph rebuilds",
                ],
            },
            {
                "capability": "Heal queue status",
                "tool": "heal.py --status / log_report.py",
                "flags": "--status",
                "examples": [
                    "heal queue",
                    "what's pending to fix?",
                    "what's left to fix?",
                ],
            },
            {
                "capability": "Write log entry",
                "tool": "log_write.py",
                "flags": "--op OP, --title TITLE, --tag TAG, --detail DETAIL",
                "examples": [
                    "log this operation",
                    "write to the log",
                    "write a log entry for this ingest",
                ],
            },
        ],
    },
    {
        "area": "Setup",
        "items": [
            {
                "capability": "Install dependencies",
                "tool": "/janus-setup skill",
                "flags": "",
                "examples": [
                    "setup",
                    "install dependencies",
                    "install the dependencies",
                    "/setup",
                ],
            },
            {
                "capability": "Reset dependencies",
                "tool": "scaffold.py --reset-deps + /setup",
                "flags": "--reset-deps",
                "examples": [
                    "reinstall deps",
                    "force reinstall",
                    "reset all dependencies",
                ],
            },
        ],
    },
    {
        "area": "General",
        "items": [
            {
                "capability": "Generate files (reports, docs, spreadsheets)",
                "tool": "Agent writes to freespace/",
                "flags": "",
                "examples": [
                    "make a Word report",
                    "create a spreadsheet",
                    "create a presentation",
                    "generate a summary PDF",
                ],
            },
            {
                "capability": "Anything else",
                "tool": "General-purpose agent",
                "flags": "",
                "examples": [
                    "JanusLM is a general-purpose assistant -- just ask!",
                ],
            },
        ],
    },
]


def print_compact(areas: list[dict]):
    print("JanusLM — What I can do\n")
    for area in areas:
        print(f"  {area['area']}")
        for item in area["items"]:
            cap = item["capability"]
            ex = item["examples"][0]
            pad = max(1, 36 - len(cap))
            print(f"    {cap}{' ' * pad}\"{ex}\"")
        print()
    print("  Tip: use --detail for full examples and tools, --area <name> to filter")


def print_detail(areas: list[dict]):
    print("JanusLM — Full capability guide\n")
    for area in areas:
        print(f"{'=' * 60}")
        print(f"  {area['area']}")
        print(f"{'=' * 60}\n")
        for item in area["items"]:
            print(f"  {item['capability']}")
            print(f"    Tool:  {item['tool']}")
            if item["flags"]:
                print(f"    Flags: {item['flags']}")
            print(f"    Ask:")
            for ex in item["examples"]:
                print(f"      - \"{ex}\"")
            print()


def print_json(areas: list[dict]):
    flat = []
    for area in areas:
        for item in area["items"]:
            flat.append({
                "area": area["area"],
                "capability": item["capability"],
                "tool": item["tool"],
                "flags": item["flags"],
                "examples": item["examples"],
            })
    print(json.dumps({"capabilities": flat, "total": len(flat)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JanusLM capability guide")
    parser.add_argument("--detail", action="store_true", help="Show full examples and tools")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    parser.add_argument("--area", type=str, help="Filter by area name (case-insensitive)")
    args = parser.parse_args()

    data = CAPABILITIES
    if args.area:
        filtered = [a for a in data if a["area"].lower() == args.area.lower()]
        if not filtered:
            valid = ", ".join(a["area"] for a in data)
            print(f"Unknown area: '{args.area}'. Valid areas: {valid}", file=sys.stderr)
            sys.exit(1)
        data = filtered

    if args.json:
        print_json(data)
    elif args.detail:
        print_detail(data)
    else:
        print_compact(data)
