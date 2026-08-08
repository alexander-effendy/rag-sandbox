## Why

Retrieval-Augmented Generation is straightforward in principle and easy to get subtly wrong in practice: retrieval fails silently, embedding-model mismatches produce confident nonsense without erroring, and a system that looks correct may simply be reciting the model's training data. This project exists to make each of those mechanics visible and measurable in a working system small enough to read end to end.

This proposal is written **retroactively**: the system described here is already built and passing its evaluation set. The specification captures the behaviour that exists and the decisions behind it, so the next round of work (a ChromaDB backend, PDF ingestion, hybrid search) has a stated contract to build against rather than an implicit one.

## What Changes

- **Local-only RAG pipeline** over Ollama (`llama3.2` for generation, `all-minilm` for embeddings) with exactly two Python dependencies, `numpy` and `requests`.
- **Markdown indexing** — recursive `backend/docs/` traversal, section-aware chunking with configurable size and overlap, heading prefixes carried into every chunk, README exclusion.
- **Exact vector search** — brute-force cosine similarity over a normalised NumPy matrix, exposed behind a two-method `VectorStore` protocol so an approximate/backed store can replace it without touching callers.
- **Grounded answering** — a prompt contract requiring answers to come only from retrieved context, with a mandatory `I don't know.` escape hatch and source citation.
- **Separated evaluation** — retrieval and generation scored independently, plus a no-retrieval control and a whole-corpus "stuffing" comparison, so a quality regression can be attributed to the stage that caused it.
- **Deliberately synthetic corpus** — 10 documents citing fictional studies, so a correct answer demonstrates retrieval rather than recall.

Not a breaking change: this is the project's initial capability set.

## Capabilities

### New Capabilities

- `document-indexing`: Reading markdown documents, splitting them into overlapping context-preserving chunks, embedding them, and persisting a reloadable index.
- `semantic-retrieval`: Embedding a query and returning the most similar chunks by cosine similarity, behind a swappable store interface.
- `grounded-answering`: Composing retrieved chunks into a prompt that constrains the model to the supplied context, and returning the answer alongside its evidence.
- `evaluation-harness`: Scoring retrieval and generation separately against a fixed question set, with no-retrieval and full-context-stuffing baselines.

### Modified Capabilities

None. `openspec/specs/` is currently empty; every capability above is new.

## Impact

**Code** (all present):
- `backend/rag/chunking.py`, `backend/rag/ollama_client.py`, `backend/rag/store.py`, `backend/rag/pipeline.py`
- `backend/scripts/ingest.py`, `backend/scripts/ask.py`, `backend/scripts/evaluate.py`, `backend/scripts/compare_stuffing.py`
- `backend/docs/` (10-document synthetic corpus), `backend/eval/questions.json` (20 cases)

**Runtime dependencies**: a running Ollama server with `llama3.2` and `all-minilm` pulled. Python 3.12 — the machine default is 3.14, which lacks wheels for several ML packages that later work will need.

**Generated, not committed**: `backend/index/` (`embeddings.npy` + `chunks.json`), rebuilt by `backend/scripts/ingest.py` in about a second.

**Explicitly out of scope**, deferred to later changes: ChromaDB and pgvector backends, PDF and non-markdown ingestion, hybrid keyword/vector search, cross-encoder reranking, and chunk-level (as opposed to document-level) retrieval scoring.

## Assumptions

- "Everything we have now" means the system as currently built and verified. Roadmap items in `backend/README.md` section 11 are recorded as out of scope above rather than specified here.
- Requirements are written to describe observable behaviour, so the existing implementation satisfies them; the accompanying tasks are verification rather than construction.
