import { useEffect, useState } from 'react'
import { getStats, getIngestionStatus, ingestPath } from '../api/client'
import { FolderOpen, Play, CheckCircle, XCircle, Clock, Database, FileText, RefreshCw } from 'lucide-react'

export default function Admin() {
  const [stats, setStats]   = useState<any>(null)
  const [ingestionLog, setIngestionLog] = useState<any[]>([])
  const [path, setPath]     = useState('')
  const [sensitivity, setSensitivity] = useState('internal')
  const [roles, setRoles]   = useState<string[]>(['analyst','operations','compliance','admin'])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError]   = useState('')

  const refresh = () => {
    Promise.all([getStats(), getIngestionStatus()])
      .then(([s, i]) => { setStats(s.data); setIngestionLog(i.data) })
  }

  useEffect(() => { refresh() }, [])

  const handleIngest = async () => {
    if (!path.trim()) return
    setLoading(true); setError(''); setResult(null)
    try {
      const { data } = await ingestPath(path.trim(), sensitivity, roles)
      setResult(data)
      refresh()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Ingestion failed.')
    } finally {
      setLoading(false)
    }
  }

  const toggleRole = (r: string) =>
    setRoles(prev => prev.includes(r) ? prev.filter(x => x !== r) : [...prev, r])

  const ROLE_PILLS = [
    { key: 'analyst',    label: 'Analyst',    color: 'bg-green-100 text-green-700 border-green-300' },
    { key: 'operations', label: 'Operations', color: 'bg-blue-100 text-blue-700 border-blue-300' },
    { key: 'compliance', label: 'Compliance', color: 'bg-purple-100 text-purple-700 border-purple-300' },
    { key: 'admin',      label: 'Admin',      color: 'bg-red-100 text-red-700 border-red-300' },
  ]

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Document Management</h1>
          <p className="text-sm text-slate-500 mt-1">Ingest documents into the knowledge base</p>
        </div>
        <button onClick={refresh} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-blue-600 hover:bg-blue-50 px-3 py-2 rounded-lg transition-colors">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
            <Database size={22} className="text-blue-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-800">{stats?.total_chunks_indexed ?? '—'}</p>
            <p className="text-xs text-slate-500">Total Chunks Indexed</p>
          </div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
            <FileText size={22} className="text-green-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-800">{ingestionLog.length}</p>
            <p className="text-xs text-slate-500">Documents Ingested</p>
          </div>
        </div>
      </div>

      {/* Ingest form */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="font-semibold text-slate-800 mb-5 flex items-center gap-2">
          <FolderOpen size={18} className="text-blue-500" /> Ingest New Documents
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5">
              File or Directory Path
            </label>
            <input
              type="text"
              value={path}
              onChange={e => setPath(e.target.value)}
              placeholder="e.g. /Users/adhi/Desktop/virtusa/data/sample_docs"
              className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5">
                Sensitivity Level
              </label>
              <select
                value={sensitivity}
                onChange={e => setSensitivity(e.target.value)}
                className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="public">Public</option>
                <option value="internal">Internal</option>
                <option value="confidential">Confidential</option>
                <option value="restricted">Restricted</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1.5">
                Allowed Roles
              </label>
              <div className="flex flex-wrap gap-2">
                {ROLE_PILLS.map(({ key, label, color }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => toggleRole(key)}
                    className={`text-xs px-3 py-1 rounded-full border font-medium transition-all ${
                      roles.includes(key) ? color : 'bg-slate-100 text-slate-400 border-slate-200'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
              <XCircle size={16} />{error}
            </div>
          )}

          {result && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800 space-y-1">
              <div className="flex items-center gap-2 font-semibold"><CheckCircle size={16} /> Ingestion complete</div>
              <p>Documents: {result.documents_processed} · New chunks: {result.chunks_created} · Skipped: {result.chunks_skipped}</p>
              {result.errors?.length > 0 && <p className="text-orange-600">Errors: {result.errors.join(', ')}</p>}
            </div>
          )}

          <button
            onClick={handleIngest}
            disabled={loading || !path.trim()}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-6 py-2.5 rounded-lg text-sm font-semibold transition-colors"
          >
            {loading
              ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Processing…</>
              : <><Play size={15} />Start Ingestion</>
            }
          </button>
        </div>
      </div>

      {/* Ingestion history */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h3 className="font-semibold text-slate-800">Ingestion History</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50">
                {['Source', 'Type', 'Status', 'Chunks', 'Processed At'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {ingestionLog.map(row => (
                <tr key={row.log_id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-700 font-medium max-w-xs truncate">{row.source_path.split('/').pop()}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs font-medium">{row.source_type}</span>
                  </td>
                  <td className="px-4 py-3">
                    {row.status === 'success' ? (
                      <span className="flex items-center gap-1 text-green-600 text-xs font-medium">
                        <CheckCircle size={13} />Success
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-orange-500 text-xs font-medium">
                        <Clock size={13} />{row.status}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{row.chunks_created}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{new Date(row.processed_at).toLocaleString()}</td>
                </tr>
              ))}
              {ingestionLog.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">No ingestion history</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
