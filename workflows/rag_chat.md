# Workflow: RAG Document Chat

## Objective
Let the user chat with their own documents through a local website. Answers must come only from the uploaded documents, cite their sources, and be written in the language of the question (Arabic or English).

## How it works
```
Upload file ──> ingest.py ──> chunks ──> Gemini embeddings ──> Pinecone index
                                                                    │
Question ──> query.py ──> embed question ──> search Pinecone (TOP_K) ┘
                     └──> context + question ──> OpenRouter LLM ──> answer + sources
```

## Tools
| Tool | Purpose |
|---|---|
| `tools/rag_common.py` | Shared config (reads `.env`), Gemini `embed()`, Pinecone `index()` (creates it if missing), OpenRouter `chat()` |
| `tools/ingest.py` | Extract text → chunk → embed → upsert to Pinecone. Re-ingesting a file replaces its old chunks |
| `tools/query.py` | Retrieve top chunks and generate the answer. Also works as a CLI test |
| `tools/chat_app.py` | Flask website: chat page + file upload. Runs at http://localhost:5000 |

## Required inputs
- `.env` must contain: `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`
- Optional settings in `.env` (code defaults shown): `EMBED_MODEL` (gemini-embedding-001), `EMBED_DIM` (768), `OPENROUTER_MODEL`, `TOP_K` (6), `MAX_TOKENS` (2000)
- Documents: `.pdf .docx .txt .md .csv .xlsx`

## Steps

### 1. Setup (one time)
```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```
Check that all keys in `.env` are filled. Never print or log their values.

### 2. Add documents
Pick one of these:
- **From the website:** click "📄 Upload file". The file is saved to `docs/` and ingested right away.
- **From the CLI** (good for many files): put them in `docs/` and run
  ```
  .venv/Scripts/python tools/ingest.py docs
  ```
Ingesting uses Gemini and Pinecone API calls. Ask the user before ingesting large folders.

### 3. Run the website
```
cd tools
../.venv/Scripts/python chat_app.py
```
Open http://localhost:5000. Run the command from inside `tools/` (or add `tools/` to the path) because the modules import each other by name.

### 4. Quick test without the website
```
.venv/Scripts/python tools/query.py "your question"
```

## Expected output
- An answer in the question's language, with citations like [1] and [2]
- An expandable "Sources" list showing the file name, page, similarity score, and a snippet

## Key settings (in code)
- `CHUNK_SIZE = 1200` characters and `CHUNK_OVERLAP = 200` (in `ingest.py`). Chunks split at paragraph or sentence ends, including Arabic punctuation (؟).
- Chunk IDs are `md5(filename)[:12]#n`. Two files with the same name in different folders overwrite each other.
- Chat history sent to the LLM is capped at the last 6 messages (`query.py`).
- The Pinecone index is serverless (aws / us-east-1) and uses cosine similarity. Its dimension must equal `EMBED_DIM`.

## Edge cases and lessons learned
- **Scanned PDF (images only):** extraction returns no text, so the file is skipped with a warning. It needs OCR first, which isn't implemented yet.
  - Watch out for CamScanner PDFs: they extract only the watermark word "CamScanner" per page, so they are NOT skipped. The useless chunks are stored and show up as low-score sources. Found 2026-10-16 with a CamScanner file.
- **Gemini 429 / 503 (rate limit or busy):** `embed()` retries up to 6 times with exponential backoff (5s, 10s, 20s, and so on).
- **OpenRouter 402:** without `max_tokens`, OpenRouter reserves the model's full output limit and rejects keys with low credit. Keep `MAX_TOKENS` set, or lower it.
- **Pinecone SDK `list()`:** newer SDK versions yield `ListItem` objects instead of plain ID strings. The code handles both with `getattr(i, "id", i)`.
- **Changing `EMBED_DIM` or `EMBED_MODEL`:** old vectors no longer match. Create a new index (new `PINECONE_INDEX_NAME`) and re-ingest everything.
- **Windows console:** scripts call `sys.stdout.reconfigure(encoding="utf-8")` so Arabic and ✓ characters print correctly.

## Ideas not built yet
- Stream answers while they are generated
- List or delete ingested documents from the website
- OCR for scanned PDFs
- Deploy online instead of running only on localhost
