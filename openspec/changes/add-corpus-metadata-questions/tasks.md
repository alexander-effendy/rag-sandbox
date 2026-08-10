> Ordered so each group is verifiable before the next depends on it: the facts are computable and checkable without routing, routing is testable without being wired in, and wiring is the last thing that changes existing behaviour.
>
> The regression check in 5.1 is the one that matters most — the whole design rests on content questions being untouched.

## 1. Corpus facts

- [x] 1.1 Add a function returning the distinct source documents in the index, so one document contributing many chunks counts once
- [x] 1.2 Add a function grouping those sources by subject area, deriving the area from the immediate subdirectory beneath the corpus root
- [x] 1.3 Handle a document stored at the corpus root by placing it in an explicit uncategorised grouping, so the listing and the count cannot disagree
- [x] 1.4 Add a function reporting whether a named subject matches a subject area, matching case-insensitively against area names and document filenames
- [x] 1.5 Verify against the current corpus: 10 documents, 2 areas (`ai` 5, `nutrition` 5), and confirm the grouped totals equal the document count

## 2. Routing

- [x] 2.1 Add a predicate that classifies a question as a corpus-metadata question, anchored on a corpus noun (`document`, `documents`, `docs`, `files`) and never on interrogative form alone
- [x] 2.2 Cover the three question kinds: how many documents exist, what documents or subjects exist, and whether a named subject is covered
- [x] 2.3 Run the predicate over all 20 existing evaluation questions and confirm it matches none of them — in particular *"How many dimensions does the all-MiniLM-L6-v2 model produce?"*, which form-only matching misroutes
- [x] 2.4 Confirm the predicate matches the metadata questions from the proposal, and record any phrasing it misses as a known limitation rather than widening the patterns to catch it

## 3. Answering path

- [x] 3.1 Add a marker to `Answer` identifying which path produced it, additive with a default so existing construction sites are unaffected
- [x] 3.2 Add the metadata answering function: deterministic formatting of the facts from group 1, no generation model, no embedding call
- [x] 3.3 Format the uncovered-subject case to state the absence and name the areas that are covered, never `I don't know.`
- [x] 3.4 Call the routing predicate at the top of `answer()`, before the embedding call, returning the metadata answer on a match and falling through to the existing pipeline otherwise
- [x] 3.5 Confirm a metadata answer carries an empty retrieved list and is distinguishable from a content answer that retrieved nothing

## 4. Evaluation

- [x] 4.1 Add an explicit expected-path field to the evaluation case format, defaulting to the retrieval path so all 20 existing cases stay valid unedited
- [x] 4.2 Teach `evaluate.py` to score metadata cases without treating them as refusal cases, and keep them out of the retrieval denominator
- [x] 4.3 Assert exact equality rather than substring matching for metadata cases — the determinism guarantee makes this possible, and substring matching would pass trivially against a long listing
- [x] 4.4 Add cases for each question kind: document count, full listing, a covered subject, an uncovered subject
- [x] 4.5 Add a boundary case asserting that a content question with a metadata-like form is answered by retrieval, so the false-positive guard is enforced by the harness rather than by inspection

## 5. Verification

- [x] 5.1 Run the full evaluation set and confirm the 20 pre-existing cases score exactly as before — this is the regression gate for the entire change
- [x] 5.2 Confirm no embedding or generation request is issued for a metadata question, so the bypass is real rather than incidental
- [x] 5.3 Confirm determinism by asking the same metadata question twice and comparing the responses byte for byte
- [x] 5.4 Add a document to the corpus, re-index, and confirm the count and listing both reflect it; remove it and confirm they revert
- [x] 5.5 Confirm the two-dependency constraint still holds — no new imports beyond `numpy` and `requests`

## 6. Documentation

- [x] 6.1 Document the metadata path in `backend/README.md`, including the measured routing table and why noun anchoring rather than form matching
- [x] 6.2 State the known limitation plainly: phrasings outside the pattern set fall through to retrieval and decline, and tool-calling is the deferred general fix
- [x] 6.3 Run `openspec validate --strict` and resolve any findings
