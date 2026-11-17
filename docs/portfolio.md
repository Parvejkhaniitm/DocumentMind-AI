# DocuMind AI: portfolio notes

## Project summary

DocuMind AI is a workspace-scoped document intelligence application. Users can upload text-based PDF and DOCX files, search extracted passages, and ask questions that return answers with citations to the source document and page where available.

## Architecture

- **Frontend:** React, TypeScript, Vite, responsive CSS, and a small API client with refresh-token handling.
- **API:** FastAPI with short-lived access tokens, rotating refresh sessions, workspace roles, upload validation, and request IDs.
- **Storage and jobs:** PostgreSQL with pgvector, private S3-compatible object storage (RustFS in the local stack), Redis, and a Celery ingestion worker.
- **Retrieval:** bounded text extraction, overlapping chunks, sentence-transformer embeddings, workspace-filtered vector search, and citation validation.
- **Local deployment:** Docker Compose runs PostgreSQL, Redis, RustFS, the API, the worker, and an Nginx-served frontend.
- **Quality checks:** Python unit tests and Ruff checks; frontend API tests, lint, and a production build in GitHub Actions.

## Demo flow

1. Register an account and create a workspace.
2. Upload a selectable-text PDF or DOCX document and wait for its status to become ready.
3. Search for a passage or ask a question whose answer is present in the document.
4. Open a citation to review its source passage and page reference.

Run locally with `docker compose up --build`; see the root README for environment setup. Grounded answers require an OpenAI-compatible API key. The sentence-transformer model is downloaded on first use.

## Resume bullets

- Built a workspace-scoped document Q&A application with FastAPI, PostgreSQL/pgvector, Redis/Celery, RustFS S3-compatible storage, and a React/TypeScript frontend.
- Implemented bounded PDF/DOCX ingestion, background extraction, overlapping text chunking, semantic retrieval, and answers restricted to citations from retrieved evidence.
- Added rotating refresh-token sessions, role-based workspace access, upload size and archive expansion limits, and tests for extraction, authorization boundaries, retrieval metrics, and API client refresh behavior.
- Containerized the API, worker, and frontend with Docker Compose and added GitHub Actions checks for backend tests/lint and frontend tests/lint/build.

## Scope and limitations

- Scanned-PDF OCR and DOCX page-accurate citations are not implemented.
- Retrieval scores have not been evaluated against a representative labeled document set; no quality or latency claim should be made without that evaluation.
- Grounded answers depend on an external OpenAI-compatible provider and require a private API key.
- The Compose stack is a local demo deployment. Public hosting still needs a chosen platform, HTTPS, managed secrets, backups, monitoring, and operational rate limits.
- Use synthetic or public documents in a portfolio demo. Do not upload confidential material.
