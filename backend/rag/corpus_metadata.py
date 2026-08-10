"""
WHAT THIS FILE DOES
===================
Answers questions about the corpus ITSELF, rather than about what is in it.

    "How many documents do you have?"        <- this file
    "How much protein should I eat?"         <- the normal RAG pipeline

The difference matters more than it first appears. Every other part of this
project answers by finding a passage that contains the answer. But no passage
anywhere states how many documents exist, so there is nothing to find. Asked
"how many documents do you have?", retrieval returns the closest-sounding
content -- which is irrelevant -- and the model correctly declines.

That is not a retrieval quality problem. No chunk size, no `k`, and no
embedding model fixes it, because semantic similarity is the wrong instrument
for a question about the shape of the collection.

WHERE THE ANSWER ACTUALLY LIVES
===============================
It is already in the index, exactly. Every chunk carries a `source` like
"nutrition/protein.md", and the corpus is organised one subject per directory.
So the count is a set cardinality and the grouping is a string split. Both are
known precisely, which is why nothing here embeds, retrieves, or calls the
language model.

That also makes this the one part of the pipeline that is exactly reproducible
-- worth noting given that the rest of the system explicitly is not.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

# Documents stored at the corpus root have no subdirectory, so no subject area.
# They are reported under this label rather than dropped -- otherwise the
# listing and the count would disagree, which is exactly the kind of quiet
# inconsistency that makes a metadata answer untrustworthy.
UNCATEGORISED = "uncategorised"


# ---------------------------------------------------------------------------
# THE FACTS
#
# Three small functions over the chunk list. Everything below them is routing
# and formatting; this is the part that actually knows anything.
# ---------------------------------------------------------------------------


def documents(sources: list[str]) -> list[str]:
    """Every distinct source document, sorted.

    A document that produced nine chunks contributes its source nine times, so
    the set collapses it to one. This is the whole implementation of "how many
    documents do you have" -- the question that previously could not be
    answered at all.

    Takes sources rather than Chunk objects because sources are all this module
    ever needs, and that keeps the demand it places on a vector store as small
    as possible. See VectorStore.sources() in store.py.
    """
    return sorted(set(sources))


def subject_areas(sources: list[str]) -> dict[str, list[str]]:
    """Group documents by subject area, derived from the directory layout.

        nutrition/protein.md  ->  area "nutrition", document "protein.md"
        ai/embeddings.md      ->  area "ai",        document "embeddings.md"
        stray.md              ->  area UNCATEGORISED

    Using the directory rather than the content is the point. Inferring a
    document's subject from its text would be a second retrieval problem, with
    its own failure modes. The corpus already encodes the answer in its own
    structure, so this is exact and free.

    Returns areas in sorted order, each with its documents sorted, so the
    formatted answer is byte-identical between runs.
    """
    grouped: dict[str, list[str]] = defaultdict(list)

    for source in documents(sources):
        # Sources are relative to the corpus root and always use "/", because
        # chunk_directory() builds them with PurePath.relative_to().
        head, sep, tail = source.partition("/")
        if sep:
            grouped[head].append(tail)
        else:
            grouped[UNCATEGORISED].append(head)

    return {area: sorted(docs) for area, docs in sorted(grouped.items())}


def matching_areas(subject: str, sources: list[str]) -> list[str]:
    """Subject areas that plausibly match a named subject, case-insensitively.

    Matches an area when the subject appears in the area name, or the area name
    appears in the subject ("ai" matches a question about "AI"), or the subject
    appears in one of the area's document filenames ("embeddings" finds the
    `ai` area via `embeddings.md`).

    KNOWN LIMITATION, stated rather than hidden: this is string matching. It
    finds "AI" against `docs/ai/` but not "artificial intelligence", and not
    "diet" against `nutrition`. An alias table would fix the common cases, and
    is deliberately deferred until real phrasings show which aliases matter --
    guessing now would encode assumptions instead of observations.
    """
    needle = subject.strip().lower()
    if not needle:
        return []

    hits = []
    for area, docs in subject_areas(sources).items():
        area_l = area.lower()
        in_area = needle in area_l or area_l in needle
        in_docs = any(needle in doc.lower().removesuffix(".md").replace("-", " ") for doc in docs)
        if in_area or in_docs:
            hits.append(area)
    return hits


# ---------------------------------------------------------------------------
# ROUTING
#
# The design decision worth understanding here: patterns anchor on a CORPUS
# NOUN ("documents", "docs", "files"), never on question FORM ("how many").
#
# Measured against the 20-question evaluation set:
#
#   form-only patterns    1/20 content questions misrouted
#   noun-anchored         0/20 content questions misrouted
#
# The single false positive was "How many dimensions does the all-MiniLM-L6-v2
# model produce?" -- a real content question that happens to open like a count
# question. Requiring the noun eliminates it.
#
# The cost is the reverse error: "what's in your knowledge base?" will not
# match. That direction is deliberately the safe one. A MISS falls through to
# retrieval and produces today's "I don't know." -- no regression. A MISROUTE
# would answer a content question with a document listing, which is a new and
# worse failure. The two errors are not symmetric, so the patterns are tight
# rather than generous.
# ---------------------------------------------------------------------------

# What counts as referring to the collection itself.
_CORPUS_NOUN = r"(?:documents?|docs?|files?|corpus|knowledge ?base)"

# "how many documents ...", but never "how many dimensions ..."
_COUNT = re.compile(rf"\bhow many\b[^?]{{0,30}}?\b{_CORPUS_NOUN}\b", re.I)

# "what documents do you have", "list your docs", "what's in the corpus"
_LIST = re.compile(
    rf"\b(?:what|which|list|show|name|tell me)\b[^?]{{0,40}}?\b{_CORPUS_NOUN}\b", re.I
)

# "what topics do you cover" -- no corpus noun, so it must instead be pinned to
# the collection explicitly ("you", "the corpus"), or it would catch content
# questions asking what a paper or benchmark covers.
_LIST_TOPICS = re.compile(
    r"\bwhat\b[^?]{0,20}\b(?:topics?|subjects?|categories|areas)\b[^?]{0,30}?"
    r"\b(?:do you|are (?:there|available)|does (?:the corpus|it))\b",
    re.I,
)

# "do you have documents about X", "any AI-related docs?"
_COVERAGE = re.compile(
    rf"\b(?:do|does|have) (?:you|the corpus|it|we)\b[^?]{{0,60}}?\b{_CORPUS_NOUN}\b", re.I
)

# How to pull the subject out of a coverage question. Tried in order.
_SUBJECT_PATTERNS = [
    # "... documents about cryptocurrency?"  /  "... on transformers?"
    re.compile(r"\b(?:about|on|regarding|covering|related to)\s+([^?.,]+)", re.I),
    # "... any AI-related documents?"
    #
    # The capture is bounded to at most two words on purpose. An unbounded
    # `[\w\- ]+?` looks correct because it is non-greedy, but the engine still
    # takes the LEFTMOST viable start, so "Do you have any AI-related docs?"
    # captured "Do you have AI". Two words covers "AI" and "machine learning"
    # without being able to swallow the auxiliary verb.
    re.compile(r"\b(\w+(?:[-\s]\w+)?)[-\s]related\b", re.I),
    # "... any nutrition docs?" -- adjective sitting directly before the noun
    re.compile(rf"\b(?:any|some)\s+([\w\- ]+?)\s+{_CORPUS_NOUN}\b", re.I),
]

# Words that are never the subject, so we do not treat "any documents" as a
# question about a subject called "any".
_SUBJECT_STOPWORDS = {"any", "some", "the", "a", "an", "your", "my", "these", "those"}


@dataclass(frozen=True)
class MetadataQuestion:
    """A routed question: which kind it is, and the subject if it named one."""

    kind: str  # "count" | "list" | "coverage"
    subject: str = ""


def _extract_subject(question: str) -> str:
    """Pull the subject out of a coverage question, or return "" if there isn't one.

    "Do you have documents about cryptocurrency?" -> "cryptocurrency"
    "Do you have any AI-related documents?"       -> "AI"
    "Do you have any documents?"                  -> ""   (a listing, not coverage)
    """
    for pattern in _SUBJECT_PATTERNS:
        match = pattern.search(question)
        if not match:
            continue
        # Strip the corpus noun if it got swept into the capture, e.g.
        # "about cryptocurrency documents" -> "cryptocurrency".
        subject = re.sub(rf"\b{_CORPUS_NOUN}\b", "", match.group(1), flags=re.I)
        subject = " ".join(w for w in subject.split() if w.lower() not in _SUBJECT_STOPWORDS)
        if subject:
            return subject.strip()
    return ""


def classify(question: str) -> MetadataQuestion | None:
    """Decide whether this is a corpus-metadata question, and which kind.

    Returns None for everything else, which is the signal for answer() to run
    the normal retrieval pipeline. Order matters: a coverage question is a
    listing question that named a subject, so the subject check comes first.
    """
    if _COUNT.search(question):
        return MetadataQuestion(kind="count")

    if _COVERAGE.search(question):
        subject = _extract_subject(question)
        # "Do you have any documents?" names no subject -- that is a listing.
        return MetadataQuestion(kind="coverage", subject=subject) if subject else MetadataQuestion(kind="list")

    if _LIST.search(question) or _LIST_TOPICS.search(question):
        subject = _extract_subject(question)
        return MetadataQuestion(kind="coverage", subject=subject) if subject else MetadataQuestion(kind="list")

    return None


# ---------------------------------------------------------------------------
# ANSWERS
#
# Formatted directly from the facts, with no language model involved.
#
# The facts are already exact, so passing them through llama3.2 to be phrased
# would add a hallucination surface over something that cannot otherwise be
# wrong -- in exchange for nicer prose. Not a good trade here. The upside is
# that these answers are instant, free, and byte-for-byte reproducible, which
# means the evaluation harness can assert them exactly rather than by substring.
# ---------------------------------------------------------------------------


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def answer_count(sources: list[str]) -> str:
    areas = subject_areas(sources)
    breakdown = ", ".join(f"{area} ({len(docs)})" for area, docs in areas.items())
    return (
        f"The corpus contains {_plural(len(documents(sources)), 'document')} "
        f"across {_plural(len(areas), 'subject area')}: {breakdown}."
    )


def answer_list(sources: list[str]) -> str:
    areas = subject_areas(sources)
    lines = [
        f"The corpus contains {_plural(len(documents(sources)), 'document')} "
        f"across {_plural(len(areas), 'subject area')}:"
    ]
    for area, docs in areas.items():
        lines.append(f"\n{area} ({len(docs)}):")
        lines.extend(f"  - {doc}" for doc in docs)
    return "\n".join(lines)


def answer_coverage(subject: str, sources: list[str]) -> str:
    """Answer "do you have anything about X?".

    The absent case is the interesting one. The normal pipeline would say
    "I don't know." here, which is wrong in a specific way: whether the corpus
    covers a subject is not unknown to us, it is knowable exactly, and the
    honest answer is "no". So this states the absence and names what IS
    covered, which is also the more useful reply.
    """
    areas = subject_areas(sources)
    hits = matching_areas(subject, sources)

    if not hits:
        return (
            f"No — the corpus has no documents about {subject}. "
            f"It covers {', '.join(areas)}."
        )

    lines = [f"Yes — the corpus has documents about {subject}:"]
    for area in hits:
        lines.append(f"\n{area} ({len(areas[area])}):")
        lines.extend(f"  - {doc}" for doc in areas[area])
    return "\n".join(lines)


def answer_question(question: str, sources: list[str]) -> str | None:
    """Route and answer, or return None so the caller runs normal retrieval.

    This is the only function pipeline.answer() calls. Returning None rather
    than raising keeps the fall-through path in the caller a single `if`.
    """
    routed = classify(question)
    if routed is None:
        return None
    if not sources:
        return "The corpus is empty — no documents have been indexed."
    if routed.kind == "count":
        return answer_count(sources)
    if routed.kind == "coverage":
        return answer_coverage(routed.subject, sources)
    return answer_list(sources)
