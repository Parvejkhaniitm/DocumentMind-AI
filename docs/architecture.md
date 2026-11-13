# Architecture

## Context

The browser client calls a versioned FastAPI service. The API owns identity, workspace authorization, document metadata, chat records, and orchestration. Passwords are stored as Argon2 hashes; access tokens are short-lived and each authenticated request checks the associated revocable session. Long-running ingestion work is sent to Celery through Redis. PostgreSQL stores application data and vectors; an S3-compatible service stores original files.

```mermaid
flowchart LR
  U[Workspace member] --> UI[React + Vite]
  UI -->|HTTPS / JSON| API[FastAPI /api/v1]
  API --> DB[(PostgreSQL + pgvector)]
  API --> Q[Redis queue]
  Q --> W[Celery ingestion worker]
  W --> OBJ[(MinIO / S3 object storage)]
  W --> DB
  API --> RET[Retrieval and RAG services]
  RET --> DB
  RET --> LLM[LLM provider adapter]
```

## Document ingestion

1. The API authenticates the user and checks workspace membership.
2. It validates the file type and size, stores the original in object storage, creates a `documents` row with `queued` status, and enqueues an ingestion job.
3. A worker downloads the object, extracts PDF or DOCX text while preserving page references, and marks the document `processing`.
4. Text is normalized and split into overlapping chunks. Each chunk retains document, workspace, page, and ordinal metadata.
5. The embedding adapter produces vectors; the worker writes chunks and vectors to PostgreSQL and marks the document `ready`.
6. On a recoverable failure, the job retries. On terminal failure, the document becomes `failed` with a safe, user-visible error summary.

## Question answering

1. The API validates workspace membership before accepting the query.
2. The embedding adapter encodes the question with the same model and preprocessing used for document chunks.
3. Retrieval searches only chunks in the requested workspace. Candidate passages may be reranked with a cross-encoder.
4. The answer service sends a bounded set of passages to the configured LLM, with instructions to use only the supplied evidence and return structured citations.
5. The API validates that every cited chunk belongs to the workspace and maps citations to document names and pages before returning the response.
6. If retrieval finds insufficient evidence, return that outcome instead of presenting an unsupported answer as fact.

## Trust boundaries and safeguards

- The API is the authorization boundary; frontend filtering is never relied on for access control.
- Every document, chunk, conversation, and source lookup is scoped to an authorized workspace.
- Uploaded files and extracted text are untrusted. Treat document content as data, not as instructions to the assistant.
- Do not expose object-store credentials or raw internal errors to clients.
- Keep provider credentials in environment configuration and redact them from logs.

## Deployment shape

Local development will use Docker Compose for PostgreSQL, Redis, and MinIO. The API, worker, and frontend can run as separate processes. Production deployment can replace MinIO with S3-compatible storage and use managed PostgreSQL/Redis without changing application boundaries.

## Decisions to revisit with evidence

Chunk size and overlap, retrieval metric, top-k, reranking depth, embedding model, LLM provider, and storage limits should be selected using a fixed evaluation set and operational constraints, not treated as universal constants.
