#!/usr/bin/env python3
from __future__ import annotations

"""
Ingest queue state machine + scaffold + validation.

Contract:
  --scan              -> scan raw/, find files not yet in queue,
                        populate ingest_queue.json. Dedup by source_path.
                        Compare with wiki/sources/ to exclude already ingested files.
  --add file1 file2   -> add specific files to the queue.
                        Error if file does not exist or is already in queue.
  --status            -> print current queue state as JSON
  --next N            -> print next N pending items (default 3)
  --set-tag id --tag T -> set project tag on an item.
                        Error if item does not exist or is not pending.
  --init id           -> create source page scaffold in wiki/sources/<slug>.md
                        with complete frontmatter and empty sections.
                        Update wiki_slug in the item.
                        Requires tag to be set (error otherwise).
                        Returns JSON with created path + instructions.
  --archive id        -> move original non-md file from raw/ to processed/.
                        Update source_path in the item.
                        Error if file is already .md or does not exist.
  --validate id       -> post-validate: read source page, follow all
                        [[wikilinks]], check complete frontmatter, index sync,
                        tag propagation, wikilink integrity, non-empty sections.
                        Also checks the raw source document for known wiki
                        pages (entities/concepts) mentioned but not linked.
                        Returns JSON with status PASS/FAIL + errors + fixes.
                        Missing links are reported as warnings (non-blocking).
  --done id ...       -> mark items as completed, read title from frontmatter
                        of source page (wiki_slug), log via log_write.py
                        with --op ingest --title <title> --tag <tag>
  --new-page            -> create entity/concept page scaffold.
                        Requires --type (entity|concept), --name, --tag.
                        If page already exists: return JSON with exists: true,
                        path, current tags (never overwrites).
                        If not: create scaffold with frontmatter + empty
                        ## Description. Naming enforced: TitleCase for filename.
  --skip id --reason "..." -> mark items as skipped with reason.
                        If reason starts with "rejected:", also append
                        to rejected.json for historical tracking.
  --check-rejected id   -> check if the item's source_path is in
                        rejected.json. Returns JSON with rejected: true/false.
                        If true, includes reason, tag, date of previous rejection.

Inputs:  ingest_queue.json, rejected.json, raw/*, wiki/**/*.md, wiki/index.md
Outputs: ingest_queue.json (mutated), wiki/sources/<slug>.md (created by --init),
         stdout JSON

If this script fails:
  - FileNotFoundError on ingest_queue.json -> recreate empty structure
  - File in --add not found -> error message, no queue mutation
  - --init without tag -> error: "Set tag first with --set-tag"
  - --init on already-initialized item -> error: wiki_slug already set
  - --validate finds errors -> status FAIL with actionable fix list
  - JSON decode error -> queue corrupted, reset to empty
"""

import sys
import re
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import date
from collections import Counter

from shared import REPO_ROOT, WIKI_DIR, read_file, extract_tags

INGEST_QUEUE = REPO_ROOT / "ingest_queue.json"
REJECTED_FILE = REPO_ROOT / "rejected.json"
SOURCES_DIR = WIKI_DIR / "sources"
INDEX_FILE = WIKI_DIR / "index.md"


def read_queue() -> dict:
    if not INGEST_QUEUE.exists():
        return {"items": [], "created": None, "stats": {"total": 0, "completed": 0, "skipped": 0}}
    try:
        return json.loads(INGEST_QUEUE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("Warning: ingest_queue.json corrupted, resetting", file=sys.stderr)
        return {"items": [], "created": None, "stats": {"total": 0, "completed": 0, "skipped": 0}}


def write_queue(data: dict):
    INGEST_QUEUE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_rejected() -> list[dict]:
    if not REJECTED_FILE.exists():
        return []
    try:
        data = json.loads(REJECTED_FILE.read_text(encoding="utf-8"))
        return data.get("rejected", [])
    except (json.JSONDecodeError, ValueError):
        return []


def append_rejected(source_path: str, tag: str, reason: str):
    entries = read_rejected()
    entries.append({
        "source_path": source_path.replace("\\", "/"),
        "tag": tag,
        "reason": reason,
        "date": date.today().isoformat(),
    })
    REJECTED_FILE.write_text(
        json.dumps({"rejected": entries}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def find_rejected(source_path: str) -> dict | None:
    normalized = source_path.replace("\\", "/")
    for entry in read_rejected():
        if entry.get("source_path", "").replace("\\", "/") == normalized:
            return entry
    return None


def update_stats(queue: dict):
    items = queue["items"]
    queue["stats"] = {
        "total": len(items),
        "completed": sum(1 for i in items if i["status"] == "completed"),
        "skipped": sum(1 for i in items if i["status"] == "skipped"),
    }


def find_item(queue: dict, item_id: str) -> dict | None:
    for item in queue["items"]:
        if item["id"] == item_id:
            return item
    return None


def get_ingested_source_files() -> set[str]:
    """Read source_file from frontmatter of all wiki/sources/*.md files."""
    result = set()
    if not SOURCES_DIR.exists():
        return result
    for p in SOURCES_DIR.glob("*.md"):
        content = read_file(p)
        match = re.search(r'^source_file:\s*(.+)$', content, re.MULTILINE)
        if match:
            result.add(match.group(1).strip())
    return result


def slugify(name: str) -> str:
    name = Path(name).stem
    name = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[\s_]+", "-", name).strip("-")


def normalize_page_name(name: str) -> str:
    """'Marco Bianchi' -> 'MarcoBianchi', 'RAG' -> 'RAG', 'open ai' -> 'OpenAi'."""
    parts = re.split(r'[\s\-_]+', name.strip())
    return "".join(p[0].upper() + p[1:] for p in parts if p)


# -- Commands ---------------------------------------------------------------

def cmd_scan():
    today = date.today().isoformat()
    queue = read_queue()
    raw_dir = REPO_ROOT / "raw"

    if not raw_dir.exists():
        print(json.dumps({"action": "scan", "error": "raw/ directory not found"}, indent=2))
        sys.exit(1)

    raw_files = [
        str(f.relative_to(REPO_ROOT))
        for f in raw_dir.rglob("*")
        if f.is_file() and not f.name.startswith(".") and f.name != ".gitkeep"
    ]

    ingested = get_ingested_source_files()
    queued = {item["source_path"] for item in queue["items"]}
    already = ingested | queued

    new_items = []
    counter = 0
    for rp in sorted(raw_files):
        if rp not in already:
            counter += 1
            new_items.append({
                "id": f"ingest-{today}-{counter:03d}",
                "source_path": rp,
                "tag": None,
                "status": "pending",
                "wiki_slug": None,
                "skip_reason": None,
                "added": today,
            })

    queue["items"].extend(new_items)
    queue["created"] = queue["created"] or today
    update_stats(queue)
    write_queue(queue)

    pending = sum(1 for i in queue["items"] if i["status"] == "pending")
    print(json.dumps({
        "action": "scan",
        "new_items": len(new_items),
        "total_pending": pending,
        "total_items": len(queue["items"]),
    }, indent=2))


def cmd_add(files: list[str]):
    today = date.today().isoformat()
    queue = read_queue()
    ingested = get_ingested_source_files()
    queued = {item["source_path"] for item in queue["items"]}
    already = ingested | queued

    added = []
    errors = []
    counter = len(queue["items"])

    for f in files:
        path = Path(f)
        if not path.is_absolute():
            path = REPO_ROOT / f
        rel = str(path.relative_to(REPO_ROOT))

        if not path.exists():
            errors.append(f"File not found: {rel}")
            continue
        if rel in already:
            errors.append(f"Already in queue or ingested: {rel}")
            continue

        counter += 1
        queue["items"].append({
            "id": f"ingest-{today}-{counter:03d}",
            "source_path": rel,
            "tag": None,
            "status": "pending",
            "wiki_slug": None,
            "skip_reason": None,
            "added": today,
        })
        added.append(rel)
        queued.add(rel)

    queue["created"] = queue["created"] or today
    update_stats(queue)
    write_queue(queue)

    result = {"action": "add", "added": added, "added_count": len(added)}
    if errors:
        result["errors"] = errors
    print(json.dumps(result, indent=2))


def cmd_status():
    queue = read_queue()
    pending = [i for i in queue["items"] if i["status"] == "pending"]
    print(json.dumps({
        "status": "active" if pending else "empty",
        "created": queue["created"],
        "total": len(queue["items"]),
        "pending": len(pending),
        "completed": queue["stats"].get("completed", 0),
        "skipped": queue["stats"].get("skipped", 0),
    }, indent=2))


def cmd_next(n: int):
    queue = read_queue()
    pending = [i for i in queue["items"] if i["status"] == "pending"]
    batch = pending[:n]
    print(json.dumps({
        "batch_size": len(batch),
        "remaining_after": len(pending) - len(batch),
        "items": batch,
    }, indent=2))


def cmd_set_tag(item_id: str, tag: str):
    queue = read_queue()
    item = find_item(queue, item_id)

    if not item:
        print(json.dumps({"error": f"Item not found: {item_id}"}, indent=2), file=sys.stderr)
        sys.exit(1)
    if item["status"] != "pending":
        print(json.dumps({"error": f"Item is not pending: {item_id} (status: {item['status']})"}, indent=2), file=sys.stderr)
        sys.exit(1)

    item["tag"] = tag
    write_queue(queue)

    print(json.dumps({
        "action": "set_tag",
        "id": item_id,
        "tag": tag,
    }, indent=2))


def cmd_done(ids: list[str]):
    queue = read_queue()
    done_items = []

    for item in queue["items"]:
        if item["id"] in ids and item["status"] == "pending":
            item["status"] = "completed"
            done_items.append(item)

    update_stats(queue)
    write_queue(queue)

    for item in done_items:
        title = ""
        if item.get("wiki_slug"):
            content = read_file(REPO_ROOT / item["wiki_slug"])
            title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
        if not title:
            title = Path(item["source_path"]).stem

        tag = item.get("tag", "")
        cmd = [sys.executable, str(REPO_ROOT / "tools" / "log_write.py"),
               "--op", "ingest", "--title", title]
        if tag:
            cmd.extend(["--tag", tag])
        subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True)

    pending = sum(1 for i in queue["items"] if i["status"] == "pending")
    print(json.dumps({
        "action": "done",
        "marked": len(done_items),
        "total": len(queue["items"]),
        "completed": queue["stats"]["completed"],
        "pending": pending,
        "skipped": queue["stats"]["skipped"],
    }, indent=2))


def cmd_skip(ids: list[str], reason: str):
    queue = read_queue()
    skipped_now = 0
    rejected_now = 0

    for item in queue["items"]:
        if item["id"] in ids and item["status"] == "pending":
            item["status"] = "skipped"
            item["skip_reason"] = reason
            skipped_now += 1
            if reason.lower().startswith("rejected:"):
                append_rejected(
                    item["source_path"],
                    item.get("tag", ""),
                    reason[len("rejected:"):].strip(),
                )
                rejected_now += 1

    update_stats(queue)
    write_queue(queue)

    pending = sum(1 for i in queue["items"] if i["status"] == "pending")
    result = {
        "action": "skip",
        "skipped_now": skipped_now,
        "reason": reason,
        "pending": pending,
    }
    if rejected_now:
        result["rejected_logged"] = rejected_now
    print(json.dumps(result, indent=2))


def add_to_index(section: str, rel_link: str, display_name: str):
    """Insert '- [Name](path) —' under the given ## section in index.md."""
    index_text = read_file(INDEX_FILE)
    if rel_link in index_text:
        return
    entry = f"- [{display_name}]({rel_link}) —"
    header = f"## {section}"
    lines = index_text.split("\n")
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
    if insert_at is not None:
        lines.insert(insert_at, entry)
        INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")


def cmd_check_rejected(item_id: str):
    queue = read_queue()
    item = find_item(queue, item_id)
    if not item:
        print(json.dumps({"error": f"Item not found: {item_id}"}, indent=2), file=sys.stderr)
        sys.exit(1)

    prev = find_rejected(item["source_path"])
    if prev:
        print(json.dumps({
            "rejected": True,
            "source_path": item["source_path"].replace("\\", "/"),
            "reason": prev["reason"],
            "tag": prev["tag"],
            "date": prev["date"],
        }, indent=2))
    else:
        print(json.dumps({
            "rejected": False,
            "source_path": item["source_path"].replace("\\", "/"),
        }, indent=2))


def cmd_new_page(page_type: str, name: str, tag: str):
    if page_type not in ("entity", "concept"):
        print(json.dumps({"error": f"--type must be 'entity' or 'concept', got '{page_type}'"}, indent=2), file=sys.stderr)
        sys.exit(1)

    normalized = normalize_page_name(name)
    subdir = "entities" if page_type == "entity" else "concepts"
    page_dir = WIKI_DIR / subdir
    page_dir.mkdir(parents=True, exist_ok=True)
    page_path = page_dir / f"{normalized}.md"

    if page_path.exists():
        content = read_file(page_path)
        existing_tags = extract_tags(content)
        print(json.dumps({
            "exists": True,
            "path": str(page_path.relative_to(REPO_ROOT)).replace("\\", "/"),
            "tags": existing_tags,
            "name": normalized,
            "type": page_type,
        }, indent=2))
        return

    today = date.today().isoformat()
    content = f"""---
title: "{name}"
type: {page_type}
tags: [{tag}]
last_updated: {today}
---

## Description

"""
    page_path.write_text(content, encoding="utf-8")

    section = "Entities" if page_type == "entity" else "Concepts"
    rel_link = f"{subdir}/{normalized}.md"
    add_to_index(section, rel_link, name)

    print(json.dumps({
        "exists": False,
        "path": str(page_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "created": True,
        "name": normalized,
        "type": page_type,
        "tag": tag,
    }, indent=2))


VALID_TYPES = {"source", "entity", "concept"}
REQUIRED_SECTIONS = {"Summary", "Key Claims", "Connections"}
ENTITIES_DIR = WIKI_DIR / "entities"
CONCEPTS_DIR = WIKI_DIR / "concepts"


def extract_wikilinks(content: str) -> list[str]:
    return re.findall(r'\[\[([^\]]+)\]\]', content)


def resolve_wikilink(name: str) -> Path | None:
    for subdir in ["entities", "concepts", "sources"]:
        candidate = WIKI_DIR / subdir / f"{name}.md"
        if candidate.exists():
            return candidate
    return None


def parse_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    result = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


def check_frontmatter(path: Path, rel_path: str) -> list[dict]:
    errors = []
    content = read_file(path)
    fm = parse_frontmatter(content)

    title = fm.get("title", "").strip('"').strip("'")
    if not title:
        errors.append({
            "type": "empty_title",
            "file": rel_path,
            "fix": f"Add a title in the frontmatter of {rel_path}: title: \"Title\""
        })

    page_type = fm.get("type", "")
    if page_type not in VALID_TYPES:
        errors.append({
            "type": "invalid_type",
            "file": rel_path,
            "message": f"type '{page_type}' is invalid",
            "fix": f"Set type to one of: {', '.join(sorted(VALID_TYPES))}"
        })

    tags = extract_tags(content)
    if not tags:
        errors.append({
            "type": "missing_tag",
            "file": rel_path,
            "message": "No tags in frontmatter",
            "fix": f"Add tags: [tag] in the frontmatter of {rel_path}"
        })

    if not fm.get("last_updated"):
        errors.append({
            "type": "missing_last_updated",
            "file": rel_path,
            "fix": f"Add last_updated: {date.today().isoformat()} in the frontmatter of {rel_path}"
        })

    return errors


def check_sections(path: Path, rel_path: str) -> list[dict]:
    errors = []
    content = read_file(path)
    from shared import strip_frontmatter
    body = strip_frontmatter(content)

    for section_name in REQUIRED_SECTIONS:
        pattern = rf'^## {re.escape(section_name)}\s*$(.*?)(?=^## |\Z)'
        match = re.search(pattern, body, re.MULTILINE | re.DOTALL)
        if not match:
            errors.append({
                "type": "missing_section",
                "file": rel_path,
                "section": section_name,
                "fix": f"Add section ## {section_name} in {rel_path}"
            })
        else:
            section_body = match.group(1).strip()
            if not section_body:
                errors.append({
                    "type": "empty_section",
                    "file": rel_path,
                    "section": section_name,
                    "fix": f"Write content in section ## {section_name} of {rel_path}"
                })
    return errors


def check_index_entry(path: Path, rel_path: str) -> list[dict]:
    index_content = read_file(INDEX_FILE)
    wiki_rel = str(path.relative_to(WIKI_DIR)).replace("\\", "/")
    if wiki_rel not in index_content:
        page_type = parse_frontmatter(read_file(path)).get("type", "entity")
        section_map = {"source": "Sources", "entity": "Entities", "concept": "Concepts"}
        section = section_map.get(page_type, "Entities")
        name = path.stem
        return [{
            "type": "index_missing",
            "file": rel_path,
            "fix": f"Add under ## {section} in index.md: - [{name}]({wiki_rel}) -- description"
        }]
    return []


def cmd_init(item_id: str):
    queue = read_queue()
    item = find_item(queue, item_id)

    if not item:
        print(json.dumps({"error": f"Item not found: {item_id}"}, indent=2), file=sys.stderr)
        sys.exit(1)
    if item["status"] != "pending":
        print(json.dumps({"error": f"Item is not pending: {item_id} (status: {item['status']})"}, indent=2), file=sys.stderr)
        sys.exit(1)
    if not item.get("tag"):
        print(json.dumps({"error": "Set tag first with --set-tag"}, indent=2), file=sys.stderr)
        sys.exit(1)
    if item.get("wiki_slug"):
        print(json.dumps({"error": f"Already initialized: {item['wiki_slug']}"}, indent=2), file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    slug = slugify(Path(item["source_path"]).stem)
    wiki_path = f"wiki/sources/{slug}.md"
    full_path = REPO_ROOT / wiki_path

    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    content = f"""---
title: ""
type: source
tags: [{item['tag']}]
date: {today}
source_file: {item['source_path']}
last_updated: {today}
---

## Summary

## Key Claims

## Key Quotes

## Connections

## Contradictions
"""
    full_path.write_text(content, encoding="utf-8")

    display_name = Path(item["source_path"]).stem.replace("-", " ").replace("_", " ").title()
    add_to_index("Sources", f"sources/{slug}.md", display_name)

    item["wiki_slug"] = wiki_path
    write_queue(queue)

    result = {
        "action": "init",
        "id": item_id,
        "wiki_path": wiki_path,
        "source_path": item["source_path"],
        "tag": item["tag"],
        "instructions": "Fill title, Summary, Key Claims, Key Quotes. Add [[wikilinks]] in Connections. Check Contradictions against existing wiki content.",
    }

    print(json.dumps(result, indent=2))


def cmd_archive(item_id: str):
    queue = read_queue()
    item = find_item(queue, item_id)

    if not item:
        print(json.dumps({"error": f"Item not found: {item_id}"}, indent=2), file=sys.stderr)
        sys.exit(1)

    source = Path(item["source_path"])
    if source.suffix.lower() == ".md":
        print(json.dumps({"error": f"Source is already .md, nothing to archive: {source}"}, indent=2), file=sys.stderr)
        sys.exit(1)

    src_full = REPO_ROOT / source
    if not src_full.exists():
        print(json.dumps({"error": f"Source file not found: {source}"}, indent=2), file=sys.stderr)
        sys.exit(1)

    processed_dir = REPO_ROOT / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    dest = processed_dir / source.name

    shutil.move(str(src_full), str(dest))

    old_path = item["source_path"]
    item["source_path"] = f"processed/{source.name}"
    write_queue(queue)

    print(json.dumps({
        "action": "archive",
        "id": item_id,
        "moved_from": old_path,
        "moved_to": item["source_path"],
    }, indent=2))


def collect_known_pages() -> dict[str, str]:
    """Return {display_name: relative_path} for all entity/concept pages."""
    pages: dict[str, str] = {}
    for subdir in [ENTITIES_DIR, CONCEPTS_DIR]:
        if not subdir.exists():
            continue
        for p in subdir.glob("*.md"):
            content = read_file(p)
            title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else p.stem
            rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
            pages[title] = rel
            if p.stem != title:
                pages[p.stem] = rel
    return pages


def check_missing_links(source_doc_path: Path, wiki_wikilinks: list[str]) -> list[dict]:
    """Compare known wiki pages against source document content.

    Finds entity/concept pages whose name appears in the source document
    but are not linked via [[wikilink]] in the wiki page.
    """
    if not source_doc_path.exists():
        return []

    doc_text = read_file(source_doc_path).lower()
    linked = {wl.lower() for wl in wiki_wikilinks}
    known = collect_known_pages()
    warnings = []

    for name, rel_path in known.items():
        if name.lower() in linked:
            continue
        stem = Path(rel_path).stem.lower()
        if stem in linked:
            continue
        pattern = re.compile(re.escape(name.lower()))
        matches = pattern.findall(doc_text)
        if len(matches) >= 2:
            warnings.append({
                "type": "possible_missing_link",
                "term": name,
                "occurrences_in_source": len(matches),
                "wiki_page": rel_path,
                "fix": f"Consider adding [[{Path(rel_path).stem}]] in Connections of the source page",
            })

    warnings.sort(key=lambda w: w["occurrences_in_source"], reverse=True)
    return warnings


def cmd_validate(item_id: str):
    queue = read_queue()
    item = find_item(queue, item_id)

    if not item:
        print(json.dumps({"error": f"Item not found: {item_id}"}, indent=2), file=sys.stderr)
        sys.exit(1)
    if not item.get("wiki_slug"):
        print(json.dumps({"error": "Item not initialized. Run --init first."}, indent=2), file=sys.stderr)
        sys.exit(1)

    source_path = REPO_ROOT / item["wiki_slug"]
    if not source_path.exists():
        print(json.dumps({"error": f"Source page not found: {item['wiki_slug']}"}, indent=2), file=sys.stderr)
        sys.exit(1)

    source_rel = item["wiki_slug"]
    source_content = read_file(source_path)
    source_tag = item.get("tag", "")

    all_errors: list[dict] = []
    pages_checked: list[str] = [source_rel]

    # Check source page frontmatter
    all_errors.extend(check_frontmatter(source_path, source_rel))

    # Check source page sections
    all_errors.extend(check_sections(source_path, source_rel))

    # Check source page in index
    all_errors.extend(check_index_entry(source_path, source_rel))

    # Follow wikilinks from source page
    wikilinks = extract_wikilinks(source_content)
    for link_name in wikilinks:
        target = resolve_wikilink(link_name)
        if target is None:
            all_errors.append({
                "type": "broken_wikilink",
                "file": source_rel,
                "link": f"[[{link_name}]]",
                "fix": f"Create wiki/entities/{link_name}.md or wiki/concepts/{link_name}.md, or remove the [[wikilink]]"
            })
            continue

        target_rel = str(target.relative_to(REPO_ROOT)).replace("\\", "/")
        if target_rel not in pages_checked:
            pages_checked.append(target_rel)

        # Check linked page frontmatter
        all_errors.extend(check_frontmatter(target, target_rel))

        # Check linked page in index
        all_errors.extend(check_index_entry(target, target_rel))

        # Check tag propagation
        if source_tag:
            target_tags = extract_tags(read_file(target))
            if source_tag not in target_tags:
                all_errors.append({
                    "type": "missing_tag",
                    "file": target_rel,
                    "message": f"Tag '{source_tag}' not present",
                    "fix": f"Add '{source_tag}' to tags: [] in the frontmatter of {target_rel}"
                })

    # Check for known wiki pages mentioned in source doc but not linked
    raw_doc_path = REPO_ROOT / item["source_path"]
    missing_link_warnings = check_missing_links(raw_doc_path, wikilinks)

    if all_errors:
        result = {
            "status": "FAIL",
            "id": item_id,
            "wiki_path": source_rel,
            "errors": all_errors,
            "pages_checked": pages_checked,
        }
    else:
        result = {
            "status": "PASS",
            "id": item_id,
            "wiki_path": source_rel,
            "pages_checked": pages_checked,
            "summary": f"Source page complete, {len(pages_checked)} pages checked, all tags propagated, 0 broken wikilinks",
        }

    if missing_link_warnings:
        result["warnings"] = missing_link_warnings

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest queue state machine")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true", help="Scan raw/ and populate ingest queue")
    group.add_argument("--add", nargs="+", metavar="FILE", help="Add specific files to queue")
    group.add_argument("--status", action="store_true", help="Show current queue status")
    group.add_argument("--next", type=int, metavar="N", help="Get next N pending items")
    group.add_argument("--set-tag", metavar="ID", help="Set project tag on an item")
    group.add_argument("--init", metavar="ID", help="Create source page scaffold for an item")
    group.add_argument("--archive", metavar="ID", help="Move original binary from raw/ to processed/")
    group.add_argument("--validate", metavar="ID", help="Post-ingest validation for an item")
    group.add_argument("--done", nargs="+", metavar="ID", help="Mark items as completed")
    group.add_argument("--new-page", action="store_true", help="Create entity/concept page scaffold")
    group.add_argument("--check-rejected", metavar="ID", help="Check if an item was previously rejected")
    group.add_argument("--skip", nargs="+", metavar="ID", help="Mark items as skipped")
    parser.add_argument("--tag", type=str, help="Project tag (used with --set-tag or --new-page)")
    parser.add_argument("--type", type=str, dest="page_type", help="Page type: entity or concept (used with --new-page)")
    parser.add_argument("--name", type=str, help="Page name (used with --new-page)")
    parser.add_argument("--reason", type=str, default="", help="Reason for skipping (used with --skip)")
    args = parser.parse_args()

    if args.scan:
        cmd_scan()
    elif args.add:
        cmd_add(args.add)
    elif args.status:
        cmd_status()
    elif args.next is not None:
        cmd_next(args.next)
    elif args.set_tag:
        if not args.tag:
            print("Error: --tag is required with --set-tag", file=sys.stderr)
            sys.exit(1)
        cmd_set_tag(args.set_tag, args.tag)
    elif args.init:
        cmd_init(args.init)
    elif args.archive:
        cmd_archive(args.archive)
    elif args.new_page:
        if not args.page_type:
            print("Error: --type is required with --new-page", file=sys.stderr)
            sys.exit(1)
        if not args.name:
            print("Error: --name is required with --new-page", file=sys.stderr)
            sys.exit(1)
        if not args.tag:
            print("Error: --tag is required with --new-page", file=sys.stderr)
            sys.exit(1)
        cmd_new_page(args.page_type, args.name, args.tag)
    elif args.check_rejected:
        cmd_check_rejected(args.check_rejected)
    elif args.validate:
        cmd_validate(args.validate)
    elif args.done:
        cmd_done(args.done)
    elif args.skip:
        if not args.reason:
            print("Error: --reason is required with --skip", file=sys.stderr)
            sys.exit(1)
        cmd_skip(args.skip, args.reason)
