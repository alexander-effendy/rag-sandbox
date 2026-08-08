## Context

See `proposal.md` — Why. Requirements are in `specs/`.

The relevant existing shape: `pipeline.answer()` embeds the question, searches the store, builds a prompt, and calls the generation model. `Answer` carries the text plus the retrieved passages and their scores. Callers — `ask.py`, `evaluate.py`, and any future frontend — go through `answer()` and nothing else.

The facts this change needs are already exact and already loaded. `store.chunks` carries a `source` per chunk (`nutrition/protein.md`), and the corpus is organised one subject per directory. Nothing needs to be inferred, searched, or embedded.

## Goals / Non-Goals

**Goals:**

- Metadata questions answered exactly, from data the system already holds.
- Zero regression on content questions — measurable against the existing evaluation set.
- Routing that fails safe: an unrecognised metadata phrasing degrades to today's behaviour, never to a wrong answer.
- Small enough that the mechanism is still readable, in keeping with the rest of the repository.

**Non-Goals:**

- General natural-language understanding of metadata questions. A pattern set will miss phrasings; that is accepted and bounded.
- Any change to retrieval, chunking, or the content-answering prompt.
- Metadata beyond counts, listings, and subject coverage.

## Decisions

### Routing lives in `answer()`, not in the CLI

Detection happens inside `pipeline.answer()` before the embedding call, so every caller inherits it. Putting it in `ask.py` would mean the planned frontend and `evaluate.py` each reimplement it, and the routing rule would exist in three places.

Alternative considered: an explicit `--about-corpus` flag with no detection. Zero misrouting risk and trivially testable, but a chat interface cannot ask the user to pick a flag, and the flag would not exist in the API the frontend eventually calls.

### Patterns anchor on a corpus noun, never on question form

A pattern matches only when the question refers to the collection — `document`, `documents`, `docs`, `files`, or an equivalent noun. Interrogative form alone (`how many`, `do you have`) is never sufficient.

This was measured against the existing 20-case evaluation set:

| Pattern style | Content questions misrouted | Metadata questions caught |
|---|---|---|
| Form-only (`how many`, `do you have`) | **1/20** | 6/6 |
| Noun-anchored | **0/20** | 5/6 |

The single form-only false positive is *"How many dimensions does the all-MiniLM-L6-v2 model produce?"* — a content question that happens to start like a count question. Requiring the noun eliminates it.

The cost is the reverse error: noun-anchored matching missed `"List your documents"` in the sample above, and phrasings like *"what's in your knowledge base?"* will miss too. That direction is the safe one, which is the next decision.

### Failures are directed toward the retrieval path

A missed metadata question falls through to retrieval and produces today's `I don't know.` — the exact behaviour the user already has, so nothing regresses. A misrouted content question, by contrast, would return a document listing instead of the answer, which is a new and worse failure.

The two errors are not symmetric, so the pattern set is deliberately tight rather than generous.

### Answers are computed and formatted, with no generation model

The count is a set cardinality and the grouping is a directory walk. Both are exactly known, so passing them through a language model to be phrased would add a hallucination surface over facts that cannot otherwise be wrong, plus a generation call, in exchange for nicer prose.

This also makes the path instant, free, and byte-for-byte reproducible — worth noting given that the rest of the system is explicitly *not* reproducible, and that this is the only part of the pipeline that can be asserted exactly in a test.

Alternative considered: supply the computed facts as prompt context and let the model phrase the sentence. Recorded as deferred rather than rejected — it is the natural upgrade once phrasing variety matters more than exactness.

### Subject areas come from the directory layout

`nutrition/protein.md` is in area `nutrition`. The corpus already encodes this, so grouping is exact where inferring subject from content would be a second retrieval problem.

A document at the corpus root has no subdirectory. Rather than silently omitting it — which would make the listing disagree with the count — it is reported under an explicit uncategorised grouping. The specs require the count and the listing to agree, so this case cannot be left undefined.

Subject matching for coverage questions is case-insensitive against area names and document filenames. This handles `"AI"` against `docs/ai/` but not `"artificial intelligence"`. Accepted limitation, recorded as an open question rather than solved speculatively.

### `Answer` gains a way to identify the path that produced it

Metadata answers return an empty retrieved list, which is indistinguishable from a content question where retrieval found nothing. Callers need to tell those apart: `evaluate.py` must not score a metadata answer as a refusal, and a frontend that renders retrieved chunks needs to know there are legitimately none.

An explicit marker on `Answer` is preferred to inferring the path from an empty list, because inference would silently misclassify the day a content question legitimately retrieves nothing.

### The store interface gains enumeration, rather than callers reaching into it

*Decided during implementation.* Answering a metadata question needs the list of documents in the index. The obvious move is to read `store.chunks` directly, which works because the NumPy store has that attribute — and quietly breaks the seam, because `VectorStore` declares only `add`, `search`, and `__len__`. A ChromaDB backend implementing exactly the declared interface would type-check and then raise `AttributeError` the first time anyone asked how many documents exist.

The interface therefore gains a third member: enumerate the distinct source documents.

It returns source identifiers rather than chunk objects, which is narrower in two useful ways. A backend can satisfy it with a metadata query instead of materialising every chunk, and callers cannot reach past the interface into one implementation's internals. It also turns out to be all the metadata path ever needs — the count, the grouping, and the coverage check are all derived from sources alone.

Alternatives considered: passing chunks in from each caller, which pushes the problem onto the future frontend; and `getattr(store, "chunks", None)` with silent degradation, which is exactly the quiet-failure-with-no-error mode this project has been deliberate about avoiding elsewhere.

### The evaluation harness needs a third case kind

`questions.json` currently has two kinds, distinguished by `expect_source`: a content case naming its expected document, and a refusal case with `null`. A metadata case also has no expected source but must not be scored as a refusal — and the harness currently excludes `null` cases from the retrieval denominator, which happens to be correct here for a different reason.

Adding an explicit field for the expected answering path, defaulting to the retrieval path, keeps existing cases untouched and makes the intent legible rather than encoded in the absence of a value.

## Risks / Trade-offs

- **Pattern set will miss phrasings** — *"what's in your knowledge base?"*, *"summarise your contents"* → Misses degrade to current behaviour, not to wrong answers. The general fix is tool-calling, explicitly deferred.
- **Directory names are the vocabulary** — `ai` and `nutrition` are what a user must roughly say → Case-insensitive matching against area names and filenames covers the common cases; alias handling is an open question.
- **Two answering paths in one function** — a reader of `answer()` must now understand routing before retrieval → Mitigated by keeping detection in one named predicate rather than inline conditionals, so the retrieval path reads as it does today.
- **Metadata answers cannot be graded by the existing substring matcher in a meaningful way** — a listing is long and exact, so a substring check passes trivially → Worth asserting exact equality for these cases instead, which the determinism guarantee makes possible.
- **Changing `Answer`'s shape touches every consumer** — `ask.py`, `evaluate.py`, `compare_stuffing.py` → Additive with a default, so existing construction sites keep working.

## Migration Plan

No data migration; the index format is unchanged and no re-indexing is required. Existing content questions take the same path as before. Rollback is removing the routing call from `answer()`.

## Open Questions

- Whether subject matching should carry an alias table (`AI` ↔ `artificial intelligence`, `nutrition` ↔ `diet`, `food`). Deferred because it changes no interface and can be added once real phrasings show which aliases matter — guessing now would encode assumptions rather than observations.
- Whether the listing should report chunk counts per document. Deferred: it is easy to add, but it is index detail rather than corpus content, and no asked-for question needs it.
