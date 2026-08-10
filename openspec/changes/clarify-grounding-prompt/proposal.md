## Why

The grounding prompt never says whether the model may reason over the retrieved context or must find the answer stated in it. The model resolves that silence differently depending on how a question is phrased, so identical grounding produces opposite behaviour.

Observed on the same document, with the same chunks retrieved, both reproducible across repeated runs:

| Question | Retrieved | Answer |
|---|---|---|
| "eat protein for what" | 4 chunks from `nutrition/protein.md` | *"To maximize lean mass retention."* |
| "why should I eat protein" | the same 4 chunks | `I don't know.` |

The first answer is not stated anywhere in the context. The corpus says an intake of 1.6 g/kg *maximised lean mass retention* — a finding about dose. Turning that into a reason to eat protein is inference, and the current prompt permitted it. The second question, needing the same inference over the same text, was refused.

So the system is not strict. It is **inconsistent**, which is worse than either policy would be on its own: a user cannot predict whether a borderline question will be answered, and neither outcome is wrong under the prompt as written.

The line responsible is `If the context does not contain the answer` — *contain* reads as "present as text", which pulls toward extraction, but it is a nudge rather than a rule.

This change makes the rule explicit. It is a clarification of an underspecified instruction, not a relaxation of grounding: what may be used as evidence does not change, only what may be done with it.

## What Changes

- **The grounding prompt states explicitly that conclusions following from the retrieved context are permitted**, even where the context does not phrase them as an answer.
- **The refusal rule is restated in terms of support rather than presence**: decline when the context cannot support the answer, not merely when it does not state it verbatim.
- **The prohibition on outside knowledge is unchanged and stays absolute.** Every fact in an answer must still come from the retrieved passages.
- **The clarified prompt replaces the current one.** No flag, no second mode — the finding is that one rule was ambiguous, and two prompts would preserve the ambiguity as a configuration axis.
- **Evaluation gains synthesis cases**: questions answerable only by reasoning across retrieved chunks, so consistency is enforced by the harness rather than checked by hand.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `grounded-answering`: Both requirements governing what the generation model may do with retrieved context are clarified.
  - `Answers restricted to retrieved context` — gains an explicit statement that reasoning over the context is permitted while introducing outside facts is not, and scenarios pinning the distinction.
  - `Explicit refusal when context is insufficient` — refusal is restated as a test of whether the context *supports* the answer, rather than whether it *states* it.

## Impact

**Code:**
- `backend/rag/pipeline.py` — the prompt template, and its explanatory comment
- `backend/eval/questions.json` — synthesis cases, and a case pinning that outside knowledge is still refused

**No new dependencies. No index change, no re-ingest.** The prompt is read at query time.

**The acceptance gate is the refusal cases.** *"What is the capital of Australia?"* must still be declined. A prompt that answers it has traded grounding for helpfulness and must not ship, whatever it does for synthesis. The corpus cites fabricated studies precisely so this is measurable rather than assumed.

**Explicitly out of scope:**
- Permitting outside knowledge under any condition.
- Per-question or per-caller prompt selection.
- Changing retrieval, chunking, or the corpus-metadata path.

## Assumptions

- **This change archives after `add-corpus-metadata-questions`.** That change is complete but not yet archived, and it modifies the same two requirements. The delta specs here are written against its post-archive text, so archiving in the other order would revert its scoping clauses.
- Making the rule explicit is expected to change behaviour toward *consistency* rather than toward answering strictly more questions. Whether that holds is measured, not assumed — the same prediction made informally about query length during investigation proved wrong when tested.
- The current behaviour is treated as a defect in the specification rather than in the model. Under the prompt as written, both observed answers are defensible.
