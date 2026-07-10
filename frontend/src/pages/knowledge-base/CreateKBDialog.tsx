import { useState } from 'react'
import { Briefcase, GraduationCap, User } from 'lucide-react'
import type { KBType } from '../../entities/knowledge-base/model'
import { KB_TYPE_LABELS } from '../../entities/knowledge-base/model'
import { Dialog, Input, Textarea, Button } from '../../shared/ui'
import { cn } from '../../shared/lib/cn'

interface Props {
  open: boolean
  onClose: () => void
  onCreate: (name: string, type: KBType, description: string) => void
  loading: boolean
}

const typeMeta: Record<KBType, { icon: typeof Briefcase }> = {
  work: { icon: Briefcase }, study: { icon: GraduationCap }, personal: { icon: User },
}

export default function CreateKBDialog({ open, onClose, onCreate, loading }: Props) {
  const [name, setName] = useState('')
  const [type, setType] = useState<KBType>('study')
  const [description, setDescription] = useState('')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    onCreate(name.trim(), type, description.trim())
    setName(''); setDescription(''); setType('study')
  }

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()} title="新建知识库">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-600">知识库名称</label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="例如：情绪传播研究" maxLength={50} autoFocus required />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-600">类型</label>
          <div className="grid grid-cols-3 gap-2">
            {(Object.keys(typeMeta) as KBType[]).map(t => {
              const Icon = typeMeta[t].icon
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => setType(t)}
                  className={cn(
                    'flex items-center justify-center gap-1.5 rounded-xl border py-2.5 text-sm font-medium transition-all',
                    type === t ? 'border-indigo-400 bg-indigo-50 text-indigo-600' : 'border-slate-200 text-slate-500 hover:border-slate-300',
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {KB_TYPE_LABELS[t]}
                </button>
              )
            })}
          </div>
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-600">描述（可选）</label>
          <Textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="简要描述用途…" maxLength={200} rows={3} />
        </div>
        <div className="flex gap-3 pt-1">
          <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>取消</Button>
          <Button type="submit" className="flex-1" loading={loading} disabled={!name.trim()}>创建</Button>
        </div>
      </form>
    </Dialog>
  )
}
