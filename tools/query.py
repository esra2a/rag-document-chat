"""Retrieve relevant chunks from Pinecone and answer with an OpenRouter model.

Usage (CLI test):
    .venv/Scripts/python tools/query.py "your question"
"""
import sys

from rag_common import TOP_K, chat, embed, index

SYSTEM_PROMPT = """You are a helpful assistant that answers questions using ONLY the provided context from the user's documents.
- Answer in the same language the user asked in (Arabic or English).
- If the answer is not in the context, say clearly that you couldn't find it in the documents. Do not make things up.
- Cite sources at the end of relevant sentences like [1], [2] matching the context numbers.
- Be clear and well-organized; use bullet points when listing several items."""


def retrieve(question, top_k=TOP_K):
    vec = embed([question], task_type="RETRIEVAL_QUERY")[0]
    res = index().query(vector=vec, top_k=top_k, include_metadata=True)
    return [
        {
            "text": m.metadata.get("text", ""),
            "source": m.metadata.get("source", "?"),
            "page": int(m.metadata.get("page", 1)),
            "score": round(m.score, 3),
        }
        for m in res.matches
    ]


def answer(question, history=None):
    """history: list of {"role": "user"|"assistant", "content": str} from earlier turns."""
    chunks = retrieve(question)
    context = "\n\n".join(
        f"[{i}] (source: {c['source']}, page {c['page']})\n{c['text']}" for i, c in enumerate(chunks, 1)
    ) or "(no documents found)"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += (history or [])[-6:]
    messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"})
    return {"answer": chat(messages), "sources": chunks}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    out = answer(" ".join(sys.argv[1:]))
    print(out["answer"])
    print("\nSources:")
    for i, s in enumerate(out["sources"], 1):
        print(f"  [{i}] {s['source']} p.{s['page']} (score {s['score']})")
