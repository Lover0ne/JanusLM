---
name: wiki-ingest
description: Ingest source documents into the wiki knowledge base. Full pipeline from queue management to validation. Use when the user wants to add new documents to the KB.
---

# Wiki Ingest

You are the wiki ingest handler. Follow this workflow to process documents into
the knowledge base.

## Project Tagging — Mandatory

Every wiki page MUST have at least one project tag. Tags are the primary mechanism
for organizing knowledge by domain/project.

**Before starting any ingest**, ask the user:
> "Which project or domain does this document belong to?"

Present existing tags (grep `tags:` across `wiki/` pages) as options so the user
can pick an existing one or create a new one. **Never proceed without a confirmed tag.**

Tag format: `kebab-case` (e.g. `project-alpha`, `ai-strategy`, `client-onboarding`)

### How tags propagate during ingest

- The **source page** gets the project tag
- Every **entity page** touched gets the project tag added (without removing existing tags)
- Every **concept page** touched gets the project tag added
- If an entity/concept page already exists with a different project tag, **separate
  the new content under a project-specific heading** (e.g. `## In project-alpha`)

### Tag management

- `python tools/ingest.py --tags` — list all existing project tags
- `python tools/ingest.py --rename-tag OLD --tag NEW` — rename a tag across all wiki
  pages (frontmatter `tags:`, `## In <tag>` section headings, `last_updated`).

## Page Format

Page structure is created by deterministic Python scaffolds — the agent never
writes frontmatter or section headers directly. Use `[[PageName]]` wikilinks to
link to other wiki pages.

| Field | Source (`--init`) | Entity/Concept (`--new-page`) |
|---|---|---|
| `title:` | `""` (agent fills) | `"Name"` (pre-filled) |
| `type:` | `source` | `entity` / `concept` |
| `tags:` | `[tag]` | `[tag]` |
| `date:` | today | — |
| `source_file:` | `raw/...` | — |
| `last_updated:` | today | today |
| Sections | Summary, Key Claims, Key Quotes, Connections, Contradictions | Description, In \<tag> |

---

## Ingest Workflow

Triggered by: *"ingest <file>"*, *"ingest all"*, or `/wiki-ingest`

Uses `tools/ingest.py` for deterministic queue management, scaffolding, and validation.
The agent handles semantic content: reading documents, understanding meaning, filling
scaffolded pages, and finding correlations.

### Phase A — Queue

| Step | Command |
|---|---|
| 1 | `python tools/ingest.py --status` — check queue state |
| 2a | `python tools/ingest.py --scan` — if user says "ingest all" |
| 2b | `python tools/ingest.py --add raw/file1.md raw/file2.md` — if specific files |
| 3 | `python tools/ingest.py --next 3` — get the next batch |

### Phase B — Per-item processing

For each item in the batch, follow steps 4–16 in order:

**Step 4 — File conversion (if needed)**
If the file is not `.md`:
1. Invoke the `/convert` skill to produce the `.md` in `raw/`
2. Archive the original: `python tools/ingest.py --archive <id>`
   This moves the binary to `processed/` and updates `source_path` in the queue.
3. All subsequent steps use the `.md` file in `raw/` as the source document.

**Step 5 — Rejection check**
`python tools/ingest.py --check-rejected <id>`

If `"rejected": true`: show the user the previous rejection reason, tag, and date.
Ask if they want to proceed anyway or skip this item.
- If the user wants to skip: `python tools/ingest.py --skip <id> --reason "rejected: confirmed previous rejection"`
- If the user wants to proceed: continue to step 6.

If `"rejected": false`: continue to step 6.

**Step 6 — Ask for project tag**
`python tools/ingest.py --tags`

Present the returned tags as options to the user. If the list is empty, ask for a new tag.
Let the user pick an existing tag or create a new one.
**Do not proceed without a confirmed tag.**

**Step 7 — Set tag**
`python tools/ingest.py --set-tag <id> --tag <tag>`

**Step 8 — Domain validation (3 phases)**
Blind review in three phases — prevents anchoring bias:

**Phase A — Semantic evaluation (blind):**
Read the new document and the existing wiki pages tagged with the target project.
Form your own assessment of thematic relevance **WITHOUT** running the quantitative
script and **WITHOUT** seeing any score. Produce:
- Affinity: HIGH / MEDIUM / LOW
- Reasoning: why the document belongs or doesn't belong to this domain

**Phase B — Quantitative scoring (independent):**
Only after completing Phase A, run `python tools/validate_domain.py --doc <path> --tag <tag> --json`
and read the JSON output. If the script is not available (missing dependencies),
skip to Phase C with only the semantic evaluation.

**Phase C — Comparison and final verdict:**
Produce the final affinity report:
```
Semantic evaluation (blind): HIGH/MEDIUM/LOW — [reasoning]
Quantitative score: XX% (TF-IDF: XX%, Entity: X/Y, Concept: X/Y)
Agreement: YES/NO — [if NO, explain discrepancy]
Final verdict: PROCEED / WARN
```

Decision logic:
- No existing pages for this tag → skip validation, first document for the domain
- Both point to relevance → proceed automatically
- Both point to low relevance → warn user, ask for confirmation
- Disagreement → present both, ask the user

If the user declines: `python tools/ingest.py --skip <id> --reason "rejected: <motivo>"`
This automatically logs the rejection to `rejected.json`.

**Step 9 — Create scaffold**
`python tools/ingest.py --init <id>`
This creates the source page skeleton with complete frontmatter, empty sections, and
adds the source entry to `wiki/index.md`.

**Step 10 — Read source document**
Read the full document using the Read tool.
For converted files, read the `.md` in `raw/` (same stem as the original).

**Step 11 — CRITICAL: Discovery (three sources)**

> **This is the most important step in the entire workflow.**
> Do NOT rush. Do NOT skip levels. Take the time to think deeply.

Discovery uses three complementary sources. All three are mandatory.

**11a — Index scan (structure)**

Read `wiki/index.md` in full — **without filtering by tag**. This gives the complete
map of every entity, concept, and source that already exists in the wiki.
Keep it as context for the next steps.

**11b — Alias and correlation analysis (content)**

Read the document and produce an exhaustive network of:
- **Direct aliases**: exact synonyms, abbreviations, acronyms, translations
  (e.g., RAG, Retrieval-Augmented Generation, retrieval augmented generation)
- **First-level correlations**: directly related concepts
  (e.g., RAG → embedding, vector search, knowledge base, grounding)
- **Second-level correlations**: concepts related to the correlations
  (e.g., embedding → LLM, transformer, tokenization)
- **Cross-domain correlations**: broader field connections
  (e.g., LLM → AI, machine learning, agents, prompt engineering)

Keep expanding until the network is complete. Each level reveals connections
that a literal match would never find.

**11c — Grep massivo (content)**

Launch a single grep with all aliases concatenated across the entire wiki:

```bash
grep -rl -i -E "alias1|alias2|alias3|..." wiki/
```

The result is the map of files to read and potentially update.
Note the match count per file — higher count means more relevant.

**11d — Wikilink traversal (graph)**

For each page found by the grep, read it and follow its `[[wikilinks]]`.
Those neighbors are likely relevant too, even if they didn't match any alias.
Add them to the map.

**11e — Merge**

Combine all three sources (index context, grep matches, wikilink neighbors)
into a single list of pages to create or update. The project tag is NOT a filter —
pages from other projects are included if relevant. The tag is only used as an
output label (to create `## In <project-tag>` sections on existing pages).

**Step 12 — Write content**

Read the pages identified in step 10. Then:

1. Fill the source page: title, Summary, Key Claims, Key Quotes, Connections (with [[wikilinks]]), Contradictions

2. **For each entity/concept identified, call `--new-page` BEFORE writing any content:**
   ```bash
   python tools/ingest.py --new-page --type entity --name "EntityName" --tag <tag>
   python tools/ingest.py --new-page --type concept --name "ConceptName" --tag <tag>
   ```
   - If `"exists": false` → scaffold created with both `## Description` and
     `## In <tag>`. Fill `## Description` with generic, project-agnostic content
     (what this entity/concept IS in general). Fill `## In <tag>` with
     project-specific context from this document (how it's used, what role
     it plays, specific details from the source).
     Confirm via `section_added` in the JSON response.
   - If `"exists": true` → the tool has already added the project tag to frontmatter
     and created the `## In <tag>` heading. Fill content under `## In <tag>` only —
     do NOT rewrite `## Description` (it already contains generic content).
     Check `tag_added` and `section_added` in the JSON response to confirm.
   - **NEVER create entity/concept pages directly with the Write tool.**
     Always go through `--new-page` to guarantee correct frontmatter and structure.
   - **NEVER edit frontmatter tags or write section headings manually.**
     The `--new-page` command handles both deterministically.

3. For each new entry added by `--new-page`, run `python tools/wiki_index.py update --path "<path>" --description "<one-line description>"` to complete the index entry. **NEVER edit wiki/index.md directly.**

**Step 12b — Discovery review (blind review)**

Phase A is already complete — you did discovery (step 11) and wrote content
(step 12) without any deterministic assist.

**Phase B:** run the term extraction tool on the original source document:
```bash
python tools/extract_terms.py --doc <source_path> --wiki <wiki_slug> --json
```

**Phase C:** Compare the term frequency list against `already_linked`.
Ignore noise (articles, prepositions, common words — you can recognize them).
Focus on high-frequency terms NOT in `already_linked` — if any are relevant
entities or concepts you missed, create the pages with `--new-page` and add
the wikilinks before proceeding to validation.

**Step 13 — Post-ingest validation**
`python tools/ingest.py --validate <id>`

**Step 14 — Fix loop**
If `"status": "FAIL"`: read the errors, apply the suggested fixes, re-run `--validate`.
Repeat until `"status": "PASS"`.

If `"warnings"` are present (even with PASS): these are known wiki pages mentioned
in the source document but not linked via `[[wikilink]]`. Review each warning —
if the term is relevant, add the wikilink and run `--validate` again. If it's a
false positive (e.g. a common word matching a page name), ignore it.

**Step 15 — Complete**
`python tools/ingest.py --done <id>`

**Step 16 — Log**
`python tools/log_write.py --op ingest --title "<source title>" --tag <tag>`

### Phase C — Progress

After the batch: `python tools/ingest.py --status`
- If items remain: "Ingested X/Y. Run `/wiki-ingest` again to continue."
- If queue empty: "Ingest complete."
