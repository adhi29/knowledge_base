import { useState, useRef, useEffect } from 'react'
import { chat as apiChat, type ChatMessage, type Citation } from '../api/client'
import { useAuth } from '../context/AuthContext'
import {
  Send, Bot, User, FileText, ChevronDown, ChevronUp,
  Trash2, Clock, Zap, BookOpen
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

const TYPE_COLORS: Record<string, string> = {
  procedural:         'bg-blue-100 text-blue-700',
  policy:             'bg-purple-100 text-purple-700',
  factual:            'bg-green-100 text-green-700',
  'exception-handling': 'bg-orange-100 text-orange-700',
  general:            'bg-slate-100 text-slate-600',
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
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set())
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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
      if (!sessionId) setSessionId(data.session_id)

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
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-lg font-bold text-slate-800">Banking Knowledge Assistant</h1>
          <p className="text-xs text-slate-500">Ask questions about SOPs, policies, and procedures</p>
        </div>
        <div className="flex items-center gap-3">
          {sessionId && (
            <span className="text-xs text-slate-400 font-mono bg-slate-100 px-2 py-1 rounded">
              Session active
            </span>
          )}
          {messages.length > 0 && (
            <button
              onClick={() => { setMessages([]); setSessionId(undefined) }}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-red-500 hover:bg-red-50 px-3 py-1.5 rounded-lg transition-colors"
            >
              <Trash2 size={13} /> Clear
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6 scrollbar-thin">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-4">
              <BookOpen size={28} className="text-blue-600" />
            </div>
            <h2 className="text-lg font-semibold text-slate-700 mb-2">How can I help you?</h2>
            <p className="text-sm text-slate-400 max-w-md mb-8">
              Ask anything about banking operations — wire transfers, KYC policies, compliance procedures, or onboarding steps.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-xl">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="text-left text-sm text-slate-600 bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50 px-4 py-3 rounded-xl transition-all"
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
              {/* Bubble */}
              <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-sm'
                  : msg.error
                    ? 'bg-red-50 text-red-700 border border-red-200 rounded-tl-sm'
                    : 'bg-white text-slate-800 border border-slate-200 shadow-sm rounded-tl-sm'
              }`}>
                {msg.role === 'assistant' && !msg.error ? (
                  <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0.5">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p>{msg.content}</p>
                )}
              </div>

              {/* Metadata bar */}
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
                      {Math.round(msg.confidence * 100)}% confidence
                    </span>
                  )}
                  {msg.latency_ms !== undefined && (
                    <span className="flex items-center gap-1 text-xs text-slate-400">
                      <Clock size={11} />
                      {(msg.latency_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                  {msg.citations && msg.citations.length > 0 && (
                    <button
                      onClick={() => toggleCitations(msg.id)}
                      className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium"
                    >
                      <FileText size={11} />
                      {msg.citations.length} source{msg.citations.length > 1 ? 's' : ''}
                      {expandedCitations.has(msg.id) ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    </button>
                  )}
                </div>
              )}

              {/* Citations panel */}
              {msg.citations && expandedCitations.has(msg.id) && (
                <div className="bg-white border border-slate-200 rounded-xl p-3 space-y-2 w-full shadow-sm">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Sources</p>
                  {msg.citations.map(c => (
                    <div key={c.chunk_id} className="flex items-start gap-2 text-xs text-slate-600">
                      <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-[10px] flex-shrink-0">
                        {c.index}
                      </span>
                      <div>
                        <span className="font-medium">{c.source_name}</span>
                        {c.page_number && <span className="text-slate-400"> · p.{c.page_number}</span>}
                        {c.section && <span className="text-slate-400"> · {c.section.slice(0, 60)}</span>}
                        {c.relevance_score != null && (
                          <span className="ml-1 text-slate-400">({(c.relevance_score * 100).toFixed(0)}%)</span>
                        )}
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
            <div className="w-8 h-8 rounded-xl bg-blue-600 flex-shrink-0 flex items-center justify-center">
              <Bot size={15} className="text-white" />
            </div>
            <div className="bg-white border border-slate-200 shadow-sm rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="bg-white border-t border-slate-200 px-6 py-4">
        <form
          onSubmit={e => { e.preventDefault(); sendMessage(input) }}
          className="flex items-end gap-3"
        >
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) } }}
              placeholder="Ask about SOPs, policies, wire transfers, KYC..."
              rows={1}
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none leading-relaxed"
              style={{ maxHeight: '120px' }}
            />
          </div>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="w-11 h-11 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-xl flex items-center justify-center transition-colors flex-shrink-0"
          >
            <Send size={17} />
          </button>
        </form>
        <p className="text-xs text-slate-400 mt-2 text-center">
          Logged in as <strong>{user?.username}</strong> · Role: <strong>{user?.role}</strong>
        </p>
      </div>
    </div>
  )
}
