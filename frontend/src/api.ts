export interface User {
  id: string
  email: string
  display_name: string
  created_at: string
}

export interface Workspace {
  id: string
  name: string
  created_by: string
  created_at: string
  role: 'owner' | 'editor' | 'viewer'
}

export interface DocumentRecord {
  id: string
  workspace_id: string
  filename: string
  content_type: string
  size_bytes: number
  status: 'queued' | 'processing' | 'ready' | 'failed' | 'deleting'
  page_count: number | null
  error_summary: string | null
  created_at: string
  updated_at: string
}

export interface SearchResult {
  chunk_id: string
  document_id: string
  document_name: string
  source_index: number
  page_number: number | null
  content: string
  score: number
}

export interface Citation {
  chunk_id: string
  document_id: string
  document_name: string
  page_number: number | null
  source_index: number
  relevance_score: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  answer_status: 'answered' | 'insufficient_evidence' | null
  created_at: string
  sources: Citation[]
}

export interface Conversation {
  id: string
  workspace_id: string
  title: string
  created_at: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
}

interface ApiErrorBody {
  error?: { message?: string }
  detail?: string
}

const TOKEN_KEY = 'documind.session.v1'
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
let refreshInFlight: Promise<boolean> | null = null

function readTokens(): TokenPair | null {
  try {
    const value = localStorage.getItem(TOKEN_KEY)
    return value ? (JSON.parse(value) as TokenPair) : null
  } catch {
    return null
  }
}

function saveTokens(tokens: TokenPair | null) {
  if (tokens) localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens))
  else localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function refreshSession(): Promise<boolean> {
  const tokens = readTokens()
  if (!tokens?.refresh_token) return false

  try {
    const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: tokens.refresh_token }),
    })
    if (!response.ok) {
      saveTokens(null)
      return false
    }
    saveTokens((await response.json()) as TokenPair)
    return true
  } catch {
    return false
  }
}

async function request<T>(path: string, init: RequestInit = {}, canRefresh = true): Promise<T> {
  const headers = new Headers(init.headers)
  const tokens = readTokens()
  if (tokens?.access_token) headers.set('Authorization', `Bearer ${tokens.access_token}`)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE}/api/v1${path}`, { ...init, headers })
  } catch {
    throw new ApiError('Could not reach DocuMind. Check that the API is running and try again.', 0)
  }

  const nonRefreshableAuthRoutes = ['/auth/login', '/auth/register', '/auth/refresh']
  if (response.status === 401 && canRefresh && !nonRefreshableAuthRoutes.includes(path)) {
    refreshInFlight ??= refreshSession().finally(() => {
      refreshInFlight = null
    })
    if (await refreshInFlight) return request<T>(path, init, false)
    saveTokens(null)
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorBody
    throw new ApiError(
      payload.error?.message ?? payload.detail ?? `Request failed (${response.status}).`,
      response.status,
    )
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  async login(email: string, password: string) {
    const tokens = await request<TokenPair>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    saveTokens(tokens)
  },
  async register(display_name: string, email: string, password: string) {
    await request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ display_name, email, password }),
    })
  },
  async me() {
    return request<User>('/auth/me')
  },
  async logout() {
    try {
      await request('/auth/logout', { method: 'POST' }, false)
    } finally {
      saveTokens(null)
    }
  },
  clearSession() {
    saveTokens(null)
  },
  hasSession() {
    return Boolean(readTokens()?.access_token)
  },
  listWorkspaces() {
    return request<Workspace[]>('/workspaces')
  },
  createWorkspace(name: string) {
    return request<Workspace>('/workspaces', {
      method: 'POST',
      body: JSON.stringify({ name }),
    })
  },
  listDocuments(workspaceId: string) {
    return request<DocumentRecord[]>(`/workspaces/${workspaceId}/documents`)
  },
  uploadDocument(workspaceId: string, file: File) {
    const body = new FormData()
    body.append('upload', file)
    return request<DocumentRecord>(`/workspaces/${workspaceId}/documents`, {
      method: 'POST',
      body,
    })
  },
  deleteDocument(workspaceId: string, documentId: string) {
    return request<void>(`/workspaces/${workspaceId}/documents/${documentId}`, { method: 'DELETE' })
  },
  reprocessDocument(workspaceId: string, documentId: string) {
    return request<DocumentRecord>(`/workspaces/${workspaceId}/documents/${documentId}/reprocess`, {
      method: 'POST',
    })
  },
  search(workspaceId: string, query: string) {
    return request<{ query: string; items: SearchResult[] }>(`/workspaces/${workspaceId}/search`, {
      method: 'POST',
      body: JSON.stringify({ query, limit: 10 }),
    })
  },
  listConversations(workspaceId: string) {
    return request<Conversation[]>(`/workspaces/${workspaceId}/conversations`)
  },
  createConversation(workspaceId: string) {
    return request<Conversation>(`/workspaces/${workspaceId}/conversations`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
  },
  getConversation(workspaceId: string, conversationId: string) {
    return request<ConversationDetail>(
      `/workspaces/${workspaceId}/conversations/${conversationId}`,
    )
  },
  ask(workspaceId: string, conversationId: string, content: string) {
    return request<Message>(
      `/workspaces/${workspaceId}/conversations/${conversationId}/messages`,
      { method: 'POST', body: JSON.stringify({ content }) },
    )
  },
}
