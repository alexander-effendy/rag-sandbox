"""
A minimal RAG implementation, built for learning rather than for production.

WHAT AN __init__.py IS FOR
==========================
This file is what makes the `rag/` directory an importable Python package. It
also re-exports the useful names, so callers can write

    from rag import answer, NumpyVectorStore

instead of having to know which module each one lives in

    from rag.pipeline import answer
    from rag.store import NumpyVectorStore

Both still work. The short form is just a nicer front door.

WHERE TO START READING
======================
In the order data actually flows:

    1. rag/chunking.py        markdown -> small overlapping pieces of text
    2. rag/ollama_client.py   text -> vectors, and prompt -> answer
    3. rag/store.py           the search itself (this is the interesting one)
    4. rag/pipeline.py        the four steps joined into one function

Then the scripts, which are thin wrappers over the above:

    scripts/ingest.py         build the index (run this first)
    scripts/ask.py            ask a question
    scripts/evaluate.py       score the whole thing
"""

from .chunking import Chunk, chunk_directory, chunk_markdown
from .pipeline import Answer, answer, answer_without_rag, retrieve
from .store import NumpyVectorStore, VectorStore

# __all__ declares the public API: it is what `from rag import *` would pull
# in, and it signals to readers which names are intended for outside use.
__all__ = [
    "Answer",
    "Chunk",
    "NumpyVectorStore",
    "VectorStore",
    "answer",
    "answer_without_rag",
    "chunk_directory",
    "chunk_markdown",
    "retrieve",
]
