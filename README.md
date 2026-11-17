# DocuMind AI

A document intelligence platform for teams. Upload PDFs and DOCX files, find relevant passages with semantic search, and ask questions that return answers grounded in cited source pages.

> Project status: Day 8 frontend foundation. The React app connects to the authenticated API for workspace documents, semantic search, and source-backed conversations.

## Product goal

A signed-in user can create or join a workspace, upload a document, wait for it to be processed, and ask a question. DocuMind returns an answer supported by passages from documents the user is allowed to access. Every citation points back to a document and page.

## Project progress

- **Day 1:** product requirements, architecture, initial data model, API contracts, and repository setup.
- **Day 2:** FastAPI application, versioned API router, liveness endpoint, settings, SQLAlchemy session foundation, Alembic setup, and local PostgreSQL service.
- **Day 3:** Argon2 password hashing, signed access tokens, rotating/revocable refresh sessions, current-user endpoint, workspace access control, and membership role management.
- **Day 4:** private S3-compatible storage, bounded PDF/DOCX uploads, asynchronous Celery extraction, source-page text records, processing status, and workspace-scoped document management.
- **Day 5:** token-aware overlapping chunks, normalized 384-dimensional embeddings, pgvector storage, semantic search restricted to ready documents in the current workspace, and document reprocessing for reindexing.
- **Day 6:** private conversation history, retrieval-grounded answers through an OpenAI-compatible provider, validated citations, and an explicit insufficient-evidence response.
- **Day 7:** focused backend unit tests for authentication primitives, chunk boundaries, request validation, retrieval metrics, and citation filtering; development-only test/lint dependencies; and CI checks.
- **Day 8:** responsive React/Vite frontend with sign-in and registration, workspace switching, document upload/status management, semantic search, and cited conversations.

See [docs/requirements.md](docs/requirements.md), [docs/architecture.md](docs/architecture.md), [docs/data-model.md](docs/data-model.md), and [docs/api-contracts.md](docs/api-contracts.md).

## Planned stack

- **Frontend:** React, TypeScript, Vite, responsive CSS
- **API:** Python, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic
- **Data:** PostgreSQL with pgvector; Redis and Celery for background jobs
- **Files:** S3-compatible object storage (MinIO locally)
- **Retrieval:** Sentence Transformers embeddings, vector search, optional cross-encoder reranking
- **Answer generation:** an LLM provider behind a small adapter interface

The model provider and deployment target remain configuration decisions. No API keys or credentials belong in source control.

## Planned repository layout

```text
DocuMind-AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── tasks/
│   ├── migrations/
│   └── tests/
├── frontend/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Run the backend locally

Requirements: Python 3.11+ and Docker Compose.

1. From the repository root, copy `.env.example` to `.env`. Replace `JWT_SECRET` with the output of `python -c "import secrets; print(secrets.token_hex(32))"`; the checked-in placeholder is rejected by the API.
2. Start PostgreSQL with pgvector, Redis, and MinIO: `docker compose up -d db redis minio`.
3. Install the backend and embedding model support in editable mode: `python -m pip install -e "./backend[embeddings]"`. For development and tests, use `python -m pip install -e "./backend[dev,embeddings]"`.
4. Apply the initial schema: `python -m alembic -c backend/alembic.ini upgrade head`.
5. Start the API: `python -m uvicorn app.main:app --reload --app-dir backend`.
6. In another terminal, start the worker from `backend`: `python -m celery -A app.core.celery_app:celery_app worker --loglevel=INFO`.
7. Open `http://127.0.0.1:8000/docs` for the generated API reference. The liveness route is `GET http://127.0.0.1:8000/api/v1/health`.

## Run the frontend locally

1. Start the backend and its required services using the steps above.
2. In a second terminal, change to `frontend` and run `npm install`.
3. Copy `frontend/.env.example` to `frontend/.env` if you need to change the API proxy target. By default the Vite dev server forwards `/api` requests to `http://127.0.0.1:8000`.
4. Run `npm run dev` and open the local URL printed by Vite (normally `http://127.0.0.1:5173`). For a deployed frontend, set `VITE_API_BASE_URL` to the API origin at build time.

The frontend includes account registration/sign-in, workspace creation and switching, document upload and processing status, retry/delete actions, semantic search, and private conversation history with source citations. Owners and editors can upload files; viewers see a read-only library.

Authentication routes live under `/api/v1/auth`; workspace routes live under `/api/v1/workspaces`. The checked-in placeholder `JWT_SECRET` is intentionally rejected. Generate a private secret for local development, and use a secret manager for deployed environments.

The health route reports whether the API process is running. It does not claim that PostgreSQL, Redis, or object storage are ready. Alembic creates users, authentication sessions, workspaces, memberships, document metadata, and extracted source units.

Uploads are limited to 20 MiB by default. Text-based PDFs retain page references; DOCX text is stored as one source unit because DOCX has no reliable page boundaries. Scanned-PDF OCR remains planned. The embedding model is downloaded from Hugging Face on first indexing/search, so first use needs network access.

Grounded answers require `LLM_API_KEY` and an OpenAI-compatible chat-completions endpoint. Set `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_BASE_URL` in your untracked `.env`; `.env.example` shows the defaults. The API stores each user's conversations separately and checks workspace membership before retrieval. Apply migrations with `python -m alembic -c backend/alembic.ini upgrade head` after pulling updates.

For a separately hosted frontend, set `CORS_ORIGINS` in the backend `.env` to a comma-separated allowlist of its exact origins. Do not use a wildcard for authenticated browser clients.

Chunks default to 220 wordpieces with 40 wordpieces of overlap. The roadmap suggested 500/100, but `all-MiniLM-L6-v2` truncates inputs at 256 wordpieces. Keeping each chunk below the model input limit preserves the full text; chunk size remains an evaluation setting, not a quality claim.

## Tests and retrieval evaluation

Install the development extra with `python -m pip install -e "./backend[dev]"`, then run `python -m pytest backend/tests`, `python -m ruff check backend/app backend/tests`, and `python -m ruff format --check backend/app backend/tests`. Embedding libraries are an optional extra so CI and API-only development avoid installing the large model runtime. The unit suite covers security primitives, request validation, chunk boundaries, retrieval metrics, and answer citation validation.

For a local retrieval benchmark, prepare a private JSONL file with one object per query: `{"workspace_id":"…","query":"…","relevant_chunk_ids":["…"]}`. From `backend`, run `python -m app.scripts.evaluate_retrieval path/to/benchmark.jsonl --top-k 6`. It reports recall@k, MRR, mean latency, p50, and p95. Keep labels and workspace identifiers local; do not commit user document content. No benchmark score or performance claim is included until a representative labeled set is run.

## Definition of done

A user can register, create a workspace, upload and process a supported document, ask a question, and receive an answer with valid citations. A user outside that workspace cannot access its files, chunks, or search results.

## Development principles

- Keep ingestion, retrieval, reranking, and answer generation independently testable.
- Enforce workspace access in the API and data layer, not only in the interface.
- Treat uploaded files and their contents as untrusted input.
- Record decisions and measured results as the implementation evolves; do not claim planned features as shipped.
