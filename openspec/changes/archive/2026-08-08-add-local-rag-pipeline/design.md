## Context

See `proposal.md` — Why. Requirements are in `specs/`; this document records the technical choices behind them and the measurements that justified each.

Constraints that shaped the design:

- **Learning is the product.** The system's value is that its mechanics are legible, so abstraction that hides retrieval is a cost rather than a benefit.
- **Fully local.** Generation and embedding both run against a local Ollama server. No network egress, no API keys, no per-query cost — which makes running the evaluation set repeatedly free, and repeated measurement is what most of these decisions rest on.
- **Small corpus.** 10 documents, ~5,500 words, 73 chunks, ~9,000 tokens. Small enough that the entire corpus fits in the generation model's context window, which means retrieval has to justify itself rather than being structurally necessary.
- **Host Python is 3.12.** The machine default is 3.14, which lacks wheels for several packages the deferred roadmap requires.

## Goals / Non-Goals

**Goals:**

- Every stage of the pipeline inspectable from the command line without a debugger.
- Each design decision backed by a measurement against the evaluation set, not by convention.
- A store boundary narrow enough that replacing the backend is provably cheap.
- Failure modes that are reproducible on demand, so the system can be broken deliberately.

**Non-Goals:**

- Throughput, concurrency, or incremental indexing. Full rebuild takes about a second.
- Approximate search. Exactness is worth more here than speed at this scale.
- Framework compatibility. The design deliberately does not target LangChain or LlamaIndex conventions.

## Decisions

### Brute-force NumPy store instead of a vector database

Cosine similarity over a normalised matrix, comparing against every chunk.

Alternatives considered: **ChromaDB** — the natural default, embedded and pip-installable, but it makes retrieval a library call and the mechanics disappear. **pgvector** — requires operating Postgres, so early failures would be infrastructure failures rather than RAG failures. **FAISS** — index structures without persistence or metadata, more machinery than the problem needs.

Rationale: the search is three lines. Exposing them is the point. At 73 chunks the O(n) scan is sub-millisecond, and being exact means a retrieval failure is never attributable to index approximation — which matters when the goal is to learn what actually causes retrieval to fail.

Mitigation for the obvious objection: the store sits behind a two-method interface (add, search), so the ChromaDB port is one new class with no changes to answering logic. The narrowness of that interface is itself the argument that choosing a vector database early is a decision not worth agonising over.

### Two dependencies, and raw HTTP to the model service

Only `numpy` and `requests`. The official client library would shorten the code and hide the request and response shapes, which are exactly what a first-time reader needs to see.

### Vectors normalised once at index time

Cosine similarity is `(a·b)/(|a|·|b|)`. With both operands at unit length the denominator vanishes and similarity is a plain dot product, so each query is one matrix multiply with no per-query normalisation. Zero-norm vectors have their divisor clamped to 1, keeping them at zero rather than producing NaN that would silently contaminate every score it touched.

### Section-aware chunking, 120 words with 30-word overlap

Chunks are cut within markdown sections rather than across whole documents, and each carries its section heading.

Two problems motivate this. A fact spanning a cut is retrievable from neither side — overlap fixes that. A chunk that reads "it should be taken with fat" is uninterpretable alone — the heading prefix fixes that, and it also enriches the embedding, since headings are dense in topic words.

Measured: rebuilding with `--chunk-words 60 --overlap 0` dropped answers from 20/20 to 18/20.

### Similarity floor defaults to zero

A minimum-score filter is the obvious guard against answering from weak matches. Measured across the evaluation set:

| | Score |
|---|---|
| Worst *correct* retrieval | 0.442 |
| Best *should-be-rejected* retrieval | 0.405 |

0.037 apart. Any threshold separating them is fitted to these twenty questions. Score also tracks question length more than relevance — the same fact scores 0.205 or 0.702 depending on phrasing, with the correct document ranked first in both cases — so a floor penalises terse questions rather than irrelevant ones.

Decision: default the floor to zero and let the prompt's grounding rules handle refusal. Both refusal cases pass with no threshold at all.

Consequence worth stating: ranking is trustworthy, absolute scores are not. Scores are comparable within one query's results and not across queries.

### Grounding enforced in the prompt, including against known-correct answers

The prompt requires answers to come only from supplied context, mandates the exact string `I don't know.` when they cannot, and explicitly forbids outside knowledge even where the model is confident.

That last clause is load-bearing. The evaluation set asks for the capital of Australia — a fact the model knows and must still decline, because an answer not supported by the corpus cannot be audited against it.

### Retrieval scored at document level, with the limitation recorded

Retrieval passes if the expected source document appears among the retrieved chunks.

This is too coarse and is knowingly retained. Degrading chunking held retrieval at a perfect 18/18 while answers fell to 18/20: fragmented chunks still surfaced the right file but no longer contained the whole fact. A green retrieval score can therefore hide a real retrieval problem.

Retained because it is honest about what it measures and the failure it hides is itself instructive. Chunk-level scoring is a listed next step.

### Substring matching for answer grading

An answer passes if it contains any of several expected substrings. A model judge would be more faithful but slower, costlier, and non-deterministic — and the harness's job is regression detection, not prose evaluation.

### Synthetic corpus citing fabricated studies

Every document is written for this project, and the studies named in them do not exist. A correct answer to a question the model already knows proves nothing, since retrieval could be entirely broken and the answer would look identical. A correct answer about a fictional study proves retrieval ran.

Measured: 19–20/20 with retrieval, 5/20 without.

Each document declares that it is synthetic and that its figures are fabricated, since the nutrition content is otherwise plausible enough to be mistaken for health information.

### READMEs excluded from the corpus

Found by observation, not by design: `backend/docs/README.md` explains the corpus methodology and was being retrieved as the fourth result for a protein question, because it quotes the phrasing it describes. Documentation about a corpus is not part of it. This generalises to the common practice of pointing a loader at a repository and indexing every markdown file in it.

### Full rebuild rather than incremental indexing

Re-indexing rebuilds everything from current corpus contents. Additions, edits, and deletions are therefore handled by one code path with no invalidation logic and no stale state. At roughly one second per rebuild the cost is not worth optimising.

### Temperature pinned to zero, without claiming determinism

Sampling is pinned so that differences between runs are attributable to the change under test. The service is nonetheless not bit-reproducible: two identical runs scored 20/20 and 19/20. Documented as noise rather than presented as exact reproducibility.

## Risks / Trade-offs

- **Document-level retrieval metric hides chunk-level failures** → Recorded above and in the README; chunk-level scoring is a listed next step.
- **Substring grading cannot detect negation** — "not 1.6 grams" scores as a pass → Acceptable for regression detection; noted where evaluation cases are defined.
- **Scan cost grows linearly, and the matrix is reallocated per ingest batch** → Irrelevant at 73 chunks, and the store interface exists precisely so the backend can be replaced before it matters.
- **Corpus too small to reproduce some failure modes** — retrieving 20 chunks instead of 4 produced no degradation, because 20 chunks is over a quarter of everything and never gets long enough for position effects to appear → Recorded honestly rather than asserted from theory; re-test as the corpus grows.
- **Run-to-run variation of roughly one case** → Treat single-question changes as noise; require a result to survive repeated runs.
- **Embedding-model changes silently invalidate an index** — vectors from different models are not comparable and produce no error → Documented as a mandatory re-index; the deeper fix is recording the embedding model in the index and refusing mismatched loads, which is not yet implemented.
- **Whole-corpus prompting is a real alternative at this size** → Measured rather than dismissed: 16/20 for full-context against 19–20/20 for retrieval, at 13× the prompt size. The comparison is kept in the repository so it can be re-run as the corpus grows.

## Migration Plan

Not applicable — this is the project's initial capability set, and the index is generated rather than committed. Rebuilding is a single command.

For the deferred ChromaDB backend: implement the store interface, index both backends from the same corpus, and score both with the evaluation harness. Equivalent scores are the acceptance criterion, and they are what retrospectively justifies having started with NumPy.

## Open Questions

- Whether to record the embedding model identity in the persisted index and refuse to load a mismatched one. Deferred because it changes no current behaviour and can be added without altering the store interface.
- What chunk-level retrieval scoring should count as a hit when a fact legitimately spans two overlapping chunks. Needs the metric to exist before the question can be answered usefully.
