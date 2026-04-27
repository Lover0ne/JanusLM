---
name: healer
description: Heal the wiki knowledge base — fix orphans, broken links, missing tags, empty pages, index desyncs. Use when the user wants to repair or clean up the wiki.
---

# Wiki Healer

You are the wiki healer. Your job is to fix problems in the knowledge base
using deterministic scripts for detection and state management, and your own
reasoning for the actual corrections.

## Heal Workflow

Triggered by: *"heal"*, *"fix the wiki"*, *"repair"*, or `/heal`

### Step 1 — Check state

Run: `python tools/heal.py --status`

- If `"status": "active"` with pending items → **resume** from where you left off (go to Step 3)
- If `"status": "empty"` → run detection (go to Step 2)

### Step 2 — Detect problems

Run: `python tools/heal.py --detect`

This scans the entire wiki using `health.py` and `build_graph.py`, then populates
`heal_queue.json` with all detected problems.

Read the output. If `total_pending` is 0, tell the user:
> "Wiki is healthy — no problems detected."

If problems were found, continue to Step 3.

### Step 3 — Fetch batch

Run: `python tools/heal.py --next 5`

This returns the next 5 pending items as JSON. Read them carefully.

### Step 4 — Fix each item

For each item in the batch, apply the appropriate correction:

| Type | How to fix |
|---|---|
| `orphan` | Read the file. Find related pages in the wiki (by topic, tag, or content). Add [[wikilinks]] in both directions — in this page and in the related pages. |
| `phantom_hub` | This is a page referenced by others but that doesn't exist. Create it as an entity or concept page (infer from context). Add to `wiki/index.md`. |
| `missing_tag` | Read the file. Deduce the project tag from content, position in the wiki, or related pages. Add the tag to the YAML frontmatter. |
| `empty_file` | Read who links to this page ([[wikilinks]] pointing here). Use that context to populate the page with meaningful content following the page format from the maintainer skill. |
| `index_desync_stale` | Remove the stale entry from `wiki/index.md` — the file doesn't exist anymore. |
| `index_desync_missing` | Add the missing entry to `wiki/index.md` under the appropriate section (Sources, Entities, Concepts, or Syntheses). |
| `singleton_tag` | Check if it's a typo of an existing tag (e.g., `proect-alpha` vs `project-alpha`). If typo: correct it. If legitimate: skip with reason. |
| `log_missing` | Add the missing ingest entry via `python tools/log_write.py --op ingest --title "<source title>" --tag <tag>`. Use the file's frontmatter for title and tag. |

**Ambiguity rule**: if you cannot determine the correct fix with confidence (e.g., an orphan
that could belong to multiple projects, a tag that could be either a typo or intentional),
**ask the user**. Do not guess. Use `--skip` with a reason if the user declines.

### Step 5 — Confirm batch

After fixing all items in the batch, mark them:

```bash
python tools/heal.py --done id1 id2 id3 id4 id5
```

For any items you skipped due to ambiguity:

```bash
python tools/heal.py --skip id1 --reason "could belong to project-alpha or project-beta"
```

### Step 6 — Report progress

Run: `python tools/log_report.py --json`

Read the output and communicate progress factually:

- If items remain: **"Fixed X/Y. Run `/heal` again to continue."**
- If queue empty: **"Heal complete. X/Y fixed, Z skipped."**

---

## Rules

- **Do NOT ask "do you want to continue?"** — the user launched /heal, they want it done.
  Process the entire batch, then stop with a progress message.
- **Stop ONLY for genuine ambiguity** — when you truly cannot determine the correct fix.
- **ALWAYS use the deterministic scripts** to update state. Never edit `heal_queue.json` directly.
- **ALWAYS use `--done` or `--skip`** after processing items. The queue is the source of truth.
- Follow the page format conventions from the `/maintainer` skill when creating or editing pages.

---

## Log Format

For log entry format and field meanings, see the "Log Format & Contract" section
in the `/maintainer` skill. Heal entries are written automatically by `heal.py --done`.
