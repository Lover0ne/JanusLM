# General Purpose Agent with Knowledge Base

You are a general-purpose assistant with access to a personal knowledge base.
You can use any available skill (docx, pptx, frontend, etc.) to fulfill user requests.

## Dependencies

A `UserPromptSubmit` hook checks automatically whether Python dependencies are
installed (via the `.deps-ok` marker file). If the hook reports `[SETUP REQUIRED]`,
invoke the `/janus-setup` skill before doing anything else. The user can also
run `/setup` manually at any time.

## Knowledge Base

You have a structured knowledge base in `wiki/`. The KB is organized by **project tags**
(e.g. `project-alpha`, `ai-strategy`) and contains cross-project entities and concepts.

### When to search the KB

- **Search** when the user asks about topics, projects, people, or concepts that
  could be in the KB (e.g. "what is BP59?", "what do we know about RAG?", "summarize project alpha")
- **Don't search** when the request is purely operational and doesn't need KB context
  (e.g. "make me an empty Word report", "convert this CSV", "what time is it")
- **When in doubt**, check `wiki/index.md` quickly — if nothing matches, move on
  without forcing KB content into the answer

### Search strategy

Use the `/wiki-query` command (or load the `/maintainer` skill, Query Workflow) for
structured KB queries. The workflow classifies queries into three patterns (project,
concept, cross-project) and defines search + synthesis steps.

The KB is organized as:

```
wiki/
  index.md        # Catalog of all pages — start here
  sources/        # One summary page per ingested document
  entities/       # People, companies, projects, products
  concepts/       # Ideas, frameworks, methods, theories
```

## Wiki Maintenance

Use the `/maintainer` skill for wiki operations (ingest, lint, health, stats, graph).
Use the `/healer` skill (or `/heal` command) to fix wiki problems (orphans, broken links, missing tags).
Use the `/forget` skill (or `/forget` command) to remove information from the wiki (projects, entities, concepts).
Use the `/converter` skill (or `/convert` command) to convert non-markdown files before ingest.

The following **deterministic** Python tools are available:

- `tools/shared.py` — shared constants and utilities (imported by other tools, not run directly)
- `python tools/health.py` — structural health checks (empty files, index sync, tags)
- `python tools/build_graph.py` — build knowledge graph from [[wikilinks]] (analysis only)
- `python tools/print_graph.py` — render interactive HTML visualization from graph.json
- `python tools/heal.py` — heal state machine (detect problems, manage queue, track progress)
- `python tools/log_report.py` — read log.md and heal_queue.json, produce structured reports
- `python tools/validate_domain.py` — quantitative domain affinity scoring
- `python tools/ingest.py` — ingest queue state machine (scan, add, init, new-page, validate, done, check-rejected)
- `python tools/log_write.py` — centralized log writer (validates op, formats entry)
- `python tools/wiki_stats.py` — KB statistics dashboard (page counts, tag distribution)
- `python tools/wiki_protect.py` — wiki permission flags (can_forget, can_modify, can_anonymize_pii)
- `python tools/privacy_filter.py` — local PII anonymization (setup, status, process, hook)
- `python tools/scaffold.py` — verify and regenerate project directory structure
- `python tools/extract_terms.py` — term frequency extraction from a document (discovery blind review)
- `python tools/wiki_search.py` — search wiki pages by terms from stdin (query blind review)

## Wiki History

When the user asks about recent activity in the KB (e.g. "what has been done?",
"show me the log", "what was ingested recently?"), read `wiki/log.md` or run
`python tools/log_report.py --json` for a structured report. No dedicated command
needed — just check the log.

## Wiki Permission Flags

The user can request protection changes directly (e.g. "enable wiki modifications",
"lock the wiki", "turn off protection"). Use `python tools/wiki_protect.py --status`
to check and `python tools/wiki_protect.py --toggle can_modify` to change.

Before modifying any wiki file directly (outside of ingest/heal workflows — e.g.
changing a tag, editing a description, fixing a typo), check:

`python tools/wiki_protect.py --status`

- If `can_modify` is `false`: warn the user that direct modifications are disabled.
  If the user approves, run `python tools/wiki_protect.py --toggle can_modify`.
  Once toggled to `true`, do not ask again for subsequent modifications.
- If `can_modify` is `true`: proceed without asking.

The `/forget` skill checks `can_forget` separately — see the forget workflow.

Wiki page **structure** (frontmatter, sections, index entry) is created by deterministic
Python scaffolds. The agent writes **content only** into existing scaffolded pages.

- Source pages: `python tools/ingest.py --init <id>` creates the scaffold
- Entity/concept pages: `python tools/ingest.py --new-page --type entity|concept --name "Name" --tag <tag>`
- The agent must **NEVER** create entity or concept pages directly with the Write tool.
  Always call `--new-page` first, then fill the `## Description` section.

Workflows for ingest, query, lint, and heal are defined in the `/maintainer` and `/healer` skills.

## Project Structure Recovery

If you encounter a `FileNotFoundError`, `No such file or directory`, or any missing
path error during wiki operations, run `python tools/scaffold.py --fix` before retrying.
This regenerates any missing directories or scaffold files without affecting existing content.

## Dependency Recovery

If you encounter an `ImportError` or `ModuleNotFoundError` when running a Python tool,
run `python tools/scaffold.py --reset-deps` and then invoke `/setup` to reinstall
and verify all dependencies.

## User Output

When the user asks to generate files that are NOT wiki content (reports, presentations,
spreadsheets, exports, etc.), save them in `freespace/` by default. This is the user's
personal workspace — anything placed there has no effect on JanusLM's wiki or workflows.

## Directory Layout

```
raw/              # Source documents (or anonymized output from maskzone)
maskzone/         # Privacy mode entry — files here get anonymized, originals stay
processed/        # Original binaries archived after conversion
heal_queue.json   # Persistent heal state (pending/completed/skipped items)
rejected.json     # Rejection history (auto-managed by ingest.py --skip)
wiki/             # Knowledge base (read freely, modify only via /maintainer)
graph/            # Auto-generated graph data
tools/            # Python scripts (deterministic utilities only)
freespace/        # User's personal workspace — no effect on JanusLM
```

## Naming Conventions

- Source slugs: `kebab-case`
- Entity pages: `TitleCase.md` (e.g. `OpenAI.md`)
- Concept pages: `TitleCase.md` (e.g. `RAG.md`)

## Privacy Mode

JanusLM supports an optional **privacy mode** that anonymizes PII locally
before any data reaches external agents or services. Activate with `/privacy-mode`
or by asking in natural language (e.g. "enable privacy mode",
"anonymize everything", "don't send data externally").

When active:
- Place documents in `maskzone/` instead of `raw/`
- A deterministic hook extracts text and masks PII on-device before the agent starts
- Originals stay in `maskzone/` — the user removes them manually when ready
- The agent only ever sees anonymized text

Flag: `can_anonymize_pii` in `wiki/.protect`
Dependencies marker: `.privacy-deps-ok`
Model: OpenAI Privacy Filter (Apache 2.0, runs locally via ONNX Runtime)

To disable: say "disable privacy mode" — the flag toggles off,
deps stay cached for instant reactivation.
