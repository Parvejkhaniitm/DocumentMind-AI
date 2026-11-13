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
| GET | `/workspaces/{workspace_id}/documents` | List authorized workspace documents |
| GET | `/workspaces/{workspace_id}/documents/{document_id}` | Read metadata and processing status |
| DELETE | `/workspaces/{workspace_id}/documents/{document_id}` | Remove a document and schedule file/chunk cleanup |

Upload returns `202 Accepted` with `{ "id": "…", "status": "queued" }`. A successful response means the job was queued, not that extraction has completed. Enforce file limits and allowlisted MIME types server-side.

## Search and chat

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/workspaces/{workspace_id}/search` | Search authorized document chunks |
| POST | `/workspaces/{workspace_id}/conversations` | Start a conversation |
| GET | `/workspaces/{workspace_id}/conversations` | List caller's workspace conversations |
| GET | `/workspaces/{workspace_id}/conversations/{conversation_id}` | Read messages and sources |
| POST | `/workspaces/{workspace_id}/conversations/{conversation_id}/messages` | Ask a question and receive a grounded answer |
| POST | `/workspaces/{workspace_id}/messages/{message_id}/feedback` | Submit answer feedback |

Search request: `{ "query": "…", "document_ids": [], "limit": 10 }`. Search response items include chunk text, document ID/name, page range, and a relevance score.

Question request: `{ "content": "…" }`. Response shape:

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
      "page_start": 4,
      "page_end": 4,
      "chunk_id": "chunk-uuid"
    }
  ]
}
```

`answer_status` can be `answered` or `insufficient_evidence`. Source IDs must resolve to chunks from the requested workspace. Exact streaming behavior is deferred until the non-streaming contract is stable.

## Status codes

Use `400` for invalid input, `401` for missing/invalid authentication, `403` for authenticated users without access, `404` for absent or intentionally concealed resources, `409` for conflicts, `413` for oversized files, `415` for unsupported formats, `422` for schema validation, and `429` for rate limits. Do not leak whether an inaccessible workspace resource exists.
