import { useState, useEffect, useCallback } from 'react'
import { Plus, Library } from 'lucide-react'
import { toast } from 'sonner'
import type { KnowledgeBase, KBType } from '../types'
import { listKBs, createKB, deleteKB } from '../api/client'
import KBCard from '../components/KBCard'
import CreateKBDialog from '../components/CreateKBDialog'
import { Button, Spinner } from '../components/ui'

export default function KnowledgeBases() {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)

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
      <div className="mx-auto max-w-5xl px-8 py-8">
        <header className="mb-8 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">知识库管理</h2>
            <p className="mt-1 text-sm text-slate-400">创建并管理论文知识库，上传 PDF、配置切分与索引</p>
          </div>
          <Button onClick={() => setDialogOpen(true)}><Plus className="h-4 w-4" />新建知识库</Button>
        </header>

        {loading ? (
          <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>
        ) : kbs.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
              <Library className="h-7 w-7" />
            </div>
            <h3 className="text-base font-medium text-slate-600">还没有知识库</h3>
            <p className="mt-1 text-sm text-slate-400">点击右上角「新建知识库」开始</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {kbs.map(kb => <KBCard key={kb.id} kb={kb} onDelete={handleDelete} />)}
          </div>
        )}
      </div>

      <CreateKBDialog open={dialogOpen} onClose={() => setDialogOpen(false)} onCreate={handleCreate} loading={creating} />
    </div>
  )
}
