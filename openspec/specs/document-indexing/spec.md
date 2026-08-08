# document-indexing Specification

## Purpose

Turns a directory of markdown documents into a persisted, searchable index of embedded text chunks, preserving enough surrounding context that each chunk remains interpretable on its own.

## Requirements

### Requirement: Recursive document discovery

The system SHALL discover all markdown documents beneath a specified corpus directory, including nested subdirectories, and SHALL process them in a deterministic order so that repeated indexing runs over unchanged input produce an identical index.

The system SHALL exclude documents named `README.md` from the corpus, because documentation describing a corpus is not part of that corpus and would otherwise compete with real content for retrieval slots.

#### Scenario: Documents in nested directories are indexed

- **WHEN** the corpus directory contains markdown files in subdirectories
- **THEN** every such file is included in the index
- **AND** each indexed chunk records a source identifier relative to the corpus root

#### Scenario: README files are excluded

- **WHEN** the corpus directory contains a `README.md`
- **THEN** its content does not appear in the index
- **AND** it cannot be returned as a retrieval result

#### Scenario: Indexing is reproducible

- **WHEN** the corpus is indexed twice with no intervening changes
- **THEN** both runs produce the same chunks in the same order

### Requirement: Context-preserving chunking

The system SHALL split documents into chunks small enough to embed precisely, and each chunk SHALL carry the nearest preceding section heading so it remains interpretable without its surrounding document.

Chunk size and overlap SHALL be configurable at index time.

#### Scenario: Chunks carry their section heading

- **WHEN** a document section has a heading and a body longer than one chunk
- **THEN** every chunk derived from that section includes the heading text
- **AND** the heading is available for display and citation

#### Scenario: Chunk size is configurable

- **WHEN** a caller specifies a chunk size different from the default
- **THEN** the resulting chunks reflect that size
- **AND** the index reports the resulting chunk count

### Requirement: Overlapping chunk boundaries

Consecutive chunks derived from the same section SHALL share a configurable number of words, so that a fact spanning a chunk boundary remains intact within at least one chunk.

The system SHALL reject an overlap greater than or equal to the chunk size, with a message naming both values, rather than producing an index that never advances.

#### Scenario: Adjacent chunks overlap

- **WHEN** a section is long enough to produce two or more chunks
- **THEN** each chunk after the first repeats the configured number of trailing words from its predecessor

#### Scenario: Invalid overlap is rejected before any work

- **WHEN** indexing is requested with an overlap greater than or equal to the chunk size
- **THEN** the operation fails with a message naming both values
- **AND** no index is written and no embedding requests are made

### Requirement: Index persistence and reload

The system SHALL persist the index so subsequent queries can reload it without re-embedding the corpus, and SHALL store chunk text in a human-readable form so chunk boundaries can be inspected directly.

#### Scenario: Index survives across processes

- **WHEN** an index is built and the process exits
- **THEN** a later process can load that index and answer queries against it
- **AND** no embedding requests are made for corpus documents during loading

#### Scenario: Querying without an index gives an actionable error

- **WHEN** a query is attempted against a directory containing no index
- **THEN** the operation fails with a message naming the missing location and the command that builds one

### Requirement: Full-rebuild indexing semantics

Indexing SHALL rebuild the index from the current corpus contents, so that added, edited, and deleted documents are all reflected without a separate invalidation step.

#### Scenario: A new document becomes retrievable

- **WHEN** a document is added to the corpus and indexing is re-run
- **THEN** the reported document and chunk counts increase
- **AND** questions answerable only from the new document are answered from it

#### Scenario: A deleted document stops being retrievable

- **WHEN** a document is removed from the corpus and indexing is re-run
- **THEN** its content no longer appears in retrieval results
- **AND** questions answerable only from it are declined

### Requirement: Precondition validation before indexing

The system SHALL verify that the generation service is reachable and that the required models are available before performing any chunking or embedding work, and SHALL report each failure with the command that resolves it.

#### Scenario: Generation service unavailable

- **WHEN** indexing is requested while the model service is not running
- **THEN** the operation fails with a message identifying the unreachable service and how to start it
- **AND** the failure occurs before any documents are processed

#### Scenario: Required model not installed

- **WHEN** indexing is requested and a required model is not installed
- **THEN** the operation fails with a message naming the missing model and the command that installs it

#### Scenario: Empty corpus

- **WHEN** indexing is requested against a directory containing no markdown documents
- **THEN** the operation fails with a message naming the directory searched
