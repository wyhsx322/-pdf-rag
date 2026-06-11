import { NavLink, useLocation } from 'react-router-dom'

const navItems = [
  { to: '/', label: '知识库', icon: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
    </svg>
  )},
  { to: '/chunking', label: '智能切片', icon: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M4 6h16M4 12h16M4 18h7" />
    </svg>
  )},
  { to: '/search', label: '混合检索', icon: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  )},
  { to: '/chat', label: '问答对话', icon: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  )},
  { to: '/thesis', label: '论文助手', icon: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )},
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside className="w-60 bg-slate-900 flex flex-col shrink-0">
      {/* Logo 区域 */}
      <div className="h-16 flex items-center px-6 border-b border-slate-700/50">
        <span className="text-xl mr-2.5">📄</span>
        <div>
          <h1 className="text-sm font-semibold text-white leading-tight">论文 RAG</h1>
          <p className="text-xs text-slate-400 leading-tight">知识库管理系统</p>
        </div>
      </div>

      {/* 导航菜单 */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(item => {
          const isActive = item.to === '/'
            ? location.pathname === '/' || location.pathname.startsWith('/kb/')
            : location.pathname.startsWith(item.to)

          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-indigo-500/20 text-indigo-300'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {item.icon}
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      {/* 底部信息 */}
      <div className="px-6 py-4 border-t border-slate-700/50">
        <p className="text-xs text-slate-500">v2.0.0 · Multi-Agent</p>
      </div>
    </aside>
  )
}
