# RAG Document Chat (Arabic & English)

Chat with your own documents. Upload PDF, Word, Excel, CSV or text files, then ask questions. Answers come **only** from your documents, in the language of the question, with numbered citations, page numbers and similarity scores.

## How it works

```
Upload file ─> ingest.py ─> extract text ─> chunk ─> Gemini embeddings ─> Pinecone index
                                                                              │
Question ─> query.py ─> embed question ─> search Pinecone (top-k) ────────────┘
                   └──> context + question ─> LLM (Claude via OpenRouter) ─> answer + sources
```

1. **Extract**: text from `.pdf .docx .xlsx .csv .txt .md`, page by page (Excel: sheet by sheet, Word: paragraphs and tables).
2. **Chunk**: ~1,200-character chunks with 200 characters of overlap, cut at paragraph or sentence ends, including Arabic punctuation (`؟`).
3. **Embed and store**: Gemini embeddings (768 dimensions) in a serverless Pinecone index (cosine similarity). Re-uploading a file replaces its old chunks, so there are no duplicates.
4. **Retrieve and answer**: the question is embedded, the top chunks are retrieved, and the LLM answers only from that context and cites `[1]`, `[2]`, and so on.

## Reliability

- **Retries with exponential backoff**: when the embedding API returns a rate-limit (429) or busy (503) error, the request is retried up to 6 times (wait 5s, 10s, 20s...) instead of failing the upload.
- **Output cap** (`MAX_TOKENS`) so the LLM provider never rejects a request for reserving too many tokens.
- **Empty-document detection**: files with no extractable text (scanned images) are skipped with a warning.
- **Unicode-safe console output** for Arabic on Windows.

Result: finding an answer in a document set went from 5-10 minutes of manual search to under 30 seconds per question.

## Project structure

```
tools/
  rag_common.py   # config, Gemini embed() with retries, Pinecone index(), OpenRouter chat()
  ingest.py       # extract -> chunk -> embed -> upsert
  query.py        # retrieve + generate answer (also a CLI)
  chat_app.py     # Flask web app: chat page + file upload
workflows/
  rag_chat.md     # runbook: setup, steps, edge cases and lessons learned
docs/             # put documents here (sample included)
```

## Run it

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
cp .env.example .env                              # then fill in your keys

.venv/Scripts/python tools/ingest.py docs         # index the documents
cd tools && ../.venv/Scripts/python chat_app.py   # open http://localhost:5000
```

Quick test without the website:

```bash
.venv/Scripts/python tools/query.py "What are the opening hours?"
```

## Tech stack

Python · Flask · Gemini embeddings · Pinecone (serverless) · Claude via OpenRouter · pypdf · python-docx · openpyxl

## Next steps

- OCR for scanned PDFs
- Streaming answers
- Manage (list / delete) indexed documents from the web app
