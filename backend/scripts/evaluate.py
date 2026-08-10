#!/Users/z5289605/dev/rag-sandbox/.venv/bin/python
"""
WHAT THIS SCRIPT DOES
=====================
Runs every question in eval/questions.json through the pipeline and scores the
results. This is how you tell whether a change (different chunk size, different
k, different embedding model) actually helped, instead of guessing from a
couple of questions that felt about right.

THE CENTRAL IDEA: SCORE RETRIEVAL AND GENERATION SEPARATELY
===========================================================
A single end-to-end "was the answer good" number cannot tell you where to look
when it drops. These two failures look identical in the output and have
completely unrelated fixes:

    retrieval PASS, answer FAIL  -> the right text WAS found, the model
                                    misread it. Fix the prompt, or use a
                                    bigger model.

    retrieval FAIL, answer FAIL  -> the right text was never found. The prompt
                                    is irrelevant; no model can answer from
                                    text it was not given. Fix chunking, the
                                    embedding model, or k.

Systems measured only end-to-end get tuned in the wrong place, because the
obvious thing to reach for is the prompt and half the time the prompt was never
the problem.

HOW EACH QUESTION IS SCORED
===========================
From eval/questions.json:

    expect_source  the document the answer should come from. Scored PASS if
                   that file appears among the retrieved chunks. null means
                   the corpus cannot answer this -- see the refusal tests below.

    expect_any     substrings, any one of which means the answer is right.
                   Deliberately loose: we check for "1.6", not an exact
                   sentence, because the model phrases things differently every
                   run and we are testing retrieval, not prose.

A NOTE ON WHAT THIS MEASURES, AND WHAT IT MISSES
================================================
The retrieval score asks whether the right *document* was retrieved. With ten
documents that is a fairly easy bar. Testing showed chunking badly enough to
drop answers from 20/20 to 18/20 while retrieval stayed at a perfect 18/18 --
fragmented chunks still surfaced the right file, they just no longer contained
the whole fact.

So a green retrieval score can hide a real retrieval problem. Scoring at the
chunk level rather than the document level would be more sensitive, and is a
good exercise.

USAGE
=====
    python backend/scripts/evaluate.py
    python backend/scripts/evaluate.py --compare     # also answer each question with no RAG
    python backend/scripts/evaluate.py -k 8          # try retrieving more chunks
    python backend/scripts/evaluate.py --index /tmp/experiment    # score another index
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# See scripts/ingest.py for why this is here.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import ollama_client, pipeline  # noqa: E402
from rag.store import NumpyVectorStore  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PASS, FAIL = "PASS", "FAIL"


def contains_any(text: str, needles: list[str]) -> bool:
    """True if any expected substring appears in the answer, case-insensitively.

    Crude on purpose. Proper answer grading needs either a human or another
    model as judge; substring matching is enough to catch regressions while
    staying instant, free, and perfectly repeatable.

    Its weakness is worth stating plainly: it cannot tell "1.6 grams per kg" from
    "definitely not 1.6 grams per kg". Watch for that if you add questions.
    """
    lowered = text.lower()
    return any(n.lower() in lowered for n in needles)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-k", type=int, default=4, help="chunks to retrieve")
    parser.add_argument("--compare", action="store_true", help="also answer without RAG")
    parser.add_argument("--index", type=Path, default=ROOT / "index")
    parser.add_argument("--questions", type=Path, default=ROOT / "eval" / "questions.json")
    args = parser.parse_args()

    try:
        store = NumpyVectorStore.load(args.index)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    questions = json.loads(args.questions.read_text())

    retrieval_hits = answer_hits = no_rag_hits = no_rag_scored = 0
    # Counted separately from len(questions): the refusal tests have no correct
    # source to retrieve, so including them would make the retrieval score
    # unreachable. Retrieval is scored over 18, answers over 20.
    scored = 0

    print(f"{len(questions)} questions, k={args.k}, {len(store)} chunks indexed\n")

    for i, case in enumerate(questions, 1):
        question = case["question"]
        try:
            result = pipeline.answer(question, store, k=args.k)
        except ollama_client.OllamaError as exc:
            # Ollama died mid-run. Stop rather than logging 20 identical
            # failures that look like a quality collapse.
            print(f"error: {exc}", file=sys.stderr)
            return 1

        # ---- Score 1: retrieval. Did the right document come back?
        expected_source = case.get("expect_source")
        if expected_source:
            scored += 1
            retrieved = expected_source in result.sources
            retrieval_hits += retrieved  # True counts as 1 in Python
            retrieval_mark = PASS if retrieved else FAIL
        else:
            # THE REFUSAL TESTS. expect_source is null because nothing in the
            # corpus answers these, and the correct behaviour is to decline.
            # There is no source to retrieve, so retrieval is not scored.
            #
            # One of them is "What is the capital of Australia?" -- the model
            # knows it perfectly well and should still refuse, because the
            # corpus does not contain it. That refusal is the grounding
            # instructions in rag/pipeline.py doing their job, and it is the
            # single most important behaviour in this whole test set.
            retrieval_mark = "  --"

        # ---- Score 1b: did the question take the path the case expects?
        #
        # Three case kinds now share "no expected source", and they mean
        # different things:
        #   content case  -- names its source, scored on retrieval
        #   refusal case  -- no source, correct behaviour is to decline
        #   metadata case -- no source because it never retrieves at all
        #
        # Without an explicit expected path, a metadata case is indistinguishable
        # from a refusal case, and a routing regression would score as a pass.
        # The field defaults to the retrieval path, so every pre-existing case
        # stays valid unedited.
        expected_path = case.get("expect_path", pipeline.RETRIEVAL_PATH)
        path_ok = result.path == expected_path
        path_mark = "" if path_ok else f"  path {FAIL} ({result.path}, wanted {expected_path})"

        # ---- Score 2: the answer itself.
        #
        # Metadata answers are computed, not generated, so they are exactly
        # reproducible -- which means we can demand exact equality instead of a
        # substring. That matters: a listing is long, so a substring check
        # against it passes almost trivially and would not catch a document
        # silently dropped from the middle of the list.
        if expected_path == pipeline.METADATA_PATH and "expect_exact" in case:
            correct = result.text == case["expect_exact"]
        else:
            correct = contains_any(result.text, case["expect_any"])
        correct = correct and path_ok
        answer_hits += correct

        print(f"{i:2}. {question}")
        print(f"    retrieval {retrieval_mark}   answer {PASS if correct else FAIL}{path_mark}")

        # Only print diagnostics for failures -- a wall of detail on passing
        # cases buries the two lines you actually need to read.
        if not correct or (expected_source and not retrieved):
            if "expect_exact" in case:
                print(f"    expected exactly: {' '.join(case['expect_exact'].split())[:200]}")
            else:
                print(f"    expected: one of {case['expect_any']}")
            if expected_source:
                print(f"    expected source: {expected_source}")
            print(f"    got: {' '.join(result.text.split())[:200]}")
            if result.retrieved:
                # What DID come back, with scores. Usually diagnoses it
                # instantly: a near-miss at 0.71 is a k or ranking issue, while
                # nothing above 0.3 means the corpus does not cover this.
                ranked = ", ".join(f"{c.source}({s:.2f})" for c, s in result.retrieved)
                print(f"    retrieved: {ranked}")

        # ---- Optional score 3: the same question with no retrieval at all.
        #
        # Skipped for metadata cases. The comparison exists to show what
        # retrieval bought you, and a metadata case never retrieves -- asking
        # the bare model how many documents we hold measures nothing, and
        # counting it would drag the baseline down for the wrong reason.
        if args.compare and expected_path != pipeline.METADATA_PATH:
            plain = pipeline.answer_without_rag(question)
            hit = contains_any(plain, case.get("expect_any", []))
            no_rag_hits += hit
            no_rag_scored += 1
            print(f"    no-RAG {PASS if hit else FAIL}: {' '.join(plain.split())[:100]}")
        print()

    print("-" * 60)
    if scored:
        print(f"Retrieval:  {retrieval_hits}/{scored} correct source in top-{args.k}")
    print(f"Answers:    {answer_hits}/{len(questions)} contained the expected content")
    if args.compare:
        # The headline number. Currently ~5/20 without RAG against 19-20/20
        # with it. Note the two refusal questions show "no-RAG FAIL" here --
        # the bare model happily answers "Canberra", and failing that check is
        # the correct outcome.
        #
        # Denominator excludes metadata cases, which are never run without RAG;
        # counting them would understate the baseline rather than measure it.
        print(f"Without RAG: {no_rag_hits}/{no_rag_scored}  <- what retrieval bought you")

    # Exit code 2 on any failure, so this can gate CI later. Note the scores
    # wobble slightly between runs even at temperature 0, so treat a single
    # question's change as noise until it survives a couple of runs.
    return 0 if answer_hits == len(questions) else 2


if __name__ == "__main__":
    raise SystemExit(main())
