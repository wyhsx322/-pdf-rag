import * as Dropdown from '@radix-ui/react-dropdown-menu'
import { FileText, Loader2, Play, Database, Trash2 } from 'lucide-react'
import type { Document } from '../types'
import { DOC_STATUS_LABELS } from '../types'
import Badge from './ui/Badge'

interface Props {
  doc: Document
  onDelete: (id: number) => void
  onProcess: (id: number) => void
  onViewVectorStats: (id: number) => void
  onDeleteVectors: (id: number) => void
  onReindex: (id: number) => void
  processing: boolean
}

const statusTone: Record<string, 'slate' | 'blue' | 'amber' | 'emerald' | 'rose'> = {
  uploaded: 'slate', parsed: 'blue', chunked: 'amber', indexed: 'emerald', error: 'rose',
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const menuItem = 'flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-slate-600 outline-none data-[highlighted]:bg-slate-100'

export default function DocumentRow({ doc, onDelete, onProcess, onViewVectorStats, onDeleteVectors, onReindex, processing }: Props) {
  const isProcessing = processing || doc.status === 'parsed'

  return (
    <tr className="border-b border-slate-50 transition-colors last:border-0 hover:bg-slate-50/60">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <FileText className="h-4 w-4 shrink-0 text-rose-400" />
          <div className="min-w-0">
            <p className="max-w-[260px] truncate text-sm font-medium text-slate-700" title={doc.original_name}>{doc.original_name}</p>
            <p className="text-xs text-slate-400">{fmtSize(doc.file_size)}</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3"><Badge tone={statusTone[doc.status]}>{DOC_STATUS_LABELS[doc.status]}</Badge></td>
      <td className="px-4 py-3 text-center text-sm text-slate-500">{doc.page_count ? `${doc.page_count} 页` : '—'}</td>
      <td className="px-4 py-3 text-xs text-slate-400">{new Date(doc.created_at).toLocaleString('zh-CN')}</td>
      <td className="px-4 py-3">
        <div className="flex items-center justify-end gap-1">
          {doc.status !== 'indexed' && (
            <button
              onClick={() => onProcess(doc.id)}
              disabled={isProcessing}
              className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-indigo-600 transition-colors hover:bg-indigo-50 disabled:opacity-50"
              title="解析→切片→入库流水线"
            >
              {isProcessing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              {isProcessing ? '处理中' : '处理'}
            </button>
          )}

          {(doc.status === 'indexed' || doc.status === 'chunked') && (
            <Dropdown.Root>
              <Dropdown.Trigger className="rounded-lg p-1.5 text-slate-400 outline-none transition-colors hover:bg-slate-100 hover:text-slate-600" title="向量库操作">
                <Database className="h-4 w-4" />
              </Dropdown.Trigger>
              <Dropdown.Portal>
                <Dropdown.Content align="end" sideOffset={4} className="z-50 w-40 rounded-xl border border-slate-200 bg-white p-1.5 shadow-float">
                  <Dropdown.Item className={menuItem} onSelect={() => onViewVectorStats(doc.id)}>查看向量统计</Dropdown.Item>
                  {doc.status === 'indexed' && (
                    <Dropdown.Item className={menuItem} onSelect={() => onDeleteVectors(doc.id)}>删除向量数据</Dropdown.Item>
                  )}
                  {doc.status === 'chunked' && (
                    <Dropdown.Item className={menuItem} onSelect={() => onReindex(doc.id)}>重新索引</Dropdown.Item>
                  )}
                </Dropdown.Content>
              </Dropdown.Portal>
            </Dropdown.Root>
          )}

          <button onClick={() => onDelete(doc.id)} className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-500" title="删除文档">
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </td>
    </tr>
  )
}
