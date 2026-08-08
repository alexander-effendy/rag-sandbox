#!/Users/z5289605/dev/rag-sandbox/.venv/bin/python
"""
THE EXPERIMENT: what if we skip RAG and just put every document in the prompt?

This is the honest comparison. It runs the same 20 eval questions three ways:

    1. STUFFED   every document pasted into the prompt, no retrieval at all
    2. RAG       retrieve the 4 best chunks, prompt with only those
    3. NEITHER   no context, the bare model (the control from evaluate.py)

and reports accuracy, prompt size, and latency for each.

Stuffing is a completely legitimate strategy at small scale, and this script
exists to show you where it stops being one.

    python backend/scripts/compare_stuffing.py
    python backend/scripts/compare_stuffing.py --limit 5     # quick run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import ollama_client, pipeline  # noqa: E402
from rag.store import NumpyVectorStore  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Same rules as the RAG prompt, so the only variable is what context we supply.
STUFF_TEMPLATE = """\
Answer the question using ONLY the context below.

Rules:
- If the context does not contain the answer, reply exactly: I don't know.
- Do not use outside knowledge, even if you are confident it is correct.
- Cite the sources you used as [source] at the end of your answer.

Context:
{context}

Question: {question}

Answer:"""


def load_everything(docs: Path) -> str:
    """Concatenate every document, labelled, exactly as a naive approach would."""
    parts = []
    for path in sorted(docs.rglob("*.md")):
        if path.name == "README.md":
            continue
        parts.append(f"[{path.relative_to(docs)}]\n{path.read_text()}")
    return "\n\n".join(parts)


def contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(n.lower() in lowered for n in needles)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    parser.add_argument("--index", type=Path, default=ROOT / "index")
    parser.add_argument("--questions", type=Path, default=ROOT / "eval" / "questions.json")
    parser.add_argument("--limit", type=int, help="only run the first N questions")
    args = parser.parse_args()

    store = NumpyVectorStore.load(args.index)
    questions = json.loads(args.questions.read_text())

    # Content questions only. Corpus-metadata cases ("how many documents do you
    # have?") are excluded because this script measures how well an answer can
    # be found in supplied text, and their answer is in no document at all --
    # stuffing the corpus could not produce it, so scoring them here would
    # penalise the stuffed column for the wrong reason. They also carry
    # `expect_exact` rather than `expect_any`, so including them would fail.
    skipped = [c for c in questions if c.get("expect_path") == pipeline.METADATA_PATH]
    questions = [c for c in questions if c.get("expect_path") != pipeline.METADATA_PATH]
    if skipped:
        print(f"Skipping {len(skipped)} corpus-metadata case(s) — not answerable from text.")

    if args.limit:
        questions = questions[: args.limit]

    everything = load_everything(args.docs)
    # ~4 characters per token is the standard rough estimate for English.
    stuffed_tokens = len(everything) // 4
    print(f"Whole corpus: {len(everything.split()):,} words, ~{stuffed_tokens:,} tokens")
    print(f"Questions: {len(questions)}\n")

    stats = {
        "STUFFED": {"hits": 0, "chars": 0, "secs": 0.0},
        "RAG": {"hits": 0, "chars": 0, "secs": 0.0},
        "NEITHER": {"hits": 0, "chars": 0, "secs": 0.0},
    }

    for i, case in enumerate(questions, 1):
        question, expected = case["question"], case["expect_any"]
        print(f"{i:2}. {question[:64]}")

        # --- 1. STUFFED: the entire corpus in every single prompt.
        prompt = STUFF_TEMPLATE.format(context=everything, question=question)
        t0 = time.perf_counter()
        out = ollama_client.generate(prompt)
        stats["STUFFED"]["secs"] += time.perf_counter() - t0
        stats["STUFFED"]["chars"] += len(prompt)
        stuffed_ok = contains_any(out, expected)
        stats["STUFFED"]["hits"] += stuffed_ok
        print(f"    stuffed {'PASS' if stuffed_ok else 'FAIL'}  ({len(prompt):,} chars)")

        # --- 2. RAG: only the 4 retrieved chunks.
        t0 = time.perf_counter()
        result = pipeline.answer(question, store, k=4)
        stats["RAG"]["secs"] += time.perf_counter() - t0
        rag_prompt = pipeline.build_prompt(question, result.retrieved)
        stats["RAG"]["chars"] += len(rag_prompt)
        rag_ok = contains_any(result.text, expected)
        stats["RAG"]["hits"] += rag_ok
        print(f"    rag     {'PASS' if rag_ok else 'FAIL'}  ({len(rag_prompt):,} chars)")

        # --- 3. NEITHER: the bare model.
        t0 = time.perf_counter()
        plain = pipeline.answer_without_rag(question)
        stats["NEITHER"]["secs"] += time.perf_counter() - t0
        stats["NEITHER"]["chars"] += len(question)
        none_ok = contains_any(plain, expected)
        stats["NEITHER"]["hits"] += none_ok
        print(f"    neither {'PASS' if none_ok else 'FAIL'}")

    n = len(questions)
    print("\n" + "=" * 70)
    print(f"{'approach':<10}{'correct':>10}{'avg prompt':>14}{'avg time':>12}{'total time':>13}")
    print("-" * 70)
    for name in ("STUFFED", "RAG", "NEITHER"):
        s = stats[name]
        print(
            f"{name:<10}{s['hits']:>7}/{n:<3}{s['chars'] // n:>11,} ch"
            f"{s['secs'] / n:>10.2f}s{s['secs']:>11.1f}s"
        )
    print("=" * 70)

    ratio = stats["STUFFED"]["chars"] / max(1, stats["RAG"]["chars"])
    speed = stats["STUFFED"]["secs"] / max(0.001, stats["RAG"]["secs"])
    print(f"\nStuffing sends {ratio:.1f}x more text and takes {speed:.1f}x longer per question.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
