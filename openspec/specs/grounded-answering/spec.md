# grounded-answering Specification

## Purpose

Answers a question using only the passages retrieved for it, declining explicitly when those passages do not support an answer, and returning the evidence alongside the answer so the result can be audited.

## Requirements

### Requirement: Answers restricted to retrieved context

The system SHALL instruct the generation model to answer using only the retrieved passages supplied to it, and SHALL direct it not to draw on knowledge outside that context even where the model is confident such knowledge is correct.

#### Scenario: Answer is drawn from retrieved content

- **WHEN** a question is asked whose answer appears only in the corpus
- **THEN** the answer reflects the corpus content
- **AND** the same question asked without retrieved context does not produce that answer

### Requirement: Explicit refusal when context is insufficient

When the retrieved context does not contain the answer, the system SHALL respond with the exact text `I don't know.` rather than producing a substitute answer.

This SHALL hold even when the generation model could answer correctly from its training data, because an answer not supported by the corpus cannot be audited against it.

#### Scenario: Question the corpus cannot answer

- **WHEN** a question is asked about a subject absent from the corpus
- **THEN** the response is `I don't know.`
- **AND** no fabricated detail is presented

#### Scenario: Widely-known fact absent from the corpus

- **WHEN** a question is asked whose answer the generation model knows from training but which the corpus does not contain
- **THEN** the response is `I don't know.`

### Requirement: Source citation

The system SHALL direct the generation model to cite the sources it used, and SHALL make available the distinct source documents behind an answer, ordered with the highest-scoring source first and without duplicates.

#### Scenario: Sources accompany an answer

- **WHEN** a question is answered from retrieved context
- **THEN** the source documents behind it are reported
- **AND** a document appearing in several retrieved chunks is listed once

### Requirement: Evidence returned with every answer

An answer SHALL be returned together with the retrieved passages and their similarity scores that produced it, so a caller can distinguish an answer that failed because the wrong passages were retrieved from one that failed despite the right passages being retrieved.

#### Scenario: Retrieved evidence is inspectable

- **WHEN** a question is answered
- **THEN** the retrieved passages and their scores are available alongside the answer text

### Requirement: Short-circuit when nothing is retrieved

When retrieval returns no results, the system SHALL return the refusal response directly and SHALL NOT invoke the generation model with an empty context.

#### Scenario: No results survive retrieval

- **WHEN** retrieval returns no passages for a question
- **THEN** the response is `I don't know.`
- **AND** no generation request is made

### Requirement: Comparable generation across runs

The system SHALL pin generation sampling to its least random setting, so that differences between runs are attributable to changes under test rather than to sampling. The system SHALL NOT represent output as exactly reproducible, since the underlying service does not guarantee this.

#### Scenario: Repeated runs are comparable

- **WHEN** the same question is answered twice against an unchanged index
- **THEN** the answers agree on substantive content
- **AND** any residual variation is treated as noise rather than as a change in behaviour

### Requirement: Unretrieved baseline answering

The system SHALL provide a way to answer a question with no retrieved context, using the same generation model, so the contribution of retrieval can be measured rather than assumed.

#### Scenario: Baseline answer without retrieval

- **WHEN** a question is answered in unretrieved baseline mode
- **THEN** no retrieval is performed and no index is required
- **AND** the response is identifiable as having had no supporting context
