# Vector Databases

*Synthetic document written for RAG testing. Technical details are broadly accurate; named benchmarks may be fictional.*

## What They Actually Do

A vector database stores embeddings and answers the question "which of these stored vectors are closest to this query vector".

The naive implementation is a single matrix multiplication: compare the query against every stored vector and sort the results. This is exact, trivially correct, and entirely adequate up to roughly 100,000 vectors on modern hardware. Everything a vector database adds beyond this is about scale and operations, not about a fundamentally different algorithm.

What they add is worth being specific about: approximate indexes that avoid comparing against everything, metadata filtering, durable persistence, incremental updates without full reindexing, and concurrent access.

## Approximate Nearest Neighbour Search

Beyond a few hundred thousand vectors, exhaustive comparison becomes too slow for interactive use, and systems switch to approximate search that trades a small amount of recall for a large amount of speed.

HNSW, or Hierarchical Navigable Small World, is the dominant approach. It builds a layered graph where upper layers contain long-range links for coarse navigation and lower layers contain short-range links for refinement. A search descends the layers, greedily moving toward the query. It typically achieves 95 to 99 percent recall while examining a small fraction of the collection.

IVF, or Inverted File Index, takes a different approach: cluster the vectors, then search only the clusters nearest the query. It is cheaper to build than HNSW and slower to query at equivalent recall.

The word "approximate" deserves attention. These indexes can and do miss the true nearest neighbour. At normal recall settings this rarely changes an answer, but it does mean a retrieval failure may be the index rather than the embeddings.

## Choosing an Implementation

ChromaDB is the lowest-friction option for getting started. It installs with pip, runs embedded in the application process, and persists to a local directory with no server to operate. It is well suited to prototypes and single-machine workloads, and less suited to high-concurrency production.

pgvector is an extension to PostgreSQL. Its central advantage is that vectors live in the same database as relational data, so a query can filter by user, date, and permissions in SQL and rank by vector similarity in the same statement. If an application already runs PostgreSQL, pgvector avoids operating a second datastore entirely.

FAISS is a library rather than a database. It provides the index structures and nothing else: no persistence layer, no metadata, no server. It is the right choice when maximum control and performance are needed and the surrounding infrastructure already exists.

Qdrant, Weaviate, and Milvus are purpose-built vector databases aimed at larger deployments, offering horizontal scaling and richer filtering than the embedded options.

## The Migration Path

The pragmatic sequence is to start with brute-force numpy, move to an embedded store such as Chroma when persistence and metadata filtering become tedious to hand-roll, and move to pgvector or a dedicated database when concurrency, scale, or joins against relational data force the issue.

This sequence works because the interface is genuinely small. A vector store needs to add vectors and search them, and any implementation of those two operations can be swapped for another behind a thin abstraction. Code written against a well-defined store interface can change backends in an afternoon, which is why premature selection of a production vector database is a common and avoidable waste of effort.
