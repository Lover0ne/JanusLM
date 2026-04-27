# RAG for Customer Service at Acme Corp

Author: Marco Bianchi, AI Lead — Acme Corp
Date: 2026-03-15

## Context

The AI team at Acme Corp implemented a Retrieval-Augmented Generation (RAG) system
to improve customer service. The project was led by Marco Bianchi
in collaboration with OpenAI, using the GPT-4o model as the base.

## Architecture

The system uses a three-phase pipeline:

1. **Embedding**: corporate documents are vectorized with OpenAI's
   text-embedding-3-large model and indexed in Pinecone.
2. **Retrieval**: customer questions are converted to embeddings and compared
   against the index to retrieve the 5 most relevant documents.
3. **Generation**: the retrieved documents are passed as context to GPT-4o,
   which generates the final response.

## Results

- 40% reduction in response times
- 25% increase in customer satisfaction (CSAT)
- 65% automatic coverage of tier-1 requests

## Lessons learned

Retrieval quality critically depends on the chunking strategy.
Chunks that are too large dilute relevance; chunks that are too small lose context.
The team adopted a hybrid approach: 512-token chunks with 64-token overlap.

OpenAI suggested using fine-tuning to improve precision on company-specific
terminology, but the team preferred prompt engineering to maintain
flexibility and reduce update costs.
