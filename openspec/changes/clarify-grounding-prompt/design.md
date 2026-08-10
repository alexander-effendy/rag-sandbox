## Context

See `proposal.md` — Why. Requirements are in `specs/`.

The whole surface of this change is one string: `PROMPT_TEMPLATE` in `backend/rag/pipeline.py`, four instruction lines wrapped around the retrieved context and the question. No retrieval, indexing, or routing behaviour is touched. It is read at query time, so nothing needs rebuilding to test a variation.

That makes this cheap to try and expensive to get wrong. The refusal behaviour those four lines produce is the property the entire project rests on — it is why the corpus cites studies that do not exist, and why the evaluation set asks for the capital of Australia.

## Goals / Non-Goals

**Goals:**

- One unambiguous rule about inference, so equivalent questions get equivalent treatment.
- Grounding strength preserved exactly: every fact still traceable to a retrieved passage.
- The change measured against the evaluation set rather than judged by reading answers.

**Non-Goals:**

- Making the system answer more questions. If consistency means consistently declining a class of question, that is a success — the defect is unpredictability, not strictness.
- Any use of model knowledge outside retrieved context, under any framing.
- Prompt selection per question, per caller, or per configuration.

## Decisions

### Clarify the existing rule rather than add a second mode

The finding is that one instruction is ambiguous, not that the policy is wrong. A flag would preserve the ambiguity as a configuration axis and leave two prompts to maintain, each with its own failure profile, and would not answer the question the investigation raised.

The previous wording stays available in version control, which is all the before/after comparison needs.

Alternatives considered: a `--strict` / `--synthesis` flag with both prompts permanent; and a temporary flag deleted after measurement. Rejected for the reason above, and because the cleanup step in the second reliably does not happen.

### The axis is the source of facts, not the presence of reasoning

This is the distinction the prompt has to carry, and the one that keeps the change safe:

| | Facts from | Reasoning by |
|---|---|---|
| Before (as written) | context | unspecified — resolved inconsistently |
| After | context only | the model, explicitly permitted |
| Rejected | context **and training** | the model |

Framed this way, permitting inference does not weaken grounding at all. Reasoning over retrieved passages introduces no new facts, so the auditability property is untouched: a reader can still check every claim against the cited chunks. What changes is only whether the model is allowed to join two of them.

### Refusal is restated as a test of support, not of presence

The wording doing the damage is `If the context does not contain the answer`. *Contain* invites a reading where the answer must appear as text, which is what pulls the model toward extraction on some phrasings.

Rewriting it around whether the context *supports* the answer keeps the refusal behaviour while removing the extractive nudge. Context that lacks the underlying facts is still insufficient, however topically close it looks — which is the case the evaluation set already exercises.

### The refusal cases are the acceptance gate, not a nice-to-have

A prompt that gains synthesis and loses the refusal on *"What is the capital of Australia?"* has traded the project's central property for convenience, and must not ship regardless of how much better it reads.

This is the concrete risk in permitting inference: "reason from the context" and "reason from what you know" are neighbouring instructions, and `llama3.2` is a 3B model. The evaluation set can detect the leak precisely because its studies are fabricated — a model drifting toward training data has nothing correct to drift toward on those questions.

### Measure consistency, not just pass count

The defect is that equivalent questions get different treatment, and a total score cannot see that. Two questions requesting the same information from the same passages must now both be answered or both be declined.

The pair that exposed the problem — *"eat protein for what"* answered, *"why should I eat protein"* refused, same document, same four chunks, reproducible — becomes a permanent case, so the specific inconsistency that motivated this change cannot silently return.

### Synthesis answers are harder to grade than extraction

An extractive answer is graded by looking for a number. A synthesised answer is prose that could be right, wrong, or subtly unsupported, and the existing substring matcher cannot tell those apart — it also cannot distinguish a claim from its negation.

No new grading machinery is proposed. Cases are written so the expected substrings are the load-bearing terms of the conclusion, and the limitation is recorded rather than engineered around, consistent with how the harness already treats content cases.

## Risks / Trade-offs

- **Leak toward outside knowledge** — the main risk, and the reason this could fail outright → The refusal cases gate it, and the fabricated studies make a leak visible rather than plausible. If they break, the change does not ship.
- **Plausible-but-unsupported synthesis** — a model may join two facts into a conclusion neither supports → Partly mitigated by citation, which keeps answers checkable, and by the requirement that a conclusion needing an absent fact must be declined. Not fully solvable at this model size.
- **A 3B model may not honour the distinction reliably** → Measurable rather than arguable; if behaviour stays inconsistent, the finding is that prompt wording is not the lever and the change should be reverted rather than elaborated.
- **Grading weakness on prose answers** → Recorded above; keeps expectations on load-bearing terms.
- **No automated tests exist in this repository** — the evaluation set is the only gate, and it is not a unit test suite → Unchanged by this work, but it is the reason every claim here is stated as something to measure.

## Migration Plan

None required. The prompt is read at query time, the index format is untouched, and no re-ingest is needed. Rollback is reverting one string.

Ordering constraint: this change modifies two requirements that `add-corpus-metadata-questions` also modifies, and its delta specs are written against that change's post-archive text. Archiving in the reverse order would revert the corpus-metadata scoping clauses.

## Open Questions

- Whether synthesised answers eventually warrant a different grading approach than substring matching — a model-as-judge, or asserting which chunk each claim rests on. Deferred until there are enough synthesis cases to show whether substring grading actually misses anything, rather than building for a problem not yet observed.
