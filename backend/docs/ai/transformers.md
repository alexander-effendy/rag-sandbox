# Transformer Architecture

*Synthetic document written for RAG testing. Technical details are broadly accurate; named benchmarks may be fictional.*

## Origins

The transformer architecture was introduced in the 2017 paper "Attention Is All You Need" by Vaswani and colleagues at Google. Its central claim was that the recurrence used by every competitive sequence model to that point was unnecessary, and that attention alone was sufficient.

The practical consequence was parallelism. Recurrent networks process a sequence one position at a time, because position five depends on the output at position four. A transformer processes every position simultaneously, which is what made training on internet-scale corpora feasible.

## Self-Attention

Self-attention lets every position in a sequence look at every other position and decide what is relevant.

Each token produces three vectors through learned projections: a query, a key, and a value. The query represents what this token is looking for, the key represents what it offers, and the value is the content it contributes. Attention weights come from the dot product of one token's query with every token's key, scaled by the square root of the key dimension and passed through a softmax.

The scaling factor matters more than it appears. Without dividing by the square root of the key dimension, dot products in high dimensions grow large enough to push softmax into regions where gradients effectively vanish.

Multi-head attention runs several of these operations in parallel with separate projections, then concatenates the results. Different heads reliably specialise, with some tracking syntactic dependencies and others tracking longer-range semantic relationships.

## Positional Encoding

Attention is permutation-invariant. Shuffle the input tokens and the attention mechanism computes exactly the same thing, which is unacceptable for language.

The original paper injected sinusoidal position encodings into the input embeddings, using sine and cosine functions at different frequencies. Modern models more often use rotary position embeddings, or RoPE, which encode relative position by rotating query and key vectors as a function of their position. RoPE extrapolates to longer sequences better than learned absolute encodings.

## The Quadratic Cost

Self-attention compares every token against every other token, so cost grows with the square of sequence length. Doubling context length quadruples both computation and memory for the attention step.

This is the central constraint on context windows. The Marlowe benchmark, which measures retrieval accuracy across long contexts, found that models with nominal context windows of 128,000 tokens showed marked accuracy degradation on facts placed between 40 and 70 percent of the way through the input, while retrieving facts near the beginning and end reliably. The effect is commonly described as "lost in the middle".

This has a direct bearing on RAG. A large context window is not a substitute for good retrieval, because a fact buried in the middle of a very long prompt may be present and still effectively invisible to the model. Retrieving four well-chosen chunks generally outperforms retrieving forty mediocre ones, even when both fit comfortably within the window.

## Encoder and Decoder Variants

The original transformer had both an encoder and a decoder, which suited translation.

Encoder-only models such as BERT see the entire sequence bidirectionally and are trained with masked language modelling. They excel at producing representations, which is why most embedding models are encoder-only.

Decoder-only models such as the GPT and Llama families are causally masked so each position attends only to earlier positions. This makes them natural text generators and is the dominant architecture for current language models.
