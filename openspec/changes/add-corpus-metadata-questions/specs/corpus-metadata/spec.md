## Purpose

Answers questions about the corpus itself — how many documents it holds, which documents and subject areas it contains, and whether a given subject is covered — computed exactly from the index and directory structure instead of being searched for semantically.

## ADDED Requirements

### Requirement: Corpus-metadata questions bypass retrieval

A question about the corpus itself SHALL be answered without embedding the question, without searching the index, and without invoking the generation model.

Routing SHALL be evaluated before retrieval, so a metadata question never incurs an embedding call.

#### Scenario: Metadata question performs no retrieval

- **WHEN** a corpus-metadata question is asked
- **THEN** the answer is returned with no retrieved passages
- **AND** no embedding request and no generation request are made

#### Scenario: Routing is evaluated before retrieval

- **WHEN** any question is asked
- **THEN** metadata routing is evaluated first
- **AND** retrieval runs only if routing did not match

### Requirement: Document count

The system SHALL report the number of distinct source documents in the corpus, counting each document once regardless of how many chunks it produced.

#### Scenario: Reporting how many documents exist

- **WHEN** the user asks how many documents the corpus contains
- **THEN** the response states the number of distinct source documents
- **AND** that number matches the number of distinct sources in the index

#### Scenario: Count is unaffected by chunk count

- **WHEN** one document produces many chunks
- **THEN** it contributes exactly one to the reported document count

### Requirement: Document and subject-area listing

The system SHALL report the documents in the corpus grouped by subject area, listing every document rather than a sample or a highest-scoring subset.

#### Scenario: Listing what the corpus contains

- **WHEN** the user asks what documents or subjects the corpus contains
- **THEN** the response names every subject area
- **AND** every document in the corpus is accounted for

#### Scenario: Listing is exhaustive, not ranked

- **WHEN** a subject area contains more documents than a retrieval result would return
- **THEN** all of that area's documents are reported

### Requirement: Subject coverage check

The system SHALL report whether a named subject is covered by the corpus. When it is not, the response SHALL state the absence and name the subject areas that are covered, rather than declining.

#### Scenario: Subject that is covered

- **WHEN** the user asks whether the corpus covers a subject matching an existing subject area
- **THEN** the response confirms coverage
- **AND** names the documents in that area

#### Scenario: Subject that is not covered

- **WHEN** the user asks whether the corpus covers a subject with no matching subject area
- **THEN** the response states that the subject is not covered
- **AND** names the subject areas that are covered
- **AND** the response is not `I don't know.`

### Requirement: Deterministic metadata answers

Metadata answers SHALL be computed and formatted directly from corpus facts, without a generation model. The same question against an unchanged corpus SHALL produce a byte-identical answer.

#### Scenario: Repeated question gives an identical answer

- **WHEN** the same metadata question is asked twice against an unchanged index
- **THEN** both responses are byte-identical

#### Scenario: Answers track the corpus

- **WHEN** a document is added or removed and the corpus is re-indexed
- **THEN** subsequent metadata answers reflect the new contents

### Requirement: Routing anchored on corpus nouns

Routing SHALL match only when a question refers to the collection itself using a corpus noun such as `document`, `documents`, `docs`, or `files`. A question SHALL NOT be routed on interrogative form alone.

#### Scenario: Content question sharing a metadata question form

- **WHEN** a content question uses a metadata-like form without referring to the collection, such as asking how many dimensions a model produces
- **THEN** routing does not match
- **AND** the question is answered by the normal retrieval pipeline

#### Scenario: Existing evaluation cases are unaffected

- **WHEN** the existing content-question evaluation set is run
- **THEN** no case is routed to the metadata path

### Requirement: Fall-through to the retrieval pipeline

When routing does not match, the system SHALL run the existing retrieval pipeline with its behaviour unchanged.

#### Scenario: Unmatched question uses the normal pipeline

- **WHEN** a question does not match metadata routing
- **THEN** it is embedded, retrieved, and answered exactly as before this capability existed

### Requirement: Subject areas derived from corpus structure

Subject areas SHALL be derived from the immediate subdirectory of each document beneath the corpus root, so grouping is exact rather than inferred from content.

A document stored directly at the corpus root has no subject area, and SHALL be reported under an explicit uncategorised grouping rather than omitted.

#### Scenario: Document in a subject directory

- **WHEN** a document is stored under a subdirectory of the corpus root
- **THEN** that subdirectory's name is reported as its subject area

#### Scenario: Document at the corpus root

- **WHEN** a document is stored directly at the corpus root
- **THEN** it is reported under an explicit uncategorised grouping
- **AND** it is included in the document count

### Requirement: Metadata answers are distinguishable

A metadata answer SHALL be distinguishable by a caller from a retrieval-backed answer, and SHALL carry no retrieved passages, so that evaluation and any user interface can tell which path produced it.

#### Scenario: Caller can identify the answering path

- **WHEN** a metadata question is answered
- **THEN** the result indicates it came from the metadata path
- **AND** its retrieved-passage list is empty
