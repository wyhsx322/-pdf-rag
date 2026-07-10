import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  MessageSquare, Library, PenLine, Settings,
  Plus, PanelLeftClose, PanelLeft, Sparkles, Trash2, BrainCircuit,
} from 'lucide-react'
import { useChatContext } from '../../features/chat-session/ChatContext'
import { useAppStore } from '../../shared/state/useAppStore'
import { cn } from '../../shared/lib/cn'

const navItems = [
  { to: '/', label: '论文写作助手', desc: 'Agent 写作工作台', icon: PenLine, exact: true },
  { to: '/knowledge', label: '知识库', desc: '文档、切分与 RAG', icon: Library },
  { to: '/chat', label: '学术对话', desc: '基于知识库问答', icon: MessageSquare },
]

export default function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const collapsed = useAppStore(s => s.sidebarCollapsed)
  const toggleSidebar = useAppStore(s => s.toggleSidebar)

  const { conversations, currentConvId, selectConversation, newConversation, deleteConversation, loading } = useChatContext()
  const onChatRoute = location.pathname === '/chat'

  const handleNew = () => {
    newConversation()
    navigate('/chat')
  }

  const handleSelect = (id: number) => {
    if (loading) return
    selectConversation(id)
    navigate('/chat')
  }

  return (
    <aside
      className={cn(
        'relative flex shrink-0 flex-col border-r border-white/50 bg-slate-950 text-white shadow-[22px_0_60px_rgba(15,23,42,0.18)] transition-all duration-200',
        collapsed ? 'w-[76px]' : 'w-[292px]',
      )}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_30%_8%,rgba(99,102,241,0.36),transparent_34%),radial-gradient(circle_at_100%_60%,rgba(20,184,166,0.20),transparent_32%)]" />
      <div className="relative flex h-full flex-col">
        <div className="flex h-20 items-center gap-3 px-5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-white/15 bg-white/10 shadow-glow backdrop-blur">
            <Sparkles className="h-5 w-5 text-cyan-200" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <h1 className="truncate text-[15px] font-semibold tracking-wide text-white">论文智能体</h1>
              <p className="mt-0.5 truncate text-xs text-slate-400">Research Writing OS</p>
            </div>
          )}
        </div>

        <div className="px-4 pb-4">
          <button
            onClick={handleNew}
            className={cn(
              'flex w-full items-center gap-2 rounded-2xl border border-cyan-300/30 bg-cyan-300/10 px-3.5 py-3 text-sm font-medium text-cyan-50 shadow-[0_14px_36px_rgba(6,182,212,0.14)] transition-all hover:border-cyan-200/60 hover:bg-cyan-300/15',
              collapsed && 'justify-center px-0',
            )}
          >
            <Plus className="h-4 w-4 shrink-0" />
            {!collapsed && '新建对话'}
          </button>
        </div>

        <nav className="space-y-2 px-4 py-2">
          {navItems.map(item => {
            const active = item.exact
              ? location.pathname === item.to
              : location.pathname.startsWith(item.to)
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={cn(
                  'group flex items-center gap-3 rounded-2xl px-3.5 py-3 text-sm transition-all',
                  active
                    ? 'bg-white text-slate-950 shadow-[0_16px_44px_rgba(255,255,255,0.14)]'
                    : 'text-slate-400 hover:bg-white/8 hover:text-white',
                  collapsed && 'justify-center px-0',
                )}
                title={collapsed ? item.label : undefined}
              >
                <Icon className={cn('h-[18px] w-[18px] shrink-0', active ? 'text-indigo-600' : 'text-slate-500 group-hover:text-cyan-200')} />
                {!collapsed && (
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{item.label}</span>
                    <span className={cn('mt-0.5 block truncate text-[11px]', active ? 'text-slate-500' : 'text-slate-500')}>{item.desc}</span>
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>

        {onChatRoute && !collapsed && (
          <div className="mt-5 flex min-h-0 flex-1 flex-col px-4">
            <div className="mb-2 flex items-center gap-2 px-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
              <BrainCircuit className="h-3.5 w-3.5" />
              最近对话
            </div>
            <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
              {conversations.length === 0 ? (
                <p className="rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-4 text-xs leading-5 text-slate-500">暂无历史对话</p>
              ) : (
                conversations.map(c => (
                  <div
                    key={c.id}
                    className={cn(
                      'group flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2.5 text-sm transition-colors',
                      currentConvId === c.id ? 'bg-white/12 text-white' : 'text-slate-400 hover:bg-white/8 hover:text-white',
                    )}
                    onClick={() => handleSelect(c.id)}
                  >
                    <span className="min-w-0 flex-1 truncate">{c.title || '未命名对话'}</span>
                    <button
                      onClick={e => { e.stopPropagation(); deleteConversation(c.id) }}
                      className="shrink-0 text-slate-600 opacity-0 transition-opacity hover:text-rose-300 group-hover:opacity-100"
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

        <div className="space-y-2 border-t border-white/10 p-4">
          <NavLink
            to="/settings"
            className={cn(
              'flex items-center gap-3 rounded-2xl px-3.5 py-3 text-sm font-medium transition-colors',
              location.pathname.startsWith('/settings') ? 'bg-white text-slate-950' : 'text-slate-400 hover:bg-white/8 hover:text-white',
              collapsed && 'justify-center px-0',
            )}
            title={collapsed ? '智能体模型' : undefined}
          >
            <Settings className="h-[18px] w-[18px] shrink-0" />
            {!collapsed && '智能体模型'}
          </NavLink>
          <button
            onClick={toggleSidebar}
            className={cn(
              'flex w-full items-center gap-3 rounded-2xl px-3.5 py-3 text-sm font-medium text-slate-500 transition-colors hover:bg-white/8 hover:text-slate-200',
              collapsed && 'justify-center px-0',
            )}
          >
            {collapsed ? <PanelLeft className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
            {!collapsed && '收起边栏'}
          </button>
        </div>
      </div>
    </aside>
  )
}
