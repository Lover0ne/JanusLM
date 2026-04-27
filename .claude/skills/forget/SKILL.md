---
name: forget
description: Remove information from the wiki knowledge base — forget projects, entities, or concepts. Use when the user wants to delete or remove wiki content.
---

# Wiki Forget

You are the wiki forget handler. Your job is to safely remove information from
the knowledge base following a strict safety protocol.

## Forget Workflow

Triggered by: *"forget"*, *"remove"*, *"delete"*, or `/forget`

### Step 1 — Classify the request

Determine the forget type from the user's message:

| Type | Trigger | Example |
|---|---|---|
| **project** | User names a project tag | "forget project-alpha" |
| **entity** | User names an entity | "forget OpenAI" |
| **concept** | User names a concept | "forget the concept RAG" |

If ambiguous, ask the user to clarify.

### Step 2 — Suggest /heal first

Before proceeding with any deletion, suggest:

> "Before deleting, I recommend running `/heal` to make sure the wiki
> is in good shape. Do you want to proceed directly with the deletion?"

If the user wants to heal first, stop and let them run `/heal`.
If the user wants to proceed, continue.

### Step 3 — Check safety flag

Run: `python tools/wiki_protect.py --status`

- If `"can_forget": false`:
  > "Wiki deletion operations are disabled. Do you want me to enable them?"
  If the user approves: `python tools/wiki_protect.py --toggle can_forget`
  If the user declines: **STOP** — do not proceed.

- If `"can_forget": true` → continue to Step 4.

### Step 4 — Identify targets

Based on the forget type, scan the wiki and build a list of affected pages:

#### For project forget
- Grep for pages with the project tag in frontmatter
- Classify each page:
  - **Mono-tag** (only this project tag): will be **deleted**
  - **Multi-tag** (has other project tags too): will be **modified** (remove tag and project-specific sections)
- Also identify: index.md entries to remove

#### For entity forget
- Find `wiki/entities/<Entity>.md`
- Find all pages containing `[[Entity]]` wikilinks

#### For concept forget
- Find `wiki/concepts/<Concept>.md`
- Find all pages containing `[[Concept]]` wikilinks

### Step 5 — Show deletion plan

Present to the user:

> **Deletion plan:**
> - **Pages to delete:** (list)
> - **Pages to modify:** (list with what changes)
> - **References to remove:** (wikilinks count)

Ask for confirmation before proceeding.

### Step 6 — Execute

Based on the forget type:

#### Project forget
1. Delete mono-tag pages (source, entity, concept pages with only this tag)
2. For multi-tag pages: remove the project tag from frontmatter, remove `## In <project>` sections
3. Remove deleted page entries from `wiki/index.md`

#### Entity forget
1. Delete `wiki/entities/<Entity>.md`
2. In all other pages: replace `[[Entity]]` with `Entity` (plain text)
3. Remove entity entry from `wiki/index.md`

#### Concept forget
1. Delete `wiki/concepts/<Concept>.md`
2. In all other pages: replace `[[Concept]]` with `Concept` (plain text)
3. Remove concept entry from `wiki/index.md`

**File deletion**: use the Recycle Bin method from CLAUDE.md global rules (PowerShell `SendToRecycleBin`).

### Step 7 — Log

Run:
```bash
python tools/log_write.py --op forget --title "<what was forgotten>" --detail "<type>: <scope>"
```

Examples:
- `--title "project-alpha" --detail "project: 5 pages deleted, 2 modified"`
- `--title "OpenAI" --detail "entity: page deleted, 12 wikilinks removed"`

### Step 8 — Suggest /heal after

> "Deletion complete. I recommend running `/heal` to check for broken
> links or orphans."

---

## Rules

- **NEVER proceed if `can_forget` is false** — this is a hard gate, no exceptions.
- **ALWAYS show the deletion plan** and get user confirmation before executing.
- **ALWAYS suggest /heal** both before and after the forget operation.
- **ALWAYS log** the operation via `log_write.py`.
- **Use the Recycle Bin** for file deletion (never `rm`).
- Follow naming conventions from the `/maintainer` skill.
