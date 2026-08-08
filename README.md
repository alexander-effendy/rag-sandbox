# rag-sandbox

Learning Retrieval-Augmented Generation by building it from scratch — no LangChain, no LlamaIndex, no vector database. Runs entirely locally on Ollama.

```
rag-sandbox/
├── backend/      the RAG pipeline — library, CLI, corpus, evaluation
├── frontend/     not built yet (placeholder)
├── openspec/     specifications
└── .venv/        shared virtualenv (Python 3.12)
```

| | |
|---|---|
| **[backend/](backend/README.md)** | Everything that exists today. Two dependencies (`numpy`, `requests`), heavily commented, with a 20-question evaluation harness. **Start here.** |
| **[frontend/](frontend/README.md)** | Placeholder. Needs an HTTP layer on the backend before it can do anything. |
| **[openspec/](openspec/)** | Behaviour specs and design decisions, managed with [OpenSpec](https://github.com/Fission-AI/OpenSpec). |

## Quick start

Run everything from the repo root — the virtualenv is shared.

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
```

```bash
ollama pull llama3.2 && ollama pull all-minilm
```

```bash
.venv/bin/python backend/scripts/ingest.py
```

```bash
.venv/bin/python backend/scripts/ask.py "What did the Vandermeer Study find about protein?"
```

> Python **3.12**, not 3.14 — the system default is 3.14 and several ML packages don't publish wheels for it yet.

## Where it stands

20-question evaluation set, `k=4`:

| | Score |
|---|---|
| Retrieval — correct source in top-4 | **18/18** |
| Answers with RAG | **19–20/20** |
| Answers with the whole corpus stuffed into the prompt | 16/20 |
| Answers with no retrieval at all | 5/20 |

The full walkthrough — how each stage works, what the similarity scores actually mean, and which assumptions failed when measured — is in **[backend/README.md](backend/README.md)**.
