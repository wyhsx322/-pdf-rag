import { useNavigate } from 'react-router-dom'
import { Library, FileText, Trash2 } from 'lucide-react'
import type { KnowledgeBase } from '../../entities/knowledge-base/model'
import { KB_TYPE_LABELS } from '../../entities/knowledge-base/model'
import Card from '../../shared/ui/Card'
import Badge from '../../shared/ui/Badge'

const typeTone: Record<string, 'blue' | 'emerald' | 'violet'> = {
  work: 'blue', study: 'emerald', personal: 'violet',
}

export default function KBCard({ kb, onDelete }: { kb: KnowledgeBase; onDelete: (id: number) => void }) {
  const navigate = useNavigate()
  return (
    <Card hover onClick={() => navigate(`/knowledge/${kb.id}`)} className="group cursor-pointer p-6">
      <div className="mb-5 flex items-start justify-between">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-cyan-200 shadow-glow">
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

      <h3 className="mb-2 truncate text-base font-semibold text-slate-950">{kb.name}</h3>
      <p className={`mb-5 line-clamp-2 min-h-12 text-sm leading-6 ${kb.description ? 'text-slate-500' : 'italic text-slate-300'}`}>
        {kb.description || '暂无描述'}
      </p>

      <div className="flex items-center justify-between border-t border-slate-100 pt-4">
        <Badge tone={typeTone[kb.type]}>{KB_TYPE_LABELS[kb.type]}</Badge>
        <span className="flex items-center gap-1 text-xs text-slate-400">
          <FileText className="h-3.5 w-3.5" />
          {kb.document_count} 个文档
        </span>
      </div>
    </Card>
  )
}
