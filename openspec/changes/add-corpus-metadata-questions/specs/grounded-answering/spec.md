## MODIFIED Requirements

### Requirement: Answers restricted to retrieved context

For content questions — those not handled by the `corpus-metadata` capability — the system SHALL instruct the generation model to answer using only the retrieved passages supplied to it, and SHALL direct it not to draw on knowledge outside that context even where the model is confident such knowledge is correct.

This requirement governs answers produced by retrieval. A corpus-metadata answer is computed directly from corpus facts without retrieval or generation, and is therefore outside its scope; that path has its own correctness guarantee, namely that it is derived from the index rather than inferred.

#### Scenario: Answer is drawn from retrieved content

- **WHEN** a question is asked whose answer appears only in the corpus
- **THEN** the answer reflects the corpus content
- **AND** the same question asked without retrieved context does not produce that answer

#### Scenario: Metadata question bypasses the retrieval contract

- **WHEN** a question is routed to the corpus-metadata path
- **THEN** no generation model is invoked
- **AND** the answer is computed from the corpus structure rather than from retrieved passages

### Requirement: Explicit refusal when context is insufficient

For content questions — those not handled by the `corpus-metadata` capability — when the retrieved context does not contain the answer, the system SHALL respond with the exact text `I don't know.` rather than producing a substitute answer.

This SHALL hold even when the generation model could answer correctly from its training data, because an answer not supported by the corpus cannot be audited against it.

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
