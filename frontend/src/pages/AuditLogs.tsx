import { useEffect, useState } from 'react'
import { getAuditLogs } from '../api/client'
import { ClipboardList, Search, ChevronDown, AlertCircle } from 'lucide-react'

const QUERY_TYPE_COLORS: Record<string, string> = {
  factual: 'bg-blue-100 text-blue-700',
  procedural: 'bg-purple-100 text-purple-700',
  policy: 'bg-indigo-100 text-indigo-700',
  'exception-handling': 'bg-orange-100 text-orange-700',
  general: 'bg-slate-100 text-slate-600',
}

const ROLE_COLORS: Record<string, string> = {
  analyst: 'bg-green-100 text-green-700',
  operations: 'bg-blue-100 text-blue-700',
  compliance: 'bg-purple-100 text-purple-700',
  admin: 'bg-red-100 text-red-700',
}

export default function AuditLogs() {
  const [logs, setLogs] = useState<any[]>([])
  const [filtered, setFiltered] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [expanded, setExpanded] = useState<number | null>(null)

  useEffect(() => {
    getAuditLogs()
      .then(r => { setLogs(r.data); setFiltered(r.data) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    let result = logs
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(l =>
        l.query?.toLowerCase().includes(q) ||
        l.username?.toLowerCase().includes(q)
      )
    }
    if (roleFilter !== 'all') result = result.filter(l => l.role === roleFilter)
    if (typeFilter !== 'all') result = result.filter(l => l.query_type === typeFilter)
    setFiltered(result)
  }, [search, roleFilter, typeFilter, logs])

  const roles = ['all', 'analyst', 'operations', 'compliance', 'admin']
  const types = ['all', 'factual', 'procedural', 'policy', 'exception-handling', 'general']

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Audit Logs</h1>
        <p className="text-sm text-slate-500 mt-1">Complete query history with role and access tracking</p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4">
        <div className="flex flex-wrap gap-3 items-center">
          {/* Search */}
          <div className="relative flex-1 min-w-56">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search queries or users…"
              className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Role filter */}
          <div className="relative">
            <select
              value={roleFilter}
              onChange={e => setRoleFilter(e.target.value)}
              className="appearance-none pl-3 pr-8 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white cursor-pointer"
            >
              {roles.map(r => (
                <option key={r} value={r}>{r === 'all' ? 'All Roles' : r.charAt(0).toUpperCase() + r.slice(1)}</option>
              ))}
            </select>
            <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          </div>

          {/* Query type filter */}
          <div className="relative">
            <select
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value)}
              className="appearance-none pl-3 pr-8 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white cursor-pointer"
            >
              {types.map(t => (
                <option key={t} value={t}>{t === 'all' ? 'All Types' : t}</option>
              ))}
            </select>
            <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          </div>

          <span className="text-xs text-slate-400 ml-auto">{filtered.length} record{filtered.length !== 1 ? 's' : ''}</span>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-400">
            <span className="w-5 h-5 border-2 border-slate-200 border-t-blue-500 rounded-full animate-spin mr-2" />
            Loading audit logs…
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400 gap-2">
            <ClipboardList size={32} className="text-slate-300" />
            <p>No audit logs found</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100">
                {['Timestamp', 'User', 'Role', 'Query', 'Type', 'Confidence', 'Latency', 'Results'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((log, idx) => (
                <>
                  <tr
                    key={log.log_id ?? idx}
                    className="hover:bg-slate-50 cursor-pointer"
                    onClick={() => setExpanded(expanded === idx ? null : idx)}
                  >
                    <td className="px-4 py-3 text-slate-400 text-xs whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-700">{log.username}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[log.role] ?? 'bg-slate-100 text-slate-600'}`}>
                        {log.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700 max-w-xs">
                      <p className="truncate">{log.query}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${QUERY_TYPE_COLORS[log.query_type] ?? 'bg-slate-100 text-slate-600'}`}>
                        {log.query_type ?? '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {log.confidence != null ? (
                        <div className="flex items-center gap-1.5">
                          <div className="w-12 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 rounded-full"
                              style={{ width: `${Math.round(log.confidence * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs">{Math.round(log.confidence * 100)}%</span>
                        </div>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-600 text-xs whitespace-nowrap">
                      {log.latency_ms != null ? `${log.latency_ms.toFixed(0)} ms` : '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-600 text-xs">
                      {log.results_count ?? '—'}
                    </td>
                  </tr>
                  {expanded === idx && (
                    <tr key={`exp-${idx}`} className="bg-blue-50/40">
                      <td colSpan={8} className="px-6 py-4">
                        <div className="space-y-2">
                          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Full Query</p>
                          <p className="text-sm text-slate-700">{log.query}</p>
                          {log.error && (
                            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-3 mt-2">
                              <AlertCircle size={14} className="text-red-500 mt-0.5 shrink-0" />
                              <p className="text-xs text-red-700">{log.error}</p>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
