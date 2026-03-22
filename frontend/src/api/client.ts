import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.clear()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = (username: string, password: string) => {
  const form = new URLSearchParams({ username, password })
  return api.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
}

export const getMe = () => api.get('/auth/me')

// ── Chat ──────────────────────────────────────────────────────────────────────
export interface ChatMessage { role: 'user' | 'assistant'; content: string }
export interface Citation {
  index: number; source_name: string; source_type: string;
  page_number: number | null; section: string | null;
  chunk_id: string; relevance_score: number | null
}
export interface ChatResponse {
  response: string; citations: Citation[]; query_type: string;
  confidence: number; latency_ms: number; session_id: string
}

export const chat = (
  query: string,
  session_id?: string,
  chat_history: ChatMessage[] = []
): Promise<{ data: ChatResponse }> =>
  api.post('/chat', { query, session_id, chat_history })

// ── Admin ─────────────────────────────────────────────────────────────────────
export const getStats = () => api.get('/admin/stats')
export const getIngestionStatus = () => api.get('/admin/ingestion-status')
export const getAuditLogs = (user_id?: string, limit = 100) =>
  api.get('/admin/audit-logs', { params: { user_id, limit } })
export const ingestPath = (path: string, sensitivity_level = 'internal', allowed_roles?: string[]) =>
  api.post('/admin/ingest', { path, sensitivity_level, allowed_roles, recursive: true })
