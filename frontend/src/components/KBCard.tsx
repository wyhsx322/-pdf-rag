import { useNavigate } from 'react-router-dom'
import { Library, FileText, Trash2 } from 'lucide-react'
import type { KnowledgeBase } from '../types'
import { KB_TYPE_LABELS } from '../types'
import Card from './ui/Card'
import Badge from './ui/Badge'

const typeTone: Record<string, 'blue' | 'emerald' | 'violet'> = {
  work: 'blue', study: 'emerald', personal: 'violet',
}

export default function KBCard({ kb, onDelete }: { kb: KnowledgeBase; onDelete: (id: number) => void }) {
  const navigate = useNavigate()
  return (
    <Card hover onClick={() => navigate(`/knowledge/${kb.id}`)} className="group cursor-pointer p-5">
      <div className="mb-4 flex items-start justify-between">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/10 to-violet-500/10 text-indigo-500">
          <Library className="h-5 w-5" />
        </div>
        <button
          onClick={e => { e.stopPropagation(); onDelete(kb.id) }}
          className="rounded-lg p-1.5 text-slate-300 opacity-0 transition-all hover:bg-rose-50 hover:text-rose-500 group-hover:opacity-100"
          title="删除知识库"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      <h3 className="mb-1 truncate font-semibold text-slate-800">{kb.name}</h3>
      <p className={`mb-4 line-clamp-2 text-sm ${kb.description ? 'text-slate-500' : 'italic text-slate-300'}`}>
        {kb.description || '暂无描述'}
      </p>

      <div className="flex items-center justify-between border-t border-slate-100 pt-3">
        <Badge tone={typeTone[kb.type]}>{KB_TYPE_LABELS[kb.type]}</Badge>
        <span className="flex items-center gap-1 text-xs text-slate-400">
          <FileText className="h-3.5 w-3.5" />
          {kb.document_count} 个文档
        </span>
      </div>
    </Card>
  )
}
