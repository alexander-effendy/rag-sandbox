"""
WHAT THIS FILE DOES
===================
Takes markdown documents and cuts them into small overlapping pieces
("chunks") that are the right size to embed and retrieve.

    docs/nutrition/protein.md  (a ~600 word document)
              |
              v
    [Chunk 1: 120 words] [Chunk 2: 120 words] [Chunk 3: 120 words] ...
              (each overlapping the previous one by 30 words)

This runs once, at index time, from scripts/ingest.py. Nothing here calls a
model -- it is pure text manipulation.

WHY CHUNK AT ALL? WHY NOT EMBED WHOLE DOCUMENTS?
================================================
Two reasons, and the second is the important one.

1. Size limits. all-minilm only reads 512 tokens (~380 words) at a time.
   Anything past that is silently ignored -- no error, the text just does not
   make it into the vector.

2. Dilution. This is the real reason. An embedding is a *single point*
   representing everything in the text. A document covering protein targets,
   leucine, meal distribution and DIAAS scores gets one vector sitting at the
   average of those four topics -- which means it is not especially close to
   any of them. Ask specifically about leucine and it may not rank highly,
   because three-quarters of its vector is about something else.

   Smaller chunks, one idea each, produce sharper vectors.

THE TWO PROBLEMS CHUNKING CREATES (AND HOW WE FIX THEM)
=======================================================
Cutting text up breaks it, in two predictable ways:

  Problem 1: a fact can land on a boundary.
      "...a meal must deliver roughly 2.5 grams of |CUT| leucine to trigger..."
      Now neither chunk contains the complete fact, and neither can answer it.
      FIX: overlap. Each chunk repeats the last 30 words of the previous one,
      so anything straddling a cut still appears intact somewhere.

  Problem 2: a chunk loses the context it depended on.
      "It should be taken with fat" -- taken with fat, what should? The subject
      was in a heading two paragraphs up.
      FIX: prepend the markdown heading to every chunk, so the chunk carries
      its own context into both the embedding and the prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# TUNING KNOBS -- the two numbers most worth experimenting with in this repo.
# Override them from the command line: ingest.py --chunk-words 200 --overlap 50
# ---------------------------------------------------------------------------

# Target words per chunk. This is the classic RAG trade-off:
#   SMALLER (50-100)  -> sharp, single-idea vectors, but chunks lose context
#                        and facts get split across boundaries
#   LARGER (300-800)  -> chunks carry their context, but vectors blur together
#                        and you burn prompt space on irrelevant text
# 120 is a reasonable middle for prose. There is no universally correct value.
CHUNK_WORDS = 120

# How many words each chunk repeats from the end of the previous chunk.
# 25% of chunk size is a common rule of thumb. Setting this to 0 measurably
# hurts answer quality -- the README documents the experiment.
OVERLAP_WORDS = 30


@dataclass(frozen=True)
class Chunk:
    """One retrievable piece of text, plus where it came from.

    `frozen=True` makes instances immutable -- once created, a Chunk cannot be
    modified. That matters here because the store keeps chunks in a list whose
    order must stay locked to the rows of the embedding matrix. Row 47 of the
    matrix must always describe chunk 47.
    """

    # The text that actually gets embedded. Note this INCLUDES the heading
    # prefix, so the heading contributes to the vector too -- that is deliberate
    # and it improves retrieval, because headings are dense with topic words.
    text: str

    source: str  # e.g. "nutrition/protein.md" -- shown in citations
    heading: str  # nearest markdown heading above this chunk
    index: int  # position within its source document

    @property
    def label(self) -> str:
        """Human-readable citation, e.g. "nutrition/protein.md § Daily Intake Targets".

        Used in two places: the [brackets] the model sees in its prompt, and
        the output of `ask.py --show-chunks`.
        """
        return f"{self.source} § {self.heading}" if self.heading else self.source


def _sections(markdown: str) -> list[tuple[str, str]]:
    """Split a document into (heading, body) pairs, cutting at markdown headings.

    We chunk *within* sections rather than across the whole document, so a
    chunk never spans two topics and every chunk has exactly one heading to
    attach to it. Splitting on structure the author already provided is nearly
    always better than splitting blindly every N words.

    Input:
        # Title
        intro text
        ## Daily Intake Targets
        the baseline recommendation...

    Output:
        [("Title", "intro text"), ("Daily Intake Targets", "the baseline...")]
    """
    sections: list[tuple[str, str]] = []
    heading = ""  # text before the first heading belongs to no section
    buffer: list[str] = []  # lines collected for the current section

    for line in markdown.splitlines():
        # An ATX heading: 1-6 '#' characters, a space, then the heading text.
        # Group 1 is the hashes (we only use it to detect a match), group 2 is
        # the text.
        match = re.match(r"^(#{1,6})\s+(.*)$", line)

        if match:
            # Hit a new heading, so the previous section is complete. Save it
            # before starting the next one.
            if buffer:
                sections.append((heading, "\n".join(buffer)))
                buffer = []
            heading = match.group(2).strip()
        else:
            buffer.append(line)

    # The final section has no heading after it to trigger the save above.
    if buffer:
        sections.append((heading, "\n".join(buffer)))

    # Drop sections with no body -- e.g. a heading immediately followed by
    # another heading would otherwise produce an empty chunk.
    return [(h, b) for h, b in sections if b.strip()]


def _windows(words: list[str], size: int, overlap: int):
    """Yield overlapping slices of a word list. This is where overlap happens.

    Worked example -- 10 words, size=4, overlap=2, so stride = 4-2 = 2:

        words:  [A B C D E F G H I J]
        start=0        [A B C D]
        start=2            [C D E F]      <- C,D repeated from the previous
        start=4                [E F G H]  <- E,F repeated
        start=6                    [G H I J]
        stop: 6+4 >= 10

    Every adjacent pair shares 2 words, so a fact spanning any single cut point
    survives whole in at least one window.

    This is a generator (it uses `yield`), so windows are produced one at a
    time as the caller loops, rather than all built up front.
    """
    # Stride = how far we advance each step. With size=120 and overlap=30 we
    # move forward 90 words and re-read 30.
    #
    # max(1, ...) is a guard against an infinite loop: if overlap >= size the
    # stride would be zero or negative, start would never advance, and this
    # would spin forever producing the same window. ingest.py also rejects that
    # combination up front with a clear message, but a generator that can hang
    # is worth defending twice.
    stride = max(1, size - overlap)

    for start in range(0, len(words), stride):
        window = words[start : start + size]
        if window:
            yield window

        # Stop once this window reached the end. Without this we would keep
        # emitting ever-shorter tail fragments ("...trigger a response",
        # "a response", "response") that are pure noise in the index.
        if start + size >= len(words):
            break


def chunk_markdown(
    markdown: str,
    source: str,
    chunk_words: int = CHUNK_WORDS,
    overlap_words: int = OVERLAP_WORDS,
) -> list[Chunk]:
    """Turn one markdown document into a list of Chunks.

    The full sequence: split into sections -> split each section into
    overlapping word windows -> attach the heading and source to each.
    """
    chunks: list[Chunk] = []

    for heading, body in _sections(markdown):
        # .split() with no argument splits on any whitespace and discards
        # empties, so it collapses newlines and runs of spaces for free.
        words = body.split()
        if not words:
            continue

        for window in _windows(words, chunk_words, overlap_words):
            body_text = " ".join(window)

            # Prepend the heading -- this is problem 2 from the module docstring
            # being fixed. "Daily Intake Targets\n\nThe baseline..." embeds much
            # more usefully than "The baseline..." alone, and when this chunk is
            # later dropped into the prompt, the model can see what it is about.
            text = f"{heading}\n\n{body_text}" if heading else body_text

            chunks.append(
                # index = position in this document, so chunk 0 is the first
                # piece of this file. len(chunks) works as the counter because
                # we append in order and never remove.
                Chunk(text=text, source=source, heading=heading, index=len(chunks))
            )

    return chunks


# Files matching these names are skipped by chunk_directory().
EXCLUDE = ("README.md",)


def chunk_directory(
    root: Path, exclude: tuple[str, ...] = EXCLUDE, **kwargs
) -> list[Chunk]:
    """Chunk every .md file under `root`, recursively.

    Sorted so the chunk order (and therefore the saved index) is identical on
    every run. Filesystem iteration order is not guaranteed, and a reproducible
    index makes it possible to compare two runs meaningfully.

    WHY READMEs ARE EXCLUDED -- this was a real bug, caught while testing
    ----------------------------------------------------------------------
    docs/README.md explains what the test corpus is. When it was being indexed,
    a question about protein retrieved it as the 4th result, because it happens
    to contain the phrase "recommended daily protein intake" while explaining
    the methodology.

    Documentation *about* a corpus is not part of the corpus, and indexing it
    means it competes with real content for retrieval slots. This generalises:
    pointing a document loader at a repository and indexing every markdown file
    it finds is one of the most common ways to quietly poison retrieval with
    changelogs, contributor guides and licence files.

    `**kwargs` just forwards chunk_words / overlap_words through to
    chunk_markdown, so ingest.py's command-line flags reach it.
    """
    chunks: list[Chunk] = []

    for path in sorted(root.rglob("*.md")):  # rglob = recursive glob
        if path.name in exclude:
            continue
        # Store paths relative to docs/, so citations read "ai/embeddings.md"
        # rather than "/Users/you/dev/rag-sandbox/docs/ai/embeddings.md".
        source = str(path.relative_to(root))
        chunks.extend(chunk_markdown(path.read_text(), source, **kwargs))

    return chunks
