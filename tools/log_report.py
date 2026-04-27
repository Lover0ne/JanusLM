#!/usr/bin/env python3
from __future__ import annotations

"""
Wiki operations log reader and heal queue reporter.

Contract:
  --json              → full JSON report (log stats + heal queue state) to stdout
  --summary           → human-readable markdown report to stdout (default)
  --type TYPE         → filter log by operation type (ingest, heal, graph, lint)
  --last N            → only include last N days of log entries

Inputs:  wiki/log.md (operation history), heal_queue.json (current heal state)
Outputs: stdout (JSON or markdown)

If this script fails:
  - wiki/log.md missing → not an error, returns empty log section
  - heal_queue.json missing → not an error, returns empty queue section
  - Malformed log entries → skipped silently (regex doesn't match)
  - JSON decode error on heal_queue.json → file corrupted, reset to empty:
    {"items": [], "created": null, "stats": {"total": 0, "completed": 0, "skipped": 0}}
"""

import re
import json
import argparse
from pathlib import Path
from datetime import date, timedelta
from collections import Counter

REPO_ROOT = Path(__file__).parent.parent
LOG_FILE = REPO_ROOT / "wiki" / "log.md"
QUEUE_FILE = REPO_ROOT / "heal_queue.json"

LOG_ENTRY_RE = re.compile(
    r'^## \[(\d{4}-\d{2}-\d{2})\] (\w+) \| (.+)$',
    re.MULTILINE,
)


def parse_log() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    content = LOG_FILE.read_text(encoding="utf-8")
    entries = []
    for match in LOG_ENTRY_RE.finditer(content):
        entries.append({
            "date": match.group(1),
            "type": match.group(2),
            "title": match.group(3).strip(),
        })
    return entries


def read_queue() -> dict:
    if not QUEUE_FILE.exists():
        return {"items": [], "created": None, "stats": {"total": 0, "completed": 0, "skipped": 0}}
    return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))


def build_report(type_filter: str | None = None, last_days: int | None = None) -> dict:
    entries = parse_log()

    if last_days is not None:
        cutoff = (date.today() - timedelta(days=last_days)).isoformat()
        entries = [e for e in entries if e["date"] >= cutoff]

    if type_filter:
        filtered = [e for e in entries if e["type"] == type_filter]
    else:
        filtered = entries

    by_type = dict(Counter(e["type"] for e in filtered))

    last_by_type: dict[str, str] = {}
    for e in filtered:
        if e["type"] not in last_by_type or e["date"] > last_by_type[e["type"]]:
            last_by_type[e["type"]] = e["date"]

    log_report = {
        "total_operations": len(filtered),
        "by_type": by_type,
        "last_by_type": last_by_type,
        "recent": filtered[:10],
    }

    queue = read_queue()
    pending = [item for item in queue["items"] if item["status"] == "pending"]
    completed = [item for item in queue["items"] if item["status"] == "completed"]
    skipped = [item for item in queue["items"] if item["status"] == "skipped"]

    queue_report = {
        "status": "active" if pending else "empty",
        "total": len(queue["items"]),
        "completed": len(completed),
        "remaining": len(pending),
        "skipped": len(skipped),
        "by_type": dict(Counter(item["type"] for item in pending)),
    }

    return {"log": log_report, "heal_queue": queue_report}


def format_summary(report: dict) -> str:
    lines = [f"# Wiki Status Report — {date.today().isoformat()}", ""]

    log = report["log"]
    lines.append(f"## Log: {log['total_operations']} operations")
    if log["by_type"]:
        for op_type, count in sorted(log["by_type"].items(), key=lambda x: x[1], reverse=True):
            last = log["last_by_type"].get(op_type, "?")
            lines.append(f"- **{op_type}**: {count} (last: {last})")
    else:
        lines.append("- No operations recorded.")
    lines.append("")

    hq = report["heal_queue"]
    if hq["status"] == "active":
        lines.append(f"## Heal Queue: {hq['remaining']}/{hq['total']} pending")
        lines.append(f"- Completed: {hq['completed']}")
        lines.append(f"- Skipped: {hq['skipped']}")
        if hq["by_type"]:
            lines.append("- Pending by type:")
            for item_type, count in sorted(hq["by_type"].items()):
                lines.append(f"  - {item_type}: {count}")
    else:
        lines.append("## Heal Queue: empty")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wiki log reader and status reporter")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--summary", action="store_true", help="Human-readable summary")
    parser.add_argument("--type", type=str, metavar="TYPE", help="Filter by operation type (ingest, heal, graph, lint)")
    parser.add_argument("--last", type=int, metavar="N", help="Only include last N days")
    args = parser.parse_args()

    if not args.json and not args.summary:
        args.summary = True

    report = build_report(type_filter=args.type, last_days=args.last)

    if args.json:
        print(json.dumps(report, indent=2))
    if args.summary:
        print(format_summary(report))
