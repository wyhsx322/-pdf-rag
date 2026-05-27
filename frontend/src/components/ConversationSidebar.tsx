import { useState } from 'react'
import type { Conversation } from '../types'

interface Props {
  conversations: Conversation[]
  currentConvId: number | null
  loading: boolean
  collapsed: boolean
  onToggleCollapse: () => void
  onSelect: (convId: number) => void
  onDelete: (convId: number) => void
  onNew: () => void
}

export default function ConversationSidebar({
  conversations,
  currentConvId,
  loading,
  collapsed,
  onToggleCollapse,
  onSelect,
  onDelete,
  onNew,
}: Props) {
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const handleDelete = async (e: React.MouseEvent, convId: number) => {
    e.stopPropagation()
    if (!confirm('确定要删除这个对话吗？')) return
    setDeletingId(convId)
    await onDelete(convId)
    setDeletingId(null)
  }

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso)
      const now = new Date()
      const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24))
      if (diffDays === 0) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      if (diffDays === 1) return '昨天'
      if (diffDays < 7) return `${diffDays} 天前`
      return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    } catch {
      return ''
    }
  }

  return (
    <div className={`${collapsed ? 'w-12' : 'w-64'} flex flex-col border-r border-gray-200 bg-gray-50 shrink-0 transition-all duration-200`}>
      {/* 头部 */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-gray-200">
        {!collapsed && (
          <span className="text-sm font-medium text-gray-700">历史对话</span>
        )}
        <div className="flex items-center gap-1">
          {!collapsed && (
            <button
              onClick={onNew}
              disabled={loading}
              className="p-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 disabled:opacity-50 transition-colors"
              title="新对话"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>
          )}
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-colors"
            title={collapsed ? '展开' : '收起'}
          >
            <svg className={`w-4 h-4 transition-transform ${collapsed ? '' : 'rotate-180'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* 对话列表 */}
      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          !collapsed && (
            <div className="px-3 py-8 text-center text-xs text-gray-400">
              暂无历史对话
              <br />
              选择知识库并发送问题后自动保存
            </div>
          )
        ) : (
          conversations.map(conv => (
            <button
              key={conv.id}
              onClick={() => onSelect(conv.id)}
              disabled={deletingId === conv.id}
              className={`w-full text-left px-3 py-2.5 border-b border-gray-100 transition-colors
                ${conv.id === currentConvId
                  ? 'bg-indigo-50 border-l-2 border-l-indigo-500'
                  : 'hover:bg-gray-100 border-l-2 border-l-transparent'
                }
                ${deletingId === conv.id ? 'opacity-50' : ''}
              `}
            >
              {collapsed ? (
                <div className="flex justify-center">
                  <span className="text-xs text-gray-500">{conv.message_count}</span>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-1">
                    <span className="text-sm text-gray-800 truncate flex-1 leading-snug">
                      {conv.title || '新对话'}
                    </span>
                    <span
                      onClick={e => handleDelete(e, conv.id)}
                      className="text-gray-300 hover:text-red-500 transition-colors shrink-0 p-0.5"
                      title="删除"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-gray-400">{formatDate(conv.updated_at)}</span>
                    <span className="text-xs text-gray-300">{conv.message_count} 条消息</span>
                  </div>
                </>
              )}
            </button>
          ))
        )}
      </div>
    </div>
  )
}
