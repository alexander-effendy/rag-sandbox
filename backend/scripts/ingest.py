"""
WHAT THIS SCRIPT DOES -- RUN THIS FIRST
=======================================
Builds the search index. Reads every markdown file in docs/, cuts them into
chunks, turns each chunk into a vector, and saves the result to index/.

    docs/*.md --chunk--> 73 chunks --embed--> 73 vectors --save--> index/

This is the "indexing" half of RAG. It runs ahead of time, once per change to
your documents -- not per question. On this corpus it takes about a second.

RE-RUN IT WHENEVER YOU
======================
  - edit, add, or remove a document in docs/
  - change --chunk-words or --overlap
  - switch embedding models

That last one is not optional. Vectors from two different embedding models
cannot be compared, so a model change without a re-index leaves you with an
index that returns confident nonsense and no error.

USAGE
=====
    python backend/scripts/ingest.py
    python backend/scripts/ingest.py --chunk-words 200 --overlap 50
    python backend/scripts/ingest.py --index /tmp/experiment    # build a second index
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Lets you run this as `python backend/scripts/ingest.py` from the repo root.
# Without it, Python would not find the `rag` package, because it only searches
# the script's own directory (scripts/) rather than backend/, where `rag` lives.
#   __file__          -> .../rag-sandbox/backend/scripts/ingest.py
#   .resolve()        -> absolute path, following any symlinks
#   .parent.parent    -> .../rag-sandbox/backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# `noqa: E402` silences the linter's "imports should be at the top" warning --
# these genuinely have to come after the sys.path line above.
from rag import chunking, ollama_client  # noqa: E402
from rag.store import NumpyVectorStore  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# How many chunks to embed per HTTP request. Batching matters: one request with
# 32 texts is far faster than 32 requests with one text each, because the
# per-request overhead is paid once. Larger batches are not automatically
# better -- eventually the request gets unwieldy and you lose the progress
# display's usefulness.
BATCH_SIZE = 32


def main() -> int:
    """Returns a Unix exit code: 0 for success, 1 for failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    parser.add_argument("--index", type=Path, default=ROOT / "index")
    parser.add_argument("--chunk-words", type=int, default=chunking.CHUNK_WORDS)
    parser.add_argument("--overlap", type=int, default=chunking.OVERLAP_WORDS)
    args = parser.parse_args()

    # ---- Guard 1: an overlap at least as large as the chunk size means the
    # window never advances. chunking._windows() clamps the stride to 1 so it
    # cannot hang, but that would silently produce a nonsense index, so reject
    # it here where we can explain the problem.
    if args.overlap >= args.chunk_words:
        print(
            f"error: --overlap ({args.overlap}) must be smaller than "
            f"--chunk-words ({args.chunk_words})",
            file=sys.stderr,
        )
        return 1

    # ---- Guard 2: check Ollama before doing any work. Chunking first and
    # discovering a missing model afterwards makes it look like the chunking
    # broke. Check the boring preconditions early.
    try:
        ollama_client.health_check()
    except ollama_client.OllamaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # ---- PHASE 1: chunk. Pure text manipulation, no model involved, instant.
    print(f"Reading {args.docs}...")
    chunks = chunking.chunk_directory(
        args.docs, chunk_words=args.chunk_words, overlap_words=args.overlap
    )
    if not chunks:
        print(f"error: no .md files found under {args.docs}", file=sys.stderr)
        return 1

    documents = len({c.source for c in chunks})  # set() to count unique files
    words = sum(len(c.text.split()) for c in chunks)
    print(
        f"  {documents} documents -> {len(chunks)} chunks "
        f"(~{words // len(chunks)} words each, {args.overlap}-word overlap)"
    )

    # ---- PHASE 2: embed. This is the slow part, and where Ollama does work.
    print(f"Embedding with {ollama_client.EMBED_MODEL}...")
    started = time.perf_counter()  # perf_counter is the right clock for timing
    store = NumpyVectorStore()

    # Walk the chunk list in batches of BATCH_SIZE.
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]

        # The actual work: embed this batch's text, hand vectors and chunks to
        # the store together so it can keep them aligned.
        store.add(batch, ollama_client.embed([c.text for c in batch]))

        # end="\r" returns the cursor to the line start without a newline, so
        # the counter overwrites itself instead of scrolling.
        print(f"  {len(store)}/{len(chunks)}", end="\r", flush=True)

    elapsed = time.perf_counter() - started
    # .shape is (n_chunks, n_dims); [1] is the dimensionality -- 384 for
    # all-minilm, 768 if you switch to nomic-embed-text.
    dims = store.matrix.shape[1]
    print(f"  {len(store)}/{len(chunks)} embedded in {elapsed:.1f}s ({dims} dimensions)")

    # ---- PHASE 3: save, so ask.py can load in milliseconds rather than
    # re-embedding the whole corpus on every question.
    store.save(args.index)
    size_kb = (args.index / "embeddings.npy").stat().st_size / 1024
    print(f"Saved to {args.index}/ ({size_kb:.0f} KB)")
    print("\nNext: python backend/scripts/ask.py \"What did the Vandermeer Study find?\"")
    return 0


# Only run main() when this file is executed directly, not when it is imported.
# SystemExit passes the return value out as the process exit code, so shell
# scripts and CI can tell success from failure.
if __name__ == "__main__":
    raise SystemExit(main())
