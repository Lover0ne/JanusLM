# JanusLM

> Two-faced AI agent. One side reads, catalogs, connects. The other acts: writes documents, analyzes data, answers questions. Every document in makes answers sharper. Every answer reveals what's still missing. Knowledge and action, in a loop.

<p align="center">
  <img src="https://github.com/user-attachments/assets/d9dbd0f7-3fda-4fe1-9683-401182f99542" alt="JanusLM" width="600" />
</p>

---

## 🏛️ What is this?

JanusLM turns any AI coding agent into a general-purpose assistant backed by a structured, multi-project knowledge base.

It builds on the **LLM Wiki** concept by Andrej Karpathy — a knowledge management system fully maintained by an AI agent. You drop documents in, the agent decomposes them into structured, interlinked pages: sources, entities, concepts, and syntheses. It maintains an index, a living overview, and a knowledge graph.

### Why not RAG?

|                    | Traditional RAG                               | LLM Wiki approach                                        |
| ------------------ | --------------------------------------------- | -------------------------------------------------------- |
| **Knowledge**      | Re-derived from scratch on every query        | Compiled once at ingest, kept current over time          |
| **Retrieval unit** | Raw document chunks                           | Structured, interlinked wiki pages                       |
| **Cross-refs**     | Constructed at query time, if at all          | Pre-built during ingest — entities and concepts linked   |
| **Contradictions** | May surface at query time, often missed       | Detected and flagged at ingest time                      |
| **Accumulation**   | None — each query starts from zero            | Compounding — every new source enriches the whole wiki   |

### Where I saw room to grow

As powerful as the idea is, working with it across multiple projects revealed two natural limits:

> [!NOTE]
> **No project separation.** The wiki treats all knowledge as a single flat space. Ingesting documents from different projects means entities and concepts merge together — a page like `OpenAI.md` blends information from every context. Great for discovery, harder when you need a clean, scoped answer.

> [!NOTE]
> **Single-purpose agent.** The instruction file is entirely dedicated to wiki workflows. The agent excels at knowledge operations, but asking it to generate a Word report or a slide deck falls outside its scope.

---

## 💡 The Idea

Two goals:

1. **A general-purpose agent** that uses the wiki as a knowledge base but is free to do anything else — Word documents, slides, analysis, web research, and more
2. **Project separation** — every ingested document belongs to a specific domain, and queries can filter by project without cross-contamination

---

## ⚡ Quick Start

```bash
git clone https://github.com/YOUR_USER/JanusLM.git
cd JanusLM
```

Open the repo in any coding agent — each one picks up its own instruction file automatically:

```bash
claude       # reads CLAUDE.md
codex        # reads AGENTS.md
gemini       # reads GEMINI.md
```

Works with **Cursor** (`.cursorrules`) and **Cline** (`.clinerules`) too.

On the very first prompt, the agent detects that Python dependencies are missing and installs them automatically — no manual setup needed. In **Claude Code**, a `UserPromptSubmit` hook handles this transparently; other agents check for the `.deps-ok` marker file and run `pip install` if it's missing.

Drop any file into `raw/` — markdown, PDF, Word, Excel, whatever you have. Then ask the agent to ingest it:

```
ingest raw/my-document.md
```

The ingest pipeline handles everything from there — conversion, domain validation, content extraction, discovery, and post-validation. See [Ingest Queue](#ingest-queue) for the full breakdown.

## 📖 Usage

You can talk to the agent in natural language or use shorthand:

```
ingest raw/report.md                       # add a document to the wiki
query: what are the main themes?           # ask a question across the KB
lint                                       # spot orphans, broken links, gaps
build graph                                # generate the knowledge graph
```

Or just say what you need:

```
"Ingest this paper and tag it as ai-strategy"
"What does the wiki say about RAG across all projects?"
"Are there contradictions in project-alpha?"
"Build the graph and tell me what's most connected"
```

JanusLM is multi-agent by design, optimized for Claude but it works with any coding agent that can read markdown instructions and run Python scripts — the workflows and tools are the same for everyone.

## 🟣 Obsidian Compatibility

Every page in the wiki uses `[[wikilinks]]`, so the whole `wiki/` folder already works as an [Obsidian](https://obsidian.md) vault. If you have an existing vault, just symlink:

```bash
ln -sfn /path/to/JanusLM/wiki ~/your-vault/wiki
```

A couple of settings that help:
- **Graph View**: exclude `index.md` and `log.md` (`-file:index.md -file:log.md`) — they connect to everything and clutter the view
- **Dataview**: the agent injects YAML frontmatter on every page (`type`, `tags`, `sources`) — Dataview queries work out of the box

## 🔧 Built-in Capabilities

### Ingest Queue

The ingest pipeline is backed by a persistent queue with a deterministic state machine. When you say "ingest everything", the system scans `raw/`, deduplicates against what's already in the wiki, and queues every new file. Each item progresses through defined stages: tag assignment, domain validation, page scaffolding, content extraction, discovery review, post-validation. You can process files in batches, interrupt and resume across sessions — the queue picks up where you left off. Non-markdown files are automatically converted and validated before entering the pipeline, with original binaries archived in `processed/`.

### The Blind Review Pattern

A recurring architectural pattern in JanusLM. Wherever the agent's reasoning and deterministic analysis both contribute to a decision, they run independently to prevent anchoring bias:

1. **Phase A — Agent reasons blind.** The agent reads the material and forms its own judgment — no scores, no tool output, no external data. Pure reasoning.
2. **Phase B — Deterministic tool runs independently.** A Python script performs mechanical analysis — frequency counts, text matching, scoring — with no awareness of the agent's assessment.
3. **Phase C — Agent compares and decides.** The agent sees both evaluations side by side. Agreement means high confidence. Disagreement becomes a signal worth investigating.

This pattern appears in three workflows:

| Workflow | Phase A (agent blind) | Phase B (deterministic) | Phase C (comparison) |
|---|---|---|---|
| **Domain validation** | Semantic affinity assessment | TF-IDF + entity/concept overlap scoring | Final verdict with discrepancy analysis |
| **Discovery review** | Entity/concept discovery during content writing | Term frequency extraction from source document | Check for high-frequency terms not yet linked |
| **Query search** | Alias analysis — synonyms, related terms, acronyms | Exhaustive wiki page scanning by term matching | Read matched pages, synthesize answer |

Why it matters: if the agent sees "63% PROCEED" before reading a document, it tends to align with the number. If it sees a term frequency list before doing discovery, it anchors on those terms instead of reasoning from the text. The blind review ensures both perspectives are genuinely independent.

### Discovery Review

During ingest, the agent reads the source document and identifies entities and concepts to link — blind, without any tool assistance. Then a deterministic tool (`extract_terms.py`) extracts every word from the original document with its frequency count, along with the list of terms already linked via `[[wikilinks]]`.

The agent compares the two: high-frequency terms that aren't linked yet may be entities or concepts it missed. This catches the things a human reader would notice ("this document mentions 'governance' six times but there's no link to the Data Governance page").

No filtering, no stopwords, no language-specific logic. The tool provides raw data; the agent decides what's noise and what's relevant.

### Missing Link Post-Validation

After the agent writes a wiki page, the validation step now checks for a specific blind spot: existing wiki pages whose names appear in the source document but weren't linked with `[[wikilinks]]` in the wiki page. If the source mentions "OpenAI" four times and there's an `OpenAI.md` entity page but no `[[OpenAI]]` link, the validator flags it.

These are non-blocking warnings — the validation still passes, but the agent reviews each warning and adds links where appropriate. It's a safety net that catches the links a thorough reader would expect to see.

### Project Self-Heal

If something breaks in the project structure — a missing folder, a deleted scaffold file — the agent can fix it automatically. Running `/scaffold` checks every expected directory and file against the project blueprint, and recreates whatever is missing without touching existing content. The agent also runs this on its own when it encounters a missing path error during normal operations, so most structural problems are resolved before you even notice them.

### Auto-Install Dependencies

Python dependencies are detected and installed automatically on first launch — no manual setup needed. In Claude Code, a lightweight hook checks for a `.deps-ok` marker on every prompt; other agents check for the same marker from their instruction files. Either way, the first time you open the project the agent handles everything.

### Deterministic Log System

Every wiki operation — ingest, heal, lint, graph — is recorded in `wiki/log.md` through a centralized log writer. The format is structured and machine-parseable: each entry carries a timestamp, operation type, title, and project tag. Only validated operations are accepted, and only authorized workflows can write to the log. A separate report tool can query the history and produce structured summaries filtered by operation, tag, or time range.

### Heal Mechanism

The `/heal` command finds and fixes wiki problems: orphan pages, broken wikilinks, missing entities, tag mismatches, incomplete pages. It works as a persistent state machine — first it detects all issues and queues them, then the agent processes them in batches. Progress is saved in `heal_queue.json`, so you can interrupt and resume across sessions. Each item is marked as completed or skipped with a reason, giving you a clear audit trail of what was fixed and what was left untouched.

### Forget with Safety Lock

The `/forget` command removes information from the wiki — a whole project, a single entity, or a concept. Before any deletion, the agent checks a safety flag. When wiki protection is on, all destructive operations are blocked — no exceptions. This prevents accidental data loss during normal work. Turn protection off explicitly when you're ready to prune, then turn it back on when you're done.

### File Conversion with Validation

The wiki works with Markdown. If your sources are in other formats, the agent handles the conversion automatically during ingest (or on demand with `/convert`). It writes a conversion script and a validation script in `.staging/`, runs both, and loops until validation passes. Every converted file is verified before it enters the pipeline — no silent failures.

### Knowledge Graph

The wiki can be visualized as an interactive knowledge graph. Running `build graph` extracts all `[[wikilinks]]`, detects communities via Louvain, and produces a structural report (orphans, phantom hubs, god nodes, fragile bridges). Then `print graph` renders the data into a self-contained `graph/graph.html` you can open in any browser. The graph supports project-specific views — pass a `--tag` filter and you get a subgraph limited to pages from a single project.

### Wiki Statistics

Running `stats` gives you a dashboard of the wiki's current state: page counts by type (sources, entities, concepts), tag distribution across projects, link density, orphan count, and overall coverage metrics. A quick way to understand how the knowledge base is growing and where the gaps are.

### Wiki Permission Flags

Two independent safety flags control destructive operations: `can_modify` (direct wiki edits outside workflows) and `can_forget` (deletions via the forget workflow). Both default to off. You can check or toggle them at any time — "lock the wiki", "enable modifications", "turn off protection" all work in natural language.

### Beta: Privacy Mode

JanusLM can anonymize documents locally before any data reaches the AI agent, so that no personally identifiable information ever leaves your machine.

When privacy mode is active, the ingest workflow changes: instead of placing files in `raw/`, you place them in `maskzone/`. A `UserPromptSubmit` hook intercepts every prompt, detects pending files in `maskzone/`, and runs a local PII detection model before the agent sees anything. The model identifies names, emails, phone numbers, dates, addresses, URLs, account numbers, and secrets — replacing each with a category placeholder (`[NAME]`, `[EMAIL]`, `[PHONE]`, etc.). The anonymized text is written to `raw/` as a clean markdown file. Originals stay in `maskzone/` — you remove them when you're ready. By the time the agent starts processing, it only ever sees the redacted version.

The detection model is [OpenAI Privacy Filter](https://huggingface.co/openai/privacy-filter), released under the **Apache 2.0** license. It runs entirely on-device via ONNX Runtime — no API calls, no cloud processing, no data transmitted externally. Model weights are cached locally in `~/.cache/huggingface/` after the first download.

**First-time activation** installs the required Python dependencies, downloads the model, runs a test inference to verify detection accuracy, and sets the `can_anonymize_pii` flag — all automatically after user confirmation. **Subsequent toggles** just flip the flag; dependencies and model stay cached for instant reactivation with no re-download.

| What changes | Privacy mode OFF | Privacy mode ON |
|---|---|---|
| **Document entry point** | `raw/` | `maskzone/` |
| **PII handling** | None — agent sees full text | Detected and replaced before agent access |
| **Original files** | Preserved in `raw/` | Kept in `maskzone/` — user removes manually |
| **Agent visibility** | Full document content | Redacted text only — no PII exposure |

> [!NOTE]
> Privacy mode currently requires **Claude Code**. The anonymization pipeline relies on a `UserPromptSubmit` hook that runs deterministic Python code before each prompt — a mechanism specific to Claude Code's hook system. Other agents (Cursor, Gemini CLI, Codex) can read the wiki and run all other workflows normally, but the automatic pre-prompt anonymization is not available outside Claude Code.

Activate with `/privacy-mode` or in natural language — "enable privacy mode", "anonymize everything", "don't send data externally". Disable the same way — dependencies stay cached, ready for instant reactivation.

> [!CAUTION]
> **Disclaimer.** Privacy mode is a best-effort convenience layer. The underlying model may miss, misclassify, or only partially redact certain PII — especially in non-English text, domain-specific jargon, or unconventional formats. This feature **does not replace** enterprise-grade Data Loss Prevention (DLP) systems, data classification policies, or dedicated anti-exfiltration controls. If your organization handles regulated data (GDPR, HIPAA, PCI-DSS, etc.), treat privacy mode as an additional safeguard, not as your primary line of defense.

---

## 🛠️ Commands

Everything you can do with JanusLM — via the agent or from terminal.

### Knowledge Base

| Command | What it does |
|---|---|
| `ingest raw/doc.md` | Read a document, extract entities and concepts, create/update wiki pages |
| `query "your question"` | Search the wiki and synthesize an answer with citations |
| `lint` | Find orphan pages, broken wikilinks, missing entities, tag mismatches, content gaps |
| `health` | Structural integrity checks — empty pages, index sync, log coverage, tag validation |
| `heal` | Auto-fix issues found by health and lint (creates missing pages, repairs links) |
| `stats` | Wiki dashboard — page counts by type, tag distribution, link density |
| `forget` | Remove a project, entity, or concept from the wiki (with safety confirmation) |

### Knowledge Graph

| Command | What it does |
|---|---|
| `build graph` | Extract wikilinks, detect communities, generate graph data and analysis report |
| `print graph` | Render interactive `graph.html` from the graph data |

### File Conversion & Maintenance

| Command | What it does |
|---|---|
| `/convert` | Convert any non-markdown file to markdown for ingest |
| `/privacy-mode` | Enable or disable local PII anonymization (Claude Code only) |
| `/scaffold` | Check project structure and recreate any missing directories or scaffold files |
| `/setup` | Install or reinstall Python dependencies |

All scripts accept `--help` for full options. Most support `--json` for machine-readable output.

---

## 🏗️ How I Built It

### Agent restructuring

<table>
<tr>
<td width="50%">

**Before** — a single instruction file with all wiki workflows baked in. The agent was a dedicated "wiki maintainer" and nothing else.

</td>
<td width="50%">

**After** — lean instructions define a general-purpose agent with KB access. Heavy wiki workflows live in a `/maintainer` skill, loaded only when needed. Other skills (docx, pptx, frontend...) slot in the same way.

</td>
</tr>
</table>

<p align="center">
  <img src="https://github.com/user-attachments/assets/0c4eb0b0-d40a-4aa6-997e-0fb6deb4f73c" alt="JanusLM Agent Architecture" />
</p>

### Deterministic + semantic architecture

JanusLM draws a clear line between what the agent does and what Python scripts do. Structural operations — scaffolding pages, validating frontmatter, counting terms, scanning for wikilinks, tracking queue state — are handled by deterministic tools that produce the same output every time. Semantic operations — reading documents, understanding meaning, finding correlations, writing content — are handled by the agent.

The two layers reinforce each other. The agent can't forget to check for broken links because a script does it mechanically. The script can't understand whether a document belongs to a project because that requires reasoning. Neither layer works alone; together they cover each other's blind spots.

Every Python tool in `tools/` follows the same contract: reads files, produces JSON or a table to stdout, never calls an API, never modifies wiki content directly. The agent orchestrates the tools through skill-defined workflows.

### Mandatory tagging system

Every ingested document receives a mandatory **project tag** (e.g. `project-alpha`, `ai-strategy`, `client-onboarding`). The agent proactively asks for it before every ingest — no document enters without a domain.

<details>
<summary><strong>How tags propagate</strong></summary>

- The **source page** receives the project tag
- Every **entity page** touched gets the tag added (without removing existing tags)
- Every **concept page** touched gets the tag added
- If an entity/concept page already exists with a different project tag, new content goes under a separate heading (`## In project-alpha`)

</details>

### Domain validation

Before every ingest, the agent validates that the new document actually belongs to the declared project. The validation uses a **blind review** process — the two evaluations run independently to avoid anchoring bias.

- **Step 1 — Parallel evaluation.** The agent reads the document and the existing wiki pages for that project, then forms its own semantic judgment — blind, without seeing any score. Independently, the deterministic script (`tools/validate_domain.py`) computes the quantitative analysis (TF-IDF, entity/concept overlap).
- **Step 2 — Comparison and verdict.** The agent sees both evaluations side by side, flags any discrepancy, and produces the final affinity decision. When the two disagree — a document that scores low lexically but is thematically relevant, or vice versa — the discrepancy itself becomes a valuable signal for the user.

Example output from the deterministic analysis:

**Document:** `raw/article.md` | **Tag:** `project-alpha` | **Corpus:** 12 pages (7 entities, 5 concepts)

| Metric                       | Score      | Detail                                          |
| ---------------------------- | ---------- | ----------------------------------------------- |
| Lexical similarity (TF-IDF)  | 72%        | cosine similarity on TF-IDF vectors             |
| Entity overlap               | 4/7 (57%)  | OpenAI, RAG, LangChain, Anthropic               |
| Concept overlap              | 3/5 (60%)  | PoC, Fine-tuning, Embeddings                    |
| **Composite score**          | **63%**    | weights: lexical 0.4, entity 0.3, concept 0.3  |

The validation is **advisory, never blocking** — the user always has the final word.

<p align="center">
  <img src="https://github.com/user-attachments/assets/8b6f412c-07be-4166-8733-04580e25aa7c" alt="JanusLM Ingest Workflow" />
</p>

| Affinity                    | Behavior                                                          |
| --------------------------- | ----------------------------------------------------------------- |
| Both evaluations agree      | Proceed automatically or warn, depending on the level             |
| Evaluations disagree        | Present both to the user with an explanation of the discrepancy   |
| First document for this tag | Skip validation entirely (no existing corpus to compare against)  |

If the user declines the ingest, the document is tracked in `rejected.json` with the reason for rejection. If the same document is submitted again later, the agent completes the full blind review first and only then surfaces the previous rejection — keeping the new evaluation free from bias.

<details>
<summary><strong>How it works under the hood</strong></summary>

#### Phase A — Semantic evaluation (blind)

The agent reads the new document and the existing wiki pages for the target project. It forms its own assessment of thematic relevance — without running the quantitative script and without seeing any score. This avoids anchoring bias: if the agent saw "63% PROCEED" first, it would tend to align with the number instead of reasoning independently.

#### Phase B — Quantitative scoring (`tools/validate_domain.py`)

A Python script that runs independently with zero API calls. It compares the new document against all wiki pages tagged with the target project:

1. **TF-IDF + Cosine Similarity** — vectorizes both the new document and the concatenated corpus text, then computes cosine similarity. Captures vocabulary and terminology overlap.

2. **Entity Overlap** — collects known entities from the project's wiki pages, normalizes names, and searches for them in the new document using exact matching for short names and fuzzy matching (rapidfuzz, threshold 85%) for longer names.

3. **Concept Overlap** — same mechanism applied to concepts (ideas, frameworks, methods).

4. **Composite Score** — weighted average of the three signals:

   | Signal                          | Weight | What it captures                    |
   | ------------------------------- | ------ | ----------------------------------- |
   | Lexical similarity (TF-IDF)     | 40%    | Vocabulary and terminology overlap  |
   | Entity overlap (Jaccard + fuzzy) | 30%    | Shared people, companies, products |
   | Concept overlap (Jaccard + fuzzy)| 30%    | Shared ideas, frameworks, methods  |

#### Phase C — Comparison and verdict

The agent now sees both evaluations side by side — its own blind assessment and the quantitative report. If they agree, the decision is high-confidence. If they disagree, the discrepancy is surfaced to the user with an explanation (e.g. "the document uses new terminology but is thematically aligned with the project").

Only after producing the verdict, the agent checks `rejected.json` for previous rejection entries matching the document. If found, the previous rejection reason is included in the report to the user — but never before the blind evaluation, to avoid anchoring on the old judgment. Rejected documents are tracked in a separate file from `wiki/log.md` to prevent semantic contamination when the agent reads the ingest history.

</details>

---

## 🔍 The Three-Axis Search Model

The knowledge base is navigable across three dimensions. The agent classifies each query and applies the right search strategy automatically.

The knowledge base can be modeled as a sparse matrix where **rows are pages** (sources, entities, concepts) and **columns are project tags**. A cell is filled when a page belongs to a project. Every query triggers a classification step that determines how to slice this matrix:

| Query type     | Matrix operation                                 |
| -------------- | ------------------------------------------------ |
| Project search | Column slice — read only pages in that column    |
| Concept search | Row slice — read one page across all columns     |
| Cross-project  | Join — intersect rows and columns, find patterns |
| Operational    | Bypass — skip the matrix entirely                |

The agent classifies intent before any retrieval. If the query is operational (no KB context needed), it skips the knowledge base entirely. If uncertain, it checks the index — if nothing matches, it moves on without forcing wiki content into the answer.

<p align="center">
  <img src="https://github.com/user-attachments/assets/546b7b48-b690-4dfc-9592-301b99d207f0" alt="JanusLM Three-Axis Search Model" />
</p>

### Axis 1 — Project Search (vertical)

Filter by tag. Read only pages from that project. Isolated answer, zero contamination.

> *"What is BP59 in project alpha?"*

### Axis 2 — Concept Search (cross-cutting)

Read the concept page that aggregates knowledge from all projects. Answer organized by project, never blended.

> *"What is a PoC?" — shows how each project uses it*

### Axis 3 — Cross-Project Search

Cross-reference tags and concepts. Show shared patterns and differences across projects.

> *"Which projects use RAG? What do they have in common?"*

### How search actually works

Every query goes through the blind review pattern in three phases:

1. **Alias analysis (blind).** The agent reads the user's question and generates synonyms, related terms, acronyms, alternate spellings — 10 to 30 terms — through pure reasoning. No tools, no file reads. This ensures the search casts a wide net based on the agent's own understanding.

2. **Mechanical search.** All terms are piped into `wiki_search.py`, which scans every wiki page for matches. The tool returns a ranked list — pages sorted by how many distinct terms matched, with title, description, tags, and wikilinks for each result. For project searches, a `--tag` filter limits results to one domain.

3. **Read and synthesize.** The agent reviews the search results, reads every page that matched strongly or whose description is clearly relevant, and only then produces the answer — with inline `[[wikilink]]` citations and a clear separation between KB knowledge and general knowledge.

The agent thinks first, the tool searches exhaustively, and no page is missed because of a vocabulary mismatch.

| Situation                                            | Behavior                                                    |
| ---------------------------------------------------- | ----------------------------------------------------------- |
| Question about topics, projects, or concepts         | **Searches** the KB using the appropriate axis              |
| Operational request (generate a doc, convert a file)  | **Skips** the KB entirely                                   |
| Uncertain relevance                                  | **Checks** the index quickly; moves on if nothing matches   |

---

## 🎯 Why This Matters

**One entry point, no more session sprawl.** You don't need endless parallel sessions with your AI assistant, each with its own fragile context. One interface, one knowledge base that grows with you. You go back to interacting with AI the way it felt at the beginning — a single, general conversation — except now it has memory.

**But you're not locked in.** Nothing stops you from running multiple sessions if you want to. They won't contaminate each other — project tags keep domains clean. Use one session or ten, the knowledge stays organized either way.

**Maintainable and scalable.** Skills are modular — add a new workflow without touching the core instructions. Tags scale naturally — your tenth project works exactly like your first. The knowledge base grows without degrading, because every piece of information has a domain and a structure. No monolithic prompt to maintain, no fragile context to protect.

**Works with any AI assistant.** The knowledge base is plain markdown with frontmatter and wikilinks — no proprietary format, no vendor lock-in. While JanusLM was built on Claude Code, the wiki structure works with any AI tool that can read files: Cursor, Windsurf, GitHub Copilot, Gemini CLI, ChatGPT with file access, or any future assistant. The knowledge you build is yours, portable, and readable by humans and machines alike.

**Search, transform, deliver.** Every task follows the same empowered workflow: the agent searches the knowledge base first, enriches its understanding with what you've already validated, then transforms that into the output you need. The result isn't generic — it's informed, refined, and grounded in your accumulated knowledge.

> Research → Transform → Result

---

## 📌 Tips

- Ask anything in natural language — "what was done recently?", "is the wiki healthy?", "show me the graph for project-alpha" all route to the right tool automatically
- Every script in `tools/` accepts `--help` and most support `--json` for machine-readable output
- `python tools/health.py` checks KB integrity; `lint` finds semantic gaps and suggests what's missing
- Everything is plain markdown — portable, version-controllable, no vendor lock-in
- Drop files into `raw/` from anywhere — Obsidian Web Clipper, a browser extension, or just copy-paste. Next time you open the agent, they're ready to ingest
- Use `freespace/` for your own files — reports, exports, scratch work. Nothing there affects the wiki

---

## 📁 Directory Layout

```
raw/              # Source documents (or anonymized output from maskzone)
maskzone/         # Privacy mode entry — files here get anonymized, originals stay
processed/        # Original binaries archived after conversion
rejected.json     # Documents declined during domain validation
heal_queue.json   # Persistent heal state (pending/completed/skipped items)
ingest_queue.json # Persistent ingest state (pending/completed/skipped items)
wiki/             # Knowledge base (read freely, modify only via /maintainer)
  index.md    # Catalog of all pages
  log.md      # Operation history (ingest, lint, health, graph)
  sources/    # One summary page per ingested document
  entities/   # People, companies, projects, products
  concepts/   # Ideas, frameworks, methods, theories
graph/            # Auto-generated graph data
tools/            # Deterministic Python scripts (health, ingest, graph, search, validation)
freespace/        # User's personal workspace — no effect on JanusLM
```

> The scripts in `tools/` resolve paths relative to this structure. Altering the directory layout may cause unexpected behavior.

> [!NOTE]
> **`freespace/`** is your personal workspace. Store your own files, create subdirectories, generate documents with the agent — anything you put here has no effect on JanusLM's wiki, tools, or workflows.

## 📦 Dependencies

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Codex](https://openai.com/codex), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Cursor](https://cursor.com), [Cline](https://cline.bot) — any agent that reads a config file
- [NetworkX](https://networkx.org) + Louvain + [vis.js](https://visjs.org) — knowledge graph
- No server, no database — everything is plain markdown files

Python dependencies (`requirements.txt`) are installed automatically on first use — no manual `pip install` needed. The mechanism is a two-layer design:

| Layer                    | What                 | How                                                                                                     |
| ------------------------ | -------------------- | ------------------------------------------------------------------------------------------------------- |
| **Hook** (deterministic) | Detects missing deps | Checks if `.deps-ok` exists — if not, signals the agent. Cost: <1ms per prompt.                         |
| **Skill** (intelligent)  | Installs deps        | Claude reads the `/janus-setup` skill, runs `pip install`, verifies imports, handles errors and retries.|

Once installed, a `.deps-ok` marker file is created and the hook stays silent on all subsequent prompts. To force a reinstall, delete `.deps-ok` or run `/setup`.

> [!NOTE]
> The hook mechanism is Claude Code-specific (via `UserPromptSubmit` in `.claude/settings.json`). Other agents (Codex, Gemini CLI, Cursor, Cline) use a simpler check: they read the `.deps-ok` marker from their own instruction files and run `pip install` if it's missing.

---

If you find JanusLM useful, share it with someone who might benefit from it. Word of mouth is the best way to help this project grow.

## License

[MIT](LICENSE.md)
