# Test Corpus

These documents are **synthetic** — written specifically as test data for this RAG sandbox.

The nutrition documents cite studies (the Vandermeer Study, the Kestrel Cohort, the Brightwater Survey, the Okonkwo Trial, the Aldridge formula) that **do not exist**. Neither do the AI documents' "Marlowe benchmark". This is deliberate and it is the point of the corpus.

## Why fictional studies

If you ask a RAG system "what is the recommended daily protein intake?" and it answers correctly, you have learned nothing — `llama3.2` already knows that from pretraining. Retrieval could be completely broken and the answer would still look right.

If you ask "what did the Vandermeer Study find about protein intake?" and it answers correctly, retrieval provably worked. The model cannot have known that.

Every document therefore mixes:

- **Real, well-known facts** — which the model could answer without retrieval
- **Invented specifics attached to invented sources** — which it could only answer *with* retrieval

`scripts/evaluate.py` uses the second kind. `--compare` shows you the difference between the two paths directly.

## Do not treat the nutrition content as health information

The numbers are plausible-looking but fabricated for testing purposes.
