"""Shared helpers: config, Gemini embeddings, Pinecone index, OpenRouter chat."""
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from google import genai
from pinecone import Pinecone, ServerlessSpec

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME") or "default"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-5.5")
TOP_K = int(os.getenv("TOP_K", "6"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2000"))

_gemini = None
_index = None


def gemini():
    global _gemini
    if _gemini is None:
        _gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _gemini


def embed(texts, task_type="RETRIEVAL_DOCUMENT", batch_size=50):
    """Embed a list of strings. Retries with backoff on rate limits (429)."""
    vectors = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        for attempt in range(6):
            try:
                resp = gemini().models.embed_content(
                    model=EMBED_MODEL,
                    contents=batch,
                    config={"output_dimensionality": EMBED_DIM, "task_type": task_type},
                )
                vectors.extend(e.values for e in resp.embeddings)
                break
            except Exception as e:  # rate limit / transient error
                if attempt == 5 or ("429" not in str(e) and "503" not in str(e)):
                    raise
                wait = 2 ** attempt * 5
                print(f"  Gemini busy ({str(e)[:60]}...), retrying in {wait}s")
                time.sleep(wait)
    return vectors


def index():
    """Return the Pinecone index, creating it (serverless, cosine) if missing."""
    global _index
    if _index is None:
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        if not pc.has_index(INDEX_NAME):
            print(f"Creating Pinecone index '{INDEX_NAME}' (dim={EMBED_DIM}, cosine)...")
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBED_DIM,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            while not pc.describe_index(INDEX_NAME).status["ready"]:
                time.sleep(2)
        _index = pc.Index(INDEX_NAME)
    return _index


def chat(messages, model=None):
    """Send a chat completion request to OpenRouter and return the reply text."""
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
            "X-Title": "RAG Chat",
        },
        # cap output: without max_tokens OpenRouter reserves the model's full limit and may reject low-credit keys (402)
        json={"model": model or OPENROUTER_MODEL, "messages": messages, "max_tokens": MAX_TOKENS},
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter error {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"]
