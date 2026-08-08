# Retrieval-Augmented Generation

*Synthetic document written for RAG testing. Technical details are broadly accurate; named benchmarks may be fictional.*

## The Core Idea

Retrieval-augmented generation addresses a specific limitation: a language model only knows what was in its training data, frozen at the moment training ended, and it has no way to tell you which parts of an answer it is confident about.

RAG changes the question from "what do you know" to "here is the relevant material, answer from it". At query time the system searches a document collection, selects the most relevant passages, and places them in the prompt alongside the user's question. The model then answers from text it can actually see.

The consequences are practical. Updating knowledge means re-indexing documents rather than retraining. Answers can cite their sources. Private data can be used without ever entering a training set.

## The Pipeline

Every RAG system, however elaborate, is built from two phases.

Indexing happens ahead of time and once per document. Documents are loaded, split into chunks, each chunk is embedded into a vector, and the vectors are stored alongside their text.

Querying happens per question. The question is embedded with the same model used at index time, the store is searched for the nearest chunks, those chunks are formatted into a prompt, and the model generates an answer.

The retrieval step is where most quality problems originate, and it is also where most people spend the least effort. A perfect model cannot answer from a passage that retrieval failed to surface.

## Chunking Strategy

Chunk size is the first real tuning decision, and it is a genuine trade-off rather than a setting with a correct value.

Small chunks of 100 to 200 words produce precise retrieval because each chunk covers one idea, but they frequently lack the context needed to interpret that idea. A chunk reading "it should be taken with fat" is useless without knowing what "it" refers to.

Large chunks of 500 to 1,000 words carry their context with them but dilute the embedding. A chunk covering five topics produces a vector that sits at the average of those five topics and is therefore close to none of them.

Two techniques mitigate the trade-off. Overlapping chunks by 10 to 25 percent ensures a fact spanning a boundary appears intact in at least one chunk. Prepending the section heading to each chunk restores the context that splitting removed, at a cost of a few tokens per chunk.

## Failure Modes

Three failures account for most disappointing RAG systems.

Retrieval misses happen when the correct passage exists but ranks below the cutoff, usually because the question and the passage use different vocabulary for the same concept. Hybrid search, combining vector similarity with keyword matching such as BM25, is the standard remedy.

Context dilution happens when too many chunks are retrieved. Models attend less reliably to material buried in the middle of a long context, so retrieving twenty chunks often performs worse than retrieving four.

Ungrounded generation happens when the model answers from its training data instead of the provided context, which is particularly damaging because the answer looks identical to a correct one. Explicit prompt instructions to answer only from context, combined with a required "I don't know" escape hatch, reduce but do not eliminate it.

## Evaluating a RAG System

The essential diagnostic is to evaluate retrieval separately from generation.

If the correct chunk was retrieved and the answer is still wrong, the problem is the prompt or the model. If the correct chunk was never retrieved, no amount of prompt engineering will help. Systems that only measure end-to-end answer quality cannot distinguish these cases and consequently tend to be tuned in the wrong place.
