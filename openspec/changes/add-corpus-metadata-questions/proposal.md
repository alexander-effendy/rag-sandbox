## Why

The system can only answer questions whose answer exists as literal text in a retrieved passage. Questions *about* the corpus — how many documents it holds, what subjects it covers, whether it covers a subject at all — have no such passage, so retrieval returns the closest-sounding content and the model correctly declines.

Reproduced on the current corpus:

| Question | Response | What retrieval returned |
|---|---|---|
| "How many documents do you have?" | `I don't know.` | 3 unrelated `ai/` chunks, top score 0.301 |
| "Do you have any AI-related documents?" | `I don't know.` | 4 `ai/` chunks — the *right* category — top score 0.331 |
| "Do you have documents about cryptocurrency?" | `I don't know.` | `nutrition/` chunks, top score 0.219 |

The second row is the instructive one. Retrieval succeeded — it surfaced four genuinely AI-related documents — and the answer still failed, because no chunk anywhere *states* which documents exist. This is not a retrieval quality problem, and no adjustment to chunking, `k`, or embedding model can fix it. Semantic similarity is the wrong instrument for a question about the shape of the collection.

The information needed is already sitting in the index and the directory layout, exactly and for free. It just has to be read rather than searched for.

## What Changes

- **New corpus-metadata answering path** — answers questions about the corpus by computing directly from the indexed chunk sources and the corpus directory structure, with **no embedding call and no retrieval**.
- **Three question kinds supported**: how many documents exist; what documents and subject areas exist; whether a given subject is covered at all.
- **Deterministic answers, no generation model.** Facts that are known exactly are formatted directly rather than passed through a language model, so this path cannot hallucinate and needs no similarity threshold.
- **Automatic routing with fall-through.** `answer()` tests the question against a strict pattern set first; a match takes the metadata path, and anything else runs the existing pipeline completely unchanged.
- **Subject areas come from the directory layout** — `docs/ai/*` is the `ai` area, `docs/nutrition/*` the `nutrition` area. The corpus is already organised this way, so grouping is exact rather than inferred.
- **BREAKING** (spec-level, not behavioural for existing questions): `grounded-answering` currently requires every answer to come only from retrieved passages. That requirement is narrowed to content questions, since metadata answers are now produced without retrieval.

Existing content questions are unaffected. Measured against the 20-case evaluation set, the intended pattern set matches **0** of them.

## Capabilities

### New Capabilities

- `corpus-metadata`: Answering questions about the corpus itself — its size, the documents and subject areas it contains, and whether a given subject is covered — computed exactly from the index and directory structure rather than retrieved.

### Modified Capabilities

- `grounded-answering`: Two requirements are narrowed to apply to content questions only, because a corpus-metadata question is now answered without any retrieved context and without invoking the generation model.
  - `Answers restricted to retrieved context` — scoped to content questions; gains a scenario for the metadata bypass.
  - `Explicit refusal when context is insufficient` — scoped to content questions, so that a metadata question about an uncovered subject reports the absence rather than declining.
- `semantic-retrieval`: The store interface gains enumeration alongside add and search.
  - `Substitutable store interface` — extended to include enumerating the distinct source documents held. **Declared during implementation, not at planning time**: every requirement written before this change only ever needed to *search* the corpus, so the interface had no way to ask which documents exist. Without this, a backend implementing only add and search would type-check and then fail at runtime the first time anyone asked a metadata question — precisely the substitutability the interface exists to guarantee.

## Impact

**Code:**
- `backend/rag/pipeline.py` — routing plus the metadata answering functions, alongside the existing `answer()`
- `backend/rag/store.py` — possibly a small accessor for distinct sources, if `chunks` is not convenient enough as-is
- `backend/eval/questions.json` — new cases covering the metadata path and the routing boundary
- `backend/scripts/evaluate.py` — must tolerate cases that expect no retrieval, since metadata cases retrieve nothing by design

**No new dependencies.** The two-dependency constraint (`numpy`, `requests`) holds; this path uses neither.

**Explicitly out of scope**, deferred:
- LLM tool-calling as the routing mechanism. It is the more general solution and would handle phrasings a pattern set never will, but it is a substantially larger change and this project prefers the minimal option that works.
- Natural-language phrasing of metadata answers via the generation model.
- Metadata beyond counts, listings, and subject coverage — chunk counts, index age, per-document length.
- Any change to how content questions are retrieved or answered.

## Assumptions

- Subject areas are the immediate subdirectory under the corpus root. A document placed directly in the corpus root has no subject area; the spec must say what happens to it.
- Routing patterns anchor on a corpus noun (`documents`, `docs`, `files`) rather than a question form (`how many`), because measurement showed form-only matching misroutes the existing question *"How many dimensions does the all-MiniLM-L6-v2 model produce?"* while noun-anchored matching misroutes nothing.
- A question that looks like metadata but finds nothing to report is answered as an absence, not passed to retrieval — falling through would produce a worse answer, not a better one.
