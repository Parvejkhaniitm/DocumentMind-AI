# DocuMind AI

A document intelligence platform for teams. Upload PDFs and DOCX files, find relevant passages with semantic search, and ask questions that return answers grounded in cited source pages.

> Project status: Day 1 planning and repository foundation. The application features below are planned; they are not implemented yet.

## Product goal

A signed-in user can create or join a workspace, upload a document, wait for it to be processed, and ask a question. DocuMind returns an answer supported by passages from documents the user is allowed to access. Every citation points back to a document and page.

## Day 1 deliverables

- Product requirements and a definition of done
- System architecture and document-processing flow
- Initial relational data model
- Versioned REST API contracts
- Repository structure and project decisions

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
│   └── tests/
├── frontend/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Local setup

Implementation setup instructions will be added when the backend and frontend foundations exist. For now, review the planning documents under `docs/`.

## Definition of done

A user can register, create a workspace, upload and process a supported document, ask a question, and receive an answer with valid citations. A user outside that workspace cannot access its files, chunks, or search results.

## Development principles

- Keep ingestion, retrieval, reranking, and answer generation independently testable.
- Enforce workspace access in the API and data layer, not only in the interface.
- Treat uploaded files and their contents as untrusted input.
- Record decisions and measured results as the implementation evolves; do not claim planned features as shipped.
