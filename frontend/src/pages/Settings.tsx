import { useState, useEffect } from 'react'
import {
  Save, Eye, EyeOff, KeyRound, Bot, Boxes, Wand2, Image as ImageIcon, ArrowUpDown,
  CheckCircle2, Plug, Loader2,
} from 'lucide-react'
import { toast } from 'sonner'
import { getSettings, updateSettings, testProvider, type SettingsResponse, type ModelRole } from '../api/client'
import { Card, Button, Input, Badge, Spinner } from '../components/ui'
import { cn } from '../lib/cn'

// 两个供应商密钥
const KEYS = [
  { env: 'DASHSCOPE_API_KEY', name: '阿里云百炼 DashScope', desc: '嵌入向量 / 查询处理 / 图片摘要共用' },
  { env: 'DEEPSEEK_API_KEY', name: 'DeepSeek', desc: '主回答与论文写作生成' },
] as const

// 五个模型角色
const ROLES = [
  { key: 'generation', icon: Bot, label: '生成 LLM', desc: 'RAG 回答与论文写作的主力模型', keyEnv: 'DEEPSEEK_API_KEY', hasUrl: true },
  { key: 'embedding', icon: Boxes, label: '嵌入向量模型', desc: '文本向量化，决定检索语义质量', keyEnv: 'DASHSCOPE_API_KEY', hasUrl: true },
  { key: 'query_llm', icon: Wand2, label: '查询处理 LLM', desc: '查询改写 / HyDE / 关键词抽取（轻量）', keyEnv: 'DASHSCOPE_API_KEY', hasUrl: true },
  { key: 'vl', icon: ImageIcon, label: '图片摘要 VLM', desc: '论文图表的多模态语义描述', keyEnv: 'DASHSCOPE_API_KEY', hasUrl: true },
  { key: 'reranker', icon: ArrowUpDown, label: '重排序模型', desc: '本地 BGE-Reranker 精排，无需 API Key', keyEnv: '', hasUrl: false },
] as const

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
      setSettings(data)
      setModels(JSON.parse(JSON.stringify(data.models)))
    } catch {
      toast.error('无法加载配置')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [])

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
      toast.success('配置已保存')
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

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-8 py-8">
        <header className="mb-7 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">模型配置</h2>
            <p className="mt-1 text-sm text-slate-400">配置各环节使用的模型与 API Key，仅需上传密钥即可生效</p>
          </div>
          <Button onClick={handleSave} loading={saving}><Save className="h-4 w-4" />保存配置</Button>
        </header>

        {/* API 密钥 */}
        <Card className="mb-6 p-6">
          <div className="mb-4 flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-indigo-500" />
            <h3 className="text-sm font-semibold text-slate-700">API 密钥</h3>
          </div>
          <div className="space-y-4">
            {KEYS.map(k => {
              const state = settings?.keys[k.env]
              const visible = showKey[k.env]
              return (
                <div key={k.env} className="rounded-xl border border-slate-200 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-700">{k.name}</span>
                        {state?.configured
                          ? <Badge tone="emerald"><CheckCircle2 className="h-3 w-3" />已配置 {state.hint}</Badge>
                          : <Badge tone="amber">未配置</Badge>}
                      </div>
                      <p className="mt-0.5 text-xs text-slate-400">{k.desc}</p>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => handleTest(k.env)} disabled={testing === k.env}>
                      {testing === k.env ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plug className="h-3.5 w-3.5" />}
                      测试连通
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

        {/* 模型角色 */}
        <div className="space-y-4">
          {ROLES.map(role => {
            const Icon = role.icon
            const m = models[role.key] || { model: '' }
            const keyState = role.keyEnv ? settings?.keys[role.keyEnv] : null
            return (
              <Card key={role.key} className="p-5">
                <div className="mb-4 flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/10 to-violet-500/10 text-indigo-500">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-semibold text-slate-700">{role.label}</h4>
                      {role.keyEnv
                        ? <Badge tone={keyState?.configured ? 'emerald' : 'amber'}>{role.keyEnv === 'DEEPSEEK_API_KEY' ? 'DeepSeek' : 'DashScope'}</Badge>
                        : <Badge tone="slate">本地模型</Badge>}
                    </div>
                    <p className="mt-0.5 text-xs text-slate-400">{role.desc}</p>
                  </div>
                </div>
                <div className={cn('grid gap-3', role.hasUrl ? 'sm:grid-cols-2' : 'grid-cols-1')}>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-slate-500">模型名称</label>
                    <Input value={m.model} onChange={e => patchModel(role.key, { model: e.target.value })} className="font-mono text-xs" />
                  </div>
                  {role.hasUrl && (
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-slate-500">Base URL</label>
                      <Input value={m.base_url ?? ''} onChange={e => patchModel(role.key, { base_url: e.target.value })} className="font-mono text-xs" />
                    </div>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      </div>
    </div>
  )
}
