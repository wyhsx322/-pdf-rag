import { useState, useEffect, useRef } from 'react'
import { Search as SearchIcon, FlaskConical, ChevronDown, Gauge, AlertTriangle, Lightbulb, SlidersHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import type { KnowledgeBase } from '../../entities/knowledge-base/model'
import type { SearchResultItem } from '../../entities/retrieval/model'
import { listKBs } from '../../entities/knowledge-base/api'
import { hybridSearch, type SearchResponse, type SearchDiagnostics } from './api'
import { useAppStore } from '../../shared/state/useAppStore'
import { Card, Badge, Button, Select, Switch, Slider, Spinner } from '../../shared/ui'
import { cn } from '../../shared/lib/cn'

interface RagSearchPanelProps {
  embedded?: boolean
  initialKbId?: number | null
}

export default function RagSearchPanel({ embedded, initialKbId }: RagSearchPanelProps) {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [mode, setMode] = useState('')
  const [total, setTotal] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const [diagnostics, setDiagnostics] = useState<SearchDiagnostics | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const selectedKbId = useAppStore(s => s.selectedKbId)
  const setSelectedKbId = useAppStore(s => s.setSelectedKbId)
  const topK = useAppStore(s => s.searchTopK)
  const rewrite = useAppStore(s => s.searchRewrite)
  const hyde = useAppStore(s => s.searchHyde)
  const reranker = useAppStore(s => s.searchReranker)
  const setSearch = useAppStore(s => s.setSearch)

  useEffect(() => { listKBs().then(setKbs).catch(() => {}) }, [])
  useEffect(() => {
    if (initialKbId && selectedKbId !== initialKbId) setSelectedKbId(initialKbId)
  }, [initialKbId, selectedKbId, setSelectedKbId])

  const handleSearch = async () => {
    if (!query.trim()) return
    if (!selectedKbId) { toast.warning('请先选择知识库'); return }
    setLoading(true); setExpanded(null)
    try {
      const data: SearchResponse = await hybridSearch(selectedKbId, query.trim(), topK, reranker, rewrite, hyde)
      setResults(data.results); setMode(data.search_mode); setTotal(data.total_results); setElapsed(data.elapsed_seconds)
      setDiagnostics(data.diagnostics)
      if (data.total_results === 0) toast.info('未召回结果，请确认该知识库已有入库文档')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || '检索失败，请检查后端服务')
    } finally {
      setLoading(false)
    }
  }

  const highlight = (text: string) => {
    if (!query.trim()) return text
    let r = text
    for (const w of query.split(/\s+/).filter(Boolean)) {
      const esc = w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      r = r.replace(new RegExp(`(${esc})`, 'gi'), '<mark class="rounded bg-cyan-200/70 px-0.5">$1</mark>')
    }
    return r
  }

  const kbOptions = kbs.map(kb => ({ value: String(kb.id), label: kb.name }))
  const confidenceTone = diagnostics?.confidence === 'high' ? 'emerald' : diagnostics?.confidence === 'medium' ? 'amber' : 'rose'
  const confidenceLabel = diagnostics?.confidence === 'high' ? '高' : diagnostics?.confidence === 'medium' ? '中' : '低'

  return (
    <div className={cn(!embedded && 'h-full overflow-y-auto')}>
      <div className={cn(!embedded && 'mx-auto max-w-7xl px-10 py-10')}>
        {!embedded && (
          <header className="mb-8">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.28em] text-indigo-500">RAG Fusion Lab</p>
            <h2 className="text-3xl font-semibold tracking-tight text-slate-950">RAG 混合检索</h2>
            <p className="mt-2 text-sm text-slate-500">向量语义 + BM25 关键词 · RRF 融合 · 可选查询改写 / HyDE / 重排序</p>
          </header>
        )}

        <Card className="mb-6 overflow-hidden">
          <div className="border-b border-slate-100 bg-slate-950 px-6 py-5 text-white">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <SlidersHorizontal className="h-4 w-4 text-cyan-200" />
                  检索控制台
                </div>
                <p className="mt-1 text-xs text-slate-400">测试召回质量、证据覆盖与重排序表现</p>
              </div>
              {mode && !loading && (
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-300">
                  <Badge tone="indigo">{mode}</Badge>
                  <span>共 {total} 条 · 耗时 {elapsed}s</span>
                </div>
              )}
            </div>
          </div>
          <div className="space-y-5 p-6">
            <div className="grid gap-3 lg:grid-cols-[220px_1fr_auto]">
              <Select value={selectedKbId ? String(selectedKbId) : ''} onValueChange={v => setSelectedKbId(Number(v) || null)} options={kbOptions} placeholder="选择知识库…" />
              <div className="relative">
                <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSearch()}
                  placeholder="输入研究问题、关键词或短语，观察混合召回效果…"
                  className="h-11 w-full rounded-2xl border border-slate-200 bg-white/80 pl-11 pr-4 text-sm text-slate-800 outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/15"
                />
              </div>
              <Button onClick={handleSearch} loading={loading} className="px-7">检索</Button>
            </div>

            <div className="grid gap-4 border-t border-slate-100 pt-5 xl:grid-cols-[260px_1fr]">
              <div className="flex items-center gap-3">
                <span className="shrink-0 text-xs text-slate-500">返回数量</span>
                <div className="min-w-0 flex-1"><Slider value={topK} onValueChange={v => setSearch({ searchTopK: v })} min={5} max={30} step={5} /></div>
                <span className="w-7 text-xs font-semibold text-indigo-600">{topK}</span>
              </div>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                <Switch checked={rewrite} onCheckedChange={v => setSearch({ searchRewrite: v })} label="查询改写" />
                <Switch checked={hyde} onCheckedChange={v => setSearch({ searchHyde: v })} label="HyDE 增强" />
                <Switch checked={reranker} onCheckedChange={v => setSearch({ searchReranker: v })} label="BGE 重排序" />
              </div>
            </div>
          </div>
        </Card>

        {diagnostics && !loading && (
          <Card className="mb-6 p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <Gauge className="h-4 w-4 text-indigo-500" />
                检索质量诊断
              </div>
              <Badge tone={confidenceTone}>可信度 {confidenceLabel}</Badge>
            </div>

            <div className="grid gap-3 md:grid-cols-4">
              <Metric label="文档覆盖" value={`${diagnostics.unique_sources} 篇`} hint={diagnostics.top_source ? `最高占比 ${(diagnostics.top_source_share * 100).toFixed(0)}%` : '暂无'} />
              <Metric label="图表证据" value={`${diagnostics.figure_results} 条`} hint="参与召回的图表摘要" />
              <Metric label="平均片段" value={`${diagnostics.avg_text_chars} 字`} hint="观察切片粒度" />
              <Metric label="分数区分" value={diagnostics.score_spread.toFixed(4)} hint={`RRF 最高 ${diagnostics.best_rrf_score.toFixed(4)}`} />
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <Signal title="风险信号" icon={AlertTriangle} tone="rose" items={diagnostics.risks} />
              <Signal title="优化建议" icon={Lightbulb} tone="emerald" items={diagnostics.recommendations} />
            </div>
          </Card>
        )}

        {loading ? (
          <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>
        ) : results.length > 0 ? (
          <div className="grid gap-4">
            {results.map((item, idx) => (
              <Card key={item.chunk_id} hover className="overflow-hidden">
                <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 bg-white/60 px-5 py-3">
                  <Badge tone="indigo" className="font-bold">#{item.rank}</Badge>
                  <span className="font-mono text-xs text-slate-400">{item.chunk_id}</span>
                  <span className="text-xs text-slate-500">{item.source}.pdf</span>
                  {item.page && <span className="text-xs text-slate-400">· 第 {item.page} 页</span>}
                  {item.is_figure && <Badge tone="amber">图片{item.figure_type ? ` · ${item.figure_type}` : ''}</Badge>}
                  <div className="flex-1" />
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="text-blue-600">向量 {item.vector_score.toFixed(3)}</span>
                    <span className="text-emerald-600">BM25 {item.bm25_score.toFixed(3)}</span>
                    <span className="font-medium text-violet-600">RRF {item.rrf_score.toFixed(3)}</span>
                    {item.rerank_score != null && <span className="font-semibold text-amber-600">Rerank {item.rerank_score.toFixed(3)}</span>}
                  </div>
                </div>
                <div className="px-5 py-4">
                  <p
                    className={cn('whitespace-pre-wrap text-sm leading-7 text-slate-700', expanded !== idx && 'line-clamp-4')}
                    dangerouslySetInnerHTML={{ __html: highlight(expanded === idx ? item.text : item.text.slice(0, 400)) }}
                  />
                  {item.text.length > 400 && (
                    <button onClick={() => setExpanded(expanded === idx ? null : idx)} className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700">
                      <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', expanded === idx && 'rotate-180')} />
                      {expanded === idx ? '收起' : `展开全文（${item.text.length} 字）`}
                    </button>
                  )}
                  {item.is_figure && item.image_file && (
                    <div className="mt-4 flex flex-wrap items-start gap-4 rounded-2xl border border-slate-100 bg-slate-50/70 p-3">
                      <img src={`/api/images/${item.source}/${item.image_file}`} alt={item.caption || '论文图片'} className="max-h-56 max-w-sm rounded-xl border border-slate-200 bg-white object-contain" loading="lazy" />
                      <div className="space-y-1 text-xs text-slate-500">
                        {item.caption && <p className="font-medium text-slate-700">{item.caption}</p>}
                        {item.page && <p>第 {item.page} 页</p>}
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center py-20 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/80 bg-white/70 shadow-soft">
              <FlaskConical className="h-7 w-7 text-slate-300" />
            </div>
            <p className="text-sm text-slate-400">选择知识库并输入查询词，观察混合检索的召回与各路得分</p>
          </div>
        )}
      </div>
    </div>
  )
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50/70 px-4 py-3">
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className="mt-1 text-base font-semibold text-slate-900">{value}</div>
      <div className="mt-1 truncate text-[11px] text-slate-400">{hint}</div>
    </div>
  )
}

function Signal({ title, icon: Icon, tone, items }: { title: string; icon: typeof AlertTriangle; tone: 'rose' | 'emerald'; items: string[] }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white/70 p-4">
      <div className={cn('mb-3 flex items-center gap-1.5 text-xs font-semibold', tone === 'rose' ? 'text-rose-600' : 'text-emerald-600')}>
        <Icon className="h-3.5 w-3.5" />
        {title}
      </div>
      <ul className="space-y-1.5 text-xs leading-relaxed text-slate-600">
        {items.map(item => <li key={item}>· {item}</li>)}
      </ul>
    </div>
  )
}
