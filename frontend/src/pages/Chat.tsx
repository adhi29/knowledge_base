import { useState, useRef, useEffect } from 'react'
import {
  chat as apiChat,
  getChatSessions,
  getSessionMessages,
  deleteSession,
  renameSession,
  type ChatMessage,
  type Citation
} from '../api/client'
import { useAuth } from '../context/AuthContext'
import {
  Send, Bot, User, FileText, ChevronDown, ChevronUp,
  Trash2, Zap, Plus, MessageSquare, Edit3, ChevronLeft, ChevronRight, Clock
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  query_type?: string
  confidence?: number
  latency_ms?: number
  citations?: Citation[]
  error?: boolean
}

interface ChatSession {
  session_id: string
  title: string
  updated_at: string
}

const TYPE_COLORS: Record<string, string> = {
  procedural: 'bg-blue-100 text-blue-700',
  policy: 'bg-purple-100 text-purple-700',
  factual: 'bg-green-100 text-green-700',
  'exception-handling': 'bg-orange-100 text-orange-700',
  general: 'bg-slate-100 text-slate-600',
}

const SUGGESTIONS = [
  'What are the steps to process a domestic wire transfer?',
  'What is the cut-off time for Fedwire?',
  'How do I handle an OFAC sanctions hit?',
  'What is the new joiner onboarding process?',
]

export default function Chat() {
  const { user } = useAuth()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | undefined>()

  // History Sidebar state
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set())
  const bottomRef = useRef<HTMLDivElement>(null)

  // Initial load: fetch recent sessions
  useEffect(() => {
    refreshSessions()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const refreshSessions = async () => {
    try {
      const { data } = await getChatSessions()
      setSessions(data)
    } catch (err) {
      console.error('Failed to fetch sessions', err)
    }
  }

  const loadSession = async (id: string) => {
    if (loading) return
    setLoading(true)
    setSessionId(id)
    try {
      const { data } = await getSessionMessages(id)
      const formatted: Message[] = data.map((m: any) => {
        const meta = JSON.parse(m.metadata || '{}')
        return {
          id: m.message_id,
          role: m.role,
          content: m.content,
          citations: meta.citations,
          query_type: meta.query_type,
          confidence: meta.confidence,
          latency_ms: meta.latency_ms,
          timestamp: m.timestamp
        }
      })
      setMessages(formatted)
    } catch (err) {
      console.error('Failed to load session messages', err)
    } finally {
      setLoading(false)
    }
  }

  const startNewChat = () => {
    setMessages([])
    setSessionId(undefined)
  }

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (!window.confirm('Delete this chat?')) return
    try {
      await deleteSession(id)
      if (sessionId === id) startNewChat()
      refreshSessions()
    } catch (err) {
      console.error('Delete failed', err)
    }
  }

  const handleRename = async (id: string) => {
    if (!editTitle.trim()) return
    try {
      await renameSession(id, editTitle.trim())
      setEditingSessionId(null)
      refreshSessions()
    } catch (err) {
      console.error('Rename failed', err)
    }
  }

  const toggleCitations = (id: string) => {
    setExpandedCitations(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const sendMessage = async (query: string) => {
    if (!query.trim() || loading) return
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: query }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const history: ChatMessage[] = messages.slice(-6).map(m => ({
        role: m.role, content: m.content
      }))
      const { data } = await apiChat(query, sessionId, history)

      // Track the session and refresh the sidebar list every time
      if (!sessionId) setSessionId(data.session_id)
      refreshSessions()

      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.response,
        query_type: data.query_type,
        confidence: data.confidence,
        latency_ms: data.latency_ms,
        citations: data.citations,
      }])
    } catch (err: any) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: err.response?.data?.detail || 'Something went wrong. Please try again.',
        error: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full bg-slate-50 overflow-hidden">
      {/* ── Sidebar ── */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} bg-white border-r border-slate-200 h-full flex flex-col transition-all duration-300 relative group`}>
        <div className={`flex-1 flex flex-col min-w-[256px] ${!sidebarOpen && 'invisible opacity-0'}`}>
          {/* New Chat Button */}
          <div className="p-4">
            <button
              onClick={startNewChat}
              className="w-full flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors shadow-sm"
            >
              <Plus size={16} /> New Chat
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2 space-y-1">
            <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Recent History</p>
            {sessions.map(s => (
              <div
                key={s.session_id}
                onClick={() => loadSession(s.session_id)}
                className={`group flex items-center gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors ${sessionId === s.session_id ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'
                  }`}
              >
                <MessageSquare size={14} className={sessionId === s.session_id ? 'text-blue-600' : 'text-slate-400'} />
                {editingSessionId === s.session_id ? (
                  <input
                    autoFocus
                    className="flex-1 bg-white border border-blue-300 rounded px-1 outline-none"
                    value={editTitle}
                    onChange={e => setEditTitle(e.target.value)}
                    onBlur={() => handleRename(s.session_id)}
                    onKeyDown={e => e.key === 'Enter' && handleRename(s.session_id)}
                  />
                ) : (
                  <span className="flex-1 truncate">{s.title}</span>
                )}

                <div className="hidden group-hover:flex items-center gap-1">
                  <button
                    onClick={(e) => { e.stopPropagation(); setEditingSessionId(s.session_id); setEditTitle(s.title) }}
                    className="p-1 hover:bg-blue-100 rounded text-slate-400 hover:text-blue-600"
                  >
                    <Edit3 size={12} />
                  </button>
                  <button
                    onClick={(e) => handleDeleteSession(e, s.session_id)}
                    className="p-1 hover:bg-red-100 rounded text-slate-400 hover:text-red-600"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
            {sessions.length === 0 && (
              <p className="px-3 py-4 text-xs text-slate-400 italic">No previous chats</p>
            )}
          </div>

          {/* User Profile */}
          <div className="p-4 border-t border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-600">
                <User size={16} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold text-slate-800 truncate">{user?.username}</p>
                <p className="text-[10px] text-slate-400 uppercase font-medium">{user?.role}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Toggle Button */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className={`absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 bg-white border border-slate-200 rounded-full flex items-center justify-center text-slate-400 hover:text-blue-600 shadow-sm z-10 transition-opacity ${!sidebarOpen && 'opacity-100'}`}
        >
          {sidebarOpen ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>

      {/* ── Main Chat Area ── */}
      <div className="flex-1 flex flex-col min-w-0 relative h-full">
        {/* Header */}
        <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm flex-shrink-0">
          <div>
            <h1 className="text-lg font-bold text-slate-800">Knowledge Assistant</h1>
            <p className="text-xs text-slate-500">Persistent user session: <strong>{sessionId ? 'Active' : 'New'}</strong></p>
          </div>
          <div className="flex items-center gap-3">
            {messages.length > 0 && (
              <button
                onClick={startNewChat}
                className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-blue-600 hover:bg-blue-50 px-3 py-1.5 rounded-lg transition-colors border border-slate-200"
              >
                <Plus size={13} /> New Chat
              </button>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6 scrollbar-thin bg-white">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-4">
                <Zap size={28} className="text-blue-600" />
              </div>
              <h2 className="text-xl font-bold text-slate-800 mb-2">How can I help you?</h2>
              <p className="text-sm text-slate-400 max-w-sm mb-8">
                Your chat history is now saved! Ask anything about SOPs, procedures, or policies.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl">
                {SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    className="text-left text-sm text-slate-600 bg-slate-50 border border-slate-200 hover:border-blue-300 hover:bg-blue-50 px-4 py-3 rounded-xl transition-all"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-xl bg-blue-600 flex-shrink-0 flex items-center justify-center mt-1">
                  <Bot size={15} className="text-white" />
                </div>
              )}

              <div className={`max-w-2xl ${msg.role === 'user' ? 'items-end' : 'items-start'} flex flex-col gap-2`}>
                <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-sm shadow-md'
                  : msg.error
                    ? 'bg-red-50 text-red-700 border border-red-200 rounded-tl-sm'
                    : 'bg-slate-50 text-slate-800 border border-slate-200 rounded-tl-sm shadow-sm'
                  }`}>
                  {msg.role === 'assistant' && !msg.error ? (
                    <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0.5">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p>{msg.content}</p>
                  )}
                </div>

                {msg.role === 'assistant' && !msg.error && (
                  <div className="flex items-center gap-2 flex-wrap">
                    {msg.query_type && (
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${TYPE_COLORS[msg.query_type] || TYPE_COLORS.general}`}>
                        {msg.query_type}
                      </span>
                    )}
                    {msg.confidence !== undefined && (
                      <span className="flex items-center gap-1 text-xs text-slate-400">
                        <Zap size={11} />
                        {Math.round(msg.confidence * 100)}%
                      </span>
                    )}
                    {msg.latency_ms !== undefined && msg.latency_ms > 0 && (
                      <span className="flex items-center gap-1 text-xs text-slate-400">
                        <Clock size={11} />
                        {msg.latency_ms < 1000
                          ? `${msg.latency_ms}ms`
                          : `${(msg.latency_ms / 1000).toFixed(1)}s`}
                      </span>
                    )}
                    {msg.citations && msg.citations.length > 0 && (
                      <button
                        onClick={() => toggleCitations(msg.id)}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium"
                      >
                        <FileText size={11} />
                        {msg.citations.length} sources
                        {expandedCitations.has(msg.id) ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                      </button>
                    )}
                  </div>
                )}

                {msg.citations && expandedCitations.has(msg.id) && (
                  <div className="bg-white border border-slate-200 rounded-xl p-3 space-y-2 w-full shadow-lg">
                    {msg.citations.map(c => (
                      <div key={c.chunk_id} className="flex items-start gap-2 text-xs text-slate-600 border-b border-slate-50 last:border-0 pb-1.5 last:pb-0">
                        <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-[10px] flex-shrink-0">
                          {c.index}
                        </span>
                        <div>
                          <span className="font-semibold">{c.source_name}</span>
                          <span className="text-slate-400 block mt-0.5 text-[10px] italic">
                            {c.source_type} {c.page_number && `· Page ${c.page_number}`} {c.section && `· ${c.section.slice(0, 40)}...`}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-slate-200 flex-shrink-0 flex items-center justify-center mt-1">
                  <User size={15} className="text-slate-600" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-xl bg-blue-600 flex-shrink-0 flex items-center justify-center mt-1">
                <Bot size={15} className="text-white" />
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" />
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0.4s]" />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="bg-white border-t border-slate-200 px-6 py-4 flex-shrink-0">
          <form
            onSubmit={e => { e.preventDefault(); sendMessage(input) }}
            className="flex items-end gap-3 max-w-4xl mx-auto"
          >
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) } }}
                placeholder="Message the assistant..."
                rows={1}
                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none leading-relaxed bg-slate-50"
                style={{ maxHeight: '120px' }}
              />
            </div>
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="w-11 h-11 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-xl flex items-center justify-center transition-colors flex-shrink-0 shadow-sm"
            >
              <Send size={17} />
            </button>
          </form>
          <p className="text-[10px] text-slate-400 mt-2 text-center uppercase tracking-widest font-bold">
            CITI BRAIN v1.0 · PROTECTED CONTENT
          </p>
        </div>
      </div>
    </div>
  )
}
