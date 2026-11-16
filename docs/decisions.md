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

## Day 2 note

The backend starts as a synchronous FastAPI/SQLAlchemy service. The first health route is a process liveness check, not a dependency readiness check. Database connectivity is provided through a request-scoped session dependency; no route uses it until a database-backed feature is added. Alembic is wired to the shared declarative metadata so future model migrations have one clear entry point.

## Day 3 note

Passwords are hashed with Argon2 through `pwdlib`. Access JWTs last 15 minutes; refresh JWTs last 30 days and are stored server-side only as SHA-256 digests. Refresh rotates the digest with a compare-and-swap update, and logout revokes the current session. Each authenticated request checks that its session remains active. Workspace membership is required to list members; only owners can add, change, or remove non-owner members. Ownership transfer and email invitations remain future work.

## Day 4 note

Original uploads go to a private S3-compatible bucket. Redis and Celery keep extraction off the request path. Text PDFs retain one source unit per non-empty page; DOCX text is kept in reading order as a single source unit without a page number. Uploads are allowlisted by extension and file signature, capped by compressed and expanded size, and rejected when the configured page/text limits are exceeded. OCR remains a later extension.

## Day 5 note

The first retrieval model is `sentence-transformers/all-MiniLM-L6-v2`, with 384-dimensional vectors in pgvector. Chunks use 220 tokenizer wordpieces and 40 wordpieces of overlap, aligned to word and sentence boundaries where practical. The supplied roadmap's 500/100 starting point exceeds this model's 256-wordpiece input limit and would be truncated, so this baseline stays below that ceiling until an evaluation compares chunk sizes and models. Search uses exact cosine distance for now; no approximate index is added before there is a corpus to benchmark.
## Day 6: answer generation and citation validation

- Use a configurable OpenAI-compatible chat-completions endpoint to avoid coupling conversations to one SDK or provider.
- Persist conversations per creator, even when multiple members share a workspace; all conversation routes still require current workspace membership.
- Give the model a bounded set of retrieved chunks and recent turns. Treat document passages as untrusted content and accept only citation IDs present in that retrieval result.
- Return an explicit insufficient-evidence response below a configurable initial relevance threshold. The `0.25` default is a starting setting, not an evaluated quality threshold; tune it with a fixed benchmark before making retrieval or answer quality claims.
- Keep provider secrets in the local `.env`; the example file contains no usable key.
