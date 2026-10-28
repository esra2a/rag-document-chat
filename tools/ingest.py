"""Ingest documents into Pinecone.

Usage:
    .venv/Scripts/python tools/ingest.py <file_or_folder> [more paths...]

Supports .pdf .docx .txt .md .csv .xlsx. Re-ingesting a file replaces its old chunks.
"""
import hashlib
import re
import sys
from pathlib import Path

from rag_common import embed, index

CHUNK_SIZE = 1200      # characters per chunk
CHUNK_OVERLAP = 200    # characters shared between neighbouring chunks
SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx"}


def extract_pages(path: Path):
    """Return a list of (page_number, text). Non-paged formats use page 1."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        return [(i + 1, p.extract_text() or "") for i, p in enumerate(PdfReader(path).pages)]
    if ext == ".docx":
        import docx
        d = docx.Document(path)
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return [(1, "\n".join(parts))]
    if ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        pages = []
        for n, ws in enumerate(wb.worksheets, 1):
            rows = [" | ".join("" if v is None else str(v) for v in r) for r in ws.iter_rows(values_only=True)]
            pages.append((n, f"Sheet: {ws.title}\n" + "\n".join(rows)))
        return pages
    return [(1, path.read_text(encoding="utf-8", errors="ignore"))]


def chunk_text(text: str):
    """Split on paragraph/sentence boundaries into ~CHUNK_SIZE pieces with overlap."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            window = text[start:end]
            # prefer to cut at a paragraph, then a sentence end (incl. Arabic punctuation)
            cut = max(window.rfind("\n\n"), max(window.rfind(s) for s in (". ", "؟", "!", "۔", ".\n", "\n")))
            if cut > CHUNK_SIZE * 0.5:
                end = start + cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return [c for c in chunks if c]


def ingest_file(path: Path):
    source = path.name
    prefix = hashlib.md5(source.encode("utf-8")).hexdigest()[:12]
    records = []
    for page, text in extract_pages(path):
        for chunk in chunk_text(text):
            records.append({"page": page, "text": chunk})
    if not records:
        print(f"  ! No text found in {source} (scanned PDF? needs OCR). Skipped.")
        return 0

    idx = index()
    # remove old chunks of this file so re-ingesting doesn't duplicate
    # newer Pinecone SDKs yield ListItem objects instead of plain id strings
    old_ids = [getattr(i, "id", i) for batch in idx.list(prefix=f"{prefix}#") for i in batch]
    for s in range(0, len(old_ids), 1000):
        idx.delete(ids=old_ids[s:s + 1000])

    print(f"  {source}: {len(records)} chunks, embedding...")
    vectors = embed([r["text"] for r in records], task_type="RETRIEVAL_DOCUMENT")
    items = [
        {
            "id": f"{prefix}#{i}",
            "values": v,
            # Pinecone metadata limit is 40KB per vector; chunks are far below that
            "metadata": {"text": r["text"], "source": source, "page": r["page"], "chunk": i},
        }
        for i, (r, v) in enumerate(zip(records, vectors))
    ]
    for s in range(0, len(items), 100):
        idx.upsert(vectors=items[s:s + 100])
    print(f"  ✓ {source}: uploaded {len(items)} chunks")
    return len(items)


def main(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += [f for f in sorted(p.rglob("*")) if f.suffix.lower() in SUPPORTED]
        elif p.suffix.lower() in SUPPORTED:
            files.append(p)
        else:
            print(f"  ! Unsupported or missing: {p}")
    if not files:
        sys.exit("No supported files to ingest.")
    total = sum(ingest_file(f) for f in files)
    print(f"Done. {total} chunks in index.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
