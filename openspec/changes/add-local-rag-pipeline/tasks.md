> **This change is retroactive.** The pipeline described in `specs/` is already implemented and passing its evaluation set. Groups 1–4 are therefore verification: confirm each requirement is actually met by the code as written, and record any that are not. Group 5 closes the two gaps found while writing the specs. Group 6 pins the baseline.
>
> Treat a verification task as done only when the behaviour has been observed, not when the code looks right.

## 1. Verify document-indexing

- [ ] 1.1 Confirm indexing discovers markdown recursively under `backend/docs/`, processes files in a deterministic order, and that two consecutive runs over unchanged input produce identical chunk counts and ordering
- [ ] 1.2 Confirm `README.md` files are excluded — add a distinctive phrase to `backend/docs/README.md`, re-index, and verify it is unretrievable
- [ ] 1.3 Confirm every chunk carries its section heading, and that the heading is visible in `--show-chunks` output and in citations
- [ ] 1.4 Confirm consecutive chunks from one section share the configured overlap, by inspecting adjacent entries in `backend/index/chunks.json`
- [ ] 1.5 Confirm `--chunk-words` and `--overlap` change the resulting index, and that overlap ≥ chunk size is rejected naming both values, before any embedding request is made
- [ ] 1.6 Confirm the index reloads in a later process with no embedding calls for corpus documents, and that querying with no index reports the missing location and the command that builds one
- [ ] 1.7 Confirm full-rebuild semantics for all three cases: add a document and re-index (counts rise, content retrievable), edit it (new content retrievable), delete it (content gone, related questions declined)
- [ ] 1.8 Confirm precondition failures each name their fix — model service unreachable, required model missing, and an empty corpus directory

## 2. Verify semantic-retrieval

- [ ] 2.1 Confirm semantic matching without shared vocabulary, using a query phrased entirely differently from its source passage
- [ ] 2.2 Confirm results are ordered by descending similarity, bounded by the requested count, and each carries a score plus a source identifier usable for citation
- [ ] 2.3 Confirm search compares against every indexed chunk, so no result is dropped by index approximation
- [ ] 2.4 Confirm the similarity floor defaults to zero and that a non-zero floor excludes results below it
- [ ] 2.5 Confirm searching an empty store returns an empty result set without raising
- [ ] 2.6 Record the current score distribution across the evaluation set — worst correct retrieval and best should-be-rejected retrieval — so the floor decision in `design.md` can be re-checked as the corpus grows

## 3. Verify grounded-answering

- [ ] 3.1 Confirm answers to corpus-only questions reflect corpus content, and that the same question without retrieval does not produce that answer
- [ ] 3.2 Confirm the exact string `I don't know.` is returned for a subject absent from the corpus
- [ ] 3.3 Confirm the same refusal for a fact the model knows from training but the corpus lacks — the capital-of-Australia case
- [ ] 3.4 Confirm source documents are reported highest-scoring first with duplicates removed when several chunks share a document
- [ ] 3.5 Confirm retrieved passages and their scores are returned alongside the answer text, so a retrieval failure is distinguishable from a generation failure
- [ ] 3.6 Confirm that when retrieval yields nothing, the refusal is returned with no generation request issued
- [ ] 3.7 Confirm the unretrieved baseline path requires no index and is identifiable as having had no supporting context

## 4. Verify evaluation-harness

- [ ] 4.1 Confirm retrieval and answer scores are reported as independent figures, and that a case retrieving its expected source while failing its answer is recorded as retrieval success plus answer failure
- [ ] 4.2 Confirm cases declaring no expected source are excluded from the retrieval denominator and still scored on whether the refusal occurred
- [ ] 4.3 Confirm `--compare` reports the unretrieved baseline alongside the retrieval-assisted score
- [ ] 4.4 Confirm the full-context comparison reports accuracy and average prompt size for all three modes
- [ ] 4.5 Confirm failing cases report expected content, produced answer, and retrieved sources with scores, while passing cases stay terse
- [ ] 4.6 Confirm `--index` scores an alternate index and leaves the default untouched
- [ ] 4.7 Confirm the process exits non-zero when any case fails
- [ ] 4.8 Confirm every corpus document containing invented facts states that it is synthetic

## 5. Close gaps found while specifying

- [ ] 5.1 Record the embedding model identity alongside the persisted index — `semantic-retrieval` requires that vectors from different embedding models are never silently compared, and nothing currently enforces this. Resolves the first open question in `design.md`
- [ ] 5.2 Refuse to load an index whose recorded embedding model differs from the one configured for querying, reporting both names and directing the user to re-index
- [ ] 5.3 Add a regression case covering 5.2, so the mismatch fails loudly rather than returning plausible rankings
- [ ] 5.4 Note in `design.md` that substitutability of the store interface is asserted but unproven until a second implementation exists, and that proving it is the acceptance criterion of the deferred ChromaDB change

## 6. Record the baseline

- [ ] 6.1 Run the evaluation set three times and record the range, so run-to-run variation is documented as a measured band rather than a single figure
- [ ] 6.2 Re-run the degraded-chunking and high-`k` experiments and confirm the results recorded in `design.md` and the README still hold
- [ ] 6.3 Reconcile the README's stated results with the measured baseline, correcting any figure that has drifted
- [ ] 6.4 Run `openspec validate --strict` and resolve any findings
