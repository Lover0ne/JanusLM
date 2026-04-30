# Maskzone

This folder is the privacy-mode entry point for document ingestion.

- Place documents here instead of `raw/` when privacy mode is active
- A local PII filter anonymizes content before the agent processes it
- Original files remain here until you remove them manually
- The agent only sees the anonymized version, never the originals
