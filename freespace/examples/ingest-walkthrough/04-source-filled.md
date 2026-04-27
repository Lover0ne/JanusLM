---
title: "RAG for Customer Service at Acme Corp"
type: source
tags: [project-acme]
date: 2026-04-26
source_file: raw/rag-customer-service-acme.md
last_updated: 2026-04-26
---

## Summary

Acme Corp implemented a [[RAG]] system to automate customer service,
led by [[MarcoBianchi]] in collaboration with [[OpenAI]]. The pipeline uses
[[Embedding]] with text-embedding-3-large, indexing on [[Pinecone]], and generation
with GPT-4o. It reduced response times by 40% and covers 65% of tier-1 requests.

## Key Claims

- Retrieval quality depends on the [[Chunking]] strategy: 512-token chunks with 64-token overlap
- [[PromptEngineering]] is preferred over [[FineTuning]] for flexibility and cost
- 65% automatic coverage of tier-1 requests
- CSAT increased by 25%

## Key Quotes

> "Retrieval quality critically depends on the chunking strategy.
> Chunks that are too large dilute relevance; chunks that are too small lose context."

## Connections

- [[RAG]] — core architecture of the project
- [[OpenAI]] — model provider (GPT-4o, text-embedding-3-large)
- [[MarcoBianchi]] — AI Lead, led the project
- [[Pinecone]] — vector database used for indexing
- [[Embedding]] — phase 1 of the pipeline
- [[Chunking]] — critical strategy for retrieval quality
- [[PromptEngineering]] — chosen approach vs fine-tuning
- [[FineTuning]] — discarded approach, suggested by OpenAI

## Contradictions

- Contradicts [[OpenAI]]'s recommendation on [[FineTuning]]: the team preferred
  [[PromptEngineering]] to maintain flexibility
