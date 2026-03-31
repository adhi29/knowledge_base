import { useState, type FormEvent } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Building2, Lock, User, AlertCircle } from 'lucide-react'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login, user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  // If already authenticated, redirect away — prevents Forward button re-entry
  if (!authLoading && user) return <Navigate to="/chat" replace />

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      // replace: true removes /login from history so Back can't return to it
      navigate('/chat', { replace: true })
    } catch {
      setError('Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-950 via-blue-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-8 py-8 text-center">
            <div className="w-16 h-16 bg-white/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <Building2 size={32} className="text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white">KnowledgeBot</h1>
            <p className="text-blue-200 text-sm mt-1">Citi Banking Operations</p>
          </div>

          {/* Form */}
          <div className="px-8 py-8">
            <p className="text-slate-500 text-sm text-center mb-6">Sign in to access the knowledge base</p>

            {error && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg mb-5">
                <AlertCircle size={16} />
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5">Username</label>
                <div className="relative">
                  <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                    className="w-full pl-9 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    placeholder="Enter username"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5">Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="w-full pl-9 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                    placeholder="Enter password"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-semibold py-2.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
              >
                {loading ? (
                  <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Signing in...</>
                ) : 'Sign In'}
              </button>
            </form>

            <div className="mt-6 pt-5 border-t border-slate-100">
              <p className="text-xs text-slate-400 text-center mb-3 font-medium">Demo accounts</p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { user: 'analyst1', pass: 'analyst123!', role: 'Analyst', color: 'bg-green-50 border-green-200 text-green-700' },
                  { user: 'ops_lead', pass: 'opsLead123!', role: 'Operations', color: 'bg-blue-50 border-blue-200 text-blue-700' },
                  { user: 'compliance1', pass: 'comply123!', role: 'Compliance', color: 'bg-purple-50 border-purple-200 text-purple-700' },
                  { user: 'admin', pass: 'admin123!', role: 'Admin', color: 'bg-red-50 border-red-200 text-red-700' },
                ].map(a => (
                  <button
                    key={a.user}
                    type="button"
                    onClick={() => { setUsername(a.user); setPassword(a.pass) }}
                    className={`text-xs px-3 py-2 rounded-lg border font-medium transition-opacity hover:opacity-80 ${a.color}`}
                  >
                    {a.role}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <p className="text-center text-blue-300/50 text-xs mt-6">Virtusa AI Center of Excellence — Confidential</p>
      </div>
    </div>
  )
}
