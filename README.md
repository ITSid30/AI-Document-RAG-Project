# Local RAG Document Q&A

A local-first Retrieval-Augmented Generation (RAG) service. Upload one PDF, get an automatic summary, and ask questions that are answered **only from that document**, with page citations. If the answer isn't in the document, the system says so instead of guessing.

Everything runs on your machine: text extraction, embeddings, vector search and the LLM. **No document content is sent to any external service.**

---

## Why this project exists

Searching a long document with Ctrl+F finds keywords, not meaning, and reading the whole thing to find one answer is slow. RAG fixes this by retrieving only the relevant passages and handing them to an LLM, so answers stay grounded in the source and don't rely on what the model memorized.

**Design goals**
- Grounded answers with source pages
- Honest "not found" instead of hallucination
- Zero cost: no paid APIs or subscriptions
- Private by design: zero network egress for document content

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI | Auto-generated Swagger docs, simple dependency injection |
| Metadata DB | SQLite + SQLAlchemy | Zero setup for a solo-user v1; SQLAlchemy keeps a PostgreSQL migration cheap |
| Vector store | Chroma (embedded, persistent) | Stores vector, text and metadata together, which makes page citations easy |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Small, fast on CPU, free |
| LLM | Ollama running `phi3` | Local, CPU-friendly |
| PDF parsing | `pypdf` | Per-page text extraction |

---

## Architecture

```
INGESTION (once per upload)
Upload PDF -> validate -> save to disk -> extract text per page
          -> chunk (150 words, 30 overlap, never crossing pages)
          -> embed each chunk -> store in Chroma (with page + document id)
          -> mark document "ready" -> summary generated in background

QUERY (every question)
Question -> embed -> top-k search in Chroma (this document only)
         -> distance gate (reject clearly off-topic questions, no LLM call)
         -> LLM answers from retrieved chunks only
         -> refusal check -> answer + source pages
```

**Single source of truth**
- SQLite holds document-level facts: filename, path, status, page count, summary.
- Chroma holds chunk-level facts: text, page number, document id, embedding.
- `document_id` links the two. Deleting a document must clear both.

---

## Project structure

```
app/
  main.py              FastAPI app, router registration, table creation
  config.py            Settings (e.g. MAX_PAGES)
  api/routes.py        HTTP endpoints
  models/document.py   SQLAlchemy Document model
  db/session.py        SQLite engine and session factory
  services/
    ingestion.py       PDF extraction and chunking
    embeddings.py      Embedding model + Chroma storage
    retrieval.py       Query embedding and top-k search
    generation.py      Prompting Ollama (answers and summaries)
storage/
  uploads/             Saved PDFs (named <document_id>.pdf)
  chroma_db/           Persisted vectors
  app.db               SQLite database
```

---

## Setup

**Prerequisites:** Python 3.11+ (developed on 3.13), [Ollama](https://ollama.com).

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1          # Windows PowerShell
# source venv/bin/activate         # macOS / Linux

# 2. Install dependencies
pip install fastapi uvicorn sqlalchemy chromadb sentence-transformers pypdf python-multipart ollama

# 3. Pull a small local model
ollama pull phi3

# 4. Run the API from the project root
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API. The first run downloads the embedding model (a few hundred MB, one time).

> Always start the server and run helper scripts from the project root. The SQLite and Chroma paths are relative.

---

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/documents/upload` | Upload a PDF. Returns `document_id`, `status`, `error_message`. |
| GET | `/documents/{id}/status` | `processing`, `ready` or `failed`, plus page count and error message. |
| GET | `/documents/{id}/summary` | Background-generated summary: `pending`, `ready` or `failed`. |
| POST | `/documents/{id}/question?question=...` | Grounded answer with unique source pages. |

**Status codes**

| Code | Meaning |
|---|---|
| 200 | Success. Note: a rejected-but-stored upload returns 200 with `status: "failed"` and an `error_message`. |
| 400 | Bad input: not a PDF, file too large, empty or overlong question |
| 404 | Document not found |
| 409 | Document exists but isn't `ready` |
| 503 | Local LLM (Ollama) unavailable |

---

## Key design decisions

1. **Chunk per page, never across pages.** Keeps page attribution exact. The cost is uneven chunk sizes.
2. **Chunk size 150 words, overlap 30.** Started at 300/50. Smaller chunks mixed fewer topics per vector (less semantic dilution), and overlap protects ideas that straddle a boundary.
3. **Unique chunk id: `<document_id>_chunk_<index>`.** Readable and globally unique without hashing.
4. **Insert the DB row first, then name the file by its id.** Avoids duplicate-filename overwrites and keeps client-supplied names off disk.
5. **Two-layer "not found".**
   - A distance gate (`NOT_FOUND_THRESHOLD = 1.5`) rejects obviously off-topic questions without spending an LLM call.
   - The prompt requires one exact refusal phrase, so code can detect refusals and clear the sources.
6. **System/user message split with `temperature=0`.** Stopped the small model from rambling and continuing the prompt template.
7. **Summary runs as a background task** with its own DB session and its own `summary_status`, so a failed summary never marks the document itself as failed.
8. **Status lifecycle** (`processing` -> `ready` / `failed`) with a stored `error_message`, so failures are explicit and queryable.

---

## Validation and hardening

- PDF extension check **and** `%PDF-` magic-byte check
- Max file size: 15 MB; max pages: 100 (`MAX_PAGES`)
- Files are stored as `<id>.pdf`; the original name is kept only as a display value
- Password-protected, corrupt and scanned/image-only PDFs fail with a clear message
- Failed ingestion deletes any partial vectors from Chroma
- Extracted text is Unicode-normalized (NFKC), fixing ligatures such as "ﬁ" and "ﬂ"
- Prompt-injection spot check: a PDF containing "ignore all previous instructions" did not hijack phi3 in one test (not a guarantee)

---

## Calibration findings

The "not found" threshold was calibrated on one document with 11 questions, not assumed:

| Group | Best-distance range |
|---|---|
| Relevant questions | 0.76 to 1.41 |
| Clearly off-topic questions | 1.70 to 1.92 |
| Adjacent-but-absent ("average Java salary") | about 1.25 |

- The distance gate separates off-topic questions well but **cannot** catch adjacent-but-absent ones. The prompt's refusal instruction handles those.
- The threshold is specific to this embedding model and metric (Chroma's default L2). Changing either requires recalibration.
- Latency on a CPU-only machine: about 30 to 40 seconds per answer after tuning (it was 3 to 4 minutes at first).

---

## Known limitations

- **Retrieval quality is the weakest part.** Questions about labels ("What is covered in Phase 3?") can rank poorly because embeddings match meaning, not headings. Rephrasing around the concept ("In what phase is Git covered?") works.
- Only one document per question; no cross-document search
- No conversation memory; every question is independent
- No OCR: scanned PDFs are rejected
- No authentication; any caller can read any document
- `sources` lists the pages of all retrieved chunks, not only the ones the answer used
- Summary uses the first 3 chunks only
- If the server restarts mid-summary, `summary_status` stays `pending`
- Failed uploads leave files in `storage/uploads`
- Adding model columns requires deleting `app.db` (no migrations yet); delete `storage/chroma_db` together with it, since ids are shared

---

## Roadmap

**Near term**
- `pytest` tests for `chunk_text` (overlap, page attribution, boundary and empty-page cases)
- Replace debug prints with `logging`
- Pydantic request body for questions
- Batch embedding and `upsert` in `embeddings.py`
- Move `summarize_document` out of `routes.py` into `services/`

**Later**
- Hybrid retrieval (BM25 + vectors) and reranking
- Labelled eval set measuring hit rate@k and MRR
- Delete endpoint that removes the SQLite row, file and vectors together
- Multi-document search, conversation memory, per-user auth (return 404, not 403, for other users' documents)
- Job queue for background work, Alembic migrations, PostgreSQL/pgvector, Docker and CI

---

## License

Add a license of your choice.