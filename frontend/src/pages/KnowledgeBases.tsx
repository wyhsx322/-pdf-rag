import { useState, useEffect, useCallback } from 'react'
import type { KnowledgeBase, KBType } from '../types'
import { listKBs, createKB, deleteKB } from '../api/client'
import KBCard from '../components/KBCard'
import CreateKBDialog from '../components/CreateKBDialog'

export default function KnowledgeBases() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchKBs = useCallback(async () => {
    try {
      setError(null)
      const data = await listKBs()
      setKbs(data)
    } catch {
      setError('无法加载知识库列表，请检查后端服务是否启动')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchKBs()
  }, [fetchKBs])

  const handleCreate = async (name: string, type: KBType, description: string) => {
    setCreating(true)
    try {
      const kb = await createKB(name, type, description)
      setKbs(prev => [kb, ...prev])
      setDialogOpen(false)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || '创建失败，请重试')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: number) => {
    const kb = kbs.find(k => k.id === id)
    if (!kb) return
    if (!confirm(`确定要删除知识库「${kb.name}」吗？\n该操作将同时删除其中的所有文档，不可恢复。`)) return

    try {
      await deleteKB(id)
      setKbs(prev => prev.filter(k => k.id !== id))
    } catch {
      alert('删除失败，请重试')
    }
  }

  return (
    <div>
      {/* 页面标题 */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">知识库管理</h2>
          <p className="text-sm text-gray-500 mt-1">创建和管理你的论文知识库，支持工作、学习、个人分类</p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 text-sm font-medium
            text-white hover:bg-indigo-700 shadow-sm hover:shadow transition-all duration-150"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          新建知识库
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-center gap-3">
          <svg className="w-5 h-5 text-amber-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <p className="text-sm text-amber-700">{error}</p>
        </div>
      )}

      {/* 知识库卡片网格 */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : kbs.length === 0 ? (
        <div className="text-center py-20">
          <span className="text-5xl mb-4 block">📚</span>
          <h3 className="text-lg font-medium text-gray-700 mb-2">还没有知识库</h3>
          <p className="text-sm text-gray-400 mb-6">点击上方「新建知识库」按钮创建第一个知识库</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {kbs.map(kb => (
            <KBCard key={kb.id} kb={kb} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {/* 创建弹窗 */}
      <CreateKBDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreate={handleCreate}
        loading={creating}
      />
    </div>
  )
}
