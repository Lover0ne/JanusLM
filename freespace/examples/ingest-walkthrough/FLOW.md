# Ingest example: rag-customer-service-acme.md

Source document: `00-raw-document.md`

## Phase 1 — Queue

```bash
python tools/ingest.py --add raw/rag-customer-service-acme.md
```

Agent asks: "Which project does this belong to?"
User answers: "project-acme"

```bash
python tools/ingest.py --set-tag abc123 --tag project-acme
```

## Phase 2 — Domain validation

Agent reads the document and evaluates affinity (blind).
Then:

```bash
python tools/validate_domain.py --doc raw/rag-customer-service-acme.md --tag project-acme --json
```

Comparison → PROCEED.

## Phase 3 — Scaffold source page

```bash
python tools/ingest.py --init abc123
```

Produces: `wiki/sources/rag-customer-service-acme.md` → see `01-source-scaffold.md`

## Phase 4 — Agent reads the document + alias analysis + grep

Agent reads `raw/rag-customer-service-acme.md`, produces aliases:
- RAG, Retrieval-Augmented Generation
- OpenAI, GPT-4o, text-embedding-3-large
- Marco Bianchi
- Pinecone
- Embedding, vector embedding
- Chunking, chunk strategy
- Prompt engineering
- Fine-tuning

Grep the wiki to find existing pages.

## Phase 5 — Scaffold entity/concept pages

For each entity/concept found, deterministic scaffold:

```bash
# Entities
python tools/ingest.py --new-page --type entity --name "OpenAI" --tag project-acme
# → {"exists": true, "path": "wiki/entities/OpenAI.md", "tags": ["project-beta"]}
# Page already exists! Agent will add ## In project-acme

python tools/ingest.py --new-page --type entity --name "MarcoBianchi" --tag project-acme
# → {"exists": false, "path": "wiki/entities/MarcoBianchi.md", "created": true}

python tools/ingest.py --new-page --type entity --name "Pinecone" --tag project-acme
# → {"exists": false, "path": "wiki/entities/Pinecone.md", "created": true}

# Concepts
python tools/ingest.py --new-page --type concept --name "RAG" --tag project-acme
# → {"exists": false, "path": "wiki/concepts/RAG.md", "created": true}

python tools/ingest.py --new-page --type concept --name "Embedding" --tag project-acme
# → {"exists": false, "path": "wiki/concepts/Embedding.md", "created": true}

python tools/ingest.py --new-page --type concept --name "Chunking" --tag project-acme
# → {"exists": false, "path": "wiki/concepts/Chunking.md", "created": true}

python tools/ingest.py --new-page --type concept --name "PromptEngineering" --tag project-acme
# → {"exists": false, "path": "wiki/concepts/PromptEngineering.md", "created": true}

python tools/ingest.py --new-page --type concept --name "FineTuning" --tag project-acme
# → {"exists": false, "path": "wiki/concepts/FineTuning.md", "created": true}
```

Scaffold: see `02-entity-scaffold.md`, `03-concept-scaffold.md`

## Phase 6 — Agent writes content

The agent fills:
- Source page → `04-source-filled.md`
- Existing entity page (OpenAI, adds project section) → `05-entity-filled-existing.md`
- New entity page (MarcoBianchi) → `06-entity-filled-new.md`
- New concept page (RAG) → `07-concept-filled.md`
- Updates `wiki/index.md` with all new pages → `08-index-updated.md`

## Phase 7 — Validation

```bash
python tools/ingest.py --validate abc123
```

Checks:
- ✓ Source frontmatter: title, type, tags, last_updated
- ✓ Source sections: Summary, Key Claims, Connections not empty
- ✓ Source in index.md
- ✓ Every [[wikilink]] points to an existing file
- ✓ Every linked page has tag "project-acme"
- ✓ Every linked page has valid frontmatter and index entry

If FAIL → agent fixes → re-validate.

## Phase 8 — Completion

```bash
python tools/ingest.py --done abc123
python tools/log_write.py --op ingest --title "RAG for Customer Service at Acme Corp" --tag project-acme
```
