#!/usr/bin/env python3
from __future__ import annotations

"""
Centralized log writer for wiki operations.

Contract:
  --op <op> --title <title>  -> prepends formatted entry to wiki/log.md
  Validates op against allowed list. Rejects unknown ops with error.

  Valid ops (agent-driven): ingest, lint, health, query, forget, setup
  Ops NOT handled here: heal (heal.py), graph/report (build_graph.py)

Inputs:  wiki/log.md (existing)
Outputs: wiki/log.md (prepends entry), stdout (JSON confirmation)

Log entry format:
  ## [YYYY-MM-DD] <op> | <title>[ | <tag>][ | <detail>]

Fields:
  YYYY-MM-DD  Date of operation (ISO 8601, auto-generated)
  op          Operation type — what happened
  title       Brief human-readable description of what was done
  tag         Project tag involved (optional)
  detail      Additional operation-specific info (optional)

Writers of log.md:
  log_write.py  -> agent ops (ingest, lint, health, query, forget, setup)
  heal.py       -> heal ops (automatic in mark_done())
  build_graph.py -> graph/report ops (automatic in build_graph())
  Agent direct  -> NEVER. The agent must NOT write to log.md directly.

If this script fails:
  - wiki/log.md not found -> creates it
  - invalid op -> prints error with valid ops list, exit 1
  - encoding error -> verify log.md is UTF-8
"""

import sys
import json
import argparse
from datetime import date

from shared import append_log_raw

VALID_OPS = {"ingest", "lint", "health", "forget", "setup", "convert"}


def write_log(op: str, title: str, tag: str | None = None, detail: str | None = None):
    if op not in VALID_OPS:
        print(json.dumps({
            "error": f"Invalid op '{op}'",
            "valid_ops": sorted(VALID_OPS),
        }, indent=2), file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    parts = [f"## [{today}] {op} | {title}"]
    if tag:
        parts.append(tag)
    if detail:
        parts.append(detail)

    entry = " | ".join(parts)
    append_log_raw(entry)

    print(json.dumps({
        "action": "log_write",
        "op": op,
        "title": title,
        "tag": tag,
        "detail": detail,
        "date": today,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Centralized wiki log writer"
    )
    parser.add_argument("--op", required=True,
                        help=f"Operation type: {', '.join(sorted(VALID_OPS))}")
    parser.add_argument("--title", required=True,
                        help="What was done (brief, human-readable)")
    parser.add_argument("--tag",
                        help="Project tag involved (optional)")
    parser.add_argument("--detail",
                        help="Additional info (optional)")
    args = parser.parse_args()

    write_log(args.op, args.title, args.tag, args.detail)
