import { useEffect, useState, type ComponentType } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, PenLine, Trash2, ArrowRight, Check, BrainCircuit, Library, Sparkles, Layers3 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Card, Button, Badge, Input, Textarea, Dialog, Spinner } from '../../shared/ui'
import { cn } from '../../shared/lib/cn'

interface KnowledgeBase { id: number; name: string }
interface Project {
  id: number; title: string; topic: string; kb_id: number | null; kb_ids?: number[] | string
  methodology?: string
  outline_status: 'none' | 'pending' | 'confirmed'; status: string
  created_at: string; updated_at: string
}

const api = axios.create({ baseURL: '/api' })

const STATUS: Record<string, { text: string; tone: 'slate' | 'amber' | 'emerald' }> = {
  none: { text: '未开始', tone: 'slate' },
  pending: { text: '待确认', tone: 'amber' },
  confirmed: { text: '已确认', tone: 'emerald' },
}

const TAGS = ['Multi-Agent', 'Tool Use', 'ReAct', 'Human-in-the-Loop', 'LangGraph', 'Agent Trace']

const resolveKbIds = (project: Project): number[] => {
  const raw = project.kb_ids
  if (Array.isArray(raw)) return raw
  if (typeof raw === 'string' && raw.trim()) {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        return parsed
          .map(Number)
          .filter((id): id is number => Number.isFinite(id) && id > 0)
      }
    } catch {
      // Fall through to the legacy kb_id field.
    }
  }
  return project.kb_id ? [project.kb_id] : []
}

export default function ThesisProject() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState<{ title: string; topic: string; methodology: string; kb_ids: number[] }>({ title: '', topic: '', methodology: '', kb_ids: [] })
  const [creating, setCreating] = useState(false)

  const load = async () => {
    try {
      const [p, k] = await Promise.all([api.get('/agent/projects'), api.get('/kb')])
      setProjects(p.data); setKbs(k.data)
    } catch { toast.error('加载失败') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    if (!form.title.trim() || !form.topic.trim() || !form.methodology.trim()) return
    setCreating(true)
    try {
      await api.post('/agent/projects', { title: form.title, topic: form.topic, methodology: form.methodology, kb_ids: form.kb_ids })
      setForm({ title: '', topic: '', methodology: '', kb_ids: [] }); setShowCreate(false); await load()
      toast.success('项目已创建')
    } catch { toast.error('创建失败') }
    finally { setCreating(false) }
  }

  const toggleKb = (id: number) => setForm(f => ({ ...f, kb_ids: f.kb_ids.includes(id) ? f.kb_ids.filter(x => x !== id) : [...f.kb_ids, id] }))

  const handleDelete = async (id: number) => {
    if (!confirm('确认删除该论文项目？')) return
    try { await api.delete(`/agent/projects/${id}`); await load(); toast.success('已删除') }
    catch { toast.error('删除失败') }
  }

  const kbNames = (p: Project) => {
    const ids = resolveKbIds(p)
    const names = ids.map(id => kbs.find(k => k.id === id)?.name).filter(Boolean)
    return names.length ? names.join('、') : '未绑定知识库'
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl px-10 py-10">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.28em] text-indigo-500">Thesis Agent Workspace</p>
            <h2 className="text-3xl font-semibold tracking-tight text-slate-950">论文写作助手</h2>
            <p className="mt-2 text-sm text-slate-500">多智能体协作 · 文献研究 · 大纲规划 · 逐章写作与评审（HITL）</p>
          </div>
          <Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4" />新建项目</Button>
        </header>

        <section className="mb-8 overflow-hidden rounded-[28px] border border-white/70 bg-slate-950 shadow-[0_30px_100px_rgba(15,23,42,0.22)]">
          <div className="relative grid lg:grid-cols-[1.45fr_0.9fr]">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(99,102,241,0.42),transparent_32%),radial-gradient(circle_at_78%_28%,rgba(20,184,166,0.22),transparent_30%)]" />
            <div className="relative p-8 lg:p-10">
              <div className="mb-4 flex flex-wrap gap-2">
                <Badge tone="indigo"><BrainCircuit className="h-3.5 w-3.5" /> Multi-Agent Thesis Lab</Badge>
                <Badge tone="emerald">RAG Grounded</Badge>
                <Badge tone="amber">Human Review</Badge>
              </div>
              <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-white">把论文从想法推进到可修改草稿</h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300">
                主流程负责题目/想法、大纲、章节写作、引用核验、质量评分；你在关键节点确认方向，系统负责重复检索和生成。
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Button className="bg-white text-slate-950 hover:bg-cyan-50 hover:text-slate-950" onClick={() => setShowCreate(true)}><Plus className="h-4 w-4" />创建论文</Button>
                <Button variant="outline" className="border-white/20 bg-white/10 text-white hover:bg-white/15 hover:text-white" onClick={() => navigate('/knowledge')}><Library className="h-4 w-4" />准备知识库</Button>
              </div>
            </div>
            <div className="relative grid gap-3 border-t border-white/10 bg-white/[0.04] p-6 backdrop-blur lg:border-l lg:border-t-0 lg:p-7">
              <StatPill icon={PenLine} label="活跃项目" value={projects.length} />
              <StatPill icon={Layers3} label="知识库" value={kbs.length} />
              <StatPill icon={Sparkles} label="当前模式" value="HITL" />
            </div>
          </div>
        </section>

        {loading ? (
          <div className="flex justify-center py-20"><Spinner className="h-7 w-7" /></div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400"><PenLine className="h-7 w-7" /></div>
            <h3 className="text-base font-medium text-slate-600">还没有论文项目</h3>
            <p className="mt-1 text-sm text-slate-400">点击右上角「新建项目」开始多智能体写作</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {projects.map(p => {
              const kbName = kbNames(p)
              const st = STATUS[p.outline_status] ?? STATUS.none
              return (
                <Card key={p.id} hover className="group flex flex-wrap items-start gap-5 p-6">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2.5">
                      <h3 className="truncate text-base font-semibold text-slate-900">{p.title}</h3>
                      <Badge tone={st.tone}>{st.text}</Badge>
                    </div>
                    <p className="mb-3 line-clamp-2 text-sm leading-6 text-slate-500">{p.topic}</p>
                    <p className="text-xs text-slate-400">{p.methodology ? `${p.methodology} · ` : ''}知识库：{kbName} · 更新于 {new Date(p.updated_at).toLocaleString('zh-CN')}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button size="sm" onClick={() => navigate(`/writing/${p.id}`)}>进入工作区<ArrowRight className="h-3.5 w-3.5" /></Button>
                    <button onClick={() => handleDelete(p.id)} className="rounded-lg p-2 text-slate-300 opacity-0 transition-all hover:bg-rose-50 hover:text-rose-500 group-hover:opacity-100">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </Card>
              )
            })}
          </div>
        )}

        <div className="mt-8 flex flex-wrap gap-2 border-t border-slate-100 pt-5">
          {TAGS.map(t => <Badge key={t} tone="slate">{t}</Badge>)}
        </div>
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate} title="新建论文项目">
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-600">论文标题</label>
            <Input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="例：社交媒体对青少年心理健康的影响研究" autoFocus />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-600">研究主题（Agent 研究的核心问题）</label>
            <Textarea rows={2} value={form.topic} onChange={e => setForm(f => ({ ...f, topic: e.target.value }))} placeholder="例：社交媒体使用与青少年焦虑、抑郁的关系及其影响机制" />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-600">研究方法 / 专家方向 <span className="text-rose-500">*</span></label>
            <Input value={form.methodology} onChange={e => setForm(f => ({ ...f, methodology: e.target.value }))} placeholder="例：计算传播学 / 实证社会科学 / 临床医学" />
            <p className="mt-1 text-xs text-slate-400">写作时将以该领域专家的身份与话语体系撰写</p>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-600">绑定知识库（可多选）</label>
            {kbs.length === 0 ? (
              <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-400">暂无知识库，可稍后在工作区补充</p>
            ) : (
              <div className="grid max-h-40 grid-cols-2 gap-1.5 overflow-y-auto">
                {kbs.map(k => {
                  const on = form.kb_ids.includes(k.id)
                  return (
                    <button key={k.id} type="button" onClick={() => toggleKb(k.id)}
                      className={cn('flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-left text-sm transition-colors',
                        on ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600 hover:border-slate-300')}>
                      <span className={cn('flex h-4 w-4 shrink-0 items-center justify-center rounded border', on ? 'border-indigo-500 bg-indigo-500 text-white' : 'border-slate-300')}>
                        {on && <Check className="h-3 w-3" />}
                      </span>
                      <span className="truncate">{k.name}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
          <div className="flex gap-3 pt-1">
            <Button variant="secondary" className="flex-1" onClick={() => setShowCreate(false)}>取消</Button>
            <Button className="flex-1" loading={creating} disabled={!form.title.trim() || !form.topic.trim() || !form.methodology.trim()} onClick={handleCreate}>创建项目</Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}

function StatPill({ icon: Icon, label, value }: { icon: ComponentType<{ className?: string }>; label: string; value: number | string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/10 px-4 py-4 text-white backdrop-blur">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-300">
        <Icon className="h-4 w-4 text-cyan-200" />
        {label}
      </div>
      <span className="text-xl font-semibold text-white">{value}</span>
    </div>
  )
}
