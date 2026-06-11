import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

interface KnowledgeBase {
  id: number
  name: string
}

interface ThesisProject {
  id: number
  title: string
  topic: string
  kb_id: number | null
  outline_status: 'none' | 'pending' | 'confirmed'
  status: string
  created_at: string
  updated_at: string
}

const api = axios.create({ baseURL: '/api' })

const STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  none:      { text: '未开始', cls: 'bg-slate-700 text-slate-300' },
  pending:   { text: '待确认', cls: 'bg-amber-500/20 text-amber-300' },
  confirmed: { text: '已确认', cls: 'bg-emerald-500/20 text-emerald-300' },
}

export default function ThesisProject() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<ThesisProject[]>([])
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ title: '', topic: '', kb_id: '' })
  const [creating, setCreating] = useState(false)

  const load = async () => {
    const [pRes, kRes] = await Promise.all([
      api.get('/agent/projects'),
      api.get('/kb'),
    ])
    setProjects(pRes.data)
    setKbs(kRes.data)
  }

  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    if (!form.title.trim() || !form.topic.trim()) return
    setCreating(true)
    try {
      await api.post('/agent/projects', {
        title: form.title,
        topic: form.topic,
        kb_id: form.kb_id ? Number(form.kb_id) : null,
      })
      setForm({ title: '', topic: '', kb_id: '' })
      setShowCreate(false)
      await load()
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确认删除该论文项目？')) return
    await api.delete(`/agent/projects/${id}`)
    await load()
  }

  return (
    <div className="h-full flex flex-col p-6 gap-6 overflow-auto">
      {/* 页头 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">论文写作助手</h1>
          <p className="text-sm text-slate-400 mt-1">
            多智能体协作 · 文献研究 · 大纲规划 · Human-in-the-Loop
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-indigo-500 hover:bg-indigo-400 text-white rounded-lg text-sm font-medium transition-colors"
        >
          + 新建论文项目
        </button>
      </div>

      {/* 创建表单 */}
      {showCreate && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-200">新建论文项目</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">论文标题</label>
              <input
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                placeholder="例：社交媒体对青少年心理健康的影响研究"
                value={form.title}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">绑定知识库（可选）</label>
              <select
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                value={form.kb_id}
                onChange={e => setForm(f => ({ ...f, kb_id: e.target.value }))}
              >
                <option value="">-- 不绑定 --</option>
                {kbs.map(kb => (
                  <option key={kb.id} value={kb.id}>{kb.name}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">研究主题（Agent 研究的核心问题）</label>
            <textarea
              rows={2}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
              placeholder="例：社交媒体使用与青少年焦虑、抑郁的关系及其影响机制"
              value={form.topic}
              onChange={e => setForm(f => ({ ...f, topic: e.target.value }))}
            />
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleCreate}
              disabled={creating || !form.title.trim() || !form.topic.trim()}
              className="px-4 py-2 bg-indigo-500 hover:bg-indigo-400 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
            >
              {creating ? '创建中...' : '创建项目'}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg text-sm transition-colors"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* 项目列表 */}
      {projects.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
          暂无论文项目，点击右上角新建一个
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {projects.map(p => {
            const kbName = kbs.find(k => k.id === p.kb_id)?.name ?? '未绑定知识库'
            const { text: statusText, cls: statusCls } = STATUS_LABEL[p.outline_status] ?? STATUS_LABEL.none
            return (
              <div
                key={p.id}
                className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-slate-600 transition-colors group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-base font-semibold text-white truncate">{p.title}</h3>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusCls}`}>
                        {statusText}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400 truncate mb-2">{p.topic}</p>
                    <p className="text-xs text-slate-500">
                      知识库：{kbName} · 更新于 {new Date(p.updated_at).toLocaleString('zh-CN')}
                    </p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => navigate(`/thesis/${p.id}`)}
                      className="px-3 py-1.5 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 rounded-lg text-xs font-medium transition-colors"
                    >
                      进入工作区
                    </button>
                    <button
                      onClick={() => handleDelete(p.id)}
                      className="px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-xs transition-colors opacity-0 group-hover:opacity-100"
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 技术标注 */}
      <div className="mt-auto pt-4 border-t border-slate-700/50">
        <div className="flex flex-wrap gap-2">
          {['Multi-Agent Orchestration', 'Tool Use / Function Calling', 'ReAct Pattern',
            'Human-in-the-Loop', 'Structured Output', 'Agent Trace'].map(tag => (
            <span key={tag} className="px-2 py-1 bg-slate-700/50 text-slate-400 rounded text-xs">
              {tag}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
