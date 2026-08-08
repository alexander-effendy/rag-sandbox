# Text Embeddings

*Synthetic document written for RAG testing. Technical details are broadly accurate; named benchmarks may be fictional.*

## What an Embedding Is

An embedding is a fixed-length list of numbers that represents a piece of text, produced by a model trained so that texts with similar meanings land near each other in the resulting space.

The critical property is that similarity becomes geometry. Once text is embedded, "how related are these two documents" becomes "how close are these two points", and closeness is something a computer can compute over millions of items very quickly. This is the entire basis of semantic search.

The dimensionality is a property of the model, not of the text. Every text embedded by a given model produces a vector of exactly the same length, whether the input is one word or five hundred.

## Common Models and Their Dimensions

The `all-MiniLM-L6-v2` model produces 384-dimensional vectors and is roughly 22 million parameters, small enough to run comfortably on a laptop CPU. It remains a strong default for retrieval despite its size.

`nomic-embed-text` produces 768-dimensional vectors and generally outperforms MiniLM on retrieval benchmarks, at the cost of a larger model and slower embedding. It also supports a longer context window of 8,192 tokens against MiniLM's 512.

Larger dimensionality is not automatically better. More dimensions cost more storage and more computation per query, and the relationship between dimensionality and retrieval quality flattens quickly. Model architecture and training data matter far more than vector length.

## Cosine Similarity

The standard way to compare two embeddings is cosine similarity: the cosine of the angle between the two vectors.

It ranges from -1 to 1, where 1 means the vectors point in exactly the same direction and 0 means they are orthogonal. In practice, embeddings from most modern models are non-negative enough that scores cluster between 0 and 1.

The useful trick is that if both vectors are first normalised to unit length, cosine similarity reduces to a plain dot product. Normalising the entire document matrix once at index time turns every subsequent query into a single matrix multiplication, which is why production vector stores almost always store normalised vectors.

Euclidean distance is the common alternative. For normalised vectors the two produce identical rankings, so the choice only matters if vectors are unnormalised, where cosine ignores magnitude and Euclidean does not.

## Symmetric and Asymmetric Search

A subtlety that catches people out is that questions and documents do not look alike.

A short question and a long passage that answers it may embed to noticeably different regions of the space, even though one answers the other. Models trained specifically for retrieval address this with asymmetric training, learning to place a question near its answer rather than near other questions.

Some models expose this explicitly through prefixes, expecting `search_query:` before a question and `search_document:` before a passage. Using the wrong prefix, or omitting them entirely on a model that expects them, degrades retrieval quality noticeably while producing no error at all.

The corresponding rule is absolute: documents and queries must be embedded with the same model. Vectors from two different models occupy unrelated spaces, and comparing them returns confident nonsense rather than a failure.
