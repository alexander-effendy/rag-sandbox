# frontend

Not built yet — this folder is a placeholder so the shape of the project is visible.

## What goes here

A UI over the RAG pipeline in [`../backend`](../backend). The interesting thing to build is not a chat box; it's a view that makes retrieval legible — the thing that's hard to see from a terminal:

- The retrieved chunks with their similarity scores, alongside the answer
- Which source document each chunk came from
- A toggle for the no-retrieval control, so the difference is visible side by side
- The refusal path rendered as a first-class outcome rather than an error

## What has to exist first

There is **no HTTP API yet**. The backend is a Python library plus CLI scripts; `pipeline.answer()` returns an `Answer` object in-process, and nothing serves it over a network.

So the first task is a thin API layer wrapping `pipeline.answer()` — one endpoint taking a question and returning the answer text, the retrieved chunks, their scores, and their sources. `Answer` already carries all of that; it just needs serializing.

The stack is undecided. Nothing here constrains it.
