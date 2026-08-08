"""
WHAT THIS SCRIPT DOES
=====================
Asks the RAG system a question. This is the "querying" half of RAG -- run
scripts/ingest.py first to build the index this reads.

Per question it: loads the saved index, embeds your question, finds the k
nearest chunks, builds a prompt around them, and prints what the model writes.

USAGE
=====
    python backend/scripts/ask.py "What did the Vandermeer Study find about protein?"
    python backend/scripts/ask.py --show-chunks "How much fiber per day?"
    python backend/scripts/ask.py --no-rag "What did the Vandermeer Study find?"
    python backend/scripts/ask.py                 # interactive mode, ask repeatedly

THE TWO FLAGS WORTH KNOWING
===========================
--show-chunks   Prints what was retrieved and each similarity score, before
                the answer. Use this constantly while learning. A wrong answer
                with the right chunk retrieved is a prompt problem; a wrong
                answer with the wrong chunks retrieved is a retrieval problem.
                They are fixed in completely different places.

--no-rag        Asks the model the same question with NO retrieved context.
                The control condition. Run it against any question to see what
                retrieval actually bought you -- for facts the model already
                knows, the answer is "nothing".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# See the note in scripts/ingest.py -- this makes `python backend/scripts/ask.py` work
# from the project root by putting the project root on the import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import ollama_client, pipeline  # noqa: E402
from rag.store import NumpyVectorStore  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def show(question: str, store: NumpyVectorStore, k: int, show_chunks: bool) -> None:
    """Answer one question and print it. Shared by one-shot and interactive modes."""
    # The entire RAG loop is this one call -- see rag/pipeline.py.
    result = pipeline.answer(question, store, k=k)

    if show_chunks:
        # HOW TO READ THE SCORES -- and why you should not trust them much
        #
        # Cosine similarity, roughly 0..1, higher is more similar. The
        # temptation is to read the number as confidence. Measured on this
        # corpus, that reading does not hold up:
        #
        #   "Aldridge"                                        0.118
        #   "What is the Aldridge formula?"                   0.205
        #   "What is the Aldridge formula for fluid intake?"  0.702
        #
        # Same fact, same document, and the right chunk ranked #1 in all three
        # cases. Only the score moved. Short queries score low because a few
        # words make a vector that is not close to anything in particular.
        #
        # So: the RANKING is robust, the ABSOLUTE SCORE is not. Compare scores
        # within one query's results, not across different queries.
        #
        # The flip side, which is semantic search actually earning its keep:
        #   "How much water should I drink per day?"          0.678
        # That question shares no distinctive wording with the document, which
        # is phrased around "fluid intake". Keyword search would score it zero.
        print("\nRetrieved:")
        for rank, (chunk, score) in enumerate(result.retrieved, 1):  # 1-indexed
            # " ".join(split()) collapses newlines so each preview stays on one
            # line; [:150] truncates so the output stays scannable.
            preview = " ".join(chunk.text.split())[:150]
            print(f"  {rank}. [{score:.3f}] {chunk.label}")
            print(f"     {preview}...")

    print(f"\n{result.text}")

    if result.retrieved:
        best = result.retrieved[0][1]  # [0] = top result, [1] = its score
        print(f"\n  sources: {', '.join(result.sources)}  (top score {best:.3f})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # nargs="*" collects all remaining words, so quoting the question is
    # optional -- both of these work:
    #   ask.py "how much protein"
    #   ask.py how much protein
    parser.add_argument("question", nargs="*", help="question to ask")
    parser.add_argument("-k", type=int, default=4, help="chunks to retrieve")
    parser.add_argument("--show-chunks", action="store_true", help="show what was retrieved")
    parser.add_argument("--no-rag", action="store_true", help="skip retrieval entirely")
    parser.add_argument("--index", type=Path, default=ROOT / "index")
    args = parser.parse_args()

    question = " ".join(args.question).strip()

    try:
        # ---- MODE 1: control condition. No index needed, since we never
        # retrieve anything -- this is the bare model answering from training.
        if args.no_rag:
            if not question:
                print("error: --no-rag needs a question", file=sys.stderr)
                return 1
            print(f"\n{pipeline.answer_without_rag(question)}")
            print("\n  (no retrieval — this is the model's training data talking)")
            return 0

        # Load once, up front. Reading a 110 KB file beats re-embedding 73
        # chunks, and in interactive mode it is reused for every question.
        store = NumpyVectorStore.load(args.index)

        # ---- MODE 2: one question, answer, exit.
        if question:
            show(question, store, args.k, args.show_chunks)
            return 0

        # ---- MODE 3: interactive. No question was given, so loop.
        print(f"{len(store)} chunks loaded. Ctrl-C or blank line to exit.")
        while True:
            try:
                line = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                # Ctrl-D and Ctrl-C. Exit quietly rather than dumping a
                # traceback for what is a normal way to end a session.
                print()
                return 0
            if not line:
                return 0
            show(line, store, args.k, args.show_chunks)

    # Both of these have actionable messages attached (see ollama_client.py and
    # store.load), so print the message alone -- a traceback would bury it.
    except (ollama_client.OllamaError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
