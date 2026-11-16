# Product requirements

## Problem

Teams often need a specific fact buried in a long policy, report, or collection of documents. Manually opening files and searching each one is slow, while an ungrounded chatbot can invent details or make answers difficult to verify.

## Product goal

DocuMind AI lets workspace members upload PDF and DOCX files, search across their contents, and ask natural-language questions. Answers must be grounded in retrieved passages and include document and page citations.

## Users and primary use cases

- **Workspace member:** upload a policy, find a rule, and ask follow-up questions.
- **Workspace owner:** invite members and manage their roles.
- **Analyst:** summarize a report or compare evidence across several documents.

Initial use cases include locating a leave rule, summarizing a report with supporting pages, and searching across an authorized workspace without opening files individually.

## Functional requirements

1. Users can register, sign in, refresh a session, sign out, and view their own profile.
2. A user can create and list workspaces they belong to; owners can manage membership and roles.
3. Members can upload PDF and DOCX documents to a workspace and see processing status.
4. Ingestion extracts text with document and page metadata, chunks it, creates embeddings, and indexes the chunks asynchronously.
5. Members can run semantic search and ask questions within an authorized workspace.
6. Answers identify their supporting sources with document names and page references. The API can return an explicit insufficient-evidence result.
7. Users can view prior conversations and provide answer feedback.
8. The service records basic usage and retrieval metrics to support later evaluation.

Day 6 implements conversation persistence and grounded, non-streaming question answering. The provider is configured through environment settings and receives only bounded workspace-retrieved passages. Every returned citation is validated against the retrieved candidate set. Relevance threshold and answer quality still require evaluation with a fixed benchmark before quality claims are made.

Day 7 adds automated unit coverage for security primitives, question validation, chunking edge cases, citation filtering, and retrieval metric calculations. A local benchmark command reports recall@k, MRR, and query latency percentiles for workspace-specific queries with manually labeled relevant chunks; its results are not represented by unit tests alone.

## Non-functional requirements

- Authorization is checked for every workspace-scoped request and every retrieved chunk.
- File size, MIME type, and supported formats are validated; processing errors are visible and recoverable.
- Secrets and user content are not logged by default.
- Ingestion jobs are retryable and expose clear states: queued, processing, ready, failed.
- API errors use a stable, documented response shape.
- Retrieval quality, citation accuracy, faithfulness, and latency are evaluated against a small fixed benchmark before performance claims are made.

## Out of scope for the first usable version

Scanned-document OCR, public sharing, billing, enterprise SSO, automatic document comparison, and model fine-tuning. Keep extension points for OCR and alternate providers without making them Day 1 dependencies.

## Acceptance criteria

The end-to-end milestone is complete when a registered user can create a workspace, upload a supported document, wait for processing, ask a question, and receive an answer with citations that resolve to the correct source document and page. A user who is not a workspace member must be unable to fetch that workspace's documents, search its chunks, or ask questions against them.

## Initial product decisions

- A workspace is the tenant and authorization boundary.
- Source files are stored in object storage; relational records store metadata and object keys.
- PostgreSQL with pgvector is the initial metadata and vector store.
- A background queue handles extraction, chunking, and embedding so uploads do not wait on model work.
- Model and embedding providers are configuration choices behind adapters.
