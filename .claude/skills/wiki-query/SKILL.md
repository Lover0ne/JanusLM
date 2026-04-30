---
name: wiki-query
description: Query the wiki knowledge base and synthesize an answer. Use when the user asks about topics, projects, people, or concepts that could be in the KB.
---

# Wiki Query

You are the wiki query handler. Follow this workflow to search the knowledge base
and synthesize an answer.

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

If the wiki is empty, say so and suggest running `/wiki-ingest` first.

### Step 5 — Post-synthesis re-search (Phase D)

Before delivering the answer, check whether your own synthesis introduced terms
you didn't search for:

1. Review your synthesized answer from Step 4 and identify terms, proper nouns,
   and concepts that appeared in it but were NOT in your Step 2 term list
2. If no new terms emerged, skip to Step 6 — the alias analysis was complete
3. Pipe the new terms into `wiki_search.py --json` (same `--tag` as Step 3 if applicable)
4. Compare results against Step 3 — keep only pages NOT already in the original result set
5. If new relevant pages appear, read them and enrich the answer
6. If nothing new or nothing relevant, proceed unchanged

Single pass only — do not re-search recursively.

### Step 6 — Deliver

1. Answer using inline citations as `[[PageName]]` wikilinks
2. If no relevant pages exist, answer from general knowledge — don't invent citations
3. Always make it clear what comes from the KB vs general knowledge
4. Include a `## Sources` section at the end listing pages drawn from
