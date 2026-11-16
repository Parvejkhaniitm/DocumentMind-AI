# Initial API contracts

Base path: `/api/v1`. Requests and responses use JSON except multipart document uploads. Protected routes require a bearer access token. Workspace-scoped routes verify membership and role on every request.

## Conventions

- UUIDs identify resources; timestamps use ISO 8601 UTC.
- Paginated list routes accept `limit` and `cursor` and return `{ "items": [], "next_cursor": null }`.
- Errors use `{ "error": { "code": "...", "message": "...", "request_id": "..." } }`.
- Never return password hashes, object-store credentials, or internal exception details.

## Authentication

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/register` | Create an account |
| POST | `/auth/login` | Authenticate and issue tokens |
| POST | `/auth/refresh` | Rotate/refresh an access token |
| POST | `/auth/logout` | End the current session |
| GET | `/auth/me` | Return the current user's profile |

`POST /auth/register` request: `{ "email": "person@example.com", "password": "…", "display_name": "…" }`. Return the created user with `201 Created`; never echo the password.

The implementation requires passwords of 12–128 characters. `POST /auth/login` accepts JSON `{ "email": "…", "password": "…" }` and returns a bearer access token, refresh token, token type, and access-token lifetime. Send the access token as `Authorization: Bearer <token>`. `POST /auth/refresh` accepts `{ "refresh_token": "…" }`; a successful refresh rotates the refresh token, so clients must discard the old one. `POST /auth/logout` revokes the session identified by the access token. `GET /auth/me` returns the current account. Authentication routes that issue or validate tokens require `JWT_SECRET` to be configured.

## Workspaces

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/workspaces` | Create a workspace; creator becomes owner |
| GET | `/workspaces` | List only workspaces the caller belongs to |
| GET | `/workspaces/{workspace_id}` | Read workspace details after membership check |
| POST | `/workspaces/{workspace_id}/members` | Add an existing account by user UUID (owner only) |
| PATCH | `/workspaces/{workspace_id}/members/{user_id}` | Change a member role (owner only) |
| DELETE | `/workspaces/{workspace_id}/members/{user_id}` | Remove a member (owner only) |
| GET | `/workspaces/{workspace_id}/members` | List members (workspace member only) |

Workspace creation automatically adds the creator as owner. Membership management currently adds an existing account by user UUID; it does not send invitations. Owners can change or remove non-owner members. Ownership transfer is not implemented, so the current owner cannot be demoted or removed.

## Documents and ingestion

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/workspaces/{workspace_id}/documents` | Upload PDF or DOCX as multipart form data |
| POST | `/workspaces/{workspace_id}/documents/{document_id}/reprocess` | Re-extract and re-index a failed/ready document |
| GET | `/workspaces/{workspace_id}/documents` | List authorized workspace documents |
| GET | `/workspaces/{workspace_id}/documents/{document_id}` | Read metadata and processing status |
| DELETE | `/workspaces/{workspace_id}/documents/{document_id}` | Remove a document and schedule file/chunk cleanup |

Upload accepts a multipart field named `upload`, requires the owner/editor role, validates PDF/DOCX file structure, and returns `202 Accepted` with document metadata and a processing status. A successful response means the ingestion job was queued, not that extraction has completed. The initial default file limit is 20 MiB (plus bounded multipart framing); size and page limits are configurable. Current statuses are `queued`, `processing`, `ready`, `failed`, and `deleting`. Members can list and read document metadata; owners and editors can delete documents. Original objects remain private in S3-compatible storage.

The worker extracts selectable PDF text with page numbers and DOCX text in document order. DOCX source units do not have a page number. Scanned PDFs fail with a clear status because OCR is not implemented yet. Extracted source units are retained with page references and indexed as overlapping chunks with normalized embeddings. Reprocessing rebuilds both page text and chunk vectors using the currently configured model.

## Search and chat

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/workspaces/{workspace_id}/search` | Search authorized document chunks |
| POST | `/workspaces/{workspace_id}/conversations` | Start a conversation |
| GET | `/workspaces/{workspace_id}/conversations` | List caller's workspace conversations |
| GET | `/workspaces/{workspace_id}/conversations/{conversation_id}` | Read messages and sources |
| POST | `/workspaces/{workspace_id}/conversations/{conversation_id}/messages` | Ask a question and receive a grounded answer |
| POST | `/workspaces/{workspace_id}/messages/{message_id}/feedback` | Submit answer feedback |

Search request: `{ "query": "…", "document_ids": [], "limit": 10 }`. Search response items include chunk text, document ID/name, source index, page number when available, and a cosine-similarity score.

The implementation accepts a query, optional document UUID filters, and a result limit from 1–20. It embeds the query with the configured model, then ranks chunks by cosine similarity. Results include document name, chunk text, source index, and page number when available. Search checks workspace membership and restricts retrieval to ready documents whose stored embedding model matches the configured model. Model input length is validated before embedding; cross-encoder reranking is not implemented.

Create a conversation with an optional `{ "title": "…" }` body; it is private to its creator. Send a question as `{ "content": "…" }`. The API embeds the question, retrieves only ready chunks from the authorized workspace, and supplies the top relevant passages plus a short conversation history to the configured OpenAI-compatible chat-completions provider. Passage text is treated as untrusted data. The provider must return JSON with an answer and chunk IDs; the API rejects IDs that were not in the retrieved evidence. If evidence is below the configured relevance threshold, the API records an explicit insufficient-evidence response without calling the provider. A provider key is required only when enough evidence exists to generate an answer.

Question response shape:

```json
{
  "id": "message-uuid",
  "role": "assistant",
  "content": "Answer grounded in the retrieved passages.",
  "answer_status": "answered",
  "sources": [
    {
      "document_id": "document-uuid",
      "document_name": "Policy.pdf",
      "page_number": 4,
      "source_index": 4,
      "chunk_id": "chunk-uuid",
      "relevance_score": 0.82
    }
  ]
}
```

`answer_status` can be `answered` or `insufficient_evidence`. Source IDs resolve to retrieved chunks in the requested workspace. `GET` conversation history includes user and assistant messages with their validated citations. Exact streaming behavior is deferred until the non-streaming contract is stable.

## Status codes

Use `400` for invalid input, `401` for missing/invalid authentication, `403` for authenticated users without access, `404` for absent or intentionally concealed resources, `409` for conflicts, `413` for oversized files, `415` for unsupported formats, `422` for schema validation, `429` for rate limits, and `503` when embedding or answer providers are unavailable. Do not leak whether an inaccessible workspace resource exists.
