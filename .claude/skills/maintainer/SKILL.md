---
name: maintainer
description: Wiki knowledge base maintenance — ingest documents, run health checks, lint content quality, build knowledge graph. Use when the user wants to add sources, check wiki integrity, or generate the graph.
---

# Wiki Maintainer

You are the wiki maintainer. Follow these workflows exactly when performing wiki operations.

## Slash Commands

| Command | What to say |
|---|---|
| `/wiki-ingest` | `ingest raw/my-article.md` |
| `/wiki-health` | `health` (fast, every session) |
| `/wiki-lint` | `lint the wiki` (expensive, periodic) |
| `/wiki-graph` | `build the knowledge graph` |
| `/wiki-query` | `what do we know about X?` |
| `/wiki-stats` | `wiki stats` |

## Project Tagging — Mandatory

Every wiki page MUST have at least one project tag. Tags are the primary mechanism
for organizing knowledge by domain/project and preventing information from getting
mixed across unrelated contexts.

**Before starting any ingest**, ask the user:
> "Which project or domain does this document belong to?"

Present existing tags (grep `tags:` across `wiki/` pages) as options so the user
can pick an existing one or create a new one. **Never proceed with an ingest
without a confirmed project tag.**

Tag format: `kebab-case` (e.g. `project-alpha`, `ai-strategy`, `client-onboarding`)

### How tags propagate during ingest

- The **source page** gets the project tag
- Every **entity page** touched gets the project tag added (without removing existing tags)
- Every **concept page** touched gets the project tag added
- If an entity/concept page already exists with a different project tag, **separate
  the new content under a project-specific heading** (e.g. `## In project-alpha`)

### How tags work in queries

- **No filter specified** → search all pages, answer with cross-project view
- **Project specified** → filter by tag, answer only from matching pages
- Always show which project tags contributed to the answer

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
| Sections | Summary, Key Claims, Key Quotes, Connections, Contradictions | Description |

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
1. Invoke the `/converter` skill to produce the `.md` in `raw/`
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
Present existing tags (grep `tags:` across `wiki/` pages) as options.
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
   - If `"exists": false` → scaffold created. Fill `## Description` with content.
   - If `"exists": true` → page already exists. Add content under `## In <project-tag>`.
     Also add the project tag to the existing page's `tags:` if not already present.
   - **NEVER create entity/concept pages directly with the Write tool.**
     Always go through `--new-page` to guarantee correct frontmatter and structure.

3. Update `wiki/index.md` — complete the `—` descriptions for new entries added by `--new-page`

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

### Source Page Structure

The source page structure (frontmatter + sections) is created by `--init`. The agent
fills the content: title, Summary, Key Claims, Key Quotes, Connections (with `[[wikilinks]]`),
Contradictions. Entity/concept page structure is created by `--new-page`.

---

## Lint Workflow

Triggered by: *"lint the wiki"* or `/wiki-lint`

Use Grep and Read tools to check for:
- **Untagged pages** — pages with empty `tags: []` or missing project tag (fix immediately)
- **Orphan pages** — wiki pages with no inbound `[[links]]` from other pages
- **Broken links** — `[[WikiLinks]]` pointing to pages that don't exist
- **Contradictions** — claims that conflict across pages
- **Stale summaries** — pages not updated after newer sources
- **Missing entity pages** — entities mentioned in 3+ pages but lacking their own page
- **Mixed content** — entity/concept pages with multiple project tags but no per-project headings
- **Data gaps** — questions the wiki can't answer; suggest new sources

Output a lint report and ask if the user wants it saved to `wiki/lint-report.md`.

Log the operation:
```bash
python tools/log_write.py --op lint --title "Lint report: X issues found"
```

---

## Health Workflow

Triggered by: *"health"* or `/wiki-health`

Run: `python tools/health.py` (or `python tools/health.py --json` for machine-readable output)

Fast structural integrity checks, safe to run every session:
- **Empty / stub files** — pages with no content beyond frontmatter (rate-limit damage)
- **Index sync** — `wiki/index.md` entries vs actual files on disk
- **Log coverage** — source pages missing a corresponding `ingest` entry in `wiki/log.md`

Output a health report. Use `--save` to write to `wiki/health-report.md`.

Log the operation:
```bash
python tools/log_write.py --op health --title "Health check: X issues found"
```

### Health vs Lint Boundary

| Dimension | `health` | `lint` |
|---|---|---|
| **Scope** | Structural integrity | Content quality |
| **Cost** | Free | Tokens |
| **Frequency** | Every session, before other work | Every 10-15 ingests |
| **Checks** | Empty files, index sync, log sync, tag validation | Orphans, broken links, tag mismatches, contradictions, gaps |
| **Tool** | `tools/health.py` | Agent (direct analysis) |
| **Run order** | First (pre-flight) | After health passes |

> Run `health` first — linting an empty file wastes tokens.

---

## Query Workflow

Triggered by: *"what do we know about X?"*, *"summarize project Y"*, or `/wiki-query`

### Step 1 — Classify the query

Before searching, classify the user's question into one of three patterns:

| Pattern | Trigger | Example |
|---|---|---|
| **Project search (vertical)** | User mentions a specific project or tag | "summarize project-alpha", "what is BP59 in project-beta?" |
| **Concept search (horizontal)** | User asks about a concept/entity without specifying a project | "what is RAG?", "what do we know about OpenAI?" |
| **Cross-project search** | User asks about connections or comparisons across projects | "which projects use RAG?", "compare how alpha and beta use OpenAI" |

### Step 2 — Alias analysis (blind, Phase A)

Before using any tool, reason about the query on your own:

1. Identify the core topic(s) the user is asking about
2. Generate synonyms, related terms, acronyms, alternate spellings
3. Think about what vocabulary different sources might use for the same concept
4. If the query is a project search, note the project tag for `--tag` filtering

This is pure reasoning — no tools, no file reads. You must think first so the
deterministic search can cast a wide net without anchoring your judgment.

Aim for 10-30 terms. More is better — the tool handles volume efficiently.

### Step 3 — Wiki search (deterministic, Phase B)

Pipe ALL terms from Step 2 into `wiki_search.py`, one per line:

```
echo "term1
term2
term3" | python tools/wiki_search.py --json [--tag TAG]
```

Use `--tag TAG` for project searches (vertical pattern).
Omit `--tag` for concept and cross-project searches.

The tool scans every wiki page mechanically and returns a ranked list
with: page path, title, description, type, tags, matched_terms, match_count, wikilinks.

If the tool returns no results, the wiki may be empty or the terms too narrow.
Try broader terms, or inform the user that no KB content matches.

### Step 4 — Read & synthesize (Phase C)

1. Review the search results from Step 3
2. For every page with `match_count >= 2` OR whose title/description is clearly
   pertinent to the query, read the full file — do NOT skip pages
3. Only after reading all relevant pages, synthesize the answer
4. Answer using inline citations as `[[PageName]]` wikilinks
5. If no relevant pages exist, answer from general knowledge — don't invent citations
6. Always make it clear what comes from the KB vs general knowledge
7. Include a `## Sources` section at the end listing pages drawn from

If the wiki is empty, say so and suggest running `/wiki-ingest` first.

---

## Stats Workflow

Triggered by: *"wiki stats"*, *"how many pages?"*, *"what's in the wiki?"*

Run: `python tools/wiki_stats.py` (or `--json` for machine-readable)

Fast KB inventory. Shows page counts by type and project,
link density, orphan count, and last operation dates.

---

## Graph Workflow

Triggered by: *"build the knowledge graph"* or `/wiki-graph`

Two scripts, separated by responsibility:

**`python tools/build_graph.py`** — analysis (deterministic)
- Extracts all `[[wikilinks]]` from wiki pages → edges
- Builds nodes from page metadata (type, title, tags)
- Runs Louvain community detection (networkx)
- Outputs `graph/graph.json`
- Flags: `--report` (markdown report), `--save` (save to `graph/graph-report.md`), `--json` (JSON report for other tools)

**`python tools/print_graph.py`** — visualization
- Reads `graph/graph.json` and generates `graph/graph.html` (interactive vis.js)
- Flags: `--open` (open in browser)
- Does NOT scan wiki files or use networkx

Typical flow: run `build_graph.py` first, then `print_graph.py` if the user wants the visual.

**`python tools/build_graph.py --tag tag1,tag2`** — filtered subgraph
- Produces graph with only pages tagged with at least one of the specified tags
- All report/json/save flags work on the filtered subgraph
- Use case: "graph of project-alpha only" or "relationships between alpha and beta"

---

## Log Format & Contract

Every entry in `wiki/log.md` follows a parseable format:

    ## [YYYY-MM-DD] <op> | <title>[ | <tag>][ | <detail>]

### Fields

| Field | Meaning | Example |
|---|---|---|
| `YYYY-MM-DD` | Date of operation (ISO 8601, auto-generated) | `2026-04-25` |
| `op` | Operation type — what happened | `ingest` |
| `title` | Brief human-readable description | `RAG article ingested` |
| `tag` | Project tag involved (optional) | `project-alpha` |
| `detail` | Additional operation-specific info (optional) | `affinity: 87%` |

### Valid Operations

| `op` | Meaning | When | Writer |
|---|---|---|---|
| `ingest` | New document ingested | After ingest completes | `log_write.py` (agent) |
| `heal` | Batch of problems fixed | After `heal.py --done` | `heal.py` (automatic) |
| `graph` | Knowledge graph rebuilt | After `build_graph.py` | `build_graph.py` (automatic) |
| `report` | Graph analysis report generated | After `build_graph.py --report` | `build_graph.py` (automatic) |
| `lint` | Semantic quality check | After agent-driven lint | `log_write.py` (agent) |
| `health` | Structural health check | After `health.py` | `log_write.py` (agent) |
| `forget` | Information removed from wiki | After forget workflow | `log_write.py` (agent) |
| `setup` | Wiki infrastructure modified | Structural changes | `log_write.py` (agent) |
| `convert` | File converted to markdown | After standalone `/convert` | `log_write.py` (agent) |

### Who Can Write log.md

| Writer | Operations | How |
|---|---|---|
| `log_write.py` | ingest, lint, health, forget, setup, convert | `python tools/log_write.py --op <op> --title <title>` |
| `heal.py --done` | heal | Automatic in `mark_done()` |
| `build_graph.py` | graph, report | Automatic in `build_graph()` |
| Agent direct | **NONE** | The agent must NEVER write to log.md directly |

### Reading the Log

    grep "^## \[" wiki/log.md              # all entries
    grep "^## \[" wiki/log.md | grep ingest # ingest only
    python tools/log_report.py --json       # structured report
