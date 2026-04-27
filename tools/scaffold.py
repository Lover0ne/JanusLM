#!/usr/bin/env python3
from __future__ import annotations

"""
Project structure checker and regenerator.

Contract:
  --check       -> verify project structure, return JSON PASS/FAIL
                   with list of missing directories and files.
  --fix         -> create missing directories and files. Idempotent: if
                   everything already exists, nothing is modified.
  --reset-deps  -> delete .deps-ok to force dependency reinstallation.
  --mark-deps   -> create .deps-ok after successful dependency verification.

Inputs:  filesystem (read structure)
Outputs: stdout JSON

If this script fails:
  - Permission error on mkdir/write -> report exact path
  - shared.py import error -> run /setup first
"""

import sys
import json
import argparse
from pathlib import Path

from shared import REPO_ROOT, WIKI_DIR

# ── Expected structure ────────────────────────────────────────────

DIRS_WITH_GITKEEP = [
    "raw",
    "processed",
    "graph",
    ".staging",
    "tools",
    "wiki/sources",
    "wiki/entities",
    "wiki/concepts",
    "freespace",
    "maskzone",
]

EMPTY_QUEUE = json.dumps(
    {"items": [], "created": None, "stats": {"total": 0, "completed": 0, "skipped": 0}},
    indent=2, ensure_ascii=False,
) + "\n"

FILES = {
    "wiki/index.md": (
        "# Wiki Index\n\n"
        "## Sources\n\n"
        "## Entities\n\n"
        "## Concepts\n"
    ),
    "wiki/log.md": "# Wiki Log\n",
    "wiki/.protect": '{\n  "can_forget": false,\n  "can_modify": false,\n  "can_anonymize_pii": false\n}\n',
    "heal_queue.json": EMPTY_QUEUE,
    "ingest_queue.json": EMPTY_QUEUE,
    "rejected.json": '{\n  "rejected": []\n}\n',
    "requirements.txt": (
        "# All dependencies — install with: pip install -r requirements.txt\n\n"
        "# Wiki tools (graph, validation)\n"
        "networkx\n"
        "scikit-learn\n"
        "python-frontmatter\n"
        "rapidfuzz\n"
    ),
}


# ── Commands ──────────────────────────────────────────────────────

def collect_missing() -> list[dict]:
    missing = []
    for d in DIRS_WITH_GITKEEP:
        dir_path = REPO_ROOT / d
        if not dir_path.is_dir():
            missing.append({"type": "dir", "path": d})
        else:
            gitkeep = dir_path / ".gitkeep"
            if not gitkeep.exists():
                missing.append({"type": "file", "path": f"{d}/.gitkeep"})
    for f in FILES:
        if not (REPO_ROOT / f).exists():
            missing.append({"type": "file", "path": f})
    return missing


def cmd_check():
    missing = collect_missing()
    total = len(DIRS_WITH_GITKEEP) + len(FILES)
    result = {
        "status": "PASS" if not missing else "FAIL",
        "checked": total,
        "missing": missing,
    }
    print(json.dumps(result, indent=2))


def cmd_fix():
    created_dirs = []
    created_files = []

    for d in DIRS_WITH_GITKEEP:
        dir_path = REPO_ROOT / d
        if not dir_path.is_dir():
            dir_path.mkdir(parents=True, exist_ok=True)
            created_dirs.append(d)
        gitkeep = dir_path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
            created_files.append(f"{d}/.gitkeep")

    for f, content in FILES.items():
        file_path = REPO_ROOT / f
        if not file_path.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            created_files.append(f)

    total = len(DIRS_WITH_GITKEEP) + len(FILES)
    already_ok = total - len(created_dirs) - len(created_files)
    result = {
        "status": "FIXED",
        "created_dirs": created_dirs,
        "created_files": created_files,
        "already_ok": already_ok,
    }
    print(json.dumps(result, indent=2))


def cmd_reset_deps():
    marker = REPO_ROOT / ".deps-ok"
    if marker.exists():
        marker.unlink()
        print(json.dumps({"action": "reset-deps", "deleted": True}, indent=2))
    else:
        print(json.dumps({"action": "reset-deps", "deleted": False, "note": ".deps-ok not found"}, indent=2))


def cmd_mark_deps():
    marker = REPO_ROOT / ".deps-ok"
    marker.write_text("installed\n", encoding="utf-8")
    print(json.dumps({"action": "mark-deps", "created": True}, indent=2))


def cmd_reset_privacy_deps():
    marker = REPO_ROOT / ".privacy-deps-ok"
    if marker.exists():
        marker.unlink()
        print(json.dumps({"action": "reset-privacy-deps", "deleted": True}, indent=2))
    else:
        print(json.dumps({"action": "reset-privacy-deps", "deleted": False, "note": ".privacy-deps-ok not found"}, indent=2))


def cmd_mark_privacy_deps():
    marker = REPO_ROOT / ".privacy-deps-ok"
    marker.write_text("installed\n", encoding="utf-8")
    print(json.dumps({"action": "mark-privacy-deps", "created": True}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify and regenerate project directory structure"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Check structure, report PASS/FAIL as JSON")
    group.add_argument("--fix", action="store_true", help="Create missing dirs/files (idempotent)")
    group.add_argument("--reset-deps", action="store_true", help="Delete .deps-ok to force dependency reinstall")
    group.add_argument("--mark-deps", action="store_true", help="Create .deps-ok after successful dependency verification")
    group.add_argument("--reset-privacy-deps", action="store_true", help="Delete .privacy-deps-ok to force privacy deps reinstall")
    group.add_argument("--mark-privacy-deps", action="store_true", help="Create .privacy-deps-ok after successful privacy deps verification")
    args = parser.parse_args()

    if args.check:
        cmd_check()
    elif args.fix:
        cmd_fix()
    elif args.reset_deps:
        cmd_reset_deps()
    elif args.mark_deps:
        cmd_mark_deps()
    elif args.reset_privacy_deps:
        cmd_reset_privacy_deps()
    elif args.mark_privacy_deps:
        cmd_mark_privacy_deps()
