# Initial data model

PostgreSQL is the system of record. Use UUID primary keys, UTC timestamps, foreign keys, and indexes on common ownership and lookup paths. Store original file bytes in object storage; retain only the object key and metadata in PostgreSQL.

```mermaid
erDiagram
  USERS ||--o{ WORKSPACE_MEMBERS : joins
  USERS ||--o{ AUTH_SESSIONS : authenticates
  WORKSPACES ||--o{ WORKSPACE_MEMBERS : contains
  WORKSPACES ||--o{ DOCUMENTS : owns
  USERS ||--o{ DOCUMENTS : uploads
  DOCUMENTS ||--o{ DOCUMENT_PAGES : extracts
  DOCUMENTS ||--o{ CHUNKS : indexes
  DOCUMENT_PAGES ||--o{ CHUNKS : cites
  DOCUMENTS ||--o{ CHUNKS : produces
  WORKSPACES ||--o{ CONVERSATIONS : contains
  USERS ||--o{ CONVERSATIONS : starts
  CONVERSATIONS ||--o{ MESSAGES : contains
  MESSAGES ||--o{ MESSAGE_SOURCES : cites
  CHUNKS ||--o{ MESSAGE_SOURCES : supports
  MESSAGES ||--o{ FEEDBACK : receives

  USERS {
    uuid id PK
    string email UK
    string password_hash
    string display_name
    datetime created_at
  }
  AUTH_SESSIONS {
    uuid id PK
    uuid user_id FK
    string refresh_token_hash
    datetime expires_at
    datetime revoked_at
    datetime created_at
  }
  WORKSPACES {
    uuid id PK
    string name
    uuid created_by FK
    datetime created_at
  }
  WORKSPACE_MEMBERS {
    uuid workspace_id PK,FK
    uuid user_id PK,FK
    string role
    datetime joined_at
  }
  DOCUMENTS {
    uuid id PK
    uuid workspace_id FK
    uuid uploaded_by FK
    string filename
    string content_type
    bigint size_bytes
    string sha256
    string object_key
    string status
    int page_count
    string error_summary
    datetime created_at
    datetime updated_at
  }
  DOCUMENT_PAGES {
    uuid id PK
    uuid document_id FK
    int source_index
    int page_number
    text text
  }
  CHUNKS {
    uuid id PK
    uuid document_id FK
    uuid workspace_id FK
    uuid document_page_id FK
    int ordinal
    text content
    vector embedding
    string embedding_model
    datetime created_at
  }
  CONVERSATIONS {
    uuid id PK
    uuid workspace_id FK
    uuid user_id FK
    string title
    datetime created_at
  }
  MESSAGES {
    uuid id PK
    uuid conversation_id FK
    string role
    text content
    string answer_status
    datetime created_at
  }
  MESSAGE_SOURCES {
    uuid message_id PK,FK
    uuid chunk_id PK,FK
    float relevance_score
  }
  FEEDBACK {
    uuid id PK
    uuid message_id FK
    uuid user_id FK
    int rating
    text comment
    datetime created_at
  }
```

## Constraints and indexes to implement

- Unique normalized email for each user.
- One membership row per `(workspace_id, user_id)`; roles initially `owner`, `editor`, and `viewer`.
- One chunk ordinal per document; `page_number` is nullable for formats without reliable pages, while `source_index` remains available.
- Restrict message roles to `user` and `assistant`; assistant messages may be `answered` or `insufficient_evidence`.
- Index workspace IDs on documents, chunks, and conversations. Add a pgvector index only after choosing the distance operator and validating it with representative data.
- Ensure source links can only reference chunks belonging to the conversation's workspace; enforce through service validation and, if practical, composite database constraints.
- Use Alembic migrations for all schema changes.

## Notes

Conversation records belong to their creating user and workspace. Message-source rows retain the chunk relevance score returned during retrieval; deleting a source chunk cascades its citation row. This is an evolving model; retention and conversation export remain open product decisions.
