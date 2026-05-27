import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import type { KnowledgeBaseDetail, DocumentStatus } from '../types'
import { getKB, deleteKB, uploadDocuments, deleteDocument, processDocument, batchImportDocuments, getVectorStats, deleteVectors, reindexDocument } from '../api/client'
import type { VectorStats } from '../api/client'
import { KB_TYPE_ICONS, KB_TYPE_LABELS, DOC_STATUS_LABELS } from '../types'
import UploadZone from '../components/UploadZone'
import DocumentRow from '../components/DocumentRow'

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: '全部状态' },
  { value: 'uploaded', label: '已上传' },
  { value: 'parsed', label: '已解析' },
  { value: 'chunked', label: '已切片' },
  { value: 'indexed', label: '已入库' },
  { value: 'error', label: '异常' },
]

export default function KnowledgeBaseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [kb, setKb] = useState<KnowledgeBaseDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [processingId, setProcessingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // 搜索和筛选
  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // 向量统计弹窗
  const [vectorStats, setVectorStats] = useState<VectorStats | null>(null)
  const [vectorStatsLoading, setVectorStatsLoading] = useState(false)

  const fetchKB = useCallback(async () => {
    if (!id) return
    try {
      setError(null)
      const data = await getKB(Number(id))
      setKb(data)
    } catch {
      setError('无法加载知识库详情')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchKB()
  }, [fetchKB])

  // 客户端过滤文档
  const filteredDocuments = useMemo(() => {
    if (!kb) return []
    let docs = kb.documents

    if (searchText) {
      const s = searchText.toLowerCase()
      docs = docs.filter(d =>
        d.original_name.toLowerCase().includes(s) ||
        d.filename.toLowerCase().includes(s)
      )
    }

    if (statusFilter) {
      docs = docs.filter(d => d.status === statusFilter)
    }

    return docs
  }, [kb, searchText, statusFilter])

  const handleUpload = async (files: File[]) => {
    if (!id) return
    setUploading(true)
    try {
      await uploadDocuments(Number(id), files)
      await fetchKB()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteDoc = async (docId: number) => {
    if (!confirm('确定要删除这个文档吗？相关的处理产物也将被删除。')) return
    try {
      await deleteDocument(docId)
      await fetchKB()
    } catch {
      alert('删除失败')
    }
  }

  const handleProcess = async (docId: number) => {
    // 查找文档当前状态，非首次处理时弹出覆盖确认
    const doc = kb?.documents.find(d => d.id === docId)
    if (doc && doc.status !== 'uploaded') {
      const statusLabel = DOC_STATUS_LABELS[doc.status] || doc.status
      if (!confirm(
        `该文档已有处理产物（当前状态：${statusLabel}），再次处理将覆盖原有的 Markdown、切片和向量数据。\n\n是否确定继续？`
      )) return
    }
    setProcessingId(docId)
    try {
      await processDocument(docId)
      await fetchKB()
      alert('处理完成！')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '处理失败')
    } finally {
      setProcessingId(null)
    }
  }

  const handleDeleteKB = async () => {
    if (!kb) return
    if (!confirm(`确定要删除知识库「${kb.name}」及其所有文档吗？此操作不可恢复。`)) return
    try {
      await deleteKB(kb.id)
      navigate('/')
    } catch {
      alert('删除失败')
    }
  }

  const handleBatchImport = async () => {
    if (!id) return
    try {
      const imported = await batchImportDocuments(Number(id))
      if (imported.length === 0) {
        alert('没有找到新的 PDF 文件，或所有文件已导入')
      } else {
        await fetchKB()
        alert(`成功导入 ${imported.length} 个文档`)
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '批量导入失败')
    }
  }

  // 向量库操作
  const handleViewVectorStats = async (docId: number) => {
    setVectorStatsLoading(true)
    setVectorStats(null)
    try {
      const stats = await getVectorStats(docId)
      setVectorStats(stats)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '获取向量统计失败')
    } finally {
      setVectorStatsLoading(false)
    }
  }

  const handleDeleteVectors = async (docId: number) => {
    if (!confirm('确定要删除该文档的向量数据吗？文档记录和产物文件将保留，之后可以重新索引。')) return
    try {
      await deleteVectors(docId)
      await fetchKB()
      alert('向量数据已删除')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '删除向量数据失败')
    }
  }

  const handleReindex = async (docId: number) => {
    if (!confirm('确定要重新索引该文档吗？将重新生成向量并入库。')) return
    try {
      await reindexDocument(docId)
      await fetchKB()
      alert('重新索引完成！')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '重新索引失败')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !kb) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500 mb-4">{error || '知识库不存在'}</p>
        <button
          onClick={() => navigate('/')}
          className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
        >
          返回知识库列表
        </button>
      </div>
    )
  }

  return (
    <div>
      {/* 顶部导航 */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate('/')}
          className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            {kb.name}
            <span className="text-lg font-normal text-gray-400">{KB_TYPE_ICONS[kb.type]}</span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200">
              {KB_TYPE_LABELS[kb.type]}
            </span>
          </h2>
          {kb.description && <p className="text-sm text-gray-500 mt-1">{kb.description}</p>}
        </div>
        <div className="flex-1" />
        <button
          onClick={handleBatchImport}
          className="px-3.5 py-2 rounded-lg text-sm font-medium text-gray-600 border border-gray-200
            hover:bg-gray-50 hover:border-gray-300 transition-all duration-150"
        >
          批量导入
        </button>
        <button
          onClick={handleDeleteKB}
          className="px-3.5 py-2 rounded-lg text-sm font-medium text-red-600 border border-red-200
            hover:bg-red-50 transition-all duration-150"
        >
          删除知识库
        </button>
      </div>

      {/* 上传区域 */}
      <div className="mb-8">
        <UploadZone onUpload={handleUpload} uploading={uploading} />
      </div>

      {/* 文档列表 */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
          <h3 className="font-semibold text-gray-900">
            文档列表
            <span className="ml-2 text-sm font-normal text-gray-400">
              ({filteredDocuments.length}{filteredDocuments.length !== kb.documents.length ? ` / ${kb.documents.length}` : ''} 个文档)
            </span>
          </h3>

          {/* 搜索和筛选 */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <svg className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                value={searchText}
                onChange={e => setSearchText(e.target.value)}
                placeholder="搜索文件名…"
                className="w-48 pl-9 pr-3 py-2 rounded-lg border border-gray-300 text-xs
                  focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors"
              />
            </div>
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="px-3 py-2 rounded-lg border border-gray-300 text-xs
                focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-colors"
            >
              {STATUS_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        {filteredDocuments.length === 0 ? (
          <div className="text-center py-16">
            <span className="text-4xl mb-3 block">📂</span>
            <p className="text-sm text-gray-400">
              {kb.documents.length === 0 ? '暂无文档，请上传 PDF 文件' : '没有匹配的文档'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider py-3 px-4">文件名</th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider py-3 px-4">状态</th>
                  <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wider py-3 px-4">页数</th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider py-3 px-4">上传时间</th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider py-3 px-4">操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocuments.map(doc => (
                  <DocumentRow
                    key={doc.id}
                    doc={doc}
                    onDelete={handleDeleteDoc}
                    onProcess={handleProcess}
                    onViewVectorStats={handleViewVectorStats}
                    onDeleteVectors={handleDeleteVectors}
                    onReindex={handleReindex}
                    processing={processingId === doc.id}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 向量统计弹窗 */}
      {(vectorStats || vectorStatsLoading) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30" onClick={() => { setVectorStats(null); setVectorStatsLoading(false) }} />
          <div className="relative bg-white rounded-xl shadow-xl p-6 w-96 z-10">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-900">向量库统计</h3>
              <button
                onClick={() => { setVectorStats(null); setVectorStatsLoading(false) }}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {vectorStatsLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : vectorStats ? (
              <div className="space-y-3">
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-xs text-gray-500">文档</span>
                  <span className="text-xs font-medium text-gray-700">{vectorStats.original_name}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-xs text-gray-500">Collection</span>
                  <span className="text-xs font-medium text-gray-700 font-mono">{vectorStats.collection_name}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-xs text-gray-500">状态</span>
                  <span className="text-xs font-medium text-gray-700">{vectorStats.collection_exists ? '存在' : '不存在'}</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-xs text-gray-500">向量数量</span>
                  <span className="text-sm font-bold text-indigo-600">{vectorStats.vector_count}</span>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
