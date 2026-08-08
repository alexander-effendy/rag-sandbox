"""
WHAT THIS FILE DOES
===================
This is the only file that talks to Ollama. Everything else in the project
calls into here. It exposes exactly three useful things:

    embed(["some text", ...])  -> numbers representing that text's meaning
    embed_one("some text")     -> same, for a single string
    generate("a prompt")       -> text written by the language model

WHY PLAIN `requests` INSTEAD OF THE `ollama` PYTHON PACKAGE
===========================================================
There is an official `ollama` package that would make this file shorter. We are
not using it on purpose. In a sandbox built for learning, you want to see the
actual HTTP request going out and the actual JSON coming back, because "what
exactly is an embedding call" is one of the things you are here to learn. The
`ollama` package would hide that behind a method call.

WHAT OLLAMA IS
==============
Ollama is a program running in the background on your machine (started by
`ollama serve`, or automatically by the menu bar app). It holds the models in
memory and exposes them over plain HTTP on port 11434. It is a local server --
nothing in this project sends data over the internet.
"""

from __future__ import annotations

import numpy as np
import requests

# Where the Ollama server listens. This is a local address: 11434 is Ollama's
# default port, and nothing here leaves your machine.
OLLAMA_URL = "http://localhost:11434"

# The two models, and they do completely different jobs.
#
# EMBED_MODEL turns text into a list of numbers. It does NOT write text. Ask it
# a question and you get back 384 floats, not an answer. It is small (45 MB)
# because turning text into numbers is a much easier job than writing prose.
EMBED_MODEL = "all-minilm"

# CHAT_MODEL writes text. It does NOT produce embeddings. It is 2 GB because
# generating language is a much harder job. This is the model that actually
# answers your question, using the chunks we retrieved as context.
CHAT_MODEL = "llama3.2"


class OllamaError(RuntimeError):
    """Raised for problems we can give the user a useful instruction about.

    The scripts catch this specifically and print the message without a stack
    trace, because "run `ollama serve`" is more helpful than 40 lines of
    traceback ending in ConnectionRefusedError.
    """


def _post(path: str, payload: dict, timeout: int) -> dict:
    """Send a POST request to Ollama and return the parsed JSON response.

    The leading underscore is a Python convention meaning "internal to this
    module" -- other files should call embed() or generate(), not this.

    This exists so the two error cases below are handled once instead of twice.
    """
    try:
        resp = requests.post(f"{OLLAMA_URL}{path}", json=payload, timeout=timeout)
    except requests.ConnectionError as exc:
        # Nothing is listening on port 11434, which almost always means Ollama
        # is not running at all.
        raise OllamaError(
            f"Could not reach Ollama at {OLLAMA_URL}. Is it running? Try: ollama serve"
        ) from exc

    if resp.status_code == 404:
        # Ollama is running, but this specific model was never downloaded.
        # A raw 404 would be baffling here, so we translate it into the fix.
        model = payload.get("model", "?")
        raise OllamaError(f"Model '{model}' not found. Try: ollama pull {model}")

    resp.raise_for_status()  # any other HTTP error (500 etc.) becomes an exception
    return resp.json()


def embed(texts: list[str], model: str = EMBED_MODEL) -> np.ndarray:
    """Turn a list of strings into vectors. THIS IS THE HEART OF RAG.

    WHAT AN EMBEDDING ACTUALLY IS
    -----------------------------
    A vector is just a list of numbers -- here, 384 of them. The embedding
    model was trained so that texts with similar *meanings* produce vectors
    that point in similar directions.

    That is the entire trick, and it is worth sitting with for a second,
    because everything else follows from it:

        "How much protein should I eat?"   -> [0.31, -0.02, 0.88, ...]
        "What is the daily protein RDA?"   -> [0.29, -0.04, 0.85, ...]   <- close
        "How do transformers work?"        -> [-0.55, 0.71, 0.02, ...]   <- far

    Those first two share almost no words. Keyword search would score them as
    unrelated. But they *mean* nearly the same thing, so the model places them
    near each other. Turning meaning into geometry is what lets us do
    "find me the most relevant passage" with arithmetic instead of magic.

    SHAPE OF THE RETURN VALUE
    -------------------------
    We get back a NumPy array shaped (number_of_texts, 384). Pass in 32 texts,
    get back a 32x384 grid of floats -- one row per text.

    WHY BATCH
    ---------
    Sending 32 texts in one request is far faster than 32 separate requests,
    because the per-request overhead (HTTP, model setup) is paid once instead
    of 32 times. scripts/ingest.py relies on this.
    """
    if not texts:
        # np.asarray([]) would produce a 1-D empty array, which then breaks
        # store.add() with a confusing shape error much later. Fail here, where
        # the cause is obvious.
        raise ValueError("embed() called with no texts")

    # The JSON we send looks like:
    #   {"model": "all-minilm", "input": ["first text", "second text"]}
    # and what comes back looks like:
    #   {"embeddings": [[0.1, -0.4, ...], [0.9, 0.2, ...]]}
    data = _post("/api/embed", {"model": model, "input": texts}, timeout=300)

    # float32 rather than float64: half the memory, and the extra precision is
    # meaningless for similarity scores.
    return np.asarray(data["embeddings"], dtype=np.float32)


def embed_one(text: str, model: str = EMBED_MODEL) -> np.ndarray:
    """Embed a single string, returning a flat 384-element vector.

    embed() always returns a 2-D grid, even for one text -- shape (1, 384).
    The trailing [0] pulls out that single row as a plain (384,) vector, which
    is what the search code wants. Small convenience, used for every question.
    """
    return embed([text], model=model)[0]


def generate(prompt: str, model: str = CHAT_MODEL, temperature: float = 0.0) -> str:
    """Send a prompt to the language model and return what it writes.

    WHY temperature=0.0
    -------------------
    Temperature controls randomness in word selection. At 0 the model always
    picks its highest-probability next word; at 1.0 it samples more freely.

    We pin it to 0 because this is a test harness: when you change the chunk
    size and the score moves, you want that to be caused by your change, not by
    the model rolling different dice. Note that 0 gets you *close to* but not
    exactly deterministic -- see the README, two identical eval runs here gave
    20/20 and 19/20.

    WHY stream=False
    ----------------
    Ollama can stream tokens as they are produced (that word-by-word effect in
    chat apps). We want the complete answer as one string, so we turn it off.
    """
    data = _post(
        "/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=300,  # generous: a cold model has to load into memory first
    )
    # .strip() because models often begin their reply with a newline.
    return data["response"].strip()


def health_check() -> None:
    """Fail early and clearly if Ollama is not usable.

    Called at the top of scripts/ingest.py. The point is timing: without this,
    a missing model surfaces as an error *after* chunking has run, and a
    beginner reasonably concludes their chunking code is broken. Better to
    check the obvious preconditions before doing any work.

    Returns nothing. Either it raises OllamaError, or everything is fine.
    """
    try:
        # /api/tags lists the models you have pulled locally.
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(
            f"Could not reach Ollama at {OLLAMA_URL}. Is it running? Try: ollama serve"
        ) from exc

    # Ollama reports names with a tag, like "llama3.2:latest". We compare on
    # the part before the colon so "llama3.2" matches "llama3.2:latest".
    installed = {m["name"].split(":")[0] for m in resp.json().get("models", [])}
    missing = [m for m in (EMBED_MODEL, CHAT_MODEL) if m.split(":")[0] not in installed]

    if missing:
        # Hand the user the exact commands rather than just naming the problem.
        pulls = "\n".join(f"  ollama pull {m}" for m in missing)
        raise OllamaError(f"Missing model(s): {', '.join(missing)}\n{pulls}")
