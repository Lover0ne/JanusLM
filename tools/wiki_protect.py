#!/usr/bin/env python3
from __future__ import annotations

"""
Wiki permission flags.

Contract:
  --status             -> read current flags, print as JSON (no mutation)
  --toggle <flag>      -> toggle a specific flag
                          (can_forget | can_modify | can_anonymize_pii),
                          print new state as JSON

Inputs:  wiki/.protect (JSON, created if missing)
Outputs: wiki/.protect (mutated on toggle), stdout JSON

Flags:
  can_forget  -> if true, the agent can run the /forget workflow.
                 Default false (wiki protected from deletions).
  can_modify  -> if true, the agent can edit wiki files directly
                 (outside ingest/heal workflows). Default false.

If this script fails:
  - wiki/.protect not found -> creates it with defaults (auto-init)
  - JSON decode error -> recreates with defaults
  - Old format ({"protected": ...}) -> auto-migrates to new format
  - wiki/ directory missing -> "Wiki directory not found", exit 1
  - Invalid flag name -> error message, exit 1
"""

import sys
import json
import argparse
from datetime import datetime

from shared import WIKI_DIR

PROTECT_FILE = WIKI_DIR / ".protect"
VALID_FLAGS = {"can_forget", "can_modify", "can_anonymize_pii"}
DEFAULTS = {"can_forget": False, "can_modify": False, "can_anonymize_pii": False}


def read_state() -> dict:
    if not WIKI_DIR.exists():
        print("Wiki directory not found", file=sys.stderr)
        sys.exit(1)

    if not PROTECT_FILE.exists():
        write_state(DEFAULTS.copy())
        return DEFAULTS.copy()

    try:
        data = json.loads(PROTECT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        write_state(DEFAULTS.copy())
        return DEFAULTS.copy()

    state = DEFAULTS.copy()
    for flag in VALID_FLAGS:
        if flag in data:
            state[flag] = bool(data[flag])
    return state


def write_state(state: dict):
    PROTECT_FILE.write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8"
    )


def status():
    state = read_state()
    print(json.dumps(state, indent=2))


def toggle(flag: str):
    if flag not in VALID_FLAGS:
        print(json.dumps({
            "error": f"Invalid flag: {flag}",
            "valid_flags": sorted(VALID_FLAGS),
        }, indent=2), file=sys.stderr)
        sys.exit(1)

    state = read_state()
    old_value = state[flag]
    new_value = not old_value
    state[flag] = new_value
    write_state(state)

    print(json.dumps({
        "flag": flag,
        "value": new_value,
        "toggled_from": old_value,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Wiki permission flags (can_forget, can_modify, can_anonymize_pii)"
    )
    parser.add_argument("--status", action="store_true",
                        help="Show current flags (read-only)")
    parser.add_argument("--toggle", metavar="FLAG",
                        help="Toggle a flag (can_forget | can_modify)")
    args = parser.parse_args()

    if args.status:
        status()
    elif args.toggle:
        toggle(args.toggle)
    else:
        parser.print_help()
