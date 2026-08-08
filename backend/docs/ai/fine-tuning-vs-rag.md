# Fine-Tuning Versus RAG

*Synthetic document written for RAG testing. Technical details are broadly accurate; named benchmarks may be fictional.*

## The Distinction

The two techniques are frequently framed as competitors, which obscures that they solve different problems.

RAG changes what the model knows at the moment it answers. Fine-tuning changes how the model behaves in general.

The clearest formulation is that fine-tuning teaches form and RAG supplies facts. A model fine-tuned on legal correspondence learns the register, structure, and conventions of legal writing. It does not thereby learn the contents of any particular contract, and asking it about a specific clause will produce fluent, well-formatted invention.

## When RAG Is the Right Tool

RAG is appropriate when the knowledge changes, when answers must cite sources, when the corpus is large relative to what fits in a prompt, or when access to information must be controlled per user.

The economics strongly favour RAG for knowledge tasks. Adding a document to a RAG system costs one embedding call. Adding a document to a fine-tuned model costs a retraining run, and the model still cannot tell you which document an answer came from.

Access control is the argument that usually settles it in enterprise settings. A fine-tuned model has absorbed its training data into weights that cannot be selectively revoked, so a model trained on documents from every department will happily answer questions about all of them regardless of who is asking. A RAG system filters at retrieval time, which is a solvable permissions problem rather than an intractable one.

## When Fine-Tuning Is the Right Tool

Fine-tuning earns its cost when the requirement is consistent behaviour rather than specific knowledge.

Output format is the most common case. A model that must always return valid JSON matching a particular schema is far more reliably fine-tuned than prompted. Tone and voice are similar: a support assistant that must match a company's established style is a form problem.

Fine-tuning also buys efficiency. Behaviour that requires a two-thousand-token system prompt can often be baked into weights, which reduces per-request cost and latency. At high volume this alone can justify the training cost.

Specialised domains where the vocabulary itself is unfamiliar are the remaining case. A model that has seen very little of a technical field may tokenise and represent its terminology poorly, and no amount of retrieved context fully compensates for that.

## Using Both

The two compose cleanly, and the strongest systems generally use both.

A typical arrangement fine-tunes a model to follow a house format, cite sources in a particular way, and reliably decline when context is insufficient, then uses RAG to supply the actual facts at query time. Behaviour comes from weights, knowledge comes from retrieval.

The recommended sequence is to start with RAG and good prompting, measure where it falls short, and fine-tune only for the failures that are demonstrably about behaviour rather than knowledge. Reversing this order is a common and expensive mistake, because a fine-tune undertaken to fix a knowledge gap produces a model that is wrong in the same ways but more confidently.

## Parameter-Efficient Methods

Full fine-tuning updates every weight and requires memory proportional to the full model, which puts it out of reach for most teams on larger models.

LoRA, or Low-Rank Adaptation, freezes the original weights and trains small rank-decomposition matrices injected alongside them. It typically trains under 1 percent of the parameters while approaching full fine-tuning quality on many tasks. QLoRA extends this by quantising the frozen base model to 4-bit, which is what makes fine-tuning a mid-sized model on a single consumer GPU practical.

A useful side effect is that LoRA adapters are small, often a few tens of megabytes, and can be swapped at inference time. One base model can serve many specialisations without holding many full copies in memory.
