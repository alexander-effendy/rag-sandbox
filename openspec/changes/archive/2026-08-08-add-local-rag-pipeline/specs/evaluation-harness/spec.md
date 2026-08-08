## Purpose

Measures retrieval quality and answer quality as separate scores against a fixed question set, alongside baselines that show what retrieval actually contributes, so a regression can be attributed to the stage that caused it.

## ADDED Requirements

### Requirement: Retrieval and generation scored independently

The harness SHALL report a retrieval score and an answer score as distinct figures, so that a failure where the correct source was retrieved is distinguishable from one where it was not.

#### Scenario: Both scores reported

- **WHEN** the evaluation completes
- **THEN** a retrieval score and an answer score are reported separately
- **AND** neither is derived from the other

#### Scenario: Correct source retrieved but answer wrong

- **WHEN** a case retrieves its expected source but the answer lacks the expected content
- **THEN** the case is recorded as a retrieval success and an answer failure

### Requirement: Fixed question set with declared expectations

The harness SHALL evaluate against a stored question set in which each case declares the source document expected to be retrieved and the content expected in the answer.

A case MAY declare that no source is expected, marking it as a case the corpus cannot answer.

#### Scenario: Case expectations drive scoring

- **WHEN** a case declares an expected source and expected answer content
- **THEN** retrieval is scored on whether that source was retrieved
- **AND** the answer is scored on whether it contains the expected content

### Requirement: Refusal cases excluded from the retrieval denominator

Cases declaring no expected source SHALL be excluded from the retrieval score's denominator, since no correct source exists to retrieve, and SHALL still be scored on whether the system correctly declined.

#### Scenario: Refusal case scoring

- **WHEN** a case declares no expected source
- **THEN** it does not contribute to the retrieval denominator
- **AND** it is scored on whether the answer was the expected refusal

### Requirement: Unretrieved baseline comparison

The harness SHALL support scoring every case with no retrieved context, using the same generation model, and SHALL report that score alongside the retrieval-assisted score.

#### Scenario: Baseline reported for comparison

- **WHEN** baseline comparison is requested
- **THEN** each case is additionally answered without retrieval
- **AND** the totals for both modes are reported together

### Requirement: Full-context baseline comparison

The harness SHALL support scoring every case with the entire corpus supplied as context instead of retrieved passages, and SHALL report accuracy and prompt size for that mode alongside the retrieval-assisted mode.

This exists so the choice to retrieve is justified by measurement rather than assumption.

#### Scenario: Whole-corpus mode is measured

- **WHEN** the full-context comparison is run
- **THEN** each case is answered with every corpus document supplied as context
- **AND** accuracy and average prompt size are reported for retrieval, full-context, and unretrieved modes

### Requirement: Diagnostic output on failure

For each failing case the harness SHALL report the expected content, the answer produced, and the passages that were retrieved with their similarity scores. Passing cases SHALL NOT produce this detail.

#### Scenario: Failure detail aids diagnosis

- **WHEN** a case fails
- **THEN** the expected content, the produced answer, and the retrieved sources with scores are reported

#### Scenario: Passing cases stay terse

- **WHEN** a case passes
- **THEN** only its identifier and result are reported

### Requirement: Evaluation against an alternate index

The harness SHALL accept an index location other than the default, so two indexes built with different settings can be scored and compared without rebuilding either.

#### Scenario: Comparing two indexing configurations

- **WHEN** an alternate index location is supplied
- **THEN** the evaluation scores that index
- **AND** the default index is left unmodified

### Requirement: Machine-readable success signal

The harness SHALL exit with a success status only when every case passes, and a non-success status otherwise, so it can gate automation.

#### Scenario: Failure is signalled to the caller

- **WHEN** at least one case fails
- **THEN** the process exits with a non-success status

### Requirement: Corpus designed to prove retrieval

The evaluation corpus SHALL include content that the generation model cannot know from training, so that a correct answer demonstrates retrieval rather than recall. Such content SHALL be clearly marked as fabricated within the corpus.

#### Scenario: A correct answer demonstrates retrieval

- **WHEN** a case asks about a fact present only in the corpus
- **AND** the retrieval-assisted answer is correct while the unretrieved baseline answer is not
- **THEN** retrieval is demonstrated to have supplied the answer

#### Scenario: Fabricated content is disclosed

- **WHEN** a corpus document contains invented facts or sources
- **THEN** the document states that its content is synthetic and not factual
