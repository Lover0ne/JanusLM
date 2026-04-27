---
title: "RAG"
type: concept
tags: [project-acme]
last_updated: 2026-04-26
---

## Description

Retrieval-Augmented Generation — architecture that combines document retrieval
and LLM generation. The retrieval provides factual context, reducing
hallucinations and anchoring the response to verifiable sources.

## In project-acme

Three-phase pipeline for customer service at Acme Corp:
[[Embedding]] → retrieval from [[Pinecone]] → generation with GPT-4o ([[OpenAI]]).
Quality depends on the [[Chunking]] strategy (512 tokens, 64 overlap).
Results: -40% response time, +25% CSAT, 65% tier-1 coverage.
See [[rag-customer-service-acme]].
