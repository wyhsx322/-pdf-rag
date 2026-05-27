import { useNavigate } from 'react-router-dom'
import type { KnowledgeBase } from '../types'
import { KB_TYPE_LABELS, KB_TYPE_ICONS } from '../types'

interface KBCardProps {
  kb: KnowledgeBase
  onDelete: (id: number) => void
}

export default function KBCard({ kb, onDelete }: KBCardProps) {
  const navigate = useNavigate()

  const typeColors: Record<string, string> = {
    work: 'bg-blue-50 text-blue-700 border-blue-200',
    study: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    personal: 'bg-purple-50 text-purple-700 border-purple-200',
  }

  return (
    <div
      onClick={() => navigate(`/kb/${kb.id}`)}
      className="group bg-white rounded-xl border border-gray-200 p-6 cursor-pointer
        shadow-sm hover:shadow-md hover:border-indigo-300 transition-all duration-200
        hover:-translate-y-0.5"
    >
      <div className="flex items-start justify-between mb-4">
        <span className="text-3xl">{KB_TYPE_ICONS[kb.type]}</span>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDelete(kb.id)
          }}
          className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-gray-400
            hover:text-red-500 hover:bg-red-50 transition-all duration-150"
          title="删除知识库"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>

      <h3 className="font-semibold text-gray-900 mb-1.5 truncate">{kb.name}</h3>

      {kb.description ? (
        <p className="text-sm text-gray-500 mb-3 line-clamp-2">{kb.description}</p>
      ) : (
        <p className="text-sm text-gray-400 mb-3 italic">暂无描述</p>
      )}

      <div className="flex items-center justify-between">
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${typeColors[kb.type]}`}>
          {KB_TYPE_LABELS[kb.type]}
        </span>
        <span className="text-xs text-gray-400">
          {kb.document_count} 个文档
        </span>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">
          创建于 {new Date(kb.created_at).toLocaleDateString('zh-CN')}
        </span>
      </div>
    </div>
  )
}
