# Decisions and open questions

## Decided for the first implementation

- React/Vite client and versioned FastAPI JSON API.
- PostgreSQL is the record store; pgvector is the first vector-search option.
- Redis/Celery handles long-running ingestion.
- Original uploads go to S3-compatible object storage.
- Workspaces are the authorization boundary.
- PDF and DOCX are the initial supported formats.
- Citations include document and page metadata; answers can report insufficient evidence.

## To decide before implementation hardens

- Exact deployment provider and cost constraints.
- LLM provider and whether a local development fallback is needed.
- Embedding model and vector dimensions.
- Maximum upload size, retention, and deletion semantics.
- Invitation mechanism and account verification requirements.
- Initial evaluation dataset and minimum acceptable retrieval/citation quality.

## Day 1 note

The supplied roadmap lays out a ten-week project and names planning, requirements, architecture, ER design, and GitHub setup as the first-week milestone. This repository is being organized as a ten-day sprint per the project owner's request; the longer roadmap remains the source for overall feature scope.
