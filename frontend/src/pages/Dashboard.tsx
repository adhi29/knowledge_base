import { useEffect, useState } from 'react'
import { getStats, getAuditLogs } from '../api/client'
import { Database, MessageSquare, Clock, FileStack } from 'lucide-react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts'

const COLORS = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444']

export default function Dashboard() {
  const [stats, setStats]   = useState<any>(null)
  const [logs, setLogs]     = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getStats(), getAuditLogs(undefined, 200)])
      .then(([s, l]) => { setStats(s.data); setLogs(l.data) })
      .finally(() => setLoading(false))
  }, [])

  // Compute query type distribution
  const typeCounts: Record<string, number> = {}
  logs.forEach(l => {
    const t = l.query_type || 'general'
    typeCounts[t] = (typeCounts[t] || 0) + 1
  })
  const typeData = Object.entries(typeCounts).map(([name, value]) => ({ name, value }))

  // Latency distribution buckets
  const latencyBuckets = [
    { range: '<1s',  count: 0 },
    { range: '1–3s', count: 0 },
    { range: '3–5s', count: 0 },
    { range: '>5s',  count: 0 },
  ]
  logs.forEach(l => {
    const s = (l.latency_ms || 0) / 1000
    if (s < 1) latencyBuckets[0].count++
    else if (s < 3) latencyBuckets[1].count++
    else if (s < 5) latencyBuckets[2].count++
    else latencyBuckets[3].count++
  })

  const avgLatency = logs.length
    ? (logs.reduce((sum, l) => sum + (l.latency_ms || 0), 0) / logs.length / 1000).toFixed(2)
    : '0'

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const STAT_CARDS = [
    { icon: FileStack,     label: 'Total Chunks Indexed', value: stats?.total_chunks_indexed ?? 0,  color: 'bg-blue-500'   },
    { icon: Database,      label: 'FAISS Index Size',     value: stats?.faiss_index_size ?? 0,       color: 'bg-indigo-500' },
    { icon: MessageSquare, label: 'Total Queries',        value: logs.length,                        color: 'bg-purple-500' },
    { icon: Clock,         label: 'Avg Latency',          value: `${avgLatency}s`,                   color: 'bg-green-500'  },
  ]

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Analytics Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">System performance and usage metrics</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4">
        {STAT_CARDS.map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
            <div className={`w-10 h-10 ${color} rounded-xl flex items-center justify-center mb-3`}>
              <Icon size={18} className="text-white" />
            </div>
            <p className="text-2xl font-bold text-slate-800">{value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-2 gap-4">
        {/* Query Type Pie */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <h3 className="font-semibold text-slate-800 mb-4">Query Type Distribution</h3>
          {typeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={typeData} cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={3} dataKey="value">
                  {typeData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v, n) => [v, n]} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-400 text-sm">No data yet</div>
          )}
          <div className="flex flex-wrap gap-2 mt-2">
            {typeData.map((d, i) => (
              <span key={d.name} className="flex items-center gap-1 text-xs text-slate-600">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                {d.name} ({d.value})
              </span>
            ))}
          </div>
        </div>

        {/* Latency Bar */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <h3 className="font-semibold text-slate-800 mb-4">Response Latency Breakdown</h3>
          {logs.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={latencyBuckets} barSize={40}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="range" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-400 text-sm">No queries yet</div>
          )}
        </div>
      </div>

      {/* Recent Queries */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h3 className="font-semibold text-slate-800">Recent Queries</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left">
                {['User', 'Query', 'Type', 'Latency', 'Timestamp'].map(h => (
                  <th key={h} className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {logs.slice(0, 10).map(log => (
                <tr key={log.log_id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-700">{log.user_id?.slice(0, 8)}…</td>
                  <td className="px-4 py-3 text-slate-600 max-w-xs truncate">{log.query}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">{log.query_type || '—'}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{log.latency_ms ? `${(log.latency_ms/1000).toFixed(1)}s` : '—'}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{new Date(log.timestamp).toLocaleString()}</td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">No queries logged yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
