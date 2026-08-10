## MODIFIED Requirements

### Requirement: Substitutable store interface

The retrieval store SHALL be defined by an interface consisting of adding chunks with their vectors, searching by a query vector, and enumerating the distinct source documents it holds. Any implementation satisfying that interface SHALL be usable without modifying question-answering behaviour.

Enumeration is part of the interface because answering a question about the corpus requires knowing which documents exist, and that is knowable exactly rather than by similarity. It is specified as returning source identifiers rather than the stored chunks, so that a backend may satisfy it with a metadata query instead of materialising every chunk, and so that callers cannot reach past the interface into one implementation's internals.

#### Scenario: Backend replacement requires no caller changes

- **WHEN** an alternative store implementation satisfying the interface is supplied
- **THEN** indexing and answering behave equivalently
- **AND** no changes to the answering logic are required

#### Scenario: Enumerating source documents

- **WHEN** the distinct source documents of a store are requested
- **THEN** each source appears exactly once regardless of how many chunks it produced
- **AND** the result is ordered deterministically

#### Scenario: Enumeration is independent of search

- **WHEN** source documents are enumerated
- **THEN** no query vector is required
- **AND** no similarity computation is performed
