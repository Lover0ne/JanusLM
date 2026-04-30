# Tools

This folder contains deterministic Python utilities for wiki management.

Key scripts:

- `ingest.py` — document ingestion pipeline (queue, scaffold, validate)
- `health.py` — structural integrity checks on the wiki
- `build_graph.py` — build knowledge graph from wikilinks
- `print_graph.py` — render interactive HTML visualization
- `heal.py` — detect and fix structural problems
- `wiki_stats.py` — KB statistics dashboard
- `privacy_filter.py` — local PII anonymization
- `help.py` — capability guide and discovery

These scripts are invoked by the agent or by the user via command line.
Do not modify unless you know what you are doing.
