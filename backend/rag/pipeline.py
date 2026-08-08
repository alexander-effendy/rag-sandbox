"""
WHAT THIS FILE DOES
===================
Joins the pieces together into the actual RAG loop. This is the file that
answers a question.

    question
       |
       v
    [1] embed the question              (ollama_client.embed_one)
       |
       v
    [2] find the nearest chunks         (store.search)
       |
       v
    [3] paste them into a prompt        (build_prompt)
       |
       v
    [4] ask the language model          (ollama_client.generate)
       |
       v
    answer

That is retrieval-augmented generation, complete. The name is literal:
generation, augmented by retrieval.

WHERE THE DIFFICULTY ACTUALLY LIVES
===================================
Steps 1 and 4 are single function calls. Step 2 is three lines of NumPy. Nearly
all real-world RAG quality work happens in step 3 and in the chunking that fed
step 2 -- deciding what to retrieve, how much, and how honestly you frame it to
the model.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import corpus_metadata, ollama_client
from .chunking import Chunk
from .store import SearchResult, VectorStore

# The two ways a question can be answered. See Answer.path.
RETRIEVAL_PATH = "retrieval"  # embed -> search -> prompt -> generate
METADATA_PATH = "metadata"  # computed from the index, no model involved

# ---------------------------------------------------------------------------
# THE PROMPT. Small, and responsible for a lot.
#
# Everything here is defending against ONE failure mode: the model answering
# from its training data instead of from the chunks we gave it. That failure is
# especially nasty because a wrong answer looks exactly like a right one --
# same fluency, same confidence, no error anywhere.
#
# Line by line:
#
#   "ONLY the context below"  -- capitalised because it demonstrably helps;
#                                models weight emphasis in instructions.
#
#   "reply exactly: I don't know"  -- gives the model a legitimate exit. Without
#                                an explicit way to decline, a model asked a
#                                question will nearly always produce *something*,
#                                and that something is invention.
#
#   "even if you are confident"  -- this line is doing real work. Test it: ask
#                                "What is the capital of Australia?" The model
#                                knows the answer perfectly well, and correctly
#                                refuses, because it is not in the corpus.
#
#   "Cite the sources"        -- makes the answer auditable. You can check
#                                whether the citation actually supports it.
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """\
Answer the question using ONLY the context below.

Rules:
- If the context does not contain the answer, reply exactly: I don't know.
- Do not use outside knowledge, even if you are confident it is correct.
- Cite the sources you used as [source] at the end of your answer.

Context:
{context}

Question: {question}

Answer:"""

# Returned when retrieval finds nothing at all, so we never call the model with
# an empty context. Matches the wording the prompt asks for, so downstream
# checks only have to look for one phrase.
NO_CONTEXT_ANSWER = "I don't know."


@dataclass
class Answer:
    """The model's answer plus the evidence behind it.

    Returning the retrieved chunks alongside the text -- rather than just the
    text -- is what makes the system debuggable. When an answer is wrong you
    need to know whether the right chunk was retrieved and the model misread
    it, or whether the right chunk never arrived. Those have completely
    different fixes, and you cannot tell them apart from the answer alone.
    """

    question: str
    text: str
    retrieved: list[SearchResult]  # [(chunk, score), ...], best first

    # Which path produced this answer: RETRIEVAL_PATH or METADATA_PATH.
    #
    # Needed because a metadata answer has an empty `retrieved` list, and so
    # does a content question where retrieval found nothing. Those two look
    # identical from the outside and mean opposite things -- one is a complete,
    # exact answer, the other is a refusal. evaluate.py must not score the
    # first as a refusal, and a frontend rendering retrieved chunks needs to
    # know there are legitimately none.
    #
    # Stored explicitly rather than inferred from `retrieved` being empty,
    # because that inference would silently misclassify the day a content
    # question legitimately retrieves nothing. Defaulted so every existing
    # construction site keeps working unchanged.
    path: str = RETRIEVAL_PATH

    @property
    def sources(self) -> list[str]:
        """Unique source filenames, best-scoring first, no duplicates.

        Several chunks usually come from the same document, so a plain list
        would repeat it. dict preserves insertion order in modern Python, so
        using it as an ordered set keeps best-first ordering. (set() would
        deduplicate but scramble the order.)
        """
        seen: dict[str, None] = {}
        for chunk, _ in self.retrieved:
            seen.setdefault(chunk.source, None)
        return list(seen)


def retrieve(question: str, store: VectorStore, k: int = 4) -> list[SearchResult]:
    """STEPS 1 AND 2: embed the question, then find the nearest chunks.

    THE RULE THAT MATTERS MOST IN THIS ENTIRE FILE
    ----------------------------------------------
    The question must be embedded with the SAME model used on the documents.

    Different embedding models produce vectors in unrelated spaces. Comparing
    across them does not error -- the shapes may even match -- it just returns
    confident nonsense. You get plausible-looking chunks that have nothing to do
    with the question, and no signal anywhere that something is wrong.

    This is a genuinely common production bug: someone upgrades the embedding
    model, forgets to re-index, and retrieval quietly degrades to noise.

    ABOUT k
    -------
    How many chunks to retrieve. Too few and the answer may not be among them.
    Too many and you dilute the prompt with irrelevant text, and models attend
    less reliably to material buried in a long context. 4 is a sane default;
    try `evaluate.py -k 20` to test the upper end on this corpus.
    """
    return store.search(ollama_client.embed_one(question), k=k)


def format_context(results: list[SearchResult]) -> str:
    """Lay the retrieved chunks out as text for the prompt.

    The [label] header on each chunk is what makes citation possible -- the
    model can only name its source if we tell it what the source was. Renders as:

        [nutrition/protein.md § Daily Intake Targets]
        Daily Intake Targets  The baseline recommendation for...

        [nutrition/protein.md § The Leucine Threshold]
        The Leucine Threshold  Protein synthesis does not respond...

    Note we do NOT include the similarity scores. Numbers in a prompt invite
    the model to reason about them, and its job is to read the text, not to
    second-guess the retrieval.
    """
    return "\n\n".join(f"[{chunk.label}]\n{chunk.text}" for chunk, _ in results)


def build_prompt(question: str, results: list[SearchResult]) -> str:
    """STEP 3: drop the chunks and the question into the template.

    Worth running `ask.py --show-chunks` to watch what this produces. RAG can
    feel opaque until you see that the "augmentation" is literally string
    formatting -- the model receives one block of text, and its only advantage
    over a bare model is that the answer is sitting in that text.
    """
    return PROMPT_TEMPLATE.format(context=format_context(results), question=question)


def answer(
    question: str,
    store: VectorStore,
    k: int = 4,
    min_score: float = 0.0,
) -> Answer:
    """The whole loop, end to end. This is the function the scripts call.

    ABOUT min_score, AND WHY IT DEFAULTS TO 0.0
    -------------------------------------------
    A similarity floor. Chunks scoring below it are discarded, and if that
    leaves nothing we decline without calling the model at all.

    Setting a threshold is the obvious way to stop the system answering from
    weak matches. It is much blunter than it looks. Measured across the eval
    set on this corpus:

        worst correct retrieval   0.442   <- must be KEPT
        best  should-be-rejected  0.405   <- must be DROPPED

    Those are 0.037 apart. Any threshold separating them is fitted to these
    twenty questions and will not survive the twenty-first. Score also depends
    heavily on how a question is phrased -- the same fact scores 0.205 or 0.702
    depending on question length -- so the floor punishes terse questions
    rather than irrelevant ones.

    Hence the default of 0.0: keep everything, and let the grounding
    instructions in the prompt handle refusal, which they do well (both refusal
    tests pass with no threshold at all). If you do want a floor, measure your
    own distribution first rather than borrowing a number -- and treat it as a
    coarse safety net, not a confidence score.
    """
    # ---- STEP 0: is this a question ABOUT the corpus rather than about what
    # is in it? "How many documents do you have?" has no answer in any passage,
    # so retrieval cannot help -- but the index knows exactly, so we answer
    # from it directly. See rag/corpus_metadata.py.
    #
    # This runs BEFORE the embedding call, so a metadata question costs nothing
    # and touches no model. Anything not recognised returns None and falls
    # straight through to the pipeline below, unchanged.
    metadata_answer = corpus_metadata.answer_question(question, store.sources())
    if metadata_answer is not None:
        return Answer(
            question=question,
            text=metadata_answer,
            retrieved=[],  # nothing was retrieved, by design
            path=METADATA_PATH,
        )

    # Retrieve, then drop anything below the floor.
    results = [r for r in retrieve(question, store, k=k) if r[1] >= min_score]

    if not results:
        # Nothing survived. Decline directly rather than prompting the model
        # with an empty context block -- given no context and a question, it
        # will fall back on training data, which is the exact thing we are
        # trying to prevent. Also saves a needless model call.
        return Answer(question=question, text=NO_CONTEXT_ANSWER, retrieved=[])

    text = ollama_client.generate(build_prompt(question, results))
    return Answer(question=question, text=text, retrieved=results)


def answer_without_rag(question: str) -> str:
    """THE CONTROL CONDITION: same model, same question, no retrieval.

    This is the most useful diagnostic in the repo, and the reason the test
    corpus cites studies that do not exist.

    If a question can be answered without retrieval, a correct RAG answer
    proves nothing -- retrieval could be completely broken and the model would
    still get it right from training data. Comparing the two paths is the only
    way to see what retrieval actually contributed:

        ask.py          "What did the Vandermeer Study find?"  -> 1.6 g/kg
        ask.py --no-rag "What did the Vandermeer Study find?"  -> "I couldn't
                                                                  find any
                                                                  information"

    Across the full eval set: 19-20/20 with RAG, 5/20 without.
    """
    return ollama_client.generate(
        f"Answer concisely.\n\nQuestion: {question}\n\nAnswer:"
    )
