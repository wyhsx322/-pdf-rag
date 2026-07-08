import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Search, FolderInput, Trash2, Zap, X, Check, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import type { KnowledgeBaseDetail as KBDetail, ChunkMethod, ChunkResult } from '../types'
import {
  getKB, deleteKB, uploadDocuments, deleteDocument, processDocument, batchImportDocuments,
  getVectorStats, deleteVectors, reindexDocument, previewChunking, executeChunking, batchProcessDocuments,
} from '../api/client'
import type { VectorStats, BatchProgressEvent } from '../api/client'
import { KB_TYPE_LABELS, CHUNK_METHOD_LABELS, DEFAULT_SEPARATORS, DOC_STATUS_LABELS } from '../types'
import UploadZone from '../components/UploadZone'
import DocumentRow from '../components/DocumentRow'
import SeparatorEditor from '../components/SeparatorEditor'
import ChunkPreview from '../components/ChunkPreview'
import { Card, Button, Badge, Input, Select, Switch, Slider, Spinner, Dialog, Tabs } from '../components/ui'
import { cn } from '../lib/cn'

export default function KnowledgeBaseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [kb, setKb] = useState<KBDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [processingId, setProcessingId] = useState<number | null>(null)
  const [tab, setTab] = useState('docs')

  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const [vectorStats, setVectorStats] = useState<VectorStats | null>(null)
  const [vectorStatsLoading, setVectorStatsLoading] = useState(false)
  const [vectorOpen, setVectorOpen] = useState(false)

  // 批量处理
  const [batchIds, setBatchIds] = useState<Set<number>>(new Set())
  const [batchProgress, setBatchProgress] = useState<Map<number, BatchProgressEvent>>(new Map())
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchCtl, setBatchCtl] = useState<AbortController | null>(null)

  // 切分配置
  const [method, setMethod] = useState<ChunkMethod>('recursive')
  const [chunkSize, setChunkSize] = useState(1000)
  const [chunkOverlap, setChunkOverlap] = useState(200)
  const [separators, setSeparators] = useState<string[]>([...DEFAULT_SEPARATORS.recursive])
  const [preserveImages, setPreserveImages] = useState(true)
  const [preserveTables, setPreserveTables] = useState(true)
  const [targetDocId, setTargetDocId] = useState<number | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewChunks, setPreviewChunks] = useState<ChunkResult[]>([])
  const [totalChunks, setTotalChunks] = useState(0)
  const [avgChunkSize, setAvgChunkSize] = useState(0)
  const [executing, setExecuting] = useState(false)

  const fetchKB = useCallback(async () => {
    if (!id) return
    try { setKb(await getKB(Number(id))) }
    catch { toast.error('无法加载知识库详情') }
    finally { setLoading(false) }
  }, [id])

  useEffect(() => { fetchKB() }, [fetchKB])

  const filteredDocs = useMemo(() => {
    if (!kb) return []
    let docs = kb.documents
    if (searchText) {
      const s = searchText.toLowerCase()
      docs = docs.filter(d => d.original_name.toLowerCase().includes(s))
    }
    if (statusFilter !== 'all') docs = docs.filter(d => d.status === statusFilter)
    return docs
  }, [kb, searchText, statusFilter])

  const errMsg = (err: unknown, fallback: string) =>
    (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback

  // ── 文档操作 ──
  const handleUpload = async (files: File[]) => {
    if (!id) return
    setUploading(true)
    try { await uploadDocuments(Number(id), files); await fetchKB(); toast.success(`已上传 ${files.length} 个文件`) }
    catch (err) { toast.error(errMsg(err, '上传失败')) }
    finally { setUploading(false) }
  }

  const handleDeleteDoc = async (docId: number) => {
    if (!confirm('确定删除该文档？相关处理产物也将删除。')) return
    try { await deleteDocument(docId); await fetchKB(); toast.success('已删除') }
    catch { toast.error('删除失败') }
  }

  const handleProcess = async (docId: number) => {
    const doc = kb?.documents.find(d => d.id === docId)
    if (doc && doc.status !== 'uploaded' &&
      !confirm(`该文档已有处理产物（${DOC_STATUS_LABELS[doc.status]}），再次处理将覆盖。是否继续？`)) return
    setProcessingId(docId)
    try { await processDocument(docId); await fetchKB(); toast.success('处理完成') }
    catch (err) { toast.error(errMsg(err, '处理失败')) }
    finally { setProcessingId(null) }
  }

  const handleDeleteKB = async () => {
    if (!kb || !confirm(`确定删除知识库「${kb.name}」及其所有文档？不可恢复。`)) return
    try { await deleteKB(kb.id); toast.success('已删除'); navigate('/knowledge') }
    catch { toast.error('删除失败') }
  }

  const handleBatchImport = async () => {
    if (!id) return
    try {
      const imported = await batchImportDocuments(Number(id))
      if (imported.length === 0) toast.info('没有找到新的 PDF 文件')
      else { await fetchKB(); toast.success(`导入 ${imported.length} 个文档`) }
    } catch (err) { toast.error(errMsg(err, '批量导入失败')) }
  }

  const handleViewVectorStats = async (docId: number) => {
    setVectorOpen(true); setVectorStatsLoading(true); setVectorStats(null)
    try { setVectorStats(await getVectorStats(docId)) }
    catch (err) { toast.error(errMsg(err, '获取向量统计失败')); setVectorOpen(false) }
    finally { setVectorStatsLoading(false) }
  }

  const handleDeleteVectors = async (docId: number) => {
    if (!confirm('确定删除该文档的向量数据？产物文件保留，可重新索引。')) return
    try { await deleteVectors(docId); await fetchKB(); toast.success('向量数据已删除') }
    catch (err) { toast.error(errMsg(err, '删除失败')) }
  }

  const handleReindex = async (docId: number) => {
    if (!confirm('确定重新索引该文档？将重新生成向量并入库。')) return
    try { await reindexDocument(docId); await fetchKB(); toast.success('重新索引完成') }
    catch (err) { toast.error(errMsg(err, '重新索引失败')) }
  }

  // ── 批量处理 ──
  const toggleBatch = (docId: number) => setBatchIds(prev => {
    const next = new Set(prev)
    next.has(docId) ? next.delete(docId) : next.add(docId)
    return next
  })

  const runBatch = () => {
    if (!id || batchIds.size === 0) { toast.warning('请先勾选要处理的文档'); return }
    setBatchRunning(true); setBatchProgress(new Map())
    const ctl = batchProcessDocuments(
      Number(id), Array.from(batchIds),
      (e) => setBatchProgress(prev => new Map(prev).set(e.doc_id, e)),
      (total) => { setBatchRunning(false); setBatchCtl(null); fetchKB(); toast.success(`批量处理完成，共 ${total} 个`) },
      (error) => { setBatchRunning(false); setBatchCtl(null); toast.error(`批量处理出错：${error}`) },
    )
    setBatchCtl(ctl)
  }

  // ── 切分 ──
  const onMethodChange = (m: ChunkMethod) => { setMethod(m); setSeparators([...DEFAULT_SEPARATORS[m]]) }

  const handlePreview = async () => {
    setPreviewLoading(true)
    try {
      const sample = `--- PAGE 1 ---\n## 摘要\n\n本文提出了一种基于深度学习的方法，结合 Transformer 与图神经网络，在多个基准上取得优异性能。\n\n## 1. 引言\n\n自然语言处理是人工智能的重要方向。近年来深度学习推动了该领域发展，Transformer 架构尤为关键。\n\n然而现有方法仍有局限：需要大量标注数据；对长文本处理不佳；缺乏结构建模能力。`
      const r = await previewChunking({ text: sample, method, chunk_size: chunkSize, chunk_overlap: chunkOverlap, separators, preserve_images: preserveImages, preserve_tables: preserveTables })
      setPreviewChunks(r.chunks); setTotalChunks(r.total_chunks); setAvgChunkSize(r.avg_chunk_size)
    } catch (err) { toast.error(errMsg(err, '预览失败')) }
    finally { setPreviewLoading(false) }
  }

  const handleExecute = async () => {
    if (!targetDocId) { toast.warning('请先选择目标文档'); return }
    const doc = kb?.documents.find(d => d.id === targetDocId)
    if (doc && (doc.status === 'chunked' || doc.status === 'indexed') &&
      !confirm(`该文档已有切片数据（${DOC_STATUS_LABELS[doc.status]}），再次执行将覆盖。是否继续？`)) return
    setExecuting(true)
    try {
      await executeChunking(targetDocId, { method, chunk_size: chunkSize, chunk_overlap: chunkOverlap, separators, preserve_images: preserveImages, preserve_tables: preserveTables })
      await fetchKB(); toast.success('切片执行成功')
    } catch (err) { toast.error(errMsg(err, '切片执行失败')) }
    finally { setExecuting(false) }
  }

  if (loading) return <div className="flex h-full items-center justify-center"><Spinner className="h-7 w-7" /></div>
  if (!kb) return (
    <div className="flex h-full flex-col items-center justify-center gap-3">
      <p className="text-sm text-slate-400">知识库不存在</p>
      <Button variant="outline" onClick={() => navigate('/knowledge')}>返回列表</Button>
    </div>
  )

  const docOptions = kb.documents.map(d => ({ value: String(d.id), label: `${d.original_name}（${DOC_STATUS_LABELS[d.status]}）` }))

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl px-8 py-7">
        {/* 头部 */}
        <div className="mb-6 flex items-center gap-3">
          <button onClick={() => navigate('/knowledge')} className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="min-w-0">
            <h2 className="flex items-center gap-2.5 text-xl font-semibold text-slate-800">
              <span className="truncate">{kb.name}</span>
              <Badge tone="indigo">{KB_TYPE_LABELS[kb.type]}</Badge>
            </h2>
            {kb.description && <p className="mt-0.5 truncate text-sm text-slate-400">{kb.description}</p>}
          </div>
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={handleBatchImport}><FolderInput className="h-4 w-4" />批量导入</Button>
          <Button variant="outline" size="sm" onClick={handleDeleteKB} className="text-rose-500 hover:border-rose-300 hover:bg-rose-50"><Trash2 className="h-4 w-4" />删除</Button>
        </div>

        <Tabs value={tab} onValueChange={setTab} items={[{ value: 'docs', label: '文档管理' }, { value: 'chunk', label: '切分策略' }]} className="mb-6" />

        {tab === 'docs' ? (
          <div className="space-y-6">
            <UploadZone onUpload={handleUpload} uploading={uploading} />

            {/* 批量处理流水线 */}
            {kb.documents.length > 0 && (
              <Card className="p-5">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-700">批量处理流水线</h3>
                    <p className="text-xs text-slate-400">PDF 解析 → 图片摘要 → 切片 → 向量化入库</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {batchRunning ? (
                      <Button size="sm" variant="danger" onClick={() => { batchCtl?.abort(); setBatchRunning(false); setBatchCtl(null) }}>取消</Button>
                    ) : (
                      <>
                        <Button size="sm" variant="ghost" onClick={() => setBatchIds(new Set(kb.documents.map(d => d.id)))}>全选</Button>
                        <Button size="sm" variant="ghost" onClick={() => setBatchIds(new Set())}>清空</Button>
                        <Button size="sm" onClick={runBatch} disabled={batchIds.size === 0}><Zap className="h-3.5 w-3.5" />一键处理 ({batchIds.size})</Button>
                      </>
                    )}
                  </div>
                </div>
                <div className="max-h-52 space-y-0.5 overflow-y-auto">
                  {kb.documents.map(doc => {
                    const p = batchProgress.get(doc.id)
                    const running = batchRunning && batchIds.has(doc.id) && (!p || p.status === 'processing')
                    return (
                      <label key={doc.id} className={cn('flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors', !batchRunning && 'cursor-pointer hover:bg-slate-50')}>
                        <input type="checkbox" checked={batchIds.has(doc.id)} onChange={() => toggleBatch(doc.id)} disabled={batchRunning}
                          className="h-3.5 w-3.5 shrink-0 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 disabled:opacity-50" />
                        <span className="min-w-0 flex-1 truncate text-xs text-slate-600">{doc.original_name}</span>
                        <Badge tone={doc.status === 'indexed' ? 'emerald' : doc.status === 'error' ? 'rose' : 'slate'}>{DOC_STATUS_LABELS[doc.status]}</Badge>
                        {running && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-indigo-500" />}
                        {p?.status === 'done' && <Check className="h-3.5 w-3.5 shrink-0 text-emerald-500" />}
                        {p?.status === 'error' && <X className="h-3.5 w-3.5 shrink-0 text-rose-500" />}
                      </label>
                    )
                  })}
                </div>
              </Card>
            )}

            {/* 文档表 */}
            <Card className="overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
                <h3 className="text-sm font-semibold text-slate-700">
                  文档列表 <span className="ml-1 font-normal text-slate-400">({filteredDocs.length}{filteredDocs.length !== kb.documents.length ? ` / ${kb.documents.length}` : ''})</span>
                </h3>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                    <Input value={searchText} onChange={e => setSearchText(e.target.value)} placeholder="搜索文件名…" className="h-9 w-48 pl-8 text-xs" />
                  </div>
                  <Select value={statusFilter} onValueChange={setStatusFilter} className="h-9 w-32 text-xs" placeholder="全部状态"
                    options={[{ value: 'all', label: '全部状态' }, { value: 'uploaded', label: '已上传' }, { value: 'parsed', label: '已解析' }, { value: 'chunked', label: '已切片' }, { value: 'indexed', label: '已入库' }, { value: 'error', label: '异常' }]} />
                </div>
              </div>

              {filteredDocs.length === 0 ? (
                <div className="py-16 text-center text-sm text-slate-400">{kb.documents.length === 0 ? '暂无文档，请上传 PDF 文件' : '没有匹配的文档'}</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50/50 text-left text-xs font-medium uppercase tracking-wider text-slate-400">
                        <th className="px-4 py-2.5">文件名</th>
                        <th className="px-4 py-2.5">状态</th>
                        <th className="px-4 py-2.5 text-center">页数</th>
                        <th className="px-4 py-2.5">上传时间</th>
                        <th className="px-4 py-2.5 text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDocs.map(doc => (
                        <DocumentRow key={doc.id} doc={doc} onDelete={handleDeleteDoc} onProcess={handleProcess}
                          onViewVectorStats={handleViewVectorStats} onDeleteVectors={handleDeleteVectors} onReindex={handleReindex}
                          processing={processingId === doc.id} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        ) : (
          /* 切分策略 */
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="space-y-5">
              <Card className="p-5">
                <h3 className="mb-3 text-sm font-semibold text-slate-700">切片方式</h3>
                <div className="grid grid-cols-2 gap-2">
                  {(Object.keys(CHUNK_METHOD_LABELS) as ChunkMethod[]).map(m => (
                    <button key={m} onClick={() => onMethodChange(m)}
                      className={cn('rounded-xl py-2.5 text-sm font-medium transition-all',
                        method === m ? 'bg-gradient-to-r from-indigo-500 to-violet-500 text-white shadow-soft' : 'border border-slate-200 text-slate-500 hover:border-slate-300')}>
                      {CHUNK_METHOD_LABELS[m]}
                    </button>
                  ))}
                </div>
              </Card>

              <Card className="space-y-5 p-5">
                <h3 className="text-sm font-semibold text-slate-700">参数设置</h3>
                <div>
                  <div className="mb-2 flex justify-between text-xs"><span className="font-medium text-slate-500">Chunk 大小</span><span className="font-mono font-bold text-indigo-600">{chunkSize}</span></div>
                  <Slider value={chunkSize} onValueChange={v => { setChunkSize(v); if (chunkOverlap >= v) setChunkOverlap(Math.floor(v * 0.2)) }} min={100} max={3000} step={50} />
                </div>
                <div>
                  <div className="mb-2 flex justify-between text-xs"><span className="font-medium text-slate-500">重叠大小</span><span className="font-mono font-bold text-indigo-600">{chunkOverlap}</span></div>
                  <Slider value={chunkOverlap} onValueChange={setChunkOverlap} min={0} max={Math.min(800, chunkSize - 50)} step={10} />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-slate-500">分隔符（按优先级，越靠上越优先）</label>
                  <SeparatorEditor separators={separators} onChange={setSeparators} />
                </div>
              </Card>

              <Card className="space-y-3 p-5">
                <h3 className="text-sm font-semibold text-slate-700">上下文保留</h3>
                <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3.5 py-2.5">
                  <div><p className="text-sm font-medium text-slate-700">保留图片上下文</p><p className="text-xs text-slate-400">将 ![]() 替换为 [图N: 标题]</p></div>
                  <Switch checked={preserveImages} onCheckedChange={setPreserveImages} />
                </div>
                <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3.5 py-2.5">
                  <div><p className="text-sm font-medium text-slate-700">保留表格上下文</p><p className="text-xs text-slate-400">表格作为完整单元不被分割</p></div>
                  <Switch checked={preserveTables} onCheckedChange={setPreserveTables} />
                </div>
              </Card>

              <Card className="space-y-3 p-5">
                <label className="block text-xs font-medium text-slate-500">执行目标文档（需已解析）</label>
                <Select value={targetDocId ? String(targetDocId) : ''} onValueChange={v => setTargetDocId(Number(v) || null)} options={docOptions} placeholder="选择要切片的文档…" className="w-full" />
                <div className="flex gap-3">
                  <Button className="flex-1" variant="outline" onClick={handlePreview} loading={previewLoading}>预览切片</Button>
                  <Button className="flex-1" onClick={handleExecute} loading={executing} disabled={!targetDocId}>执行切片</Button>
                </div>
              </Card>
            </div>

            <Card className="p-5">
              <h3 className="mb-4 text-sm font-semibold text-slate-700">切片预览{totalChunks > 0 && <span className="ml-2 font-normal text-slate-400">({totalChunks} 块)</span>}</h3>
              <ChunkPreview chunks={previewChunks} totalChunks={totalChunks} avgChunkSize={avgChunkSize} loading={previewLoading} />
            </Card>
          </div>
        )}
      </div>

      {/* 向量统计弹窗 */}
      <Dialog open={vectorOpen} onOpenChange={setVectorOpen} title="向量库统计">
        {vectorStatsLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : vectorStats ? (
          <div className="space-y-2.5 text-sm">
            {[
              ['文档', vectorStats.original_name],
              ['Collection', vectorStats.collection_name],
              ['集合状态', vectorStats.collection_exists ? '存在' : '不存在'],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-slate-100 py-2">
                <span className="text-slate-400">{k}</span><span className="max-w-[60%] truncate font-medium text-slate-700">{v}</span>
              </div>
            ))}
            <div className="flex justify-between py-1"><span className="text-slate-400">向量数量</span><span className="text-base font-bold text-indigo-600">{vectorStats.vector_count}</span></div>
          </div>
        ) : null}
      </Dialog>
    </div>
  )
}
