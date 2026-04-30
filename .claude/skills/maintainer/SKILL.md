---
name: maintainer
description: Wiki knowledge base maintenance — health checks, build knowledge graph, view stats. Use for wiki integrity and graph operations. For ingest use /wiki-ingest, for queries use /wiki-query.
---

# Wiki Maintainer

You are the wiki maintainer. Follow these workflows exactly when performing wiki operations.

## Slash Commands

| Command | Skill | What to say |
|---|---|---|
| `/wiki-ingest` | `/wiki-ingest` | `ingest raw/my-article.md` |
| `/wiki-query` | `/wiki-query` | `what do we know about X?` |
| `/wiki-health` | this skill | `health` (fast, every session) |
| `/wiki-graph` | this skill | `build the knowledge graph` |
| `/wiki-stats` | this skill | `wiki stats` |

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
| `health` | Structural health check | After `health.py` | `log_write.py` (agent) |
| `forget` | Information removed from wiki | After forget workflow | `log_write.py` (agent) |
| `setup` | Wiki infrastructure modified | Structural changes | `log_write.py` (agent) |
| `convert` | File converted to markdown | After standalone `/convert` | `log_write.py` (agent) |
| `anonymize` | Document anonymized via privacy filter | After privacy filter processes a file | `log_write.py` (agent) |

### Who Can Write log.md

| Writer | Operations | How |
|---|---|---|
| `log_write.py` | ingest, health, forget, setup, convert, anonymize | `python tools/log_write.py --op <op> --title <title>` |
| `heal.py --done` | heal | Automatic in `mark_done()` |
| `build_graph.py` | graph, report | Automatic in `build_graph()` |
| Agent direct | **NONE** | The agent must NEVER write to log.md directly |

### Reading the Log

    grep "^## \[" wiki/log.md              # all entries
    grep "^## \[" wiki/log.md | grep ingest # ingest only
    python tools/log_report.py --json       # structured report
