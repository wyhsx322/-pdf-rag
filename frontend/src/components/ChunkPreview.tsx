import { FlaskConical } from 'lucide-react'
import type { ChunkResult } from '../types'
import { Badge, Spinner } from './ui'

interface Props {
  chunks: ChunkResult[]
  totalChunks: number
  avgChunkSize: number
  loading: boolean
}

export default function ChunkPreview({ chunks, totalChunks, avgChunkSize, loading }: Props) {
  if (loading) return <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>

  if (chunks.length === 0) {
    return (
      <div className="flex flex-col items-center py-20 text-center">
        <FlaskConical className="mb-3 h-9 w-9 text-slate-300" />
        <p className="text-sm text-slate-400">配置参数后点击「预览切片」查看效果</p>
      </div>
    )
  }

  const figureCount = chunks.filter(c => c.has_figure).length

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {[
          { v: totalChunks, l: '总块数', c: 'text-indigo-600 bg-indigo-50' },
          { v: avgChunkSize, l: '平均字符', c: 'text-emerald-600 bg-emerald-50' },
          { v: figureCount, l: '含图片块', c: 'text-amber-600 bg-amber-50' },
        ].map(s => (
          <div key={s.l} className={`rounded-xl p-3.5 text-center ${s.c}`}>
            <p className="text-xl font-bold">{s.v}</p>
            <p className="mt-0.5 text-xs opacity-70">{s.l}</p>
          </div>
        ))}
      </div>

      <div className="max-h-[560px] space-y-2.5 overflow-y-auto pr-1">
        {chunks.map((chunk, i) => (
          <div key={chunk.chunk_id || i} className="rounded-xl border border-slate-200 p-3.5 transition-colors hover:border-indigo-200">
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <Badge tone="slate" className="font-mono">{chunk.chunk_id || `#${i + 1}`}</Badge>
              {chunk.page > 0 && <Badge tone="blue">第 {chunk.page} 页</Badge>}
              <Badge tone="slate">{chunk.text_length} 字符</Badge>
              {chunk.has_figure && <Badge tone="amber">含图片</Badge>}
            </div>
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-600">{chunk.text}</p>
            {chunk.text_length > 500 && <p className="mt-1 text-xs text-slate-400">（预览前 500 字，完整 {chunk.text_length} 字）</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
