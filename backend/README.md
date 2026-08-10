# rag-sandbox

A RAG implementation small enough to read in one sitting, built to learn the pieces rather than to ship.

Runs entirely locally on Ollama. Two dependencies — `numpy` and `requests`. No LangChain, no LlamaIndex, no vector database. Every file is heavily commented; this README is the map.

---

## 1. What RAG actually is

A language model only knows what was in its training data. It cannot read your documents, and when asked about them it will invent a fluent, confident, wrong answer rather than decline.

RAG changes the question from *"what do you know?"* to *"here is the relevant text — answer from it."*

The mechanism is less clever than the name suggests. Before asking the model anything, you search your documents for passages related to the question, and paste them into the prompt. That's it. "Augmented" means **string concatenation**.

The genuinely clever part is the search, because you can't use keyword matching — a question and its answer rarely share words. That's what embeddings solve, and it's covered in section 3.

---

## 2. What happens when you ask a question

Two phases. The first runs once, ahead of time; the second runs per question.

### Phase A — Indexing (`scripts/ingest.py`, ~1 second)

```
docs/*.md ──1──> 73 chunks ──2──> 73 vectors ──3──> index/
```

| Step | Where | What |
|---|---|---|
| 1 | [rag/chunking.py](rag/chunking.py) | Cut 10 documents into 73 overlapping pieces of ~120 words |
| 2 | [rag/ollama_client.py](rag/ollama_client.py) | Send each chunk to `all-minilm` → 384 numbers per chunk |
| 3 | [rag/store.py](rag/store.py) | Stack into a 73×384 matrix, save to `index/` |

### Phase B — Querying (`scripts/ask.py`, ~1 second)

```
"What is the Aldridge formula?"
        │
        0  about the corpus itself?  ──yes──>  answer from the index, done
        │                                      (no model at all — section 5)
        │ no
        ├──4──> [0.31, -0.02, ...]        embed the question, same model
        │
        ├──5──> matrix @ query            score all 73 chunks at once
        │       → top 4 chunks
        │
        ├──6──> "Answer using ONLY..."    paste chunks into the prompt
        │
        └──7──> llama3.2                  → "35 millilitres per kilogram"
```

| Step | Where | What |
|---|---|---|
| 0 | [`corpus_metadata.answer_question`](rag/corpus_metadata.py) | *"How many documents do you have?"* — answered from the index, skipping everything below |
| 4 | [`embed_one`](rag/ollama_client.py) | Question → 384 numbers. **Must use the same model as step 2** |
| 5 | [`NumpyVectorStore.search`](rag/store.py) | One matrix multiply scores every chunk; keep the best 4 |
| 6 | [`build_prompt`](rag/pipeline.py) | Chunks + question → one string |
| 7 | [`generate`](rag/ollama_client.py) | The model reads that string and writes an answer |

Run `ask.py --show-chunks` to watch steps 5–7 happen.

---

## 3. Why embeddings, instead of keyword search

An embedding model converts text into a fixed list of numbers — here, 384 of them — such that **texts with similar meanings produce vectors pointing in similar directions**.

That turns meaning into geometry, and "find the most relevant passage" becomes arithmetic.

Measured on this corpus:

```
"How much water should I drink per day?"   →  0.678 similarity to docs/nutrition/hydration.md
```

That question shares **no distinctive words** with the document, which is written around "fluid intake" and "Aldridge formula". Keyword search scores it zero. Semantic search ranks it first.

### Reading the similarity scores (they're less meaningful than they look)

The obvious move is to treat the score as confidence. Measured, that doesn't hold:

| Query | Top score | Correct doc rank |
|---|---|---|
| `"Aldridge"` | 0.118 | **#1** |
| `"What is the Aldridge formula?"` | 0.205 | **#1** |
| `"What is the Aldridge formula for daily fluid intake?"` | 0.702 | **#1** |

Same fact, same document, correct every time — only the *score* moved. Short queries score low because a handful of words produce a vector that isn't near anything in particular.

**Ranking is robust; absolute scores are not.** Compare scores within one query's results, never across queries.

This is also why `min_score` defaults to `0.0`. Across the eval set, the worst *correct* retrieval scores **0.442** and the best *should-be-rejected* one scores **0.405** — 0.037 apart. Any threshold splitting those is fitted to these 20 content questions and won't survive the 21st. The prompt's grounding rules handle refusal better, and both refusal tests pass with no threshold at all.

---

## 4. Why not just put every document in the prompt?

A fair question, and at this corpus size a fair strategy. `llama3.2` has a 131,072-token context window; the whole corpus is ~9,000 tokens. It fits with room to spare.

[scripts/compare_stuffing.py](scripts/compare_stuffing.py) runs the same 20 content questions three ways and measures it:

| Approach | Correct | Avg prompt |
|---|---|---|
| **STUFFED** — every document in every prompt | 16/20 | 36,307 chars |
| **RAG** — the 4 retrieved chunks | **19–20/20** | 2,789 chars |
| **NEITHER** — bare model | 5/20 | 63 chars |

So stuffing genuinely works — 16/20 is far better than nothing. It's just worse than RAG while sending **13× more text**.

**How it fails matters.** All four stuffing failures were `I don't know.` — not hallucinations. The facts were sitting in the context and the model couldn't locate them. That's a safe failure mode, but a silent one.

**Position dominates.** Planting a document containing one invented fact, then asking for it:

| Same 7,231 tokens, only position changed | Result |
|---|---|
| Planted document **first** | **FOUND** |
| Planted document **last** | **LOST** |

Identical content, identical length. And a bare one-line fact (rather than a realistic paragraph) was lost as soon as a *single* other document was added — 790 tokens total.

So a large context window is not a substitute for retrieval. It's the ceiling on what you *can* pass, not a promise the model will use it evenly.

**Where stuffing is genuinely the right call:** a handful of documents, low query volume, no need for citations. Don't build RAG for 5 files.

**Where it stops working:**

- **Scale** — 500 PDFs will not fit in any context window
- **Cost** — you reprocess the entire corpus on every question
- **Citations** — retrieval knows which chunk it used; stuffing doesn't
- **Access control** — RAG can filter per user before the model sees anything

```bash
.venv/bin/python backend/scripts/compare_stuffing.py
```

---

## 5. Questions retrieval cannot answer at all

Sections 3 and 4 are about making retrieval *better*. This one is about a class of question where retrieval is simply the wrong instrument.

```
$ ask.py "How many documents do you have?"          # before
I don't know.
  sources: ai/fine-tuning-vs-rag.md, ai/embeddings.md ...  (top score 0.301)
```

Nothing is broken here. No passage anywhere *states* how many documents exist, so there is nothing to find — retrieval returns the closest-sounding text, which is irrelevant, and the model correctly declines. No chunk size, no `k`, and no embedding model fixes it.

The sharpest version of this was *"Do you have any AI-related documents?"* — retrieval returned **four genuinely AI-related documents** and the answer was still `I don't know.`, because no chunk lists what the corpus contains.

### The fix: stop searching, start counting

The answer is already in the index, exactly. Every chunk carries a `source` like `nutrition/protein.md`, and the corpus is one subject per directory. So the count is a set size and the grouping is a string split. [rag/corpus_metadata.py](rag/corpus_metadata.py) answers these directly — **no embedding call, no retrieval, no language model**:

```
$ ask.py "How many documents do you have?"          # after
The corpus contains 10 documents across 2 subject areas: ai (5), nutrition (5).

$ ask.py "Do you have documents about cryptocurrency?"
No — the corpus has no documents about cryptocurrency. It covers ai, nutrition.
```

That second one matters: the old answer was `I don't know.`, which is wrong in a specific way. Whether the corpus covers a subject isn't unknown to us — it's knowable exactly, and the honest answer is "no".

### Routing on the noun, not the question form

Detection is a small pattern set, and the one design decision worth knowing is that it anchors on a **corpus noun** (`documents`, `docs`, `files`) and never on question *form* (`how many`). Measured against the 20 content questions in the eval set:

| Pattern style | Content questions misrouted | Metadata questions caught |
|---|---|---|
| Form-only (`how many`, `do you have`) | **1/20** | 6/6 |
| Noun-anchored | **0/20** | 5/6 |

The single false positive was *"How many dimensions does the all-MiniLM-L6-v2 model produce?"* — a real content question that opens like a count question. Requiring the noun eliminates it. That question is now a permanent boundary case in the eval set.

### The limitation, stated plainly

Phrasings outside the pattern set won't match — *"what's in your knowledge base?"* falls through to retrieval and gets today's `I don't know.` Subject matching is string-based, so `"AI"` finds `docs/ai/` but `"artificial intelligence"` does not.

That direction is deliberate. **A miss costs nothing** — it degrades to the behaviour you already had. **A misroute would be a new failure**, answering a content question with a document listing. The two errors aren't symmetric, so the patterns are tight rather than generous.

The general fix is LLM tool-calling — let the model decide which tool to call. It's the right long-term answer and deliberately deferred: it's a much bigger change, and this repo prefers the minimal thing that works.

---

## 6. Every file, and what it does

### The library — `rag/`

| File | Job |
|---|---|
| [rag/chunking.py](rag/chunking.py) | Markdown → overlapping chunks. Handles the two problems cutting text creates: facts landing on a boundary (fixed by 30-word overlap) and chunks losing context (fixed by prepending the heading) |
| [rag/ollama_client.py](rag/ollama_client.py) | The only file that talks to Ollama. `embed()` for vectors, `generate()` for text. Raw `requests` so you can see the HTTP |
| [rag/store.py](rag/store.py) | Holds the matrix, does the search. **The most interesting file** |
| [rag/pipeline.py](rag/pipeline.py) | Joins steps 4–7 into `answer()`. Also holds the prompt and the metadata routing check |
| [rag/corpus_metadata.py](rag/corpus_metadata.py) | Answers questions *about* the corpus — count, listing, subject coverage — with no model involved. See section 5 |
| [rag/\_\_init\_\_.py](rag/__init__.py) | Makes `rag/` a package, re-exports the useful names |

### The scripts — `scripts/`

| File | Job |
|---|---|
| [scripts/ingest.py](scripts/ingest.py) | Build the index. **Run first.** Re-run after editing docs or changing chunk settings |
| [scripts/ask.py](scripts/ask.py) | Ask a question. One-shot, or interactive with no arguments |
| [scripts/evaluate.py](scripts/evaluate.py) | Score all 24 eval cases — content, refusal, and corpus-metadata. Scores retrieval and generation *separately* |
| [scripts/compare_stuffing.py](scripts/compare_stuffing.py) | RAG vs. stuffing every document into the prompt vs. no context. See section 4 |

### Data

| Path | What |
|---|---|
| [docs/](docs/) | The corpus — 10 synthetic documents. See section 8 |
| [eval/questions.json](eval/questions.json) | 24 cases. `expect_source` = which doc should be retrieved (`null` = refusal or metadata case), `expect_path` = `retrieval` (default) or `metadata`, `expect_any` = substrings that mean the answer is right, `expect_exact` = full-string match for metadata cases |
| `index/` | Generated. `embeddings.npy` (the matrix) + `chunks.json` (the text). Gitignored — rebuilt in a second |

---

## 7. The search itself

This is the whole vector database, in [rag/store.py](rag/store.py):

```python
query  = normalize(query_embedding)   # make it unit length
scores = self.matrix @ query          # compare against ALL 73 chunks at once
top    = np.argsort(-scores)[:k]      # take the k highest
```

**Line 1** — Cosine similarity is `(a · b) / (|a| × |b|)`. If both vectors have length 1, the denominator is 1 and the whole formula collapses to a plain dot product. So we normalise once at index time and every query becomes a bare multiply.

**Line 2** — `@` is matrix multiplication. A `(73, 384)` matrix times a `(384,)` vector gives `(73,)` — one similarity score per chunk, computed in a single native operation rather than a Python loop.

**Line 3** — `argsort` returns indices that would sort ascending, so we sort the *negated* scores to get descending, and slice the top k.

That's exact search — it compares against everything, so it can never miss. It's O(n), which is fine to roughly 100,000 chunks. Chroma, pgvector, Pinecone and FAISS answer the same question; what they add is ANN indexes (so you don't compare against everything), metadata filters, persistence and concurrency. Real and valuable at scale — but not a different idea.

---

## 8. Why the test documents cite studies that don't exist

The corpus in [docs/](docs/) is synthetic, and its studies — Vandermeer, Kestrel, Brightwater, Okonkwo, Marlowe — are **invented on purpose**.

If you ask a RAG system something the model already knows, a correct answer proves nothing. Retrieval could be completely broken and the answer would still look right. Ask about a study that exists only in your corpus, and a correct answer *proves* retrieval worked:

```
$ ask.py "What daily protein intake did the Vandermeer Study find?"
1.6 grams per kilogram of body weight per day [source]

$ ask.py --no-rag "What daily protein intake did the Vandermeer Study find?"
I couldn't find any information on the "Vandermeer Study"...
```

The nutrition numbers are fabricated. Don't treat them as health information — see [docs/README.md](docs/README.md).

---

## 9. Setup and usage

> **Run every command from the repo root**, not from `backend/`. The virtualenv lives at the root and is shared, so paths are written as `backend/scripts/...`.

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
```

> Use **3.12**, not 3.14. Your system default is 3.14 and several ML packages don't publish wheels for it yet — this bites the moment you add ChromaDB.

```bash
ollama pull llama3.2 && ollama pull all-minilm
```

Then:

```bash
.venv/bin/python backend/scripts/ingest.py
```

```bash
.venv/bin/python backend/scripts/ask.py "What did the Vandermeer Study find about protein?"
```

| # | Task | Command | Files involved | What it does |
|---|---|---|---|---|
| 1 | Build the index (run first, and after any doc edit) | `ingest.py` | [chunking.py](rag/chunking.py) → [ollama_client.py](rag/ollama_client.py) → [store.py](rag/store.py) | Chunks `docs/`, embeds each chunk with `all-minilm`, saves the matrix to `index/` |
| 2 | Ask a question | `ask.py "..."` | [ask.py](scripts/ask.py) → [pipeline.py](rag/pipeline.py) | Embeds the question, retrieves top-k chunks, prompts `llama3.2`, prints the answer |
| 3 | See what was retrieved | `ask.py --show-chunks "..."` | same as #2 | Same as #2, plus each chunk's text and similarity score — use whenever an answer looks wrong |
| 4 | Ask with no retrieval (the control) | `ask.py --no-rag "..."` | [pipeline.py](rag/pipeline.py) `answer_without_rag()` | Skips the index, sends the bare question straight to `llama3.2` — shows what retrieval bought you |
| 5 | Interactive REPL | `ask.py` (no question) | same as #2 | Loads the index once, then loops until Ctrl-C or a blank line |
| 6 | Change how many chunks get retrieved | `ask.py -k 8 "..."` / `evaluate.py -k 8` | [pipeline.py](rag/pipeline.py) `retrieve()` | Retrieves the top `k` chunks instead of the default 4 |
| 7 | Rebuild with different chunking | `ingest.py --chunk-words 200 --overlap 50` | [chunking.py](rag/chunking.py) | Same as #1, with a different chunk size / overlap — see section 11 |
| 8 | Build a second index without overwriting the first | `ingest.py --index /tmp/experiment` | [store.py](rag/store.py) `save()` | Writes elsewhere so two configs can be compared; query it with `ask.py --index /tmp/experiment "..."` |
| 9 | Score the whole system | `evaluate.py` | [evaluate.py](scripts/evaluate.py) → [pipeline.py](rag/pipeline.py) | Runs all 24 `eval/questions.json` cases, scores retrieval and answer quality *separately* |
| 10 | Score with RAG vs. no-RAG side by side | `evaluate.py --compare` | same as #9, plus `answer_without_rag()` | Same content questions, also answered with no retrieval — source of the 5/20 figure in section 10 |
| 11 | Compare RAG vs. stuffing vs. nothing | `compare_stuffing.py` | [compare_stuffing.py](scripts/compare_stuffing.py) | Runs the 20 content questions three ways, reports accuracy, prompt size, latency — see section 4 |

Typical order: #1 once → #2/#3 while poking at it → #9 whenever something changes → #6/#7/#8 to experiment → #11 to see the alternative you're not using.

---

## 10. Current results

24 questions at `k=4`:

| | Score |
|---|---|
| Retrieval — correct source in top-4 | **18/18** (rank #1 every time) |
| Answers, all cases | **24/24** |
| Answers without RAG (content cases only) | **5/20** |

That last row is the value proposition in one number.

The 24 cases are three kinds, and the harness scores them differently:

| Kind | Count | How it's scored |
|---|---|---|
| Content | 18 | Retrieval hit + answer contains expected substring |
| Refusal | 2 | Must reply exactly `I don't know.` — no source to retrieve |
| Corpus-metadata | 4 | **Exact string match**, and must take the metadata path |

Three caveats:

- **Scores wobble between runs.** Two identical runs gave 20/20 and 19/20 on the content cases. Temperature is pinned to 0, but Ollama isn't bit-deterministic. Treat a single question flipping as noise. The 4 metadata cases are exempt — they're computed, not generated, so they're byte-reproducible.
- **Retrieval is scored over 18, not 24.** Refusal and metadata cases have no correct source to retrieve. Metadata cases retrieve *nothing at all*, by design.
- **The refusal cases are the important ones.** One is *"What is the capital of Australia?"* — the model knows it and declines anyway, because the corpus doesn't contain it. (Under `--compare` those two show `no-RAG FAIL`; the bare model answers "Canberra", and failing there is correct. Metadata cases are skipped under `--compare` — asking a bare model how many documents we hold measures nothing.)

---

## 11. Things worth breaking

A tuned system is the least educational state for one to be in. Measured results from actually running these:

**Destroy the overlap** — `ingest.py --chunk-words 60 --overlap 0`

```
Retrieval:  18/18     (unchanged!)
Answers:    18/20     (down from 19-20)
```

Answers degraded while retrieval looked perfectly healthy. That gap is the lesson: the retrieval metric only asks whether the right *document* ranked top-4, and with 10 documents that's an easy bar. Fragmented chunks still surfaced the right file — they just no longer contained the whole fact. **A green retrieval score can hide a real retrieval problem** when the metric is coarser than the failure. Scoring at chunk level instead would be a good exercise.

**Retrieve too much** — `evaluate.py -k 20`

```
Answers:    20/20     (no degradation)
```

Did **not** reproduce. The "lost in the middle" effect described in [docs/ai/transformers.md](docs/ai/transformers.md) is real, but this corpus is 73 chunks — k=20 pulls over a quarter of everything and the context never gets long enough for position to matter. A sandbox this small can't demonstrate every failure mode.

Still untested, both worth trying:

- **Huge chunks** — `--chunk-words 800`, so each vector becomes the average of many topics and sits close to none.
- **Mismatched embedding models** — ingest with `all-minilm`, query with `nomic-embed-text`. Should give confident nonsense with no error at all, because the vectors live in unrelated spaces.

---

## 12. Next steps

1. **Port to ChromaDB.** [`VectorStore`](rag/store.py) is a `Protocol` with two methods. Write `ChromaVectorStore` satisfying it and nothing in `pipeline.py` changes — that's the point of the seam. Both should score identically on `evaluate.py`, which is exactly what justifies having started with NumPy.
2. **Score retrieval at chunk level**, not document level — section 11 shows why the current metric is too forgiving.
3. **Add hybrid search.** Vector similarity misses exact-term matches; BM25 alongside it is the standard fix. The `"Aldridge"` query scoring 0.118 is the case for it.
4. **Try `nomic-embed-text`** — 768 dims vs 384. Re-ingest, re-evaluate, see whether it earns the cost here.
5. **Add a reranker** — retrieve 20, rerank with a cross-encoder, keep 4.
6. **Then pgvector**, once you want vectors sitting next to relational data.

---

## Project spec

Managed with [OpenSpec](https://github.com/Fission-AI/OpenSpec) (`openspec/`). It wasn't working here because the repo had never been initialized — `openspec init` fixed that.
