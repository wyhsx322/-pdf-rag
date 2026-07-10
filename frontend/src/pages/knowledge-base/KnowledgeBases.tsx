import { useState, useEffect, useCallback } from 'react'
import { ArrowLeft, Plus, Library, ScanSearch } from 'lucide-react'
import { toast } from 'sonner'
import type { KnowledgeBase, KBType } from '../../entities/knowledge-base/model'
import { listKBs, createKB, deleteKB } from '../../entities/knowledge-base/api'
import KBCard from './KBCard'
import CreateKBDialog from './CreateKBDialog'
import RagSearchPanel from '../../features/retrieval/RagSearchPanel'
import { Button, Spinner } from '../../shared/ui'

export default function KnowledgeBases() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [view, setView] = useState<'list' | 'rag'>('list')

  const fetchKBs = useCallback(async () => {
    try {
      const data = await listKBs()
      setKbs(data)
    } catch {
      toast.error('无法加载知识库列表，请检查后端服务')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchKBs() }, [fetchKBs])

  const handleCreate = async (name: string, type: KBType, description: string) => {
    setCreating(true)
    try {
      const kb = await createKB(name, type, description)
      setKbs(prev => [kb, ...prev])
      setDialogOpen(false)
      toast.success(`已创建「${kb.name}」`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || '创建失败，请重试')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: number) => {
    const kb = kbs.find(k => k.id === id)
    if (!kb || !confirm(`确定删除知识库「${kb.name}」及其所有文档？此操作不可恢复。`)) return
    try {
      await deleteKB(id)
      setKbs(prev => prev.filter(k => k.id !== id))
      toast.success('已删除')
    } catch {
      toast.error('删除失败，请重试')
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl px-10 py-10">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.28em] text-indigo-500">Knowledge Infrastructure</p>
            <h2 className="text-3xl font-semibold tracking-tight text-slate-950">{view === 'rag' ? 'RAG 检索实验台' : '知识库管理'}</h2>
            <p className="mt-2 text-sm text-slate-500">创建并管理论文知识库，上传 PDF、配置切分、索引与召回诊断</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {view === 'rag' ? (
              <Button variant="outline" onClick={() => setView('list')}><ArrowLeft className="h-4 w-4" />返回知识库</Button>
            ) : (
              <Button variant="outline" onClick={() => setView('rag')}><ScanSearch className="h-4 w-4" />RAG 检索</Button>
            )}
            <Button onClick={() => setDialogOpen(true)}><Plus className="h-4 w-4" />新建知识库</Button>
          </div>
        </header>

        {view === 'rag' ? (
          <RagSearchPanel embedded />
        ) : loading ? (
          <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>
        ) : kbs.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/80 bg-white/70 text-slate-400 shadow-soft">
              <Library className="h-7 w-7" />
            </div>
            <h3 className="text-base font-medium text-slate-600">还没有知识库</h3>
            <p className="mt-1 text-sm text-slate-400">点击右上角「新建知识库」开始</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {kbs.map(kb => <KBCard key={kb.id} kb={kb} onDelete={handleDelete} />)}
          </div>
        )}
      </div>

      <CreateKBDialog open={dialogOpen} onClose={() => setDialogOpen(false)} onCreate={handleCreate} loading={creating} />
    </div>
  )
}
