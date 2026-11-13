# DocuMind AI

A document intelligence platform for teams. Upload PDFs and DOCX files, find relevant passages with semantic search, and ask questions that return answers grounded in cited source pages.

> Project status: Day 3 authentication and workspace foundation. Registration, login, refresh, logout, current-user, workspace creation/listing, and owner-managed membership are implemented. Document ingestion, search, and chat remain planned.

## Product goal

A signed-in user can create or join a workspace, upload a document, wait for it to be processed, and ask a question. DocuMind returns an answer supported by passages from documents the user is allowed to access. Every citation points back to a document and page.

## Project progress

- **Day 1:** product requirements, architecture, initial data model, API contracts, and repository setup.
- **Day 2:** FastAPI application, versioned API router, liveness endpoint, settings, SQLAlchemy session foundation, Alembic setup, and local PostgreSQL service.
- **Day 3:** Argon2 password hashing, signed access tokens, rotating/revocable refresh sessions, current-user endpoint, workspace access control, and membership role management.

See [docs/requirements.md](docs/requirements.md), [docs/architecture.md](docs/architecture.md), [docs/data-model.md](docs/data-model.md), and [docs/api-contracts.md](docs/api-contracts.md).

## Planned stack

- **Frontend:** React, Vite, Tailwind CSS
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
│   │   └── services/
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
2. Start PostgreSQL with pgvector: `docker compose up -d db`.
3. Install the backend in editable mode: `python -m pip install -e ./backend`.
4. Apply the initial schema: `python -m alembic -c backend/alembic.ini upgrade head`.
5. Start the API: `python -m uvicorn app.main:app --reload --app-dir backend`.
6. Open `http://127.0.0.1:8000/docs` for the generated API reference. The liveness route is `GET http://127.0.0.1:8000/api/v1/health`.

Authentication routes live under `/api/v1/auth`; workspace routes live under `/api/v1/workspaces`. The checked-in placeholder `JWT_SECRET` is intentionally rejected. Generate a private secret for local development, and use a secret manager for deployed environments.

The health route reports whether the API process is running. It does not claim that PostgreSQL or other dependencies are ready. Alembic is configured under `backend/`; its first migration creates users, authentication sessions, workspaces, and workspace memberships.

## Definition of done

A user can register, create a workspace, upload and process a supported document, ask a question, and receive an answer with valid citations. A user outside that workspace cannot access its files, chunks, or search results.

## Development principles

- Keep ingestion, retrieval, reranking, and answer generation independently testable.
- Enforce workspace access in the API and data layer, not only in the interface.
- Treat uploaded files and their contents as untrusted input.
- Record decisions and measured results as the implementation evolves; do not claim planned features as shipped.
