import { useState, useEffect, type ComponentType } from 'react'
import {
  Save, Eye, EyeOff, KeyRound, BookOpen, ClipboardList, PenLine,
  CheckCircle2, Plug, Loader2, Route, ShieldCheck, SearchCheck,
  Bot, Boxes, Wand2, Image as ImageIcon, ArrowUpDown,
} from 'lucide-react'
import { toast } from 'sonner'
import { getSettings, updateSettings, testProvider, type SettingsResponse, type ModelRole, type ModelOption } from '../../features/settings/api'
import { Card, Button, Input, Badge, Spinner, Select } from '../../shared/ui'

const DEFAULT_MODEL_OPTIONS: ModelOption[] = [
  {
    id: 'deepseek-chat',
    label: 'DeepSeek Chat',
    model: 'deepseek-chat',
    base_url: 'https://api.deepseek.com/v1',
    api_key_env: 'DEEPSEEK_API_KEY',
    provider: 'DeepSeek',
  },
  {
    id: 'deepseek-reasoner',
    label: 'DeepSeek Reasoner',
    model: 'deepseek-reasoner',
    base_url: 'https://api.deepseek.com/v1',
    api_key_env: 'DEEPSEEK_API_KEY',
    provider: 'DeepSeek',
  },
  {
    id: 'qwen3.7-plus',
    label: 'Qwen 3.7 Plus',
    model: 'qwen3.7-plus',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    api_key_env: 'DASHSCOPE_API_KEY',
    provider: 'DashScope',
  },
  {
    id: 'qwen-plus',
    label: 'Qwen Plus',
    model: 'qwen-plus',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    api_key_env: 'DASHSCOPE_API_KEY',
    provider: 'DashScope',
  },
  {
    id: 'qwen-turbo',
    label: 'Qwen Turbo',
    model: 'qwen-turbo',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    api_key_env: 'DASHSCOPE_API_KEY',
    provider: 'DashScope',
  },
]

const DEFAULT_AGENT_MODELS: Record<string, ModelRole> = {
  coordinator: {
    model: 'deepseek-chat',
    base_url: 'https://api.deepseek.com/v1',
    api_key_env: 'DEEPSEEK_API_KEY',
  },
  literature: {
    model: 'deepseek-chat',
    base_url: 'https://api.deepseek.com/v1',
    api_key_env: 'DEEPSEEK_API_KEY',
  },
  outline: {
    model: 'deepseek-chat',
    base_url: 'https://api.deepseek.com/v1',
    api_key_env: 'DEEPSEEK_API_KEY',
  },
  writing: {
    model: 'deepseek-chat',
    base_url: 'https://api.deepseek.com/v1',
    api_key_env: 'DEEPSEEK_API_KEY',
  },
  review: {
    model: 'qwen3.7-plus',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    api_key_env: 'DASHSCOPE_API_KEY',
  },
}

const KEYS = [
  { env: 'DASHSCOPE_API_KEY', name: '阿里云百炼 DashScope', desc: 'Qwen 模型、嵌入向量、图片摘要共用' },
  { env: 'DEEPSEEK_API_KEY', name: 'DeepSeek', desc: 'DeepSeek Chat / Reasoner' },
] as const

const AGENTS: Array<{
  key: string
  icon: ComponentType<{ className?: string }>
  label: string
  desc: string
}> = [
  { key: 'coordinator', icon: Route, label: 'CoordinatorAgent 协调器', desc: '判断用户意图并决定调用哪些子智能体' },
  { key: 'literature', icon: BookOpen, label: 'LiteratureAgent 文献研究', desc: '检索文献、提炼研究论点与素材摘要' },
  { key: 'outline', icon: ClipboardList, label: 'OutlineAgent 大纲规划', desc: '生成结构化论文大纲，进入人工确认节点' },
  { key: 'writing', icon: PenLine, label: 'SectionWritingAgent 章节写作', desc: '逐章检索证据并生成论文草稿' },
  { key: 'review', icon: ShieldCheck, label: 'ReviewAgent 学术评审', desc: '独立评估章节质量，避免写作模型自评' },
]

const SYSTEM_ROLES: Array<{
  key: string
  icon: ComponentType<{ className?: string }>
  label: string
  desc: string
  keyEnv: string
  hasUrl: boolean
}> = [
  { key: 'generation', icon: Bot, label: '生成 LLM', desc: 'RAG 回答与通用生成链路的默认模型', keyEnv: 'DEEPSEEK_API_KEY', hasUrl: true },
  { key: 'embedding', icon: Boxes, label: '嵌入向量模型', desc: '文本向量化，决定知识库语义召回质量', keyEnv: 'DASHSCOPE_API_KEY', hasUrl: true },
  { key: 'query_llm', icon: Wand2, label: '查询处理 LLM', desc: '查询改写、HyDE 与关键词抽取的轻量模型', keyEnv: 'DASHSCOPE_API_KEY', hasUrl: true },
  { key: 'vl', icon: ImageIcon, label: '图片摘要 VLM', desc: '论文图表和图片证据的多模态摘要模型', keyEnv: 'DASHSCOPE_API_KEY', hasUrl: true },
  { key: 'reranker', icon: ArrowUpDown, label: '重排序模型', desc: 'BGE reranker 精排模型，通常本地运行', keyEnv: '', hasUrl: false },
]

function optionIdFor(model: ModelRole | undefined, options: ModelOption[]) {
  if (!model) return ''
  const found = options.find(opt =>
    opt.model === model.model &&
    opt.base_url === model.base_url &&
    opt.api_key_env === model.api_key_env
  )
  return found?.id || ''
}

function applyOption(option: ModelOption): ModelRole {
  return {
    model: option.model,
    base_url: option.base_url,
    api_key_env: option.api_key_env,
  }
}

export default function Settings() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({})
  const [showKey, setShowKey] = useState<Record<string, boolean>>({})
  const [models, setModels] = useState<Record<string, ModelRole>>({})
  const [testing, setTesting] = useState<string | null>(null)

  const load = async () => {
    try {
      const data = await getSettings()
      const normalized = {
        ...data,
        model_options: data.model_options?.length ? data.model_options : DEFAULT_MODEL_OPTIONS,
      }
      setSettings(normalized)
      setModels(JSON.parse(JSON.stringify({ ...DEFAULT_AGENT_MODELS, ...data.models })))
    } catch {
      toast.error('无法加载配置')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

  const setAgentModel = (role: string, optionId: string) => {
    const option = settings?.model_options.find(opt => opt.id === optionId)
    if (!option) return
    setModels(prev => ({ ...prev, [role]: applyOption(option) }))
  }

  const patchModel = (role: string, patch: Partial<ModelRole>) =>
    setModels(prev => ({ ...prev, [role]: { ...prev[role], ...patch } }))

  const handleSave = async () => {
    setSaving(true)
    try {
      const keys: Record<string, string> = {}
      for (const [env, val] of Object.entries(keyInputs)) if (val.trim()) keys[env] = val.trim()
      const data = await updateSettings({ keys, models })
      setSettings(data)
      setModels(JSON.parse(JSON.stringify(data.models)))
      setKeyInputs({})
      toast.success('配置已保存，重启后端后已运行进程会加载新配置')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (env: string) => {
    setTesting(env)
    try {
      const r = await testProvider(env)
      r.ok ? toast.success(r.message || '连通正常') : toast.error(r.message || '连通失败')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || '测试失败')
    } finally {
      setTesting(null)
    }
  }

  if (loading) return <div className="flex h-full items-center justify-center"><Spinner className="h-7 w-7" /></div>

  const options = settings?.model_options?.length ? settings.model_options : DEFAULT_MODEL_OPTIONS
  const selectOptions = options.map(opt => ({ value: opt.id, label: `${opt.label} · ${opt.provider}` }))

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl px-10 py-10">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.28em] text-indigo-500">Agent Runtime</p>
            <h2 className="text-3xl font-semibold tracking-tight text-slate-950">智能体模型配置</h2>
            <p className="mt-2 text-sm text-slate-500">查看并切换每个智能体使用的 LLM，选择项来自当前可用的大模型</p>
          </div>
          <Button onClick={handleSave} loading={saving}><Save className="h-4 w-4" />保存配置</Button>
        </header>

        <Card className="mb-6 p-6">
          <div className="mb-4 flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-indigo-500" />
            <h3 className="text-sm font-semibold text-slate-700">API 密钥</h3>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {KEYS.map(k => {
              const state = settings?.keys[k.env]
              const visible = showKey[k.env]
              return (
                <div key={k.env} className="rounded-2xl border border-slate-100 bg-white/60 p-5">
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-slate-700">{k.name}</span>
                        {state?.configured
                          ? <Badge tone="emerald"><CheckCircle2 className="h-3 w-3" />已配置 {state.hint}</Badge>
                          : <Badge tone="amber">未配置</Badge>}
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{k.desc}</p>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => handleTest(k.env)} disabled={testing === k.env}>
                      {testing === k.env ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plug className="h-3.5 w-3.5" />}
                      测试
                    </Button>
                  </div>
                  <div className="relative">
                    <Input
                      type={visible ? 'text' : 'password'}
                      value={keyInputs[k.env] ?? ''}
                      onChange={e => setKeyInputs(prev => ({ ...prev, [k.env]: e.target.value }))}
                      placeholder={state?.configured ? '已保存，留空则不修改…' : '粘贴 API Key…'}
                      className="pr-10 font-mono"
                    />
                    <button type="button" onClick={() => setShowKey(prev => ({ ...prev, [k.env]: !visible }))}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                      {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>

        <div className="space-y-4">
          {AGENTS.map(agent => {
            const Icon = agent.icon
            const selected = optionIdFor(models[agent.key], options)
            const current = models[agent.key]
            const provider = options.find(opt => opt.id === selected)?.provider
            const keyState = current?.api_key_env ? settings?.keys[current.api_key_env] : null
            return (
              <Card key={agent.key} className="p-6">
                <div className="grid gap-5 lg:grid-cols-[1fr_320px] lg:items-center">
                  <div className="flex min-w-0 items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/10 to-violet-500/10 text-indigo-500">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-sm font-semibold text-slate-700">{agent.label}</h4>
                        {provider && <Badge tone="slate">{provider}</Badge>}
                        {keyState && <Badge tone={keyState.configured ? 'emerald' : 'amber'}>{current?.api_key_env}</Badge>}
                      </div>
                      <p className="mt-1 text-xs leading-5 text-slate-400">{agent.desc}</p>
                      <p className="mt-2 font-mono text-xs text-slate-500">
                        {current?.model || '未配置'}
                      </p>
                    </div>
                  </div>
                  <Select
                    value={selected}
                    onValueChange={value => setAgentModel(agent.key, value)}
                    options={selectOptions}
                    placeholder="选择模型"
                    className="w-full"
                  />
                </div>
              </Card>
            )
          })}

          <Card className="p-6">
            <div className="mb-5">
              <h3 className="text-sm font-semibold text-slate-800">基础模型链路</h3>
              <p className="mt-1 text-xs text-slate-400">这些角色由 RAG、检索增强、图片摘要和重排序流程直接使用</p>
            </div>
            <div className="grid gap-4">
              {SYSTEM_ROLES.map(role => {
                const Icon = role.icon
                const m = models[role.key] || { model: '' }
                const keyState = role.keyEnv ? settings?.keys[role.keyEnv] : null
                return (
                  <div key={role.key} className="rounded-2xl border border-slate-100 bg-white/60 p-4">
                    <div className="mb-3 flex items-start gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-cyan-200">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="text-sm font-semibold text-slate-700">{role.label}</h4>
                          {role.keyEnv
                            ? <Badge tone={keyState?.configured ? 'emerald' : 'amber'}>{role.keyEnv}</Badge>
                            : <Badge tone="slate">本地模型</Badge>}
                        </div>
                        <p className="mt-1 text-xs leading-5 text-slate-400">{role.desc}</p>
                      </div>
                    </div>
                    <div className={role.hasUrl ? 'grid gap-3 md:grid-cols-2' : 'grid gap-3'}>
                      <div>
                        <label className="mb-1.5 block text-xs font-medium text-slate-500">模型名称</label>
                        <Input value={m.model || ''} onChange={e => patchModel(role.key, { model: e.target.value })} className="font-mono text-xs" />
                      </div>
                      {role.hasUrl && (
                        <div>
                          <label className="mb-1.5 block text-xs font-medium text-slate-500">Base URL</label>
                          <Input value={m.base_url ?? ''} onChange={e => patchModel(role.key, { base_url: e.target.value })} className="font-mono text-xs" />
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
                <SearchCheck className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-slate-700">CitationAgent 引用核验</h4>
                <p className="mt-1 text-xs leading-5 text-slate-400">
                  该智能体不使用生成式 LLM。它通过引用格式解析、来源页码匹配、embedding 相似度和 reranker 辅助判断引用是否真实支撑正文。
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge tone="slate">Embedding: {models.embedding?.model || '未配置'}</Badge>
                  <Badge tone="slate">Reranker: {models.reranker?.model || '未配置'}</Badge>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
