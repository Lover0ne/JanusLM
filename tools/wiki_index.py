"""
Deterministic index manager for wiki/index.md.

All mutations to wiki/index.md MUST go through this tool.
The agent must NEVER edit wiki/index.md directly.

Subcommands:
  add    --section SECTION --name NAME --path PATH --description DESC
         Insert a new entry under ## SECTION. Idempotent: no-op if path exists.
  remove --path PATH
         Remove the entry matching PATH. Idempotent: no-op if not found.
  update --path PATH --description DESC
         Replace the description of an existing entry. Error if not found.

Sections: Sources, Entities, Concepts

Output: JSON to stdout with action result.

Inputs:  wiki/index.md
Outputs: wiki/index.md (mutated), stdout JSON

If this script fails:
  - FileNotFoundError → wiki/index.md must exist; run scaffold.py --fix
  - Section not found → typo in --section; valid values: Sources, Entities, Concepts
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shared import read_file, WIKI_DIR

INDEX_FILE = WIKI_DIR / "index.md"
VALID_SECTIONS = {"Sources", "Entities", "Concepts"}
ENTRY_RE = re.compile(r'-\s*\[.*?\]\((.+?)\)\s*[—–-]\s*(.*)')


def parse_entries(text: str) -> list[dict]:
    """Parse all index entries, returning list of {line_idx, path, description, raw}."""
    entries = []
    for i, line in enumerate(text.split("\n")):
        m = ENTRY_RE.match(line.strip())
        if m:
            entries.append({
                "line_idx": i,
                "path": m.group(1).strip(),
                "description": m.group(2).strip(),
                "raw": line,
            })
    return entries


def find_entry(text: str, path: str) -> dict | None:
    for e in parse_entries(text):
        if e["path"] == path:
            return e
    return None


def cmd_add(section: str, name: str, path: str, description: str):
    if section not in VALID_SECTIONS:
        print(json.dumps({"error": f"Invalid section: {section}. Valid: {', '.join(sorted(VALID_SECTIONS))}"}), file=sys.stderr)
        sys.exit(1)

    text = read_file(INDEX_FILE)
    if not text:
        print(json.dumps({"error": "wiki/index.md not found or empty. Run: python tools/scaffold.py --fix"}), file=sys.stderr)
        sys.exit(1)

    existing = find_entry(text, path)
    if existing:
        print(json.dumps({"action": "add", "status": "noop", "path": path, "reason": "entry already exists"}))
        return

    entry = f"- [{name}]({path}) — {description}" if description else f"- [{name}]({path}) —"
    header = f"## {section}"
    lines = text.split("\n")

    insert_at = None
    for i, line in enumerate(lines):
        if line.strip() == header:
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            while j > i + 1 and not lines[j - 1].strip():
                j -= 1
            insert_at = j
            break

    if insert_at is None:
        print(json.dumps({"error": f"Section '## {section}' not found in index.md"}), file=sys.stderr)
        sys.exit(1)

    lines.insert(insert_at, entry)
    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"action": "add", "status": "ok", "section": section, "path": path, "name": name, "description": description}))


def cmd_remove(path: str):
    text = read_file(INDEX_FILE)
    if not text:
        print(json.dumps({"error": "wiki/index.md not found or empty"}), file=sys.stderr)
        sys.exit(1)

    existing = find_entry(text, path)
    if not existing:
        print(json.dumps({"action": "remove", "status": "noop", "path": path, "reason": "entry not found"}))
        return

    lines = text.split("\n")
    del lines[existing["line_idx"]]
    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"action": "remove", "status": "ok", "path": path}))


def cmd_update(path: str, description: str):
    text = read_file(INDEX_FILE)
    if not text:
        print(json.dumps({"error": "wiki/index.md not found or empty"}), file=sys.stderr)
        sys.exit(1)

    existing = find_entry(text, path)
    if not existing:
        print(json.dumps({"error": f"Entry not found for path: {path}. Use 'add' to create it first."}), file=sys.stderr)
        sys.exit(1)

    old_line = existing["raw"]
    name_match = re.match(r'-\s*\[(.+?)\]\((.+?)\)', old_line)
    if not name_match:
        print(json.dumps({"error": f"Could not parse entry line: {old_line}"}), file=sys.stderr)
        sys.exit(1)

    display_name = name_match.group(1)
    new_line = f"- [{display_name}]({path}) — {description}"

    lines = text.split("\n")
    lines[existing["line_idx"]] = new_line
    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"action": "update", "status": "ok", "path": path, "description": description}))


def main():
    parser = argparse.ArgumentParser(description="Deterministic wiki/index.md manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add a new entry to index.md")
    p_add.add_argument("--section", required=True, choices=sorted(VALID_SECTIONS), help="Section header (Sources, Entities, Concepts)")
    p_add.add_argument("--name", required=True, help="Display name for the entry")
    p_add.add_argument("--path", required=True, help="Relative path from wiki/ (e.g. entities/OpenAI.md)")
    p_add.add_argument("--description", default="", help="One-line description after the dash")

    p_remove = sub.add_parser("remove", help="Remove an entry from index.md")
    p_remove.add_argument("--path", required=True, help="Relative path of the entry to remove")

    p_update = sub.add_parser("update", help="Update description of an existing entry")
    p_update.add_argument("--path", required=True, help="Relative path of the entry to update")
    p_update.add_argument("--description", required=True, help="New one-line description")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.section, args.name, args.path, args.description)
    elif args.command == "remove":
        cmd_remove(args.path)
    elif args.command == "update":
        cmd_update(args.path, args.description)


if __name__ == "__main__":
    main()
