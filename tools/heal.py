#!/usr/bin/env python3
from __future__ import annotations

"""
Heal queue state machine.

Contract:
  --detect       → runs health.py --json + build_graph.py --json via subprocess,
                   collects all problems, populates heal_queue.json.
                   Preserves completed/skipped items, deduplicates pending.
  --status       → prints queue summary as JSON to stdout
  --next N       → prints next N pending items as JSON to stdout (default 5)
  --done id ...  → marks items completed, appends summary to wiki/log.md
  --skip id --reason "..." → marks item skipped with reason

Inputs:  heal_queue.json, health.py --json output, build_graph.py --json output
Outputs: heal_queue.json (mutated), wiki/log.md (appended), stdout JSON

If this script fails:
  - FileNotFoundError on heal_queue.json → recreate empty:
    {"items": [], "created": null, "stats": {"total": 0, "completed": 0, "skipped": 0}}
  - subprocess error on health.py or build_graph.py → run them standalone to diagnose
  - JSON decode error on heal_queue.json → file corrupted, reset to empty structure
  - KeyError on item fields → queue was written by an older version, re-run --detect
"""

import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import date
from collections import Counter

from shared import REPO_ROOT, QUEUE_FILE, LOG_FILE, append_log_raw


def read_queue() -> dict:
    if not QUEUE_FILE.exists():
        return {"items": [], "created": None, "stats": {"total": 0, "completed": 0, "skipped": 0}}
    return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))


def write_queue(data: dict):
    QUEUE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_health_json() -> dict:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "health.py"), "--json"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print(f"Warning: health.py failed: {result.stderr.strip()}", file=sys.stderr)
        return {}
    return json.loads(result.stdout)


def run_graph_json() -> dict:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "build_graph.py"), "--json"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print(f"Warning: build_graph.py failed: {result.stderr.strip()}", file=sys.stderr)
        return {}
    return json.loads(result.stdout)


def detect():
    """Scan wiki, collect all problems, populate heal_queue.json."""
    today = date.today().isoformat()
    queue = read_queue()

    health = run_health_json()
    graph = run_graph_json()

    new_items: list[dict] = []
    item_counter = 0

    def make_id() -> str:
        nonlocal item_counter
        item_counter += 1
        return f"heal-{today}-{item_counter:03d}"

    for ef in health.get("empty_files", []):
        new_items.append({
            "id": make_id(),
            "type": "empty_file",
            "path": ef["path"],
            "description": f"File is {ef['status']} ({ef['body_bytes']} body bytes)",
            "status": "pending",
            "skip_reason": None,
        })

    for stale in health.get("index_sync", {}).get("in_index_not_on_disk", []):
        new_items.append({
            "id": make_id(),
            "type": "index_desync_stale",
            "path": stale,
            "description": "Listed in index.md but file does not exist on disk",
            "status": "pending",
            "skip_reason": None,
        })

    for missing in health.get("index_sync", {}).get("on_disk_not_in_index", []):
        new_items.append({
            "id": make_id(),
            "type": "index_desync_missing",
            "path": missing,
            "description": "File exists on disk but not listed in index.md",
            "status": "pending",
            "skip_reason": None,
        })

    for mt in health.get("missing_tags", []):
        status_desc = "no tags field" if mt["status"] == "missing" else "tags list is empty"
        new_items.append({
            "id": make_id(),
            "type": "missing_tag",
            "path": mt["path"],
            "description": f"Page has {status_desc}",
            "status": "pending",
            "skip_reason": None,
        })

    for tag, page in health.get("tag_consistency", {}).get("singleton_tags", {}).items():
        new_items.append({
            "id": make_id(),
            "type": "singleton_tag",
            "path": page,
            "description": f"Tag '{tag}' is used only in this page — possible typo",
            "status": "pending",
            "skip_reason": None,
        })

    for lm in health.get("log_coverage", []):
        new_items.append({
            "id": make_id(),
            "type": "log_missing",
            "path": lm["path"],
            "description": f"Source page '{lm['title']}' has no ingest entry in log.md",
            "status": "pending",
            "skip_reason": None,
        })

    for orphan in graph.get("orphans", []):
        new_items.append({
            "id": make_id(),
            "type": "orphan",
            "path": orphan["path"],
            "description": "Page has zero graph connections (no inbound/outbound [[wikilinks]])",
            "status": "pending",
            "skip_reason": None,
        })

    for phantom in graph.get("phantom_hubs", []):
        new_items.append({
            "id": make_id(),
            "type": "phantom_hub",
            "path": f"[[{phantom['name']}]]",
            "description": f"Referenced by {phantom['ref_count']} pages but does not exist: {', '.join(phantom['referenced_by'][:3])}",
            "status": "pending",
            "skip_reason": None,
        })

    pending_existing = [item for item in queue["items"] if item["status"] == "pending"]
    existing_paths_types = {(item["path"], item["type"]) for item in pending_existing}
    truly_new = [item for item in new_items if (item["path"], item["type"]) not in existing_paths_types]

    all_items = queue["items"] + truly_new
    pending_count = sum(1 for item in all_items if item["status"] == "pending")
    completed_count = sum(1 for item in all_items if item["status"] == "completed")
    skipped_count = sum(1 for item in all_items if item["status"] == "skipped")

    queue["items"] = all_items
    queue["created"] = queue["created"] or today
    queue["stats"] = {
        "total": len(all_items),
        "completed": completed_count,
        "skipped": skipped_count,
    }

    write_queue(queue)

    print(json.dumps({
        "action": "detect",
        "new_items": len(truly_new),
        "total_pending": pending_count,
        "total_items": len(all_items),
        "by_type": dict(Counter(item["type"] for item in all_items if item["status"] == "pending")),
    }, indent=2))


def status():
    """Print current queue status."""
    queue = read_queue()
    pending = [item for item in queue["items"] if item["status"] == "pending"]
    completed = [item for item in queue["items"] if item["status"] == "completed"]
    skipped = [item for item in queue["items"] if item["status"] == "skipped"]

    print(json.dumps({
        "status": "active" if pending else "empty",
        "created": queue["created"],
        "total": len(queue["items"]),
        "pending": len(pending),
        "completed": len(completed),
        "skipped": len(skipped),
        "pending_by_type": dict(Counter(item["type"] for item in pending)),
    }, indent=2))


def next_batch(n: int):
    """Print the next N pending items."""
    queue = read_queue()
    pending = [item for item in queue["items"] if item["status"] == "pending"]
    batch = pending[:n]

    print(json.dumps({
        "batch_size": len(batch),
        "remaining_after": len(pending) - len(batch),
        "items": batch,
    }, indent=2))


def mark_done(ids: list[str]):
    """Mark items as completed, update stats, append to log."""
    queue = read_queue()
    today = date.today().isoformat()
    done_types: list[str] = []

    for item in queue["items"]:
        if item["id"] in ids and item["status"] == "pending":
            item["status"] = "completed"
            done_types.append(item["type"])

    completed_count = sum(1 for item in queue["items"] if item["status"] == "completed")
    skipped_count = sum(1 for item in queue["items"] if item["status"] == "skipped")
    queue["stats"] = {
        "total": len(queue["items"]),
        "completed": completed_count,
        "skipped": skipped_count,
    }
    write_queue(queue)

    if done_types:
        type_summary = ", ".join(f"{t}({c})" for t, c in Counter(done_types).items())
        append_log_raw(f"## [{today}] heal | Fixed {len(done_types)} items | types: {type_summary}")

    pending = sum(1 for item in queue["items"] if item["status"] == "pending")
    print(json.dumps({
        "action": "done",
        "marked": len(done_types),
        "total": len(queue["items"]),
        "completed": completed_count,
        "pending": pending,
        "skipped": skipped_count,
    }, indent=2))


def skip_items(ids: list[str], reason: str):
    """Mark items as skipped with a reason."""
    queue = read_queue()
    skipped_count_new = 0

    for item in queue["items"]:
        if item["id"] in ids and item["status"] == "pending":
            item["status"] = "skipped"
            item["skip_reason"] = reason
            skipped_count_new += 1

    completed_count = sum(1 for item in queue["items"] if item["status"] == "completed")
    skipped_count = sum(1 for item in queue["items"] if item["status"] == "skipped")
    queue["stats"] = {
        "total": len(queue["items"]),
        "completed": completed_count,
        "skipped": skipped_count,
    }
    write_queue(queue)

    pending = sum(1 for item in queue["items"] if item["status"] == "pending")
    print(json.dumps({
        "action": "skip",
        "skipped_now": skipped_count_new,
        "reason": reason,
        "pending": pending,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wiki heal state machine")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--detect", action="store_true", help="Scan wiki and populate heal queue")
    group.add_argument("--status", action="store_true", help="Show current queue status")
    group.add_argument("--next", type=int, metavar="N", help="Get next N pending items")
    group.add_argument("--done", nargs="+", metavar="ID", help="Mark items as completed")
    group.add_argument("--skip", nargs="+", metavar="ID", help="Mark items as skipped")
    parser.add_argument("--reason", type=str, default="", help="Reason for skipping (used with --skip)")
    args = parser.parse_args()

    if args.detect:
        detect()
    elif args.status:
        status()
    elif args.next is not None:
        next_batch(args.next)
    elif args.done:
        mark_done(args.done)
    elif args.skip:
        if not args.reason:
            print("Error: --reason is required with --skip", file=sys.stderr)
            sys.exit(1)
        skip_items(args.skip, args.reason)
