import { useState, useEffect, useCallback } from 'react'
import type { Document, ChunkMethod, ChunkResult } from '../types'
import { CHUNK_METHOD_LABELS, DEFAULT_SEPARATORS, DOC_STATUS_LABELS } from '../types'
import { listKBs, getKB, previewChunking, executeChunking, batchProcessDocuments } from '../api/client'
import type { BatchProgressEvent } from '../api/client'
import SeparatorEditor from '../components/SeparatorEditor'
import ChunkPreviewComp from '../components/ChunkPreview'
import { useStickyState } from '../hooks/useStickyState'

export default function SmartChunking() {
  // 文档选择
  const [kbs, setKbs] = useState<{ id: number; name: string }[]>([])
  const [selectedKbId, setSelectedKbId] = useStickyState<number | null>('chunking:selectedKbId', null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedDocId, setSelectedDocId] = useStickyState<number | null>('chunking:selectedDocId', null)
  const [loadingDocs, setLoadingDocs] = useState(false)

  // 切片配置
  const [method, setMethod] = useStickyState<ChunkMethod>('chunking:method', 'recursive')
  const [chunkSize, setChunkSize] = useStickyState('chunking:chunkSize', 1000)
  const [chunkOverlap, setChunkOverlap] = useStickyState('chunking:chunkOverlap', 200)
  const [separators, setSeparators] = useStickyState<string[]>('chunking:separators', [...DEFAULT_SEPARATORS.recursive])
  const [preserveImages, setPreserveImages] = useStickyState('chunking:preserveImages', true)
  const [preserveTables, setPreserveTables] = useStickyState('chunking:preserveTables', true)

  // 预览状态
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewChunks, setPreviewChunks] = useStickyState<ChunkResult[]>('chunking:previewChunks', [])
  const [totalChunks, setTotalChunks] = useStickyState('chunking:totalChunks', 0)
  const [avgChunkSize, setAvgChunkSize] = useStickyState('chunking:avgChunkSize', 0)
  const [sampleText, setSampleText] = useStickyState('chunking:sampleText', '')
  const [useCustomText, setUseCustomText] = useStickyState('chunking:useCustomText', false)

  // 执行状态
  const [executing, setExecuting] = useState(false)

  // 批量处理状态
  const [batchDocIds, setBatchDocIds] = useStickyState<Set<number>>('chunking:batchDocIds', new Set())
  const [batchProgress, setBatchProgress] = useStickyState<Map<number, BatchProgressEvent>>('chunking:batchProgress', new Map())
  const [batchRunning, setBatchRunning] = useState(false)
  const [batchController, setBatchController] = useState<AbortController | null>(null)

  // 加载知识库列表
  useEffect(() => {
    listKBs().then(data => setKbs(data.map(k => ({ id: k.id, name: k.name })))).catch(() => {})
  }, [])

  // 当选择知识库后，加载其文档列表
  const loadDocuments = useCallback(async (kbId: number) => {
    setLoadingDocs(true)
    try {
      const data = await getKB(kbId)
      setDocuments(data.documents)
    } catch { /* ignore */ }
    finally { setLoadingDocs(false) }
  }, [])

  // 知识库变化时加载文档（包括页面切换回来恢复选中状态时）
  useEffect(() => {
    if (selectedKbId) {
      loadDocuments(selectedKbId)
    } else {
      setDocuments([])
      setSelectedDocId(null)
    }
  }, [selectedKbId, loadDocuments])

  // 切换切片方式时，更新默认分隔符
  const handleMethodChange = (newMethod: ChunkMethod) => {
    setMethod(newMethod)
    setSeparators([...DEFAULT_SEPARATORS[newMethod]])
  }

  // 加载示例文本（从已处理的文档中获取）
  const loadSampleText = useCallback(async () => {
    if (useCustomText) return  // 使用自定义文本时不需要加载
    if (!sampleText) {
      // 使用默认的示例文本
      setSampleText(`--- PAGE 1 ---
## 摘要

本文提出了一种基于深度学习的自然语言处理方法。该方法结合了Transformer架构和图神经网络，
在多个基准数据集上取得了优异的性能。实验结果表明，所提方法在文本分类、情感分析和命名实体识别
等任务上均优于现有方法。

## 1. 引言

自然语言处理是人工智能领域的重要研究方向。近年来，随着深度学习技术的快速发展，
基于神经网络的自然语言处理方法取得了显著的进展。特别是Transformer架构的提出，
极大地推动了该领域的发展。

然而，现有的方法仍然存在一些局限性。首先，它们通常需要大量的标注数据进行训练。
其次，它们对长文本的处理效果不佳。第三，它们缺乏对文本结构的建模能力。

为了解决这些问题，本文提出了一种新的方法。

## 2. 相关工作

### 2.1 基于Transformer的方法

BERT、GPT等预训练语言模型在各种NLP任务上取得了最先进的性能。
这些模型通过在大规模语料上进行预训练，学习到了丰富的语言表示。

### 2.2 图神经网络

图神经网络能够有效地建模实体之间的关系，在知识图谱、社交网络分析等领域
得到了广泛应用。最近，研究者开始将图神经网络应用于文本建模。`)
    }
  }, [sampleText, useCustomText])

  // 预览切片
  const handlePreview = async () => {
    setPreviewLoading(true)
    try {
      let text = sampleText
      if (!text) {
        // 如果没有示例文本，使用一个短文本
        text = `--- PAGE 1 ---\n这是一个测试文档。用于验证切片功能的正确性。\n\n第二段内容。包含更多信息。`
        setSampleText(text)
      }

      const result = await previewChunking({
        text,
        method,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        separators,
        preserve_images: preserveImages,
        preserve_tables: preserveTables,
      })

      setPreviewChunks(result.chunks)
      setTotalChunks(result.total_chunks)
      setAvgChunkSize(result.avg_chunk_size)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '切片预览失败，请检查后端服务')
    } finally {
      setPreviewLoading(false)
    }
  }

  // 执行切片
  const handleExecute = async () => {
    if (!selectedDocId) {
      alert('请先选择一个文档')
      return
    }
    // 检查所选文档是否已有切片数据
    const selectedDoc = documents.find(d => d.id === selectedDocId)
    if (selectedDoc && (selectedDoc.status === 'chunked' || selectedDoc.status === 'indexed')) {
      if (!confirm(
        `该文档已有切片数据（当前状态：${DOC_STATUS_LABELS[selectedDoc.status]}），再次执行切片将覆盖原有数据。\n\n是否确定继续？`
      )) return
    }
    if (!confirm(`确定要使用当前配置对文档执行切片吗？\n切片方式：${CHUNK_METHOD_LABELS[method]}\nChunk大小：${chunkSize}\n重叠：${chunkOverlap}`)) return

    setExecuting(true)
    try {
      await executeChunking(selectedDocId, {
        method,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        separators,
        preserve_images: preserveImages,
        preserve_tables: preserveTables,
      })
      alert('切片执行成功！')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '切片执行失败')
    } finally {
      setExecuting(false)
    }
  }

  // 切换文档选择（批量处理用）
  const toggleBatchDoc = (docId: number) => {
    setBatchDocIds(prev => {
      const next = new Set(prev)
      if (next.has(docId)) next.delete(docId)
      else next.add(docId)
      return next
    })
  }

  const selectAllDocs = () => {
    setBatchDocIds(new Set(documents.map(d => d.id)))
  }

  const deselectAllDocs = () => {
    setBatchDocIds(new Set())
  }

  // 批量处理
  const handleBatchProcess = () => {
    if (!selectedKbId || batchDocIds.size === 0) {
      alert('请先选择知识库和要处理的文档')
      return
    }
    // 检查所选文档中是否有已处理过的
    const processedDocs = documents.filter(
      d => batchDocIds.has(d.id) && d.status !== 'uploaded' && d.status !== 'error'
    )
    const confirmMsg = processedDocs.length > 0
      ? `所选 ${batchDocIds.size} 个文档中有 ${processedDocs.length} 个已有处理产物，再次运行将覆盖原有的 Markdown、切片和向量数据。\n\n是否确定继续？`
      : `确定要批量处理 ${batchDocIds.size} 个文档吗？\n将依次执行 PDF解析→图片摘要→切片→向量化入库`
    if (!confirm(confirmMsg)) return

    setBatchRunning(true)
    setBatchProgress(new Map())

    const controller = batchProcessDocuments(
      selectedKbId,
      Array.from(batchDocIds),
      (event) => {
        setBatchProgress(prev => {
          const next = new Map(prev)
          next.set(event.doc_id, event)
          return next
        })
      },
      (total) => {
        setBatchRunning(false)
        setBatchController(null)
        // 刷新文档列表
        if (selectedKbId) loadDocuments(selectedKbId)
        alert(`批量处理完成！共处理 ${total} 个文档`)
      },
      (error) => {
        setBatchRunning(false)
        setBatchController(null)
        alert(`批量处理出错: ${error}`)
      },
    )
    setBatchController(controller)
  }

  const handleCancelBatch = () => {
    if (batchController) {
      batchController.abort()
      setBatchRunning(false)
      setBatchController(null)
    }
  }

  // 初始化示例文本
  useEffect(() => {
    loadSampleText()
  }, [loadSampleText])

  return (
    <div>
      {/* 页面标题 */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">智能切片</h2>
        <p className="text-sm text-gray-500 mt-1">配置文本切片策略，预览切片效果，确保最佳的检索粒度</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左侧：配置面板 */}
        <div className="space-y-6">
          {/* 文档选择 */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">源文档</h3>

            <div className="space-y-3">
              {/* 选择知识库 */}
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5">知识库</label>
                <select
                  value={selectedKbId || ''}
                  onChange={e => {
                    const kbId = e.target.value ? Number(e.target.value) : null
                    setSelectedKbId(kbId)
                  }}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 text-sm
                    focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors"
                >
                  <option value="">选择知识库（切片预览用）…</option>
                  {kbs.map(kb => (
                    <option key={kb.id} value={kb.id}>{kb.name}</option>
                  ))}
                </select>
              </div>

              {/* 选择文档（用于执行切片） */}
              {selectedKbId != null && (
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">目标文档（执行切片时使用）</label>
                  <select
                    value={selectedDocId || ''}
                    onChange={e => setSelectedDocId(Number(e.target.value) || null)}
                    disabled={loadingDocs}
                    className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 text-sm
                      focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors"
                  >
                    <option value="">选择要切片的文档…</option>
                    {documents.map(doc => (
                      <option key={doc.id} value={doc.id}>
                        {doc.original_name} ({doc.status === 'indexed' ? '已入库' : doc.status === 'chunked' ? '已切片' : doc.status === 'parsed' ? '已解析' : '已上传'})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* 批量处理流水线 */}
              {selectedKbId != null && documents.length > 0 && (
                <div className="border-t border-gray-100 pt-3">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <h4 className="text-xs font-semibold text-gray-700">批量处理流水线</h4>
                      <p className="text-xs text-gray-400">PDF解析 → 切片 → 向量化入库</p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {batchRunning ? (
                        <button
                          onClick={handleCancelBatch}
                          className="px-2.5 py-1 rounded-md text-xs font-medium text-red-600 border border-red-200 hover:bg-red-50 transition-colors"
                        >
                          取消
                        </button>
                      ) : (
                        <>
                          <button onClick={selectAllDocs} className="px-2 py-1 rounded-md text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors">
                            全选
                          </button>
                          <button onClick={deselectAllDocs} className="px-2 py-1 rounded-md text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors">
                            取消
                          </button>
                          <button
                            onClick={handleBatchProcess}
                            disabled={batchDocIds.size === 0}
                            className="px-2.5 py-1 rounded-md text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            一键处理 ({batchDocIds.size})
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="max-h-48 overflow-y-auto -mx-1">
                    {documents.map(doc => {
                      const progress = batchProgress.get(doc.id)
                      const isProcessing = batchRunning && batchDocIds.has(doc.id) && (!progress || progress.status === 'processing')
                      const isDone = progress?.status === 'done'
                      const isError = progress?.status === 'error'

                      return (
                        <label
                          key={doc.id}
                          className={`flex items-center gap-2 px-1 py-1.5 rounded-md cursor-pointer transition-colors ${
                            batchRunning ? 'cursor-default' : 'hover:bg-gray-50'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={batchDocIds.has(doc.id)}
                            onChange={() => toggleBatchDoc(doc.id)}
                            disabled={batchRunning}
                            className="w-3.5 h-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 disabled:opacity-50 shrink-0"
                          />
                          <span className={`text-xs truncate flex-1 ${doc.status === 'indexed' ? 'text-emerald-600 font-medium' : 'text-gray-700'}`}>{doc.original_name}</span>
                          <span className={`shrink-0 inline-flex px-1.5 py-0.5 rounded text-xs ${
                            doc.status === 'indexed' ? 'bg-emerald-100 text-emerald-700' :
                            doc.status === 'chunked' ? 'bg-amber-100 text-amber-700' :
                            doc.status === 'error' ? 'bg-red-100 text-red-700' :
                            'bg-slate-100 text-slate-500'
                          }`}>
                            {doc.status === 'indexed' ? '已入库' : doc.status === 'chunked' ? '已切片' : doc.status === 'error' ? '异常' : '待处理'}
                          </span>
                          {isProcessing && (
                            <div className="w-3.5 h-3.5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin shrink-0" title={progress?.message} />
                          )}
                          {isDone && (
                            <svg className="w-3.5 h-3.5 text-emerald-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                          {isError && (
                            <svg className="w-3.5 h-3.5 text-red-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          )}
                        </label>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* 自定义预览文本 */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="use-custom-text"
                  checked={useCustomText}
                  onChange={e => setUseCustomText(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <label htmlFor="use-custom-text" className="text-xs text-gray-500 cursor-pointer">
                  使用自定义文本预览（勾选后可编辑下方文本）
                </label>
              </div>

              {useCustomText && (
                <textarea
                  value={sampleText}
                  onChange={e => setSampleText(e.target.value)}
                  placeholder="在此输入要预览的文本…"
                  rows={6}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-gray-300 text-sm font-mono
                    focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors resize-none"
                />
              )}
            </div>
          </div>

          {/* 切片方式 */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">切片方式</h3>
            <div className="grid grid-cols-2 gap-2">
              {(Object.keys(CHUNK_METHOD_LABELS) as ChunkMethod[]).map(m => (
                <button
                  key={m}
                  onClick={() => handleMethodChange(m)}
                  className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                    method === m
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border border-gray-200'
                  }`}
                >
                  {CHUNK_METHOD_LABELS[m]}
                </button>
              ))}
            </div>
          </div>

          {/* 参数设置 */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">参数设置</h3>

            {/* Chunk 大小 */}
            <div className="mb-5">
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-gray-500">Chunk 大小</label>
                <span className="text-xs font-bold text-indigo-600 font-mono">{chunkSize} 字符</span>
              </div>
              <input
                type="range"
                min={100}
                max={5000}
                step={50}
                value={chunkSize}
                onChange={e => {
                  const val = Number(e.target.value)
                  setChunkSize(val)
                  if (chunkOverlap >= val) setChunkOverlap(Math.floor(val * 0.2))
                }}
                className="w-full h-2 rounded-full bg-gray-200 appearance-none cursor-pointer accent-indigo-600"
              />
              <div className="flex justify-between mt-1">
                <span className="text-xs text-gray-400">100</span>
                <span className="text-xs text-gray-400">5000</span>
              </div>
            </div>

            {/* 重叠大小 */}
            <div className="mb-5">
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-medium text-gray-500">重叠大小</label>
                <span className="text-xs font-bold text-indigo-600 font-mono">{chunkOverlap} 字符</span>
              </div>
              <input
                type="range"
                min={0}
                max={1000}
                step={10}
                value={chunkOverlap}
                onChange={e => setChunkOverlap(Number(e.target.value))}
                className="w-full h-2 rounded-full bg-gray-200 appearance-none cursor-pointer accent-indigo-600"
              />
              <div className="flex justify-between mt-1">
                <span className="text-xs text-gray-400">0</span>
                <span className="text-xs text-gray-400">1000</span>
              </div>
            </div>

            {/* 分隔符编辑器 */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1.5">
                分隔符（按优先级排序，越靠上越优先匹配）
              </label>
              <SeparatorEditor separators={separators} onChange={setSeparators} />
            </div>
          </div>

          {/* 上下文保留选项 */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">上下文保留</h3>
            <div className="space-y-3">
              <label className="flex items-center justify-between py-2.5 px-3.5 rounded-lg bg-gray-100 border border-gray-200 cursor-pointer hover:bg-gray-200/70 transition-colors">
                <div>
                  <span className="text-sm font-medium text-gray-700">保留图片上下文</span>
                  <p className="text-xs text-gray-400 mt-0.5">将 ![]() 替换为语义描述 [图N: 标题]</p>
                </div>
                <button
                  type="button"
                  onClick={() => setPreserveImages(!preserveImages)}
                  className={`relative w-10 h-5.5 rounded-full transition-colors duration-200 ${
                    preserveImages ? 'bg-indigo-600' : 'bg-gray-400'
                  }`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                    preserveImages ? 'translate-x-5' : 'translate-x-0'
                  }`} />
                </button>
              </label>

              <label className="flex items-center justify-between py-2.5 px-3.5 rounded-lg bg-gray-100 border border-gray-200 cursor-pointer hover:bg-gray-200/70 transition-colors">
                <div>
                  <span className="text-sm font-medium text-gray-700">保留表格上下文</span>
                  <p className="text-xs text-gray-400 mt-0.5">保持表格结构不被分割，作为完整单元处理</p>
                </div>
                <button
                  type="button"
                  onClick={() => setPreserveTables(!preserveTables)}
                  className={`relative w-10 h-5.5 rounded-full transition-colors duration-200 ${
                    preserveTables ? 'bg-indigo-600' : 'bg-gray-400'
                  }`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${
                    preserveTables ? 'translate-x-5' : 'translate-x-0'
                  }`} />
                </button>
              </label>
            </div>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-3">
            <button
              onClick={handlePreview}
              disabled={previewLoading}
              className="flex-1 py-2.5 rounded-lg bg-indigo-600 text-sm font-medium text-white
                hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
            >
              {previewLoading ? '预览中…' : '预览切片'}
            </button>
            <button
              onClick={handleExecute}
              disabled={executing || !selectedDocId}
              className="flex-1 py-2.5 rounded-lg border border-indigo-200 text-sm font-medium text-indigo-600
                hover:bg-indigo-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {executing ? '执行中…' : '执行切片'}
            </button>
          </div>
        </div>

        {/* 右侧：预览面板 */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">
            切片预览
            {!previewLoading && totalChunks > 0 && (
              <span className="ml-2 text-xs font-normal text-gray-400">({totalChunks} 个块)</span>
            )}
          </h3>
          <ChunkPreviewComp
            chunks={previewChunks}
            totalChunks={totalChunks}
            avgChunkSize={avgChunkSize}
            loading={previewLoading}
          />
        </div>
      </div>

    </div>
  )
}
