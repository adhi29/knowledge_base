import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  MessageSquare, LayoutDashboard, FolderUp, ClipboardList,
  LogOut, Building2, ChevronRight
} from 'lucide-react'

const ROLE_COLORS: Record<string, string> = {
  admin:      'bg-red-100 text-red-700',
  compliance: 'bg-purple-100 text-purple-700',
  operations: 'bg-blue-100 text-blue-700',
  analyst:    'bg-green-100 text-green-700',
}

const NAV = [
  { to: '/chat',       icon: MessageSquare,  label: 'Chat',          roles: ['analyst','operations','compliance','admin'] },
  { to: '/dashboard',  icon: LayoutDashboard,label: 'Dashboard',     roles: ['admin','compliance'] },
  { to: '/admin',      icon: FolderUp,       label: 'Document Mgmt', roles: ['admin'] },
  { to: '/audit',      icon: ClipboardList,  label: 'Audit Logs',    roles: ['admin','compliance'] },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col shadow-sm">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center">
              <Building2 size={18} className="text-white" />
            </div>
            <div>
              <p className="font-bold text-slate-800 text-sm leading-tight">KnowledgeBot</p>
              <p className="text-xs text-slate-400">Citi Banking Ops</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.filter(n => user && n.roles.includes(user.role)).map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={18} className={isActive ? 'text-blue-600' : 'text-slate-400'} />
                  <span className="flex-1">{label}</span>
                  {isActive && <ChevronRight size={14} className="text-blue-400" />}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User info */}
        <div className="px-4 py-4 border-t border-slate-200">
          <div className="flex items-center gap-3 px-2 py-2 rounded-lg">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
              {user?.username?.[0]?.toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-800 truncate">{user?.username}</p>
              <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${ROLE_COLORS[user?.role || 'analyst']}`}>
                {user?.role}
              </span>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
              title="Logout"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <Outlet />
      </main>
    </div>
  )
}
