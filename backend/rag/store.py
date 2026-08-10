"""
WHAT THIS FILE DOES
===================
Stores the embeddings and answers one question: "given this query vector, which
stored vectors are most similar to it?"

That is what a vector database is for. This file is a complete, working, exact
implementation of it in about 40 lines of NumPy, so you can see that there is
no magic in the concept -- only engineering in the products.

THE ENTIRE SEARCH ALGORITHM IS THREE LINES
==========================================
Everything below is scaffolding around these, in search():

    query  = normalize(query_embedding)   # make it unit length
    scores = self.matrix @ query          # compare against EVERY chunk at once
    top    = np.argsort(-scores)[:k]      # take the k highest

Chroma, pgvector, Pinecone, Weaviate, FAISS -- all of them are answering the
same question those three lines answer. What they add is ANN indexes (so you
do not have to compare against everything), metadata filtering, durable
storage, concurrent writes, and clustering. Real and valuable at scale, but
none of it changes what similarity search *is*.

THE SEAM
========
`VectorStore` below is a Protocol -- an interface. `NumpyVectorStore` satisfies
it. When you port this to ChromaDB, you write a `ChromaVectorStore` that also
satisfies it, and nothing in pipeline.py changes, because pipeline.py only ever
calls .search(). That is why starting with NumPy costs you nothing later.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

import numpy as np

from .chunking import Chunk

# A search result is a chunk paired with its similarity score. This alias just
# makes the type hints below readable.
SearchResult = tuple[Chunk, float]


class VectorStore(Protocol):
    """The interface any vector store must satisfy. THIS IS THE SWAP POINT.

    A Protocol is Python's "structural typing": any class with these methods
    counts as a VectorStore, with no need to inherit from anything. pipeline.py
    is typed against this rather than against NumpyVectorStore, so swapping the
    backend requires no changes there.

    Note how small the surface is -- two methods. That is the argument against
    agonising over which vector database to pick before you have built
    anything: the thing you would be switching between is two methods wide.
    """

    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None: ...
    def search(self, query_embedding: np.ndarray, k: int) -> list[SearchResult]: ...
    def __len__(self) -> int: ...

    def sources(self) -> list[str]:
        """Every distinct source document held, sorted.

        ENUMERATION, as distinct from search -- the third thing a store must do.

        Added for corpus-metadata questions ("how many documents do you have?"),
        which similarity cannot answer because no passage states the answer, but
        which the store knows exactly.

        Deliberately narrower than exposing the chunks themselves: a backend can
        satisfy this with a metadata query rather than materialising every chunk,
        and callers cannot reach past the interface into one store's internals.
        Any store that holds chunks can say which documents they came from, so
        this stays cheap to implement.
        """
        ...


def normalize(vectors: np.ndarray) -> np.ndarray:
    """Scale each vector to length 1, so that a dot product IS cosine similarity.

    WHY THIS MATTERS
    ----------------
    Cosine similarity is the cosine of the angle between two vectors:

                    a · b
        cos(a, b) = ---------
                    |a| × |b|

    It measures *direction only* -- how aligned two vectors are -- and ignores
    magnitude. That is what we want: a long passage and a short question about
    the same topic should score as similar even though their raw vectors differ
    in size.

    Now notice: if |a| and |b| are both 1, the denominator is 1, and the whole
    formula collapses to just `a · b`, the dot product.

    So we normalise once, at index time, and every subsequent query becomes a
    plain matrix multiply -- no division, no norms computed per query. This is
    why production vector stores almost always store normalised vectors.

    THE np.where GUARD
    ------------------
    A zero vector has length 0, and dividing by 0 gives NaN, which would then
    silently contaminate every score it touches. We substitute 1 for any zero
    norm: 0/1 = 0, so the vector stays zero and scores 0 against everything,
    which is the sensible answer for "text with no content".

    `axis=-1` means "compute along the last dimension", i.e. per row. That
    makes this work unchanged on a single (384,) vector and on a whole
    (n_chunks, 384) matrix.
    `keepdims=True` preserves the shape needed for the division to broadcast
    correctly across rows.
    """
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


class NumpyVectorStore:
    """Exact similarity search by comparing against every stored vector.

    This is "brute force" or "exhaustive" search. It is O(n): the work grows
    linearly with the number of chunks. That sounds bad and is completely fine
    up to roughly 100,000 chunks on modern hardware -- our 73 chunks are
    searched in well under a millisecond.

    It is also EXACT. A real vector database at scale uses approximate (ANN)
    indexes like HNSW, which are ~95-99% accurate and can genuinely miss the
    true best match. In a learning sandbox that is the wrong trade: when
    retrieval fails here, you know it is your chunking or your embeddings, and
    never the index quietly approximating.
    """

    def __init__(self) -> None:
        # Two parallel structures that MUST stay aligned:
        #   chunks[i] is the text described by matrix[i]
        # This is the one invariant in this class. Everything else follows.
        self.chunks: list[Chunk] = []

        # Shape (n_chunks, n_dims) -- one row per chunk, 384 columns for
        # all-minilm. Rows are stored already normalised. None until the first
        # add(), because we do not know the dimensionality until the embedding
        # model tells us.
        self.matrix: np.ndarray | None = None

    def add(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        """Add chunks and their vectors. Called in batches by ingest.py."""
        if len(chunks) != len(embeddings):
            # This would otherwise corrupt the chunks[i] <-> matrix[i] alignment
            # and produce answers citing the wrong source -- a bug that looks
            # like a model problem and is not. Fail loudly and immediately.
            raise ValueError(f"{len(chunks)} chunks but {len(embeddings)} embeddings")

        # Normalise on the way in, once, so search never has to.
        normalized = normalize(np.asarray(embeddings, dtype=np.float32))

        self.chunks.extend(chunks)

        # vstack = "vertical stack", i.e. glue the new rows below the existing
        # ones. On the first call there is nothing to stack onto, so we just
        # take the new rows as the whole matrix.
        #
        # Note this reallocates and copies the full matrix on every batch,
        # which is O(n²) across ingestion. Irrelevant at 73 chunks; at a million
        # you would preallocate. Mentioned because it is exactly the kind of
        # thing a real vector database handles for you.
        self.matrix = (
            normalized if self.matrix is None else np.vstack([self.matrix, normalized])
        )

    def search(self, query_embedding: np.ndarray, k: int = 4) -> list[SearchResult]:
        """Find the k chunks most similar to the query. THE CORE OF RETRIEVAL."""
        if self.matrix is None or not self.chunks:
            return []  # empty index -- pipeline.py turns this into "I don't know"

        # STEP 1: normalise the query, matching what we did to the stored rows.
        # .reshape(-1) flattens to 1-D; -1 means "work out this dimension for
        # me". Guards against being handed a (1, 384) instead of a (384,).
        query = normalize(np.asarray(query_embedding, dtype=np.float32).reshape(-1))

        # STEP 2: compare the query against EVERY chunk, in one operation.
        #
        # `@` is matrix multiplication. Multiplying a (73, 384) matrix by a
        # (384,) vector gives a (73,) vector of scores -- one similarity score
        # per chunk. Because both sides are normalised, each score is a cosine
        # similarity in roughly 0..1, where higher means more similar.
        #
        # This single line replaces a Python loop over all 73 chunks, and NumPy
        # runs it as optimised native code. This is the whole reason vector
        # search is fast enough to be practical.
        scores = self.matrix @ query

        # STEP 3: take the k best.
        #
        # np.argsort returns the INDICES that would sort the array, ascending.
        # We want descending, so we sort the negated scores -- the largest
        # score becomes the most negative number and lands first. [:k] takes
        # the top k.
        #
        # (For very large indexes np.argpartition is cheaper, since it avoids
        # fully sorting what you are about to discard.)
        top = np.argsort(-scores)[:k]

        # Look the chunks back up by index -- this is where the chunks[i] /
        # matrix[i] alignment invariant gets used. float() converts NumPy's
        # float32 to a plain Python float so it prints and serialises cleanly.
        return [(self.chunks[i], float(scores[i])) for i in top]

    def __len__(self) -> int:
        """Lets you call len(store). Used for progress output in ingest.py."""
        return len(self.chunks)

    def sources(self) -> list[str]:
        """Distinct source documents, sorted. See VectorStore.sources().

        Note this is a document count, not a chunk count: one document that
        produced nine chunks appears once here and nine times in self.chunks.
        """
        return sorted({chunk.source for chunk in self.chunks})

    def save(self, directory: Path) -> None:
        """Persist the index to disk, so ask.py does not re-embed every run.

        Two files, because the two halves want different formats:
          embeddings.npy  -- NumPy's binary format, compact and fast to load
          chunks.json     -- human-readable, so you can open it and look

        Go and open index/chunks.json at some point. Seeing the actual chunk
        boundaries is the fastest way to build intuition about chunking.
        """
        directory.mkdir(parents=True, exist_ok=True)
        if self.matrix is None:
            raise ValueError("Nothing to save -- the store is empty")

        np.save(directory / "embeddings.npy", self.matrix)

        # asdict() converts each Chunk dataclass into a plain dict for JSON.
        (directory / "chunks.json").write_text(
            json.dumps([asdict(c) for c in self.chunks], indent=2)
        )

    @classmethod
    def load(cls, directory: Path) -> NumpyVectorStore:
        """Rebuild a store from a saved index.

        A @classmethod is called on the class rather than an instance:
            store = NumpyVectorStore.load(path)

        Note the vectors are loaded already normalised, since we normalised
        before saving. Nothing to redo.
        """
        if not (directory / "embeddings.npy").exists():
            # The overwhelmingly likely cause is that ingest was never run, so
            # say that rather than raising a bare file-not-found.
            raise FileNotFoundError(
                f"No index at {directory}. Build one first: python backend/scripts/ingest.py"
            )

        store = cls()
        store.matrix = np.load(directory / "embeddings.npy")
        # Chunk(**c) unpacks each dict back into keyword arguments:
        # {"text": "...", "source": "..."} becomes Chunk(text="...", source="...").
        store.chunks = [
            Chunk(**c) for c in json.loads((directory / "chunks.json").read_text())
        ]
        return store
