import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  MessageSquare, Library, Search, PenLine, Settings,
  Plus, PanelLeftClose, PanelLeft, Sparkles, Trash2,
} from 'lucide-react'
import { useChatContext } from '../context/ChatContext'
import { useAppStore } from '../store/useAppStore'
import { cn } from '../lib/cn'

const navItems = [
  { to: '/', label: '对话', icon: MessageSquare, exact: true },
  { to: '/knowledge', label: '知识库', icon: Library },
  { to: '/search', label: 'RAG 检索', icon: Search },
  { to: '/writing', label: '论文写作', icon: PenLine },
]

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const collapsed = useAppStore(s => s.sidebarCollapsed)
  const toggleSidebar = useAppStore(s => s.toggleSidebar)

  const { conversations, currentConvId, selectConversation, newConversation, deleteConversation, loading } = useChatContext()
  const onChatRoute = location.pathname === '/'

  const handleNew = () => {
    newConversation()
    navigate('/')
  }

  const handleSelect = (id: number) => {
    if (loading) return
    selectConversation(id)
    navigate('/')
  }

  return (
    <aside
      className={cn(
        'flex shrink-0 flex-col border-r border-slate-200 bg-white transition-all duration-200',
        collapsed ? 'w-[68px]' : 'w-64',
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-2.5 px-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-500 shadow-glow">
          <Sparkles className="h-5 w-5 text-white" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold text-slate-800">论文智能体</h1>
            <p className="truncate text-xs text-slate-400">Multi-Agent Writing</p>
          </div>
        )}
      </div>

      {/* 新对话 */}
      <div className="px-3 pb-2">
        <button
          onClick={handleNew}
          className={cn(
            'flex w-full items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-500 px-3 py-2.5 text-sm font-medium text-white shadow-soft transition-all hover:shadow-glow hover:brightness-105',
            collapsed && 'justify-center px-0',
          )}
        >
          <Plus className="h-4 w-4 shrink-0" />
          {!collapsed && '新对话'}
        </button>
      </div>

      {/* 主导航 */}
      <nav className="space-y-1 px-3 py-2">
        {navItems.map(item => {
          const active = item.exact
            ? location.pathname === '/'
            : location.pathname.startsWith(item.to)
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={cn(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
                active ? 'bg-indigo-50 text-indigo-600' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800',
                collapsed && 'justify-center px-0',
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="h-[18px] w-[18px] shrink-0" />
              {!collapsed && item.label}
            </NavLink>
          )
        })}
      </nav>

      {/* 会话历史（仅对话路由、展开态） */}
      {onChatRoute && !collapsed && (
        <div className="flex min-h-0 flex-1 flex-col px-3 pt-2">
          <p className="px-2 pb-1.5 text-xs font-medium text-slate-400">最近对话</p>
          <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
            {conversations.length === 0 ? (
              <p className="px-2 py-3 text-xs text-slate-300">暂无历史对话</p>
            ) : (
              conversations.map(c => (
                <div
                  key={c.id}
                  className={cn(
                    'group flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors',
                    currentConvId === c.id ? 'bg-slate-100 text-slate-800' : 'text-slate-500 hover:bg-slate-50',
                  )}
                  onClick={() => handleSelect(c.id)}
                >
                  <span className="min-w-0 flex-1 truncate">{c.title || '未命名对话'}</span>
                  <button
                    onClick={e => { e.stopPropagation(); deleteConversation(c.id) }}
                    className="shrink-0 text-slate-300 opacity-0 transition-opacity hover:text-rose-500 group-hover:opacity-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {!onChatRoute && <div className="flex-1" />}

      {/* 底部：设置 + 折叠 */}
      <div className="space-y-1 border-t border-slate-100 p-3">
        <NavLink
          to="/settings"
          className={cn(
            'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
            location.pathname.startsWith('/settings') ? 'bg-indigo-50 text-indigo-600' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800',
            collapsed && 'justify-center px-0',
          )}
          title={collapsed ? '设置' : undefined}
        >
          <Settings className="h-[18px] w-[18px] shrink-0" />
          {!collapsed && '模型配置'}
        </NavLink>
        <button
          onClick={toggleSidebar}
          className={cn(
            'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700',
            collapsed && 'justify-center px-0',
          )}
        >
          {collapsed ? <PanelLeft className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
          {!collapsed && '收起边栏'}
        </button>
      </div>
    </aside>
  )
}
