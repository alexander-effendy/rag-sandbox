# semantic-retrieval Specification

## Purpose

Given a natural-language query, returns the stored chunks whose meaning is closest to it, ranked by similarity, behind an interface narrow enough that the underlying store can be replaced without affecting callers.

## Requirements

### Requirement: Semantic matching independent of shared vocabulary

Retrieval SHALL rank chunks by semantic similarity rather than term overlap, so that a query sharing no distinctive wording with a passage can still retrieve it.

#### Scenario: Query with no shared terms retrieves the right passage

- **WHEN** a query asks about a topic using different vocabulary than the source passage
- **THEN** the passage is returned among the top results
- **AND** its rank reflects meaning rather than word overlap

### Requirement: Consistent embedding across indexing and querying

Queries SHALL be embedded with the same embedding model used to embed the indexed documents. The system SHALL NOT silently compare vectors produced by different embedding models, since such comparison yields plausible but meaningless rankings with no error condition.

#### Scenario: Query and documents use one embedding model

- **WHEN** a query is issued against an index
- **THEN** the query is embedded with the same model that produced the index
- **AND** the resulting scores are comparable to the stored vectors

### Requirement: Ranked results with scores and attribution

Retrieval SHALL return at most a caller-specified number of results, ordered by descending similarity. Each result SHALL carry its similarity score and an identifier of the source document and section it came from.

Similarity scores SHALL be meaningful for ordering results within a single query. The system SHALL NOT treat a score as an absolute confidence value comparable across different queries.

#### Scenario: Results are ordered and attributed

- **WHEN** a query retrieves results
- **THEN** results are ordered from most to least similar
- **AND** each carries a similarity score and a source identifier suitable for citation

#### Scenario: Result count is bounded by the caller

- **WHEN** a caller requests at most N results
- **THEN** no more than N results are returned

### Requirement: Exact similarity search

Retrieval SHALL compare a query against every indexed chunk, so a result is never missed due to index approximation. Any future approximate backend SHALL be an explicit, documented substitution rather than a silent default.

#### Scenario: Every chunk is considered

- **WHEN** a query is issued
- **THEN** the returned ranking reflects a comparison against all indexed chunks

### Requirement: Substitutable store interface

The retrieval store SHALL be defined by an interface consisting of adding chunks with their vectors and searching by a query vector. Any implementation satisfying that interface SHALL be usable without modifying question-answering behaviour.

#### Scenario: Backend replacement requires no caller changes

- **WHEN** an alternative store implementation satisfying the interface is supplied
- **THEN** indexing and answering behave equivalently
- **AND** no changes to the answering logic are required

### Requirement: Optional similarity floor

Retrieval SHALL support discarding results below a caller-specified similarity score. The floor SHALL default to zero, so that no results are discarded unless a caller opts in.

#### Scenario: Floor defaults to keeping all results

- **WHEN** no similarity floor is specified
- **THEN** all results up to the requested count are returned regardless of score

#### Scenario: Floor removes weak matches

- **WHEN** a similarity floor is specified
- **THEN** results scoring below it are excluded from the returned set

### Requirement: Empty index handling

Searching an index containing no chunks SHALL return an empty result set rather than raising an error.

#### Scenario: Search against an empty index

- **WHEN** a query is issued against a store containing no chunks
- **THEN** an empty result set is returned
- **AND** no error is raised
