import {
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  MessageSquareText,
  Plus,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  api,
  ApiError,
  type Conversation,
  type DocumentRecord,
  type Message,
  type SearchResult,
  type User,
  type Workspace,
} from './api'
import './App.css'

type View = 'overview' | 'documents' | 'search' | 'chat'
type Notice = { message: string; tone: 'error' | 'success' } | null

const navigation: { id: View; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'documents', label: 'Documents', icon: FolderOpen },
  { id: 'search', label: 'Search', icon: Search },
  { id: 'chat', label: 'Ask DocuMind', icon: MessageSquareText },
]

function firstName(user: User) {
  return user.display_name.trim().split(/\s+/)[0] || 'there'
}

function shortDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(
    new Date(value),
  )
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(0)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

function friendlyError(error: unknown) {
  if (error instanceof ApiError) return error.message
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [workspaceId, setWorkspaceId] = useState('')
  const [view, setView] = useState<View>('overview')
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [notice, setNotice] = useState<Notice>(null)
  const [authLoading, setAuthLoading] = useState(api.hasSession())
  const [dataLoading, setDataLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false)
  const [showWorkspaceMenu, setShowWorkspaceMenu] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const workspace = workspaces.find((item) => item.id === workspaceId) ?? null

  useEffect(() => {
    if (!api.hasSession()) return
    let mounted = true
    void api
      .me()
      .then(async (currentUser) => {
        if (!mounted) return
        setUser(currentUser)
        const currentWorkspaces = await api.listWorkspaces()
        if (mounted) {
          setWorkspaces(currentWorkspaces)
          setDataLoading(currentWorkspaces.length > 0)
          setWorkspaceId(currentWorkspaces[0]?.id ?? '')
        }
      })
      .catch(() => {
        api.clearSession()
      })
      .finally(() => {
        if (mounted) setAuthLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    if (!user || !workspaceId) return
    let mounted = true
    void Promise.all([api.listDocuments(workspaceId), api.listConversations(workspaceId)])
      .then(([nextDocuments, nextConversations]) => {
        if (!mounted) return
        setDocuments(nextDocuments)
        setConversations(nextConversations)
        setActiveConversationId((previous) =>
          nextConversations.some((item) => item.id === previous)
            ? previous
            : (nextConversations[0]?.id ?? ''),
        )
      })
      .catch((error: unknown) => {
        if (mounted) setNotice({ message: friendlyError(error), tone: 'error' })
      })
      .finally(() => {
        if (mounted) setDataLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [user, workspaceId])

  useEffect(() => {
    if (!workspaceId || !documents.some((item) => ['queued', 'processing'].includes(item.status))) {
      return
    }
    const timer = window.setInterval(() => {
      void api.listDocuments(workspaceId).then(setDocuments).catch(() => undefined)
    }, 5000)
    return () => window.clearInterval(timer)
  }, [documents, workspaceId])

  useEffect(() => {
    if (!workspaceId || !activeConversationId) return
    let mounted = true
    void api
      .getConversation(workspaceId, activeConversationId)
      .then((detail) => {
        if (mounted) setMessages(detail.messages)
      })
      .catch((error: unknown) => {
        if (mounted) setNotice({ message: friendlyError(error), tone: 'error' })
      })
    return () => {
      mounted = false
    }
  }, [activeConversationId, workspaceId])

  const readyCount = useMemo(
    () => documents.filter((document) => document.status === 'ready').length,
    [documents],
  )
  const totalStorage = useMemo(
    () => documents.reduce((total, document) => total + document.size_bytes, 0),
    [documents],
  )

  function selectWorkspace(nextWorkspaceId: string) {
    if (nextWorkspaceId === workspaceId) {
      setShowWorkspaceMenu(false)
      return
    }
    setDocuments([])
    setConversations([])
    setMessages([])
    setActiveConversationId('')
    setDataLoading(true)
    setWorkspaceId(nextWorkspaceId)
    setShowWorkspaceMenu(false)
  }

  function selectConversation(conversationId: string) {
    setMessages([])
    setActiveConversationId(conversationId)
  }

  async function finishSignIn() {
    const currentUser = await api.me()
    const currentWorkspaces = await api.listWorkspaces()
    setUser(currentUser)
    setWorkspaces(currentWorkspaces)
    setDataLoading(currentWorkspaces.length > 0)
    setWorkspaceId(currentWorkspaces[0]?.id ?? '')
    setView('overview')
  }

  async function createWorkspace(name: string) {
    try {
      const created = await api.createWorkspace(name)
      setDocuments([])
      setConversations([])
      setMessages([])
      setActiveConversationId('')
      setWorkspaces((current) => [created, ...current])
      setDataLoading(true)
      setWorkspaceId(created.id)
      setShowWorkspaceModal(false)
      setNotice({ message: `${created.name} is ready to use.`, tone: 'success' })
    } catch (error) {
      setNotice({ message: friendlyError(error), tone: 'error' })
    }
  }

  async function refreshDocuments() {
    if (!workspaceId) return
    try {
      setDocuments(await api.listDocuments(workspaceId))
    } catch (error) {
      setNotice({ message: friendlyError(error), tone: 'error' })
    }
  }

  async function handleUpload(file?: File) {
    if (!file || !workspaceId) return
    const supported = /\.(pdf|docx)$/i.test(file.name)
    if (!supported) {
      setNotice({ message: 'Choose a PDF or DOCX file to upload.', tone: 'error' })
      return
    }
    if (file.size > 20 * 1024 * 1024) {
      setNotice({ message: 'This file is larger than the 20 MB upload limit.', tone: 'error' })
      return
    }
    setUploading(true)
    try {
      await api.uploadDocument(workspaceId, file)
      await refreshDocuments()
      setNotice({ message: `${file.name} was added to your library.`, tone: 'success' })
    } catch (error) {
      setNotice({ message: friendlyError(error), tone: 'error' })
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(document: DocumentRecord) {
    if (!workspaceId || !window.confirm(`Delete “${document.filename}” from this workspace?`)) {
      return
    }
    try {
      await api.deleteDocument(workspaceId, document.id)
      await refreshDocuments()
      setNotice({ message: 'Document deleted.', tone: 'success' })
    } catch (error) {
      setNotice({ message: friendlyError(error), tone: 'error' })
    }
  }

  async function handleReprocess(document: DocumentRecord) {
    if (!workspaceId) return
    try {
      await api.reprocessDocument(workspaceId, document.id)
      await refreshDocuments()
      setNotice({ message: 'Document reprocessing has started.', tone: 'success' })
    } catch (error) {
      setNotice({ message: friendlyError(error), tone: 'error' })
    }
  }

  async function handleSearch(event?: FormEvent) {
    event?.preventDefault()
    if (!workspaceId || !searchQuery.trim()) return
    setSearching(true)
    try {
      const result = await api.search(workspaceId, searchQuery.trim())
      setSearchResults(result.items)
    } catch (error) {
      setNotice({ message: friendlyError(error), tone: 'error' })
    } finally {
      setSearching(false)
    }
  }

  async function startConversation() {
    if (!workspaceId) return
    try {
      const conversation = await api.createConversation(workspaceId)
      setMessages([])
      setConversations((current) => [conversation, ...current])
      setActiveConversationId(conversation.id)
      setView('chat')
    } catch (error) {
      setNotice({ message: friendlyError(error), tone: 'error' })
    }
  }

  async function sendQuestion(content: string) {
    if (!workspaceId || !content.trim() || sending) return
    setSending(true)
    try {
      let conversationId = activeConversationId
      if (!conversationId) {
        const conversation = await api.createConversation(workspaceId)
        conversationId = conversation.id
        setConversations((current) => [conversation, ...current])
        setActiveConversationId(conversationId)
      }
      const answer = await api.ask(workspaceId, conversationId, content.trim())
      setMessages((current) => [
        ...current,
        { ...answer, id: `question-${Date.now()}`, role: 'user', content: content.trim(), sources: [] },
        answer,
      ])
      const detail = await api.getConversation(workspaceId, conversationId)
      setMessages(detail.messages)
      setConversations((current) =>
        current.map((item) =>
          item.id === conversationId ? { ...item, title: content.trim().slice(0, 60) } : item,
        ),
      )
    } catch (error) {
      setNotice({ message: friendlyError(error), tone: 'error' })
    } finally {
      setSending(false)
    }
  }

  async function handleLogout() {
    await api.logout().catch(() => undefined)
    setUser(null)
    setWorkspaces([])
    setWorkspaceId('')
    setDocuments([])
    setConversations([])
    setMessages([])
  }

  if (authLoading) return <LoadingScreen />
  if (!user) return <AuthScreen onSignedIn={finishSignIn} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" onClick={(event) => event.preventDefault()}>
          <span className="brand-mark"><BookOpen size={19} strokeWidth={2.2} /></span>
          <span>Docu<span className="brand-light">Mind</span></span>
          <span className="brand-ai">AI</span>
        </a>

        <div className="workspace-switcher-wrap">
          <button className="workspace-switcher" onClick={() => setShowWorkspaceMenu((show) => !show)}>
            <span className="workspace-glyph"><FolderOpen size={16} /></span>
            <span className="workspace-switcher-text">
              <span className="eyebrow">WORKSPACE</span>
              <strong>{workspace?.name ?? 'Select workspace'}</strong>
            </span>
            <ChevronDown size={15} />
          </button>
          {showWorkspaceMenu && (
            <div className="workspace-menu">
              {workspaces.map((item) => (
                <button
                  key={item.id}
                  className={item.id === workspaceId ? 'selected' : ''}
                  onClick={() => {
                    selectWorkspace(item.id)
                  }}
                >
                  <span>{item.name}</span>
                  {item.id === workspaceId && <Check size={15} />}
                </button>
              ))}
              <button className="workspace-menu-create" onClick={() => setShowWorkspaceModal(true)}>
                <Plus size={15} /> Create workspace
              </button>
            </div>
          )}
        </div>

        <div className="sidebar-label">YOUR SPACE</div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`nav-item ${view === id ? 'active' : ''}`}
              onClick={() => setView(id)}
            >
              <Icon size={17} strokeWidth={1.9} />
              <span>{label}</span>
              {id === 'documents' && documents.length > 0 && (
                <span className="nav-count">{documents.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-divider" />
        <div className="sidebar-section-heading">
          <span>Recent chats</span>
          <button aria-label="New chat" onClick={startConversation}><Plus size={15} /></button>
        </div>
        <div className="sidebar-chats">
          {conversations.slice(0, 5).map((conversation) => (
            <button
              key={conversation.id}
              className={`chat-link ${activeConversationId === conversation.id && view === 'chat' ? 'active' : ''}`}
              onClick={() => {
                setMessages([])
                setActiveConversationId(conversation.id)
                setView('chat')
              }}
              title={conversation.title}
            >
              <MessageSquareText size={15} />
              <span>{conversation.title}</span>
            </button>
          ))}
          {conversations.length === 0 && <p className="sidebar-empty">Your conversations will show up here.</p>}
        </div>

        <div className="sidebar-bottom">
          <div className="privacy-note"><ShieldCheck size={15} /><span>Your workspace stays private</span></div>
          <button className="profile-button" onClick={handleLogout} title="Sign out">
            <span className="avatar">{initials(user.display_name)}</span>
            <span className="profile-copy"><strong>{user.display_name}</strong><small>{user.email}</small></span>
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="mobile-brand"><span className="brand-mark"><BookOpen size={17} /></span> DocuMind</div>
          <div className="breadcrumb"><span>{workspace?.name ?? 'Workspace'}</span><ChevronRight size={14} /><strong>{navigation.find((item) => item.id === view)?.label}</strong></div>
          <div className="topbar-right">
            <span className="secure-label"><span className="secure-dot" /> Private workspace</span>
            <button className="top-avatar" title="Sign out" onClick={handleLogout}>{initials(user.display_name)}</button>
          </div>
        </header>

        {notice && (
          <div className={`notice ${notice.tone}`} role="status">
            <span>{notice.message}</span>
            <button aria-label="Dismiss message" onClick={() => setNotice(null)}><X size={16} /></button>
          </div>
        )}

        {!workspace ? (
          <WorkspaceWelcome onCreate={() => setShowWorkspaceModal(true)} />
        ) : (
          <div className="page-content">
            {view === 'overview' && (
              <OverviewView
                user={user}
                workspace={workspace}
                documents={documents}
                conversations={conversations}
                readyCount={readyCount}
                totalStorage={totalStorage}
                loading={dataLoading}
                onUpload={handleUpload}
                onOpenDocuments={() => setView('documents')}
                onOpenChat={startConversation}
                onOpenSearch={() => setView('search')}
              />
            )}
            {view === 'documents' && (
              <DocumentsView
                workspace={workspace}
                documents={documents}
                loading={dataLoading}
                uploading={uploading}
                onUpload={handleUpload}
                onDelete={handleDelete}
                onReprocess={handleReprocess}
              />
            )}
            {view === 'search' && (
              <SearchView
                query={searchQuery}
                setQuery={setSearchQuery}
                results={searchResults}
                searching={searching}
                onSearch={handleSearch}
              />
            )}
            {view === 'chat' && (
              <ChatView
                conversations={conversations}
                activeConversationId={activeConversationId}
                messages={messages}
                sending={sending}
                onSelect={selectConversation}
                onNew={startConversation}
                onSend={sendQuestion}
              />
            )}
          </div>
        )}
      </main>

      {showWorkspaceModal && (
        <WorkspaceModal onClose={() => setShowWorkspaceModal(false)} onCreate={createWorkspace} />
      )}
    </div>
  )
}

function LoadingScreen() {
  return <div className="loading-screen"><span className="brand-mark"><BookOpen size={20} /></span><LoaderCircle className="spin" size={19} /> Loading your workspace</div>
}

function AuthScreen({ onSignedIn }: { onSignedIn: () => Promise<void> }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (mode === 'register') await api.register(displayName, email, password)
      await api.login(email, password)
      await onSignedIn()
    } catch (reason) {
      setError(friendlyError(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-story">
        <a className="brand auth-brand" href="#home" onClick={(event) => event.preventDefault()}>
          <span className="brand-mark"><BookOpen size={19} /></span><span>Docu<span className="brand-light">Mind</span></span><span className="brand-ai">AI</span>
        </a>
        <div className="auth-story-copy">
          <div className="auth-kicker"><Sparkles size={15} /> YOUR KNOWLEDGE, IN CONTEXT</div>
          <h1>Make every document <em>work harder.</em></h1>
          <p>Bring your team’s files together. Find the passage you need, then ask a question and see exactly where the answer came from.</p>
          <div className="auth-proof"><span className="proof-icons"><i>R</i><i>A</i><i>M</i></span><span>Private by workspace.<br /><strong>Grounded in your sources.</strong></span></div>
        </div>
        <div className="auth-footer">DOCUMIND AI <span>·</span> DOCUMENT INTELLIGENCE</div>
        <div className="auth-decoration auth-decoration-one" /><div className="auth-decoration auth-decoration-two" />
      </div>
      <div className="auth-panel">
        <div className="auth-panel-inner">
          <div className="auth-mobile-brand"><span className="brand-mark"><BookOpen size={18} /></span> DocuMind <span className="brand-ai">AI</span></div>
          <div className="auth-heading"><span className="eyebrow">{mode === 'login' ? 'WELCOME BACK' : 'GET STARTED'}</span><h2>{mode === 'login' ? 'Sign in to your workspace' : 'Create your account'}</h2><p>{mode === 'login' ? 'Pick up where your team left off.' : 'A clearer way to work with your documents.'}</p></div>
          <form className="auth-form" onSubmit={submit}>
            {mode === 'register' && <label>Your name<input autoComplete="name" required maxLength={120} value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="e.g. Alex Morgan" /></label>}
            <label>Work email<input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label>
            <label>Password<input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'register' ? 12 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === 'register' ? 'At least 12 characters' : 'Enter your password'} /></label>
            {error && <div className="form-error" role="alert">{error}</div>}
            <button className="button primary auth-submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={17} /> : null}{mode === 'login' ? 'Sign in' : 'Create account'}<ArrowUpRight size={16} /></button>
          </form>
          <div className="auth-switch">{mode === 'login' ? 'New to DocuMind?' : 'Already have an account?'} <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>{mode === 'login' ? 'Create an account' : 'Sign in'}</button></div>
          <div className="auth-security"><ShieldCheck size={15} /> Your documents stay inside your workspace</div>
        </div>
      </div>
    </div>
  )
}

function WorkspaceWelcome({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="workspace-welcome">
      <div className="welcome-icon"><FolderOpen size={24} /></div>
      <span className="eyebrow">YOUR NEXT STEP</span>
      <h1>Create a workspace for your documents.</h1>
      <p>Workspaces keep your documents and conversations organized in one private place.</p>
      <button className="button primary" onClick={onCreate}><Plus size={17} /> Create your first workspace</button>
    </div>
  )
}

function OverviewView(props: {
  user: User
  workspace: Workspace
  documents: DocumentRecord[]
  conversations: Conversation[]
  readyCount: number
  totalStorage: number
  loading: boolean
  onUpload: (file?: File) => void
  onOpenDocuments: () => void
  onOpenChat: () => void
  onOpenSearch: () => void
}) {
  const { user, workspace, documents, conversations, readyCount, totalStorage, loading } = props
  const recentDocuments = documents.slice(0, 4)
  return (
    <>
      <div className="page-heading overview-heading"><div><span className="eyebrow">YOUR DOCUMENT WORKSPACE</span><h1>Good to see you, {firstName(user)}<span className="heading-period">.</span></h1><p>Everything you need to find answers in <strong>{workspace.name}</strong>.</p></div><button className="button primary" onClick={() => document.getElementById('overview-upload')?.click()}><Upload size={16} /> Add documents</button><input id="overview-upload" className="visually-hidden" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => { props.onUpload(event.target.files?.[0]); event.currentTarget.value = '' }} /></div>

      <section className="welcome-banner">
        <div className="welcome-banner-copy"><span className="banner-kicker"><Sparkles size={14} /> YOUR KNOWLEDGE, READY WHEN YOU ARE</span><h2>Ask better questions.<br /><em>Find answers with receipts.</em></h2><p>Search across your files, or start a conversation grounded in the documents your team trusts.</p><div className="banner-actions"><button className="button banner-button" onClick={props.onOpenChat}><MessageSquareText size={16} /> Ask your documents <ArrowUpRight size={15} /></button><button className="text-button banner-link" onClick={props.onOpenSearch}>Explore semantic search <ChevronRight size={15} /></button></div></div>
        <div className="banner-art" aria-hidden="true"><div className="art-orbit orbit-one"/><div className="art-orbit orbit-two"/><div className="art-doc art-doc-back"><span/><span/><span/></div><div className="art-doc art-doc-front"><div className="art-doc-icon"><FileText size={21}/></div><b>Research brief</b><span/><span/><span/><div className="art-highlight"/><div className="art-spark"><Sparkles size={18}/></div></div><div className="art-note"><span className="art-check"><Check size={11}/></span><span><b>Source found</b><small>Page 08 · 94% match</small></span></div></div>
      </section>

      <section className="stats-grid" aria-label="Workspace summary">
        <StatCard label="In your library" value={loading ? '—' : String(documents.length)} suffix="documents" icon={<FolderOpen size={17} />} tone="green" />
        <StatCard label="Ready to search" value={loading ? '—' : String(readyCount)} suffix="indexed" icon={<Check size={17} />} tone="blue" />
        <StatCard label="Conversations" value={loading ? '—' : String(conversations.length)} suffix="threads" icon={<MessageSquareText size={17} />} tone="violet" />
        <StatCard label="Library storage" value={loading ? '—' : formatBytes(totalStorage)} suffix="total" icon={<FileText size={17} />} tone="amber" />
      </section>

      <div className="section-grid">
        <section className="panel recent-panel">
          <div className="panel-heading"><div><span className="eyebrow">LIBRARY</span><h3>Recent documents</h3></div><button className="text-button" onClick={props.onOpenDocuments}>View all <ArrowUpRight size={14} /></button></div>
          {recentDocuments.length ? <DocumentRows documents={recentDocuments} compact /> : <EmptyDocuments onUpload={props.onUpload} />}
        </section>
        <section className="panel quick-panel">
          <div className="panel-heading"><div><span className="eyebrow">GET MORE FROM YOUR FILES</span><h3>Quick actions</h3></div></div>
          <button className="quick-action" onClick={props.onOpenSearch}><span className="quick-icon search-quick"><Search size={17} /></span><span><strong>Search your library</strong><small>Find the right passage, fast</small></span><ChevronRight size={16} /></button>
          <button className="quick-action" onClick={props.onOpenChat}><span className="quick-icon chat-quick"><Sparkles size={17} /></span><span><strong>Ask a question</strong><small>Get an answer with sources</small></span><ChevronRight size={16} /></button>
          <div className="privacy-card"><ShieldCheck size={17} /><span><strong>Private by design</strong><small>Only workspace members can access these files.</small></span></div>
        </section>
      </div>
    </>
  )
}

function StatCard({ label, value, suffix, icon, tone }: { label: string; value: string; suffix: string; icon: ReactNode; tone: string }) {
  return <div className="stat-card"><div className={`stat-icon ${tone}`}>{icon}</div><span className="stat-label">{label}</span><div className="stat-value">{value}<small>{suffix}</small></div></div>
}

function EmptyDocuments({ onUpload }: { onUpload: (file?: File) => void }) {
  return (
    <div className="empty-documents"><div className="empty-icon"><FileText size={22} /></div><h4>Your library is ready for its first file.</h4><p>Upload a PDF or DOCX to make it searchable.</p><label className="button secondary upload-small"><Upload size={15} /> Choose a file<input className="visually-hidden" type="file" accept=".pdf,.docx" onChange={(event) => { onUpload(event.target.files?.[0]); event.currentTarget.value = '' }} /></label></div>
  )
}

function DocumentsView({
  workspace,
  documents,
  loading,
  uploading,
  onUpload,
  onDelete,
  onReprocess,
}: {
  workspace: Workspace
  documents: DocumentRecord[]
  loading: boolean
  uploading: boolean
  onUpload: (file?: File) => void
  onDelete: (document: DocumentRecord) => void
  onReprocess: (document: DocumentRecord) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const canEdit = workspace.role !== 'viewer'
  const [dragging, setDragging] = useState(false)
  return (
    <>
      <div className="page-heading"><div><span className="eyebrow">YOUR LIBRARY</span><h1>Documents<span className="heading-period">.</span></h1><p>Files in {workspace.name} are private to this workspace.</p></div><button className="button primary" disabled={!canEdit || uploading} onClick={() => inputRef.current?.click()}>{uploading ? <LoaderCircle className="spin" size={16} /> : <Upload size={16} />}{uploading ? 'Uploading' : 'Upload document'}</button><input ref={inputRef} className="visually-hidden" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => { onUpload(event.target.files?.[0]); event.currentTarget.value = '' }} /></div>
      <div className={`dropzone ${dragging ? 'dragging' : ''} ${!canEdit ? 'disabled' : ''}`} onDragOver={(event) => { event.preventDefault(); if (canEdit) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); if (canEdit) onUpload(event.dataTransfer.files[0]) }}>
        <div className="dropzone-icon"><Upload size={19} /></div><div><strong>{canEdit ? 'Drop a PDF or DOCX here' : 'You have read-only access'}</strong><p>{canEdit ? 'or click to choose from your computer · max 20 MB' : 'Ask an owner or editor to upload documents.'}</p></div>{canEdit && <button className="button secondary" onClick={() => inputRef.current?.click()}>Browse files</button>}
      </div>
      <section className="panel documents-panel"><div className="panel-heading document-list-heading"><div><span className="eyebrow">{documents.length} {documents.length === 1 ? 'FILE' : 'FILES'}</span><h3>All documents</h3></div><span className="sort-label"><Clock3 size={14} /> Recently added</span></div>
        {loading ? <div className="loading-inline"><LoaderCircle className="spin" size={18} /> Loading documents</div> : documents.length ? <DocumentRows documents={documents} onDelete={canEdit ? onDelete : undefined} onReprocess={canEdit ? onReprocess : undefined} /> : <EmptyDocuments onUpload={onUpload} />}
      </section>
    </>
  )
}

function DocumentRows({ documents, compact = false, onDelete, onReprocess }: { documents: DocumentRecord[]; compact?: boolean; onDelete?: (document: DocumentRecord) => void; onReprocess?: (document: DocumentRecord) => void }) {
  return (
    <div className={`document-list ${compact ? 'compact' : ''}`}>
      {documents.map((document) => (
        <div className="document-row" key={document.id}>
          <div className={`file-icon ${document.content_type === 'application/pdf' ? 'pdf' : 'docx'}`}><FileText size={18} /></div>
          <div className="document-name"><strong title={document.filename}>{document.filename}</strong><small>{formatBytes(document.size_bytes)}{document.page_count ? ` · ${document.page_count} pages` : ''} · {shortDate(document.created_at)}</small>{document.status === 'failed' && document.error_summary && <small className="document-error">{document.error_summary}</small>}</div>
          <StatusBadge status={document.status} />
          {!compact && (onDelete || onReprocess) && <div className="document-actions">{document.status === 'failed' && onReprocess && <button aria-label={`Reprocess ${document.filename}`} title="Reprocess document" onClick={() => onReprocess(document)}><RotateCcw size={15} /></button>}<button aria-label={`Delete ${document.filename}`} title="Delete document" onClick={() => onDelete?.(document)}><Trash2 size={15} /></button></div>}
        </div>
      ))}
    </div>
  )
}

function StatusBadge({ status }: { status: DocumentRecord['status'] }) {
  const label: Record<DocumentRecord['status'], string> = { queued: 'Queued', processing: 'Processing', ready: 'Ready', failed: 'Needs attention', deleting: 'Deleting' }
  return <span className={`status-badge ${status}`}><span />{label[status]}</span>
}

function SearchView({ query, setQuery, results, searching, onSearch }: { query: string; setQuery: (query: string) => void; results: SearchResult[]; searching: boolean; onSearch: (event?: FormEvent) => void }) {
  const [hasSearched, setHasSearched] = useState(false)
  function submitSearch(event: FormEvent) {
    setHasSearched(true)
    onSearch(event)
  }
  return (
    <>
      <div className="page-heading search-page-heading"><div><span className="eyebrow">MEANING, NOT JUST MATCHING</span><h1>Find the passage<span className="heading-period">.</span></h1><p>Search across your processed documents using natural language.</p></div></div>
      <section className="search-hero"><div className="search-hero-icon"><Search size={21} /></div><h2>What are you looking for?</h2><p>Ask in your own words. DocuMind will find the passages that are closest in meaning.</p><form className="search-form" onSubmit={submitSearch}><Search size={19} /><input autoFocus value={query} onChange={(event) => { setQuery(event.target.value); setHasSearched(false) }} placeholder="e.g. What is our policy on remote work?" /><button disabled={searching || query.trim().length < 2}>{searching ? <LoaderCircle className="spin" size={17} /> : 'Search'}{!searching && <ArrowUpRight size={15} />}</button></form><div className="search-suggestions"><span>Try:</span>{['annual leave policy', 'project delivery dates', 'reimbursement limits'].map((suggestion) => <button key={suggestion} onClick={() => { setQuery(suggestion); setHasSearched(false) }}>{suggestion}</button>)}</div></section>
      {searching && <div className="loading-inline search-loading"><LoaderCircle className="spin" size={18} /> Looking through your documents…</div>}
      {hasSearched && !!results.length && <section className="results-section"><div className="results-heading"><div><span className="eyebrow">SEARCH RESULTS</span><h3>{results.length} relevant {results.length === 1 ? 'passage' : 'passages'}</h3></div><span>Sorted by relevance</span></div><div className="result-list">{results.map((result) => <article className="result-card" key={result.chunk_id}><div className="result-meta"><span className="result-file"><FileText size={14} />{result.document_name}</span><span>{result.page_number ? `Page ${result.page_number}` : `Section ${result.source_index}`}</span><span className="result-score">{Math.round(result.score * 100)}% match</span></div><p>{result.content}</p><div className="result-footer"><span>Source passage</span><button onClick={() => navigator.clipboard?.writeText(result.content).then(() => undefined).catch(() => undefined)}>Copy passage</button></div></article>)}</div></section>}
      {!searching && hasSearched && query && !results.length && <div className="no-results"><div className="empty-icon"><Search size={20} /></div><h3>No passages found yet</h3><p>Try another phrase or make sure your documents have finished processing.</p></div>}
      {!query && <div className="search-footnote"><ShieldCheck size={15} /> Results are only drawn from ready documents in this workspace.</div>}
    </>
  )
}

function ChatView({ conversations, activeConversationId, messages, sending, onSelect, onNew, onSend }: { conversations: Conversation[]; activeConversationId: string; messages: Message[]; sending: boolean; onSelect: (id: string) => void; onNew: () => void; onSend: (content: string) => void }) {
  const [draft, setDraft] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const active = conversations.find((conversation) => conversation.id === activeConversationId)
  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages, sending])
  function submit(event: FormEvent) {
    event.preventDefault()
    sendDraft()
  }
  function sendDraft() {
    if (!draft.trim() || sending) return
    onSend(draft)
    setDraft('')
  }
  return (
    <div className="chat-layout">
      <aside className="chat-thread-panel"><div className="chat-thread-header"><div><span className="eyebrow">YOUR THREADS</span><h3>Conversations</h3></div><button className="icon-button new-thread-button" aria-label="New conversation" onClick={onNew}><Plus size={17}/></button></div><button className="button primary new-conversation" onClick={onNew}><Plus size={16}/> New conversation</button><div className="thread-list">{conversations.map((conversation) => <button key={conversation.id} className={`thread-item ${activeConversationId === conversation.id ? 'active' : ''}`} onClick={() => onSelect(conversation.id)}><MessageSquareText size={16}/><span><strong>{conversation.title}</strong><small>{shortDate(conversation.created_at)}</small></span><ChevronRight size={14}/></button>)}</div><div className="thread-privacy"><ShieldCheck size={15}/><span>Your chats are private to you.</span></div></aside>
      <section className="chat-panel"><div className="chat-panel-top"><div><span className="eyebrow">GROUNDED IN YOUR LIBRARY</span><h3>{active?.title ?? 'A new conversation'}</h3></div><span className="chat-model-pill"><span/> Source-backed</span></div><div className="message-scroll">
        {!messages.length && !sending ? <div className="chat-empty"><div className="chat-empty-icon"><Sparkles size={21}/></div><span className="eyebrow">YOUR DOCUMENTS, IN CONTEXT</span><h2>What would you like to know?</h2><p>Ask a question about the documents in {conversations[0]?.title ? 'this workspace' : 'your workspace'}. Answers include the source passages they came from.</p><div className="prompt-chips">{['Summarize the key points', 'What are the important dates?', 'What risks should I know about?'].map((prompt) => <button key={prompt} onClick={() => setDraft(prompt)}>{prompt}<ArrowUpRight size={14}/></button>)}</div></div> : <div className="message-list">{messages.map((message) => <MessageBubble message={message} key={message.id}/>) }{sending && <div className="assistant-thinking"><span className="thinking-avatar"><Sparkles size={15}/></span><span><i/><i/><i/></span><small>Reading your sources…</small></div>}<div ref={bottomRef}/></div>}
      </div><form className="chat-composer" onSubmit={submit}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendDraft() } }} placeholder="Ask a question about your documents…" rows={2} maxLength={2000}/><div className="composer-bottom"><span><ShieldCheck size={13}/> Answers are grounded in your workspace</span><button className="send-button" disabled={sending || draft.trim().length < 2} aria-label="Send question">{sending ? <LoaderCircle className="spin" size={17}/> : <Send size={16}/>}</button></div></form><p className="chat-disclaimer">DocuMind can make mistakes. Check the source passages for important decisions.</p></section>
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <article className={`message ${isUser ? 'user-message' : 'assistant-message'}`}>
      {!isUser && <span className="message-avatar"><Sparkles size={15}/></span>}
      <div className="message-body"><div className="message-author">{isUser ? 'You' : 'DocuMind'}{message.answer_status === 'insufficient_evidence' && <span className="answer-status">Not enough evidence</span>}</div><p>{message.content}</p>
        {!isUser && message.sources.length > 0 && <div className="citation-list"><span className="citation-heading"><BookOpen size={13}/> SOURCES</span>{message.sources.map((source) => <div className="citation-card" key={source.chunk_id}><span className="citation-file"><FileText size={14}/></span><span><strong>{source.document_name}</strong><small>{source.page_number ? `Page ${source.page_number}` : `Section ${source.source_index}`} · {Math.round(source.relevance_score * 100)}% relevance</small></span><ArrowUpRight size={14}/></div>)}</div>}
      </div>
    </article>
  )
}

function WorkspaceModal({ onClose, onCreate }: { onClose: () => void; onCreate: (name: string) => void }) {
  const [name, setName] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    if (name.trim()) onCreate(name.trim())
  }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="workspace-modal-title"><button className="modal-close" aria-label="Close" onClick={onClose}><X size={18}/></button><div className="modal-icon"><FolderOpen size={19}/></div><span className="eyebrow">A PRIVATE SPACE FOR YOUR TEAM</span><h2 id="workspace-modal-title">Create a workspace</h2><p>Keep documents and questions organized around a team or project.</p><form onSubmit={submit}><label htmlFor="workspace-name">Workspace name</label><input id="workspace-name" autoFocus required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Product research"/><div className="modal-actions"><button className="button secondary" type="button" onClick={onClose}>Cancel</button><button className="button primary" disabled={!name.trim()}><Plus size={16}/> Create workspace</button></div></form></section></div>
}

export default App
