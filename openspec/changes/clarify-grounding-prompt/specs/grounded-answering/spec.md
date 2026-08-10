## MODIFIED Requirements

### Requirement: Answers restricted to retrieved context

For content questions — those not handled by the `corpus-metadata` capability — the system SHALL instruct the generation model to answer using only the retrieved passages supplied to it, and SHALL direct it not to draw on knowledge outside that context even where the model is confident such knowledge is correct.

The instruction SHALL state explicitly that the model may reason over the retrieved context and state conclusions that follow from it, including where the context does not phrase them as an answer. The distinction the system enforces is about the **source of facts**, not the presence of reasoning: every fact underpinning an answer must come from the retrieved passages, while the step from those facts to the answer may be the model's.

Leaving this unstated SHALL be treated as a defect. An instruction silent on whether inference is permitted is resolved inconsistently between questions, producing answers for some phrasings and refusals for others from identical retrieved context.

This requirement governs answers produced by retrieval. A corpus-metadata answer is computed directly from corpus facts without retrieval or generation, and is therefore outside its scope; that path has its own correctness guarantee, namely that it is derived from the index rather than inferred.

#### Scenario: Answer is drawn from retrieved content

- **WHEN** a question is asked whose answer appears only in the corpus
- **THEN** the answer reflects the corpus content
- **AND** the same question asked without retrieved context does not produce that answer

#### Scenario: Metadata question bypasses the retrieval contract

- **WHEN** a question is routed to the corpus-metadata path
- **THEN** no generation model is invoked
- **AND** the answer is computed from the corpus structure rather than from retrieved passages

#### Scenario: Conclusion supported by the context but not stated in it

- **WHEN** a question is asked whose answer follows from the retrieved passages without being stated as such in any of them
- **THEN** the answer states that conclusion
- **AND** every fact it relies on is present in the retrieved passages

#### Scenario: Equivalent questions answered consistently

- **WHEN** two questions requesting the same information are asked, and both retrieve passages supporting it
- **THEN** both are answered
- **AND** neither is refused on the grounds that the answer is not stated verbatim

#### Scenario: Reasoning does not license outside facts

- **WHEN** a conclusion would require a fact absent from the retrieved passages
- **THEN** that conclusion is not stated
- **AND** the response is `I don't know.`

### Requirement: Explicit refusal when context is insufficient

For content questions — those not handled by the `corpus-metadata` capability — when the retrieved context cannot support the answer, the system SHALL respond with the exact text `I don't know.` rather than producing a substitute answer.

Sufficiency SHALL be assessed as whether the context **supports** the answer, not whether it **states** it. Context that supports a conclusion without expressing it is sufficient; context that lacks the underlying facts is not, however closely it relates to the subject asked about.

This SHALL hold even when the generation model could answer correctly from its training data, because an answer not supported by the corpus cannot be audited against it. Permitting reasoning over the context SHALL NOT weaken this: the prohibition is on the origin of facts, and inference over retrieved passages introduces no new ones.

A corpus-metadata question SHALL NOT be answered with `I don't know.` on the grounds that the corpus lacks the subject asked about. Whether a subject is present is itself the answer, and the absence SHALL be reported explicitly.

#### Scenario: Question the corpus cannot answer

- **WHEN** a question is asked about a subject absent from the corpus
- **THEN** the response is `I don't know.`
- **AND** no fabricated detail is presented

#### Scenario: Widely-known fact absent from the corpus

- **WHEN** a question is asked whose answer the generation model knows from training but which the corpus does not contain
- **THEN** the response is `I don't know.`

#### Scenario: Metadata question about an uncovered subject

- **WHEN** the user asks whether the corpus covers a subject it does not cover
- **THEN** the response states that the subject is not covered and names the subject areas that are
- **AND** the response is not `I don't know.`

#### Scenario: Related context that does not support the answer

- **WHEN** retrieval returns passages on the subject asked about, none of which contain the facts the answer needs
- **THEN** the response is `I don't know.`
- **AND** the answer is not assembled from the model's own knowledge of the subject
